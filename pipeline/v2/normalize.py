"""Шаг D. Нормализация: единицы, направление метрики, metric_k, duplicate_of.

Правила RAG (ТЗ v2, п. 3.5.3):
  - шкала источника сохраняется: доли и проценты не пересчитываются;
  - время -> ms (s x1000, min x60000) при известной исходной единице;
  - metric_value = normalized_value, metric_unit = normalized_unit (иначе ошибка чекера);
  - metric_direction — по справочнику семейств (profile.metric_direction);
  - metric_k — из «@k» в названии;
  - duplicate_of: повтор того же значения того же объекта в другом месте статьи —
    все ключевые поля совпадают (как требует чекер: 13 полей, значение — с допуском
    округления same_at_reported_precision).
"""
from __future__ import annotations

import json
import logging
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

from ..textnorm import normalize_number
from .extract_a import work_dir

log = logging.getLogger(__name__)

_AT_K = re.compile(r"@(\d+)(?![\d.])")

_NAME_SUFFIXES = ("relative change", "absolute gain", "relative improvement",
                  "relative reduction", "absolute change")
_NAME_ALIASES = {"exactmatch": "em", "exactmatches": "em"}


def _name_key(name: str) -> str:
    n = (name or "").lower().replace("σ", "sigma")
    n = re.sub(r"\((?:%|pct|percent|percentage)\)", "", n)
    n = re.sub(r"[^a-z0-9]+", "", n)
    return n


def load_metric_vocab(profile: dict) -> dict[str, str]:
    """Канонический словарь имён метрик: ключ нормализации -> каноническое имя.

    Источник — dev-эталон области (profile.metric_vocab). Для test-набора новые
    имена, которых нет в словаре, остаются как есть.
    """
    import csv
    path = profile.get("metric_vocab")
    vocab: dict[str, str] = {}
    if not path:
        return vocab
    p = Path(path)
    if not p.exists():
        log.warning("metric_vocab не найден: %s", path)
        return vocab
    with open(p, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("metric_name") or "").strip()
            if name:
                vocab.setdefault(_name_key(name), name)
    return vocab


def canonicalize_metric_name(name: str, vocab: dict[str, str]) -> str:
    """Приводит вольное имя метрики к каноническому из словаря (если нашлось)."""
    name = (name or "").strip()
    if not name or not vocab:
        return name
    if _name_key(name) in vocab:
        return vocab[_name_key(name)]
    base = re.sub(r"\s*\([^)]*\)", "", name).strip()
    inner = re.search(r"\(([^)]*)\)", name)
    candidates = [base]
    if inner:
        candidates.append(inner.group(1).strip())
    for cand in candidates:
        k = _NAME_ALIASES.get(_name_key(cand), _name_key(cand))
        if k in vocab:
            return vocab[k]
    # суффиксы вида «X relative change»: канонизируем основу и пересобираем
    for suf in _NAME_SUFFIXES:
        if base.lower().endswith(suf):
            stem = base[: -len(suf)].strip()
            canon_stem = canonicalize_metric_name(stem, vocab)
            rebuilt = f"{canon_stem} {suf}"
            if _name_key(rebuilt) in vocab:
                return vocab[_name_key(rebuilt)]
    import difflib
    close = difflib.get_close_matches(_name_key(base), list(vocab), n=1, cutoff=0.8)
    if close:
        return vocab[close[0]]
    return name


def same_at_reported_precision(a: str, b: str) -> bool:
    """Как в check_submission.py RAG: грубое явное округление принимается."""
    try:
        x, y = Decimal(a), Decimal(b)
        if not x.is_finite() or not y.is_finite():
            return False
        if x == y:
            return True
        ex, ey = x.as_tuple().exponent, y.as_tuple().exponent
        if ex == ey:
            return False
        coarse, fine = (x, y) if ex > ey else (y, x)
        return fine.quantize(Decimal(1).scaleb(coarse.as_tuple().exponent),
                             rounding=ROUND_HALF_UP) == coarse
    except (InvalidOperation, ValueError):
        return False


def metric_direction(metric_name: str, profile: dict) -> str:
    name = (metric_name or "").lower().strip()
    for direction, families in profile.get("metric_direction", {}).items():
        for fam in families:
            if fam in name:
                return direction
    return ""


def normalize_unit(unit: str | None, raw_value: str, profile: dict) -> str:
    """Каноническая единица: алиасы профиля, знак % у числа, иначе как есть."""
    u = (unit or "").strip()
    aliases = profile.get("unit_aliases", {})
    if u.lower() in aliases:
        u = aliases[u.lower()]
    if not u and "%" in (raw_value or ""):
        u = "%"
    return u


def convert(value: str, unit: str, profile: dict, metric_name: str = "") -> tuple[str, str]:
    """Пересчёт по профилю (unit_conversions). Возвращает (значение, единица).

    fraction -> % — только для метрик из fraction_to_percent_metrics (Solar: PCE/FF/HI);
    для остальных метрик доля остаётся долей (шкала источника сохраняется).
    """
    conv = profile.get("unit_conversions", {}).get(unit)
    if not conv:
        return value, unit
    if unit == "fraction":
        allowed = profile.get("fraction_to_percent_metrics")
        if allowed is not None and metric_name not in allowed:
            return value, unit
    num = normalize_number(value)
    if num is None:
        return value, unit
    result = float(num) * float(conv["factor"])
    out = f"{result:g}"
    return out, conv["target"]


def _dup_key(r: dict, profile: dict) -> tuple:
    """Поля идентичности результата для duplicate_of (из профиля области)."""
    return tuple((r.get(f) or "") for f in profile.get("dup_fields", []))


def run_article(pid: str, cfg: dict, area: str, set_name: str, profile: dict,
                verified: dict, force: bool = False) -> dict:
    """Шаг D для одной статьи."""
    out_path = work_dir(cfg, area, set_name, pid) / "normalized.json"
    if out_path.exists() and not force:
        return json.loads(out_path.read_text(encoding="utf-8"))

    results = []
    vocab = load_metric_vocab(profile)
    renamed = 0
    for r in verified.get("results", []):
        r = dict(r)
        name = (r.get("metric_name") or "").strip()
        canon = canonicalize_metric_name(name, vocab)
        if canon != name:
            renamed += 1
            name = canon
            r["metric_name"] = canon
        raw = (r.get("raw_value") or "").strip()

        # metric_k из названия
        if not r.get("metric_k"):
            m = _AT_K.search(name)
            if m:
                r["metric_k"] = m.group(1)

        # направление метрики
        if not r.get("metric_direction"):
            r["metric_direction"] = metric_direction(name, profile)

        # единица и пересчёт
        unit = normalize_unit(r.get("unit"), raw, profile)
        value = normalize_number(raw)  # None для диапазонов «1.2-1.4»
        if value is not None and unit:
            value, unit = convert(value, unit, profile, metric_name=name)
        raw_unit = (r.get("raw_unit") or "").strip()
        if raw_unit.lower() in profile.get("unit_aliases", {}):
            raw_unit = profile["unit_aliases"][raw_unit.lower()]

        r["metric_unit"] = unit
        r["metric_value"] = value or ""
        r["raw_unit"] = raw_unit
        r["normalized_value"] = r["metric_value"]
        r["normalized_unit"] = r["metric_unit"]
        r["aggregation"] = (r.get("aggregation") or "").strip()
        r["result_origin"] = (r.get("result_origin") or "primary").strip()
        if r["result_origin"] == "primary":
            r["cited_publication_id"] = ""
        else:
            r["cited_publication_id"] = (r.get("cited_reference") or "").strip()
        r["extraction_status"] = r.get("extraction_status") or "extracted"
        r["duplicate_of"] = ""
        results.append(r)

    # duplicate_of: тот же объект, та же метрика, то же значение (с допуском)
    seen: list[tuple[tuple, str, str]] = []  # (dup_key, value, result_id)
    prefix = profile["ids"]["results"]
    for n, r in enumerate(results, start=1):
        key = _dup_key(r, profile)
        value = r["metric_value"]
        dup_of = ""
        if value:
            for prev_key, prev_val, prev_id in seen:
                if prev_key == key and same_at_reported_precision(value, prev_val):
                    dup_of = prev_id
                    break
        r["result_id"] = f"{prefix}{n}"
        r["duplicate_of"] = dup_of
        if not dup_of:
            seen.append((key, value, r["result_id"]))

    out = {"results": results}
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    dups = sum(1 for r in results if r["duplicate_of"])
    log.info("%s: шаг D — %d результатов, канонизировано имён %d, повторов %d",
             pid, len(results), renamed, dups)
    return out
