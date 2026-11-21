"""Шаг 3. Клиенты модели: единый интерфейс, три реализации.

ModelClient.run(requests) -> {id: output}
Формат ответа (задача table): «строка | метрика | k | агрегация | значение» (5 полей)
Формат ответа (задача text):  «метрика | значение | primary/cited» (3 поля)
"""
from __future__ import annotations

import csv
import json
import logging
import time
from pathlib import Path

from .textnorm import contains_number

log = logging.getLogger(__name__)

SYSTEM_TABLE = (
    "Extract evaluation results from the table fragment: row | metric | k | aggregation | value.\n"
    "Rules: only quantitative evaluation metrics (accuracy, EM, F1, recall, precision, BLEU, ROUGE, "
    "latency, etc.). Ignore years, page numbers, reference indices, author data, section numbers. "
    "If the fragment has no evaluation results, answer exactly: нет\n"
    "Output only data lines in the exact pipe format — no markdown, no header echo, no explanations."
)
SYSTEM_TEXT = (
    "Identify the evaluation metric and its value for the marked number: metric | value | primary/cited.\n"
    "Rules: only quantitative evaluation results (accuracy, EM, F1, recall, precision, BLEU, ROUGE, "
    "latency, score, error rate, etc.). If the number is a year, page number, reference index, count, "
    "version, or anything that is NOT a reported evaluation result, answer exactly: нет\n"
    "Output only the answer line — no explanations, no markdown."
)


class ModelClient:
    """Базовый интерфейс клиента модели."""

    def run(self, requests: list[dict]) -> dict[str, str]:
        raise NotImplementedError


class MockClient(ModelClient):
    """Заглушка модели: «идеальные» ответы из dev_gold/results.csv.

    Для фрагмента берутся записи эталона той же статьи и страницы,
    чьё raw_value встречается в тексте фрагмента.
    """

    def __init__(self, gold_dir: Path):
        self._by_pub: dict[str, list[dict]] = {}
        with open(gold_dir / "results.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                self._by_pub.setdefault(row["publication_id"], []).append(row)

    def run(self, requests: list[dict]) -> dict[str, str]:
        return {r["id"]: self._answer(r) for r in requests}

    def _answer(self, request: dict) -> str:
        pid = request["id"].split("_")[0]
        records = self._by_pub.get(pid, [])
        matched = [
            r for r in records
            if str(r["source_page"]) == str(request["page"])
            and r["extraction_status"] == "extracted"
            and contains_number(request["user"], r["raw_value"])
        ]
        if request["task"] == "table":
            lines = [
                f"{r['note'].split('row ')[-1].split(';')[0] if 'row ' in r['note'] else r['config_id']}"
                f" | {r['metric_name']} | {r['metric_k']} | {r['aggregation']} | {r['raw_value']}"
                for r in matched
            ]
        else:
            lines = [
                f"{r['metric_name']} | {r['raw_value']} | {r['result_origin'] or 'primary'}"
                for r in matched
            ]
        return "\n".join(lines) if lines else "нет"


class FileBatchClient(ModelClient):
    """Обмен с командой ИИ через файлы requests.jsonl / responses.jsonl."""

    def __init__(self, model_dir: Path):
        self.model_dir = model_dir
        model_dir.mkdir(parents=True, exist_ok=True)

    def write_requests(self, requests: list[dict]) -> Path:
        path = self.model_dir / "requests.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in requests)
        log.info("Записано %d запросов в %s — передайте команде ИИ", len(requests), path)
        return path

    def run(self, requests: list[dict]) -> dict[str, str]:
        responses = self.model_dir / "responses.jsonl"
        if not responses.exists():
            self.write_requests(requests)
            raise FileNotFoundError(
                f"Нет {responses}: прогоните requests.jsonl через модель и положите ответы"
            )
        answers: dict[str, str] = {}
        with open(responses, encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                answers[row["id"]] = row["output"]
        return {r["id"]: answers.get(r["id"], "нет") for r in requests}


def build_requests(fragments: list[dict]) -> list[dict]:
    """Фрагменты шага 2 -> запросы модели."""
    requests = []
    for frag in fragments:
        task = frag["kind"]
        requests.append({
            "id": frag["fragment_id"],
            "task": task,
            "page": frag["page"],
            "system": SYSTEM_TABLE if task == "table" else SYSTEM_TEXT,
            "user": frag["text"],
        })
    return requests


class LocalClient(ModelClient):
    """Дообученная локальная модель: база Qwen + LoRA-адаптер (шаг обучения).

    Конфиг: model.client: local, model.local_path: models/extractor-v1
    """

    def __init__(self, adapter_path: Path, base_model: str = "Qwen/Qwen2.5-3B-Instruct",
                 batch_size: int = 8):
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        quant = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
        base = AutoModelForCausalLM.from_pretrained(
            base_model, quantization_config=quant, device_map="auto",
            torch_dtype=torch.float16)
        self.model = PeftModel.from_pretrained(base, str(adapter_path))
        self.model.eval()
        self.tokenizer = AutoTokenizer.from_pretrained(base_model)
        self.tokenizer.padding_side = "left"  # генерация батчами: паддинг слева
        self.batch_size = batch_size

    def run(self, requests: list[dict]) -> dict[str, str]:
        import torch

        answers: dict[str, str] = {}
        for start in range(0, len(requests), self.batch_size):
            batch = requests[start:start + self.batch_size]
            prompts = [
                self.tokenizer.apply_chat_template(
                    [
                        {"role": "system", "content": r["system"]},
                        {"role": "user", "content": r["user"]},
                    ],
                    tokenize=False, add_generation_prompt=True)
                for r in batch
            ]
            inputs = self.tokenizer(
                prompts, return_tensors="pt", padding=True,
                truncation=True, max_length=1024).to(self.model.device)
            with torch.no_grad():
                out = self.model.generate(
                    **inputs, max_new_tokens=150, do_sample=False,
                    pad_token_id=self.tokenizer.eos_token_id)
            cut = inputs["input_ids"].shape[1]  # при левом паддинге общая граница
            for req, row in zip(batch, out, strict=True):
                text = self.tokenizer.decode(row[cut:], skip_special_tokens=True)
                answers[req["id"]] = text.strip() or "нет"
            log.info("LocalClient: %d/%d запросов", min(start + self.batch_size, len(requests)),
                     len(requests))
        return answers


class ApiClient(ModelClient):
    """API-модель через OpenRouter (OpenAI-совместимый эндпоинт).

    Ключ — из .env (OPENROUTER_API_KEY), в конфиге и коде не хранится.
    Параллелизм + backoff на 429/5xx; ответы кэшируются шагом run()
    в responses.jsonl, так что повторный запуск не сжигает деньги.
    """

    def __init__(self, api_cfg: dict):
        import requests  # noqa: F401 — проверка наличия на старте

        self.base_url = api_cfg.get("base_url", "https://api.openai.com/v1")
        key = self._load_key(self.base_url)
        if not key:
            raise ValueError(f"Нет API-ключа в .env для {self.base_url}")
        self.model = api_cfg["model"]
        self.timeout = int(api_cfg.get("timeout", 90))
        self.max_retries = int(api_cfg.get("max_retries", 5))
        self.max_tokens = int(api_cfg.get("max_tokens", 200))
        self.max_parallel = int(api_cfg.get("max_parallel", 4))
        self.headers = {"Authorization": f"Bearer {key}",
                        "Content-Type": "application/json"}
        self.tokens_in = 0
        self.tokens_out = 0

    @staticmethod
    def _load_key(base_url: str) -> str:
        """Ключ по провайдеру: openai.com -> OPENAI_API_KEY, иначе OpenRouter."""
        import os
        name = "OPENAI_API_KEY" if "openai.com" in base_url else "OPENROUTER_API_KEY"
        env_path = Path(".env")
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith(f"{name}="):
                    return line.split("=", 1)[1].strip()
        return os.environ.get(name, "")

    def _ask(self, request: dict) -> str:
        import requests

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request["system"]},
                {"role": "user", "content": request["user"]},
            ],
            "temperature": 0,
            "max_tokens": self.max_tokens,
        }
        delay = 2.0
        for attempt in range(self.max_retries):
            try:
                resp = requests.post(f"{self.base_url}/chat/completions",
                                     headers=self.headers, json=payload,
                                     timeout=self.timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    usage = data.get("usage") or {}
                    self.tokens_in += usage.get("prompt_tokens", 0)
                    self.tokens_out += usage.get("completion_tokens", 0)
                    return (data["choices"][0]["message"]["content"] or "").strip()
                if resp.status_code in (429, 500, 502, 503, 504):
                    log.warning("API %s (попытка %d), пауза %.0f с",
                                resp.status_code, attempt + 1, delay)
                    time.sleep(delay)
                    delay = min(delay * 2, 60)
                    continue
                resp.raise_for_status()
            except requests.RequestException as exc:
                log.warning("API ошибка %s (попытка %d), пауза %.0f с",
                            exc, attempt + 1, delay)
                time.sleep(delay)
                delay = min(delay * 2, 60)
        log.error("API: запрос %s не выполнен после %d попыток",
                  request["id"], self.max_retries)
        return "нет"

    def run(self, requests: list[dict]) -> dict[str, str]:
        from concurrent.futures import ThreadPoolExecutor

        answers: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=self.max_parallel) as pool:
            for i, (req, out) in enumerate(
                    zip(requests, pool.map(self._ask, requests), strict=True)):
                answers[req["id"]] = out or "нет"
                if (i + 1) % 25 == 0 or i + 1 == len(requests):
                    log.info("API: %d/%d запросов (токены: %d вх / %d исх)",
                             i + 1, len(requests), self.tokens_in, self.tokens_out)
        log.info("API: всего токенов %d вх / %d исх", self.tokens_in, self.tokens_out)
        return answers


def make_client(cfg: dict) -> ModelClient:
    """Клиент модели по конфигу: mock | file | local."""
    kind = cfg["model"]["client"]
    if kind == "mock":
        return MockClient(Path(cfg["data"]["dev_gold_dir"]))
    if kind == "file":
        return FileBatchClient(Path(cfg["work"]["cache_dir"]) / "model")
    if kind == "local":
        return LocalClient(Path(cfg["model"]["local_path"]))
    if kind == "api":
        return ApiClient(cfg["model"]["api"])
    raise ValueError(f"Неизвестный клиент модели: {kind}")


_HEADER_WORDS = {"metric", "value", "row", "k", "aggregation", "primary/cited"}


def parse_response(output: str, task: str) -> list[list[str]]:
    """Разбор ответа модели: table — 5 полей, text — 3. Мусор пропускаем."""
    expected = 5 if task == "table" else 3
    rows = []
    for line in (output or "").splitlines():
        line = line.strip()
        if not line or line == "нет":
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != expected:
            log.warning("Пропуск строки ответа (%d полей вместо %d): %s", len(parts), expected, line)
            continue
        # эхо заголовка («metric | value | ...») и markdown-разделители («--- | ---»)
        lowered = {p.lower() for p in parts}
        if lowered <= _HEADER_WORDS or all(set(p) <= {"-", " ", ":"} for p in parts):
            continue
        rows.append(parts)
    return rows


def run(set_name: str, cfg: dict, only: list[str] | None = None) -> Path:
    """Прогнать модель по всем фрагментам набора -> cache/model/responses.jsonl.

    Ответы кэшируются по id: повторный запуск не спрашивает модель заново.
    """
    frag_dir = Path(cfg["work"]["cache_dir"]) / "fragments"
    model_dir = Path(cfg["work"]["cache_dir"]) / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    out_path = model_dir / "responses.jsonl"

    cached: dict[str, str] = {}
    if out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                cached[row["id"]] = row["output"]

    fragments = []
    for frag_file in sorted(frag_dir.glob("*.json")):
        if only and frag_file.stem not in only:
            continue
        fragments.extend(json.loads(frag_file.read_text(encoding="utf-8")))
    requests = [r for r in build_requests(fragments) if r["id"] not in cached]
    log.info("Запросов к модели: %d (в кэше: %d)", len(requests), len(cached))

    if requests:
        client = make_client(cfg)
        # API — чанками с записью после каждого: сбой не теряет оплаченные ответы
        chunk = 200 if cfg["model"]["client"] == "api" else len(requests)
        with open(out_path, "a", encoding="utf-8") as f:
            for i in range(0, len(requests), chunk):
                answers = client.run(requests[i:i + chunk])
                for rid, output in answers.items():
                    f.write(json.dumps({"id": rid, "output": output}, ensure_ascii=False) + "\n")
                    cached[rid] = output
                f.flush()
                log.info("Записано ответов: %d из %d", min(i + chunk, len(requests)), len(requests))
    return out_path
