"""Шаг 6. Экспорт 7 CSV в формате сдачи + журнал запуска.

Порядок колонок — строго по submission_template/schema.json.
Пустая ячейка = «нет в статье»; NaN/None/null запрещены; пишем только через csv.
"""
from __future__ import annotations

import csv
import json
import logging
import re
from pathlib import Path

from .checks import run_checks

log = logging.getLogger(__name__)

_DOI_RE = re.compile(r"10\.\d{4,9}/\S+")
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _load_schema(cfg: dict) -> dict[str, list[str]]:
    schema_path = Path(cfg["data"]["template_dir"]) / "schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))["tables"]


def _publication_meta(pages_data: dict) -> dict:
    """Библиография статьи из первой страницы PDF (лучшее усилие)."""
    page1 = pages_data["pages"][0] if pages_data["pages"] else {}
    words = page1.get("words", [])
    title = ""
    if words:
        max_size = max(w["size"] for w in words)
        title_words = [w for w in words if w["size"] >= max_size - 0.5 and w["top"] < page1.get("height", 800) * 0.4]
        title = " ".join(w["text"] for w in sorted(title_words, key=lambda w: (w["top"], w["x0"])))
    text = page1.get("text_pymupdf") or page1.get("text_pypdf") or ""
    doi = _DOI_RE.search(text)
    year = _YEAR_RE.search(text[:2000])
    return {
        "title": title.strip(),
        "year": year.group(0) if year else "",
        "DOI": doi.group(0).rstrip(".,;)") if doi else "",
        "authors": "",
        "in_scope": "true",
        "exclusion_reason": "",
    }


def _export_article(records_data: dict, pages_data: dict) -> dict[str, list[dict]]:
    """Записи одной статьи -> строки всех 7 таблиц."""
    pid = records_data["publication_id"]
    records = records_data["records"]
    configs = records_data["configs"]

    results = []
    # повторы наследуют config_id и согласованные поля исходной записи (правила checker)
    for r in records:
        dup = r.get("duplicate_of")
        if dup not in ("", None) and isinstance(dup, int):
            src = records[dup]
            r["row_label"] = src.get("row_label", r.get("row_label", ""))
            for field in ("aggregation", "metric_k", "result_origin", "cited_publication_id"):
                r[field] = src.get(field, r.get(field, ""))

    for i, r in enumerate(records, start=1):
        rid = f"R{i:03d}"
        r["_rid"] = rid
        dup = r.get("duplicate_of")
        if dup not in ("", None) and isinstance(dup, int):
            unit = "%" if "%" in records[dup]["raw_value"] else "fraction"
        else:
            unit = "%" if "%" in r["raw_value"] else "fraction"
        results.append({
            "publication_id": pid,
            "result_id": rid,
            "experiment_id": "E1",
            "config_id": configs.get(r.get("row_label", ""), ""),
            "dataset_id": "",
            "task_id": "",
            "metric_group": "",
            "metric_name": r["metric_name"],
            "metric_variant": "",
            "metric_direction": "",
            "metric_k": r.get("metric_k", ""),
            "metric_value": r["metric_value"],
            "metric_unit": unit,
            "baseline_value": "",
            "aggregation": r.get("aggregation", ""),
            "sample_size": "",
            "raw_value": r["raw_value"],
            "raw_unit": "%" if "%" in r["raw_value"] else "",
            "normalized_value": r["metric_value"],
            "normalized_unit": unit,
            "result_origin": r["result_origin"],
            "cited_publication_id": r.get("cited_publication_id", ""),
            "source_page": r["source_page"],
            "source_section": r.get("source_section", ""),
            "source_table": r.get("source_table", ""),
            "source_figure": "",
            "source_fragment": r["source_fragment"],
            "extraction_status": r["extraction_status"],
            "duplicate_of": (f"R{r['duplicate_of'] + 1:03d}" if r.get("duplicate_of") not in ("", None) else ""),
            "note": r.get("note", ""),
        })

    issues = []
    for j, issue in enumerate(run_checks(records), start=1):
        rec = issue["record"]
        issues.append({
            "publication_id": pid,
            "issue_id": f"I{j:02d}",
            "record_ids": ";".join(f"R{idx + 1:03d}" for idx in issue["records"]),
            "check_name": issue["check_name"],
            "description": issue["description"],
            "source_page": rec.get("source_page", ""),
            "source_fragment": rec.get("source_fragment", "")[:200],
        })
    for r in records:
        r.pop("_rid", None)

    return {
        "publications": [{"publication_id": pid, **_publication_meta(pages_data)}],
        "configurations": [
            {"publication_id": pid, "config_id": cid, "rag_variant": label,
             **{k: "" for k in ("retrieval_method", "retriever_model", "embedding_model",
                                "embedding_version", "chunking_method", "chunk_size",
                                "chunk_overlap", "chunk_unit", "index_type", "vector_store",
                                "top_k", "reranker_model", "generator_model",
                                "generator_version", "prompt_strategy", "context_strategy")},
             "note": f"row label: {label}"}
            for label, cid in configs.items()
        ],
        "datasets": [],
        "tasks": [],
        "experiments": [{"publication_id": pid, "experiment_id": "E1",
                         **{k: "" for k in ("evaluation_protocol", "baseline_name", "hardware",
                                            "latency_ms", "tokens_per_query", "sample_size")},
                         "note": "default experiment (mock pipeline)"}],
        "results": results,
        "issues": issues,
    }


def run(set_name: str, cfg: dict, only: list[str] | None = None) -> Path:
    """Собрать out/<set>/*.csv из cache/records + cache/pages."""
    cache = Path(cfg["work"]["cache_dir"])
    records_dir, pages_dir = cache / "records", cache / "pages"
    out_dir = Path(cfg["work"]["out_dir"]) / set_name
    out_dir.mkdir(parents=True, exist_ok=True)
    schema = _load_schema(cfg)

    tables: dict[str, list[dict]] = {name: [] for name in schema}
    for records_file in sorted(records_dir.glob("*.json")):
        pid = records_file.stem
        if only and pid not in only:
            continue
        records_data = json.loads(records_file.read_text(encoding="utf-8"))
        pages_data = json.loads((pages_dir / records_file.name).read_text(encoding="utf-8"))
        article_tables = _export_article(records_data, pages_data)
        for name, rows in article_tables.items():
            tables[name].extend(rows)

    for name, columns in schema.items():
        path = out_dir / f"{name}.csv"
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            for row in tables[name]:
                writer.writerow({c: ("" if row.get(c) is None else row.get(c, "")) for c in columns})
        log.info("%s: %d строк", path, len(tables[name]))
    return out_dir
