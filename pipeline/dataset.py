"""Сборка SFT-датасета для дообучения модели извлечения.

Пары «фрагмент -> правильный ответ» строятся из кэша фрагментов (шаг 2)
и эталонной разметки dev_gold — та же логика, что у MockClient, но на выходе
JSONL в chat-формате: {"messages": [{system},{user},{assistant}], "pid", "task"}.

Сплит — по статьям, а не по примерам: иначе модель запомнит статью,
и оценка покажет запоминание, а не обучение.

Запуск: python -m pipeline.dataset [--val D002 D013 D021] [--out data/sft]
"""
from __future__ import annotations

import argparse
import json
import logging
import random
from pathlib import Path

import yaml

from .model_client import MockClient, build_requests

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def build_examples(cfg: dict) -> list[dict]:
    """Все примеры из кэша фрагментов с эталонными ответами."""
    frag_dir = Path(cfg["work"]["cache_dir"]) / "fragments"
    mock = MockClient(Path(cfg["data"]["dev_gold_dir"]))
    examples: list[dict] = []
    for frag_file in sorted(frag_dir.glob("*.json")):
        pid = frag_file.stem
        fragments = json.loads(frag_file.read_text(encoding="utf-8"))
        requests = build_requests(fragments)
        answers = mock.run(requests)
        for req in requests:
            answer = answers[req["id"]]
            # «пустые» примеры (нет чисел) оставляем: модель должна учиться
            # отвечать «нет», иначе будет галлюцинировать значения
            examples.append({
                "pid": pid,
                "task": req["task"],
                "messages": [
                    {"role": "system", "content": req["system"]},
                    {"role": "user", "content": req["user"]},
                    {"role": "assistant", "content": answer},
                ],
            })
    return examples


def main() -> None:
    parser = argparse.ArgumentParser(description="Сборка SFT-датасета из dev_gold")
    parser.add_argument("--val", nargs="*", default=["D002", "D013", "D021"],
                        help="статьи в валидацию (по умолчанию сканы — самые тяжёлые)")
    parser.add_argument("--out", default="data/sft", help="каталог для train.jsonl/val.jsonl")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    examples = build_examples(cfg)
    val_pids = set(args.val)
    train = [e for e in examples if e["pid"] not in val_pids]
    val = [e for e in examples if e["pid"] in val_pids]

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in (("train", train), ("val", val)):
        random.Random(42).shuffle(rows)
        path = out_dir / f"{name}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)

    def stats(rows: list[dict]) -> str:
        nonempty = sum(1 for r in rows if r["messages"][2]["content"] != "нет")
        tables = sum(1 for r in rows if r["task"] == "table")
        return f"{len(rows)} примеров ({nonempty} с ответами, {tables} табличных)"

    log.info("train: %s", stats(train))
    log.info("val:   %s", stats(val))
    log.info("Записано в %s", out_dir)


if __name__ == "__main__":
    main()
