"""Шаг E для области Solar: физические проверки (ТЗ v2, п. 3.5.5).

Правила: jv_consistency (3 %), voc_limit, range, eqe_consistency (5 %),
champion_vs_mean, contradiction, unit_inconsistency.
Точных порогов range в материалах кейса нет — пороги из профиля (допущение,
фиксируется в паспорте набора).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from ..textnorm import normalize_number
from .checks import _issue
from .checks import run_article as generic_checks

log = logging.getLogger(__name__)

PIN = 100.0  # мВт/см² при AM1.5G


def _num(r: dict, field: str = "normalized_value") -> float | None:
    v = normalize_number(r.get(field) or r.get("metric_value") or "")
    return float(v) if v is not None else None


def _same_context(a: dict, b: dict) -> bool:
    """Одинаковые условия: прибор, измерение, агрегация, момент времени."""
    return all((a.get(f) or "") == (b.get(f) or "") for f in
               ("device_id", "measurement_id", "aggregation", "time_point"))


def run_article(pid: str, cfg: dict, area: str, set_name: str, profile: dict,
                normalized: dict, step_a: dict | None = None,
                force: bool = False) -> dict:
    """Физические проверки Solar + общие (contradiction, unit_inconsistency)."""
    out_path = Path(cfg["work"]["cache_dir"]) / "v2" / area / set_name / pid / "issues.json"
    if out_path.exists() and not force:
        return json.loads(out_path.read_text(encoding="utf-8"))

    # общие проверки (metric_scale выключен в профиле Solar — bounded_metrics пуст)
    base = generic_checks(pid, cfg, area, set_name, profile, normalized, force=True)
    issues = list(base["issues"])
    n = len(issues)
    prefix = profile["ids"]["issues"]
    enabled = profile.get("checks", {})

    results = [r for r in normalized.get("results", [])
               if not r.get("duplicate_of") and r.get("extraction_status") == "extracted"]
    by_metric: dict[str, list[dict]] = {}
    for r in results:
        by_metric.setdefault((r.get("metric_name") or "").strip(), []).append(r)

    entities = (step_a or {}).get("entities", {})
    bandgap = {}
    for m in entities.get("materials") or []:
        v = normalize_number(str(m.get("bandgap_value") or ""))
        if v is not None and (m.get("bandgap_unit") or "eV") == "eV":
            bandgap[m["material_id"]] = float(v)
    absorber_of = {d["device_id"]: d.get("absorber_material_id", "")
                   for d in entities.get("devices") or []}

    def flag(check: str, record_ids: list[str], description: str, anchor: dict) -> None:
        nonlocal n
        n += 1
        issues.append(_issue(pid, prefix, n, record_ids, check, description,
                             anchor.get("source_page") or "",
                             anchor.get("source_fragment") or ""))

    # jv_consistency: |Voc*Jsc*FF/Pin - PCE| / PCE > 3% (одно измерение, одна агрегация)
    if enabled.get("jv_consistency"):
        for pce in by_metric.get("PCE", []):
            ctx = [r for r in results if _same_context(r, pce)]
            voc = next((r for r in ctx if r.get("metric_name") == "Voc"), None)
            jsc = next((r for r in ctx if r.get("metric_name") == "Jsc"), None)
            ff = next((r for r in ctx if r.get("metric_name") == "FF"), None)
            if not all([voc, jsc, ff]):
                continue
            v, j, f, p = _num(voc), _num(jsc), _num(ff), _num(pce)
            if None in (v, j, f, p) or not p:
                continue
            pce_calc = v * j * f / PIN
            if abs(pce_calc - p) / abs(p) > 0.03:
                flag("jv_consistency",
                     [voc["result_id"], jsc["result_id"], ff["result_id"], pce["result_id"]],
                     f"PCE={p}% не согласуется с Voc·Jsc·FF/Pin = {v}·{j}·{f}/100 "
                     f"= {pce_calc:.2f}% (расхождение {abs(pce_calc - p) / abs(p):.1%})",
                     pce)

    # voc_limit: Voc >= Eg/q (Eg поглотителя прибора)
    if enabled.get("voc_limit"):
        for voc in by_metric.get("Voc", []):
            mat = absorber_of.get(voc.get("device_id") or "", "")
            eg = bandgap.get(mat)
            v = _num(voc)
            if eg is None or v is None:
                continue
            if v >= eg:
                flag("voc_limit", [voc["result_id"]],
                     f"Voc={v} В ≥ Eg/q={eg} В — физически невозможно", voc)

    # range: значения вне физических пределов (пороги — допущение из профиля)
    if enabled.get("range"):
        for metric, (lo, hi) in (profile.get("range_limits") or {}).items():
            for r in by_metric.get(metric, []):
                v = _num(r)
                if v is None:
                    continue
                if not (lo <= v <= hi):
                    flag("range", [r["result_id"]],
                         f"{metric}={v} {r.get('metric_unit')} вне физических пределов "
                         f"[{lo}, {hi}]", r)

    # eqe_consistency: |Jsc_EQE - Jsc| / Jsc > 5% (один прибор)
    if enabled.get("eqe_consistency"):
        for jsc in by_metric.get("Jsc", []):
            for eqe in by_metric.get("Jsc_EQE", []):
                if (jsc.get("device_id") or "") != (eqe.get("device_id") or ""):
                    continue
                j, e = _num(jsc), _num(eqe)
                if j is None or e is None or not j:
                    continue
                if abs(e - j) / abs(j) > 0.05:
                    flag("eqe_consistency", [jsc["result_id"], eqe["result_id"]],
                         f"Jsc(EQE)={e} против Jsc(ВАХ)={j} мА/см² — расхождение "
                         f"{abs(e - j) / abs(j):.1%} > 5%", jsc)

    # champion_vs_mean: среднее по партии выше лучшего прибора
    if enabled.get("champion_vs_mean"):
        for metric, rows in by_metric.items():
            champions = [r for r in rows if r.get("aggregation") == "champion"]
            means = [r for r in rows if r.get("aggregation") == "mean"]
            for mean_r in means:
                for champ in champions:
                    m, c = _num(mean_r), _num(champ)
                    if m is None or c is None:
                        continue
                    if m > c:
                        flag("champion_vs_mean", [mean_r["result_id"], champ["result_id"]],
                             f"{metric}: среднее по партии {m} выше лучшего прибора {c}",
                             mean_r)

    out = {"issues": issues}
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("%s: шаг E (solar) — %d замечаний", pid, len(issues))
    return out
