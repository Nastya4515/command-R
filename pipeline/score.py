"""Оценка качества на dev: out/dev/results.csv против dev_gold/results.csv.

Совпадение: статья + метрика (без регистра) + число после нормализации.
Точность — доля наших записей, которые есть в эталоне.
Полнота — доля записей эталона, которые мы нашли.
Запуск: python -m pipeline.score
"""
from __future__ import annotations

import csv
from pathlib import Path

import yaml

from .textnorm import normalize_number


def _key(row: dict) -> tuple[str, str, str] | None:
    value = normalize_number(row.get("raw_value") or row.get("metric_value", ""))
    if value is None:
        return None
    return (row["publication_id"], row["metric_name"].strip().lower(), value)


def _load(path: Path, exclude_figures: bool = False) -> dict[str, set]:
    by_pub: dict[str, set] = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if exclude_figures and row.get("source_figure"):
                continue  # оцифровка графиков — Won't по ТЗ, считаем отдельно
            key = _key(row)
            if key:
                by_pub.setdefault(row["publication_id"], set()).add(key)
    return by_pub


def main() -> None:
    with open("config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    ours = _load(Path(cfg["work"]["out_dir"]) / "dev" / "results.csv")
    gold = _load(Path(cfg["data"]["dev_gold_dir"]) / "results.csv", exclude_figures=True)
    gold_fig = _load(Path(cfg["data"]["dev_gold_dir"]) / "results.csv")
    for pid in gold_fig:
        gold_fig[pid] -= gold.get(pid, set())  # только фигурные записи

    lines = ["# Оценка качества на dev\n",
             "| Статья | Точность | Полнота | Наших | Эталон |",
             "|---|---|---|---|---|"]
    precisions, recalls = [], []
    for pid in sorted(gold):
        ours_keys = ours.get(pid, set())
        gold_keys = gold[pid]
        if not ours_keys and not gold_keys:
            continue
        tp = len(ours_keys & gold_keys)
        precision = tp / len(ours_keys) if ours_keys else 0.0
        recall = tp / len(gold_keys) if gold_keys else 1.0
        precisions.append(precision)
        recalls.append(recall)
        lines.append(f"| {pid} | {precision:.1%} | {recall:.1%} | {len(ours_keys)} | {len(gold_keys)} |")
    lines.append(f"| **Среднее** | **{sum(precisions) / len(precisions):.1%}** "
                 f"| **{sum(recalls) / len(recalls):.1%}** | | |")
    # D014 отдельно (ТЗ, раздел 9): почти весь её эталон — точки с графиков
    fig_d014 = len(gold_fig.get("D014", set()))
    if fig_d014:
        lines.append(f"\nD014: {fig_d014} эталонных значений — точки с графиков "
                     f"(оцифровка, Won't по ТЗ), в основную метрику не входят.")

    reports = Path(cfg["work"]["reports_dir"])
    reports.mkdir(exist_ok=True)
    from datetime import datetime

    out = reports / f"score_{datetime.now():%Y-%m-%d}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[-3:]))
    print(f"Отчёт: {out}")


if __name__ == "__main__":
    main()
