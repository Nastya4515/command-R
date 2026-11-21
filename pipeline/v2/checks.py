"""Шаг E. Предметные проверки -> issues.

Замечание не меняет исходную запись; всегда содержит правило, record_ids,
описание с числами с обеих сторон, страницу и цитату (ТЗ v2, п. 3.5.5).
"""
from __future__ import annotations

import json
import logging
import re

from .extract_a import work_dir

log = logging.getLogger(__name__)

_AT_K = re.compile(r"@(\d+)(?![\d.])")
_IMPROVE = re.compile(r"(?i)(improvement|gain|increase|Δ|delta|улучш)")


def _issue(pid: str, prefix: str, n: int, record_ids: list[str], check: str,
           description: str, page, fragment: str) -> dict:
    return {"publication_id": pid, "issue_id": f"{prefix}{n}",
            "record_ids": ";".join(record_ids), "check_name": check,
            "description": description,
            "source_page": page or "", "source_fragment": fragment or ""}


def run_article(pid: str, cfg: dict, area: str, set_name: str, profile: dict,
                normalized: dict, force: bool = False) -> dict:
    """Шаг E для одной статьи."""
    out_path = work_dir(cfg, area, set_name, pid) / "issues.json"
    if out_path.exists() and not force:
        return json.loads(out_path.read_text(encoding="utf-8"))

    enabled = profile.get("checks", {})
    bounded = set(profile.get("bounded_metrics", []))
    issues: list[dict] = []
    n = 0
    prefix = profile["ids"]["issues"]

    results = [r for r in normalized.get("results", []) if not r.get("duplicate_of")]

    for r in results:
        name = (r.get("metric_name") or "").strip()
        unit = r.get("metric_unit") or ""
        value = r.get("metric_value") or ""
        page = r.get("source_page") or ""
        frag = r.get("source_fragment") or ""

        # metric_scale: только известная шкала и ограниченные метрики
        if enabled.get("metric_scale") and value and unit in {"fraction", "%"}:
            fam = re.sub(r"@\d+$", "", name.lower()).strip()
            if fam in bounded:
                limit = 1.0 if unit == "fraction" else 100.0
                v = float(value)
                if not (0 <= v <= limit):
                    n += 1
                    issues.append(_issue(
                        pid, prefix, n, [r["result_id"]], "metric_scale",
                        f"Значение {value} вне шкалы [0, {limit:g}] для метрики "
                        f"«{name}» с единицей «{unit}»", page, frag))

        # metric_k: @k в названии vs поле
        if enabled.get("metric_k"):
            m = _AT_K.search(name)
            if m and str(r.get("metric_k") or "") != m.group(1):
                n += 1
                issues.append(_issue(
                    pid, prefix, n, [r["result_id"]], "metric_k",
                    f"В названии «{name}» k={m.group(1)}, в поле metric_k="
                    f"«{r.get('metric_k') or 'пусто'}»", page, frag))

        # unit_inconsistency: единица противоречит значению/сырому виду
        if enabled.get("unit_inconsistency") and value and unit:
            raw = r.get("raw_value") or ""
            v = float(value)
            if unit == "%" and v <= 1 and "%" not in raw:
                n += 1
                issues.append(_issue(
                    pid, prefix, n, [r["result_id"]], "unit_inconsistency",
                    f"Единица «%», но значение {raw} выглядит долей (≤1 и без знака %)",
                    page, frag))
            if unit == "fraction" and v > 1:
                n += 1
                issues.append(_issue(
                    pid, prefix, n, [r["result_id"]], "unit_inconsistency",
                    f"Единица «fraction», но значение {raw} > 1", page, frag))

        # percentage_vs_percentage_point: разность процентов, подписанная как %
        if enabled.get("percentage_vs_percentage_point") and unit == "%" \
                and _IMPROVE.search(name):
            n += 1
            issues.append(_issue(
                pid, prefix, n, [r["result_id"]], "percentage_vs_percentage_point",
                f"«{name}» = {raw} — похоже на разность процентов; уточнить, "
                "не процентные ли это пункты (percentage_points)", page, frag))

    # contradiction: тот же объект/метрика, разные значения, не объявленные дублями
    if enabled.get("contradiction"):
        groups: dict[tuple, list[dict]] = {}
        for r in results:
            key = tuple((r.get(f) or "") for f in
                        ["config_id", "dataset_id", "task_id", "metric_name",
                         "metric_variant", "metric_k", "metric_unit", "result_origin"])
            groups.setdefault(key, []).append(r)
        for key, rows in groups.items():
            values = {r["metric_value"] for r in rows if r.get("metric_value")}
            if len(values) > 1:
                rows_sorted = sorted(rows, key=lambda r: r["result_id"])
                n += 1
                vals = "; ".join(f"{r['metric_value']} (с. {r.get('source_page')})"
                                 for r in rows_sorted)
                issues.append(_issue(
                    pid, prefix, n, [r["result_id"] for r in rows_sorted],
                    "contradiction",
                    f"Одна метрика «{key[3]}» одного объекта имеет разные значения: {vals}",
                    rows_sorted[0].get("source_page") or "",
                    rows_sorted[0].get("source_fragment") or ""))

    out = {"issues": issues}
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("%s: шаг E — %d замечаний", pid, len(issues))
    return out
