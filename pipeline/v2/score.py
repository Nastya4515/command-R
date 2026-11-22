"""Оценка качества: сравнение out/<area>/<set> с эталоном dev (ТЗ v2, п. 3.4).

Сопоставление результатов RAG (п. 3.5.5): (статья, страница, нормализованное
значение с допуском округления) + близость названия метрики (регистр, пробелы,
синонимы EM / Exact Match). Значения с графиков — отдельная строка отчёта,
D014 — отдельно (искажает среднее: 28.5k из 30.8k графиковых значений эталона).

Запуск: python -m pipeline.v2.score --area rag [--only D001 D002 D003]
Отчёт: reports/score_<area>_<дата>.md
"""
from __future__ import annotations

import argparse
import csv
import logging
import re
from datetime import datetime
from pathlib import Path

import yaml

from .normalize import same_at_reported_precision
from .profile import area_cfg, load_profile

log = logging.getLogger("v2.score")

_SYNONYMS = {"exactmatch": "em", "exact_match": "em"}


def _norm_name(name: str) -> str:
    n = (name or "").lower().replace("σ", "sigma")
    n = re.sub(r"\s*\((%|pct|percent|percentage)\)", "", n)
    n = re.sub(r"[@\d]+$", "", n)
    n = re.sub(r"[^a-z]+", "", n)
    return _SYNONYMS.get(n, n)


def _load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _match_results(ours: list[dict], gold: list[dict]) -> tuple[int, int, int]:
    """Жадное сопоставление: совпавшие / наши всего / эталон всего."""
    gold_pool = list(gold)
    matched = 0
    for r in ours:
        value = r.get("normalized_value") or r.get("metric_value") or ""
        name = _norm_name(r.get("metric_name", ""))
        best = None
        for g in gold_pool:
            gval = g.get("normalized_value") or g.get("metric_value") or ""
            if not value or not gval:
                continue
            if str(g.get("source_page")) != str(r.get("source_page")):
                continue
            if not same_at_reported_precision(value, gval):
                continue
            if _norm_name(g.get("metric_name", "")) != name:
                continue
            best = g
            break
        if best is not None:
            matched += 1
            gold_pool.remove(best)
    return matched, len(ours), len(gold)


def _fill_rate(rows: list[dict], fields: list[str]) -> dict[str, str]:
    rate = {}
    for f in fields:
        filled = sum(1 for r in rows if (r.get(f) or "").strip())
        rate[f] = f"{filled}/{len(rows)}" if rows else "0/0"
    return rate


def score(area: str, cfg: dict, only: list[str] | None = None) -> str:
    profile = load_profile(area)
    area_data = area_cfg(cfg, area)
    out_dir = Path(cfg["work"]["out_dir"]) / area / "dev"
    gold_dir = Path(area_data["dev_gold_dir"])

    ours = {t: _load_csv(out_dir / f"{t}.csv") for t in profile["schema"]["tables"]}
    gold = {t: _load_csv(gold_dir / f"{t}.csv") for t in profile["schema"]["tables"]}
    if only:
        keep = set(only)
        for t, rows in ours.items():
            ours[t] = [r for r in rows if r.get("publication_id") in keep]
        for t, rows in gold.items():
            gold[t] = [r for r in rows if r.get("publication_id") in keep]

    lines = [f"# Оценка качества — область {area}, набор dev",
             f"Дата: {datetime.now().isoformat(timespec='seconds')}",
             f"Статьи: {', '.join(only) if only else 'все обработанные'}", ""]

    # --- publications ---
    gold_pubs = {p["publication_id"]: p for p in gold["publications"]}
    scope_ok = sum(1 for p in ours["publications"]
                   if p["publication_id"] in gold_pubs
                   and p.get("in_scope") == gold_pubs[p["publication_id"]].get("in_scope"))
    lines += ["## publications",
              f"- in_scope совпал с эталоном: {scope_ok}/{len(ours['publications'])}",
              ""]

    # --- results: всё, текст/графики, без D014 ---
    ours_res = [r for r in ours["results"] if not r.get("duplicate_of")]
    gold_res = [r for r in gold["results"]
                if r.get("extraction_status") == "extracted" and not r.get("duplicate_of")]

    def block(title: str, o: list[dict], g: list[dict]) -> list[str]:
        m, no, ng = _match_results(o, g)
        prec = m / no if no else 0
        rec = m / ng if ng else 0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
        return [f"### {title}",
                f"- совпало: {m} · наших: {no} · эталон: {ng}",
                f"- precision: {prec:.1%} · recall: {rec:.1%} · F1: {f1:.1%}", ""]

    lines.append("## results")
    lines += block("все результаты", ours_res, gold_res)
    o_txt = [r for r in ours_res if not r.get("source_figure")]
    g_txt = [r for r in gold_res if not r.get("source_figure")]
    lines += block("только текст/таблицы (без графиков)", o_txt, g_txt)
    o_fig = [r for r in ours_res if r.get("source_figure")]
    g_fig = [r for r in gold_res if r.get("source_figure")]
    lines += block("только графики (source_figure)", o_fig, g_fig)
    o_nod = [r for r in ours_res if r["publication_id"] != "D014"]
    g_nod = [r for r in gold_res if r["publication_id"] != "D014"]
    lines += block("без статьи D014", o_nod, g_nod)

    # --- сущности: заполненность полей ---
    lines.append("## заполненность полей сущностей (наш набор)")
    entity_fields = {
        "configurations": ["rag_variant", "retrieval_method", "retriever_model",
                           "embedding_model", "chunking_method", "chunk_size",
                           "top_k", "reranker_model", "generator_model",
                           "prompt_strategy"],
        "datasets": ["dataset_name", "language", "data_split", "scientific_domain"],
        "tasks": ["task_type"],
        "experiments": ["evaluation_protocol", "baseline_name", "sample_size"],
    }
    for _ in _entity_sections(entity_fields_map=entity_fields, ours=ours, gold=gold, lines=lines):
        pass
    return "\n".join(lines)


def _entity_sections(entity_fields_map, ours, gold, lines):
    for table, fields in entity_fields_map.items():
        n_ours = len(ours.get(table, []))
        n_gold = len(gold.get(table, []))
        lines.append(f"### {table}: наших {n_ours}, эталон {n_gold}")
        for f, rate in _fill_rate(ours.get(table, []), fields).items():
            lines.append(f"- {f}: {rate}")
        lines.append("")
        yield table


def main() -> None:
    parser = argparse.ArgumentParser(description="Оценка качества против dev_gold")
    parser.add_argument("--area", choices=["rag", "solar"], required=True)
    parser.add_argument("--only", nargs="*")
    args = parser.parse_args()
    with open("config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    report = score(args.area, cfg, args.only)
    reports = Path(cfg["work"]["reports_dir"])
    reports.mkdir(exist_ok=True)
    path = reports / f"score_{args.area}_{datetime.now():%Y-%m-%d_%H%M}.md"
    path.write_text(report, encoding="utf-8")
    print(report)
    log.info("Отчёт: %s", path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
