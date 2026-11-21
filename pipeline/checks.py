"""Шаг 5. Правила проверки -> строки issues.csv.

Исходные записи не удаляются и не исправляются — только замечания.
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

_SHARE_METRICS = {"em", "f1", "f1-score", "recall", "precision", "accuracy", "rouge", "bleu"}
_K_RE = re.compile(r"@\s*(\d+)")


def check_metric_scale(records: list[dict]) -> list[dict]:
    """Доля > 1 или < 0; процент > 100; отрицательные recall/F1/EM."""
    issues = []
    for r in records:
        try:
            value = float(r["metric_value"])
        except (TypeError, ValueError):
            continue
        unit = r.get("metric_unit", "")
        metric = r["metric_name"].lower()
        base = re.sub(r"@\d+$", "", metric).strip()
        # «improvement/gain» — относительная величина, может быть любой
        is_relative = any(w in metric for w in ("improvement", "gain", "over", "delta", "lift"))
        bad = None
        if unit == "%" and value > 100 and base in _SHARE_METRICS and not is_relative:
            bad = f"процент > 100: {r['raw_value']}"
        elif unit != "%" and base in _SHARE_METRICS and not is_relative and not 0 <= value <= 1:
            bad = f"доля вне [0, 1]: {r['raw_value']}"
        if bad:
            issues.append({"records": [r["_id"]], "check_name": "metric_scale",
                           "description": f"{r['metric_name']} = {r['raw_value']}: {bad}",
                           "record": r})
    return issues


def check_metric_k(records: list[dict]) -> list[dict]:
    """В названии @N, а metric_k другой; метрика @k без metric_k."""
    issues = []
    for r in records:
        m = _K_RE.search(r["metric_name"])
        if m and r.get("metric_k") and m.group(1) != str(r["metric_k"]):
            issues.append({"records": [r["_id"]], "check_name": "metric_k",
                           "description": f"«{r['metric_name']}», но k = {r['metric_k']}",
                           "record": r})
        elif m and not r.get("metric_k"):
            issues.append({"records": [r["_id"]], "check_name": "metric_k",
                           "description": f"«{r['metric_name']}» без metric_k",
                           "record": r})
    return issues


def check_normalization(records: list[dict]) -> list[dict]:
    """raw_value и metric_value не согласованы."""
    from .textnorm import normalize_number

    issues = []
    for r in records:
        if normalize_number(r["raw_value"]) != r["metric_value"]:
            issues.append({"records": [r["_id"]], "check_name": "normalization",
                           "description": f"raw {r['raw_value']} -> value {r['metric_value']}",
                           "record": r})
    return issues


def check_contradiction(records: list[dict]) -> list[dict]:
    """Одна конфигурация + метрика — разные значения в разных местах статьи.

    Сравниваем только внутри одной таблицы: одна строка + метрика + k —
    одно значение. Разные таблицы/датасеты не сравниваем: без привязки
    к датасету это ложные противоречия (одна строка — несколько колонок-датасетов).
    """
    by_key: dict[tuple[str, str, str, str], list[dict]] = {}
    for r in records:
        if r.get("duplicate_of") or not r.get("row_label") or not r.get("source_table"):
            continue
        key = (r["row_label"], r["metric_name"].lower(), r.get("metric_k", ""), r["source_table"])
        by_key.setdefault(key, []).append(r)
    issues = []
    for (label, metric, k, _table), group in by_key.items():
        # одинаковые (источник, значение) схлопываем — от пересекающихся окон
        seen: dict[tuple[str, str], dict] = {}
        for g in group:
            kind = "табл." if g["source_table"] else "текст"
            seen.setdefault((kind, g["raw_value"]), g)
        if len({g["metric_value"] for g in seen.values()}) > 1:
            desc = "; ".join(f"{kind}: {raw}" for (kind, raw) in seen)
            issues.append({"records": [g["_id"] for g in seen.values()],
                           "check_name": "contradiction",
                           "description": f"{label} / {metric}{'@' + k if k else ''}: {desc}",
                           "record": group[0]})
    return issues


def check_missing_source(records: list[dict]) -> list[dict]:
    """Нет страницы или цитаты."""
    return [
        {"records": [r["_id"]], "check_name": "missing_source",
         "description": f"{r['_id']}: нет страницы или цитаты", "record": r}
        for r in records
        if not r.get("source_page") or not r.get("source_fragment")
    ]


ALL_CHECKS = [check_metric_scale, check_metric_k, check_normalization,
              check_contradiction, check_missing_source]


def run_checks(records: list[dict]) -> list[dict]:
    """Все правила по записям одной статьи. _id — локальный индекс записи."""
    for i, r in enumerate(records):
        r["_id"] = i
    issues = []
    for check in ALL_CHECKS:
        issues.extend(check(records))
    for r in records:
        r.pop("_id", None)
    return issues
