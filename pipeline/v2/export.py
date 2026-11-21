"""Шаг F. Экспорт 7 CSV по схеме области + запуск check_submission.py.

Выход: out/<area>/<set>/*.csv — каноничные данные сдачи.
Отчёт: reports/check_<area>_<set>.json.
"""
from __future__ import annotations

import csv
import logging
import subprocess
import sys
from pathlib import Path

from .extract_a import ENTITY_TABLES

log = logging.getLogger(__name__)

# поля, которые есть в JSON записей, но не уходят в CSV
_SKIP = {"label", "unit", "cited_reference"}


def _csv_rows(table: str, columns: list[str], items: list[dict]) -> list[dict]:
    rows = []
    for item in items:
        row = {}
        for col in columns:
            val = item.get(col, "")
            if val is None:
                val = ""
            if isinstance(val, list):
                val = "; ".join(str(v) for v in val)
            row[col] = str(val)
        rows.append(row)
    return rows


def run_set(area: str, set_name: str, cfg: dict, profile: dict,
            publications: list[dict], entities_by_pid: dict[str, dict],
            results: list[dict], issues: list[dict]) -> Path:
    """Экспорт набора: out/<area>/<set>/*.csv + чекер организаторов."""
    schema = profile["schema"]
    out_dir = Path(cfg["work"]["out_dir"]) / area / set_name
    out_dir.mkdir(parents=True, exist_ok=True)

    tables_data: dict[str, list[dict]] = {t: [] for t in schema["tables"]}
    tables_data["publications"] = publications
    for pid, entities in entities_by_pid.items():
        for table in ENTITY_TABLES:
            for item in entities.get(table) or []:
                row = {"publication_id": pid, **item}
                tables_data[table].append(row)
    tables_data["results"] = results
    tables_data["issues"] = issues

    for table, columns in schema["tables"].items():
        rows = _csv_rows(table, columns, tables_data.get(table, []))
        path = out_dir / f"{table}.csv"
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        log.info("%s: %d строк", path, len(rows))
    return out_dir


def run_checker(area: str, set_name: str, cfg: dict, area_data: dict) -> int:
    """Внешняя проверка формата: tools/check_submission.py области."""
    checker = Path(area_data["checker"])
    out_dir = Path(cfg["work"]["out_dir"]) / area / set_name
    pdf_dir = Path(area_data[f"{set_name}_dir"]) if f"{set_name}_dir" in area_data else None
    report = Path(cfg["work"]["reports_dir"])
    report.mkdir(parents=True, exist_ok=True)
    report = report / f"check_{area}_{set_name}.json"
    cmd = [sys.executable, str(checker), str(out_dir)]
    if pdf_dir and pdf_dir.exists():
        cmd.append(str(pdf_dir))
    if checker.read_text(encoding="utf-8").find("--json-report") > 0:
        cmd += ["--json-report", str(report)]
    log.info("Запуск: %s", " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    log.info("Чекер завершился с кодом %d", result.returncode)
    return result.returncode
