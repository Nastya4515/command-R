"""Шаг 4. Проверка ответов модели и сборка записей results.

Главная защита: запись принимается, только если её значение есть
в тексте фрагмента (после нормализации чисел). Отброшенное — в rejected.csv.
Цитату и страницу код берёт из данных шага 1, а не из ответа модели.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from .model_client import parse_response
from .textnorm import contains_number, normalize_number, normalize_text

log = logging.getLogger(__name__)

_CITED_ROW_RE = re.compile(r"\[\d+\]|†")
_CITED_CAPTION_RE = re.compile(r"reported in|taken from|from\s+\[", re.IGNORECASE)


def _value_in_fragment(fragment_text: str, raw_value: str) -> bool:
    """Защита от выдуманных чисел: значение должно быть во фрагменте."""
    return contains_number(fragment_text, raw_value)


def _find_quote(fragment: dict, page: dict, row_label: str, raw_value: str) -> str:
    """Дословная цитата со страницы: «подпись строки + число» или 2–3 слова перед числом.

    Проверяется по сплошному тексту страницы (pypdf/pymupdf), как у проверяющего скрипта.
    """
    candidates = [page.get("text_pymupdf", ""), page.get("text_pypdf", "")]
    row_text = next((r["text"] for r in fragment.get("rows", []) if raw_value in r["text"]), "")

    pieces = []
    if row_label and row_text and row_label in row_text:
        idx = row_text.find(raw_value)
        pieces.append(row_text[max(0, idx - len(row_label) - 1):idx + len(raw_value)].strip())
    for text in candidates:
        idx = text.find(raw_value)
        if idx >= 0:
            before = text[max(0, idx - 60):idx].split()[-3:]
            pieces.append(" ".join(before + [raw_value]))
            break
    for piece in pieces:
        if piece and _quote_in_page(piece, candidates):
            return piece
    return raw_value  # минимум — само число


def _quote_in_page(quote: str, texts: list[str]) -> bool:
    """Цитата находится в тексте страницы (с нормализацией пробелов)."""
    norm_q = normalize_text(quote)
    return any(norm_q in normalize_text(t) for t in texts if t)


def _cited_origin(fragment: dict, row_text: str) -> tuple[str, str]:
    """(origin, cited_publication_id): cited только с извлечённым идентификатором.

    Без идентификатора ([12] или †) запись остаётся primary —
    checker считает «cited без citation identifier» ошибкой.
    """
    ref = re.search(r"\[\d+(?:[-,]\s*\d+)*\]", row_text)
    if ref:
        return "cited", ref.group(0)
    if "†" in row_text:
        return "cited", "†"
    return "primary", ""


def _make_config(records: list[dict]) -> dict[str, str]:
    """config_id по разным подписям строк (rag_variant = подпись)."""
    labels = sorted({r["row_label"] for r in records if r.get("row_label")})
    return {label: f"C{i + 1:02d}" for i, label in enumerate(labels)}


def assemble_article(pid: str, fragments: list[dict], responses: dict[str, str],
                     pages_data: dict, rejected: list[dict]) -> list[dict]:
    """Ответы модели -> проверенные записи одной статьи."""
    pages = {p["page"]: p for p in pages_data["pages"]}
    records: list[dict] = []
    for frag in fragments:
        output = responses.get(frag["fragment_id"], "")
        for fields in parse_response(output, frag["kind"]):
            if frag["kind"] == "table":
                row_label, metric, k, agg, value = fields
            else:
                row_label, k, agg = "", "", ""
                metric, value, origin = fields
            if not _value_in_fragment(frag["text"], value):
                rejected.append({"publication_id": pid, "fragment_id": frag["fragment_id"],
                                 "metric": metric, "value": value,
                                 "reason": "value_not_in_fragment"})
                continue
            page = pages.get(frag["page"], {})
            norm = normalize_number(value)
            if norm is None:
                rejected.append({"publication_id": pid, "fragment_id": frag["fragment_id"],
                                 "metric": metric, "value": value, "reason": "bad_number"})
                continue
            if frag["kind"] == "text":
                cited_id = ""
                if origin == "cited":
                    ref = re.search(r"\[\d+(?:[-,]\s*\d+)*\]", frag["text"])
                    cited_id = ref.group(0) if ref else ""
                    if not cited_id:
                        origin = "primary"  # cited без идентификатора — ошибка формата
            else:
                row_text = next((r["text"] for r in frag["rows"] if value in r["text"]), "")
                origin, cited_id = _cited_origin(frag, row_text)
            records.append({
                "publication_id": pid,
                "row_label": row_label,
                "metric_name": metric,
                "metric_k": k,
                "aggregation": agg,
                "raw_value": value,
                "metric_value": norm,
                "metric_unit": "%" if "%" in value else "",
                "result_origin": origin,
                "cited_publication_id": cited_id,
                "source_page": frag["page"],
                "source_table": frag.get("table") or "",
                "source_section": frag.get("section") or "",
                "source_fragment": _find_quote(frag, page, row_label, value),
                "extraction_status": "extracted",
                "note": (f"{frag['table']}: row {row_label}; column {metric}"
                         if frag["kind"] == "table" and frag.get("table") else ""),
            })
    return records


def _link_duplicates(records: list[dict]) -> None:
    """Повтор: текст с той же метрикой и значением, что у табличной записи."""
    table_keys: dict[tuple[str, str], int] = {}
    for i, r in enumerate(records):
        if r["source_table"]:
            table_keys.setdefault((r["metric_name"].lower(), r["metric_value"]), i)
    for r in records:
        if r["source_table"]:
            continue
        key = (r["metric_name"].lower(), r["metric_value"])
        # локальный индекс табличной записи; id проставит экспорт
        r["duplicate_of"] = table_keys.get(key, "")


def run(set_name: str, cfg: dict, only: list[str] | None = None) -> list[Path]:
    """Собрать записи всех статей -> cache/records/<pid>.json + rejected.csv."""
    import csv

    cache = Path(cfg["work"]["cache_dir"])
    frag_dir, pages_dir = cache / "fragments", cache / "pages"
    records_dir = cache / "records"
    records_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = Path(cfg["work"]["reports_dir"])
    reports_dir.mkdir(parents=True, exist_ok=True)

    responses: dict[str, str] = {}
    with open(cache / "model" / "responses.jsonl", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            responses[row["id"]] = row["output"]

    rejected: list[dict] = []
    written = []
    for frag_file in sorted(frag_dir.glob("*.json")):
        pid = frag_file.stem
        if only and pid not in only:
            continue
        fragments = json.loads(frag_file.read_text(encoding="utf-8"))
        pages_data = json.loads((pages_dir / frag_file.name).read_text(encoding="utf-8"))
        records = assemble_article(pid, fragments, responses, pages_data, rejected)
        _link_duplicates(records)
        configs = _make_config(records)
        out = {"publication_id": pid, "records": records, "configs": configs}
        (records_dir / f"{pid}.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        log.info("%s: %d записей, %d конфигураций", pid, len(records), len(configs))
        written.append(records_dir / f"{pid}.json")

    rej_path = reports_dir / "rejected.csv"
    with open(rej_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["publication_id", "fragment_id", "metric", "value", "reason"])
        writer.writeheader()
        writer.writerows(rejected)
    log.info("Отброшено записей: %d (%s)", len(rejected), rej_path)
    return written
