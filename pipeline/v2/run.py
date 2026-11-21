"""Оркестратор конвейера v2.

Запуск: python -m pipeline.v2.run --area rag --set dev [--only D001 D002]
        [--step a|b|c|d|e|f] [--force] [--mock]

Шаги: a (документ) -> b (страницы) -> c (верификация) -> d (нормализация)
      -> e (проверки) -> f (экспорт + check_submission).
Кэш каждого шага: cache/v2/<area>/<set>/<pid>/ — повторный запуск бесплатен.
--mock: шаги A/B не ходят в API, а отвечают из dev_gold (только для dev,
только чтобы проверить механику шагов C–F без расхода бюджета).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.v2 import checks, export, extract_a, extract_b, normalize, verify
from pipeline.v2.llm import BudgetExceeded, Llm
from pipeline.v2.profile import area_cfg, load_profile

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("v2.run")


def load_config(path: str = "config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class MockLlm:
    """Шаги A/B из эталона dev — для проверки механики без API."""

    def __init__(self, gold_dir: Path):
        import csv
        self.gold = {}
        for table in ("publications", "configurations", "datasets", "tasks",
                      "experiments", "results"):
            path = gold_dir / f"{table}.csv"
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    self.gold[table] = list(csv.DictReader(f))
        self.calls = 0

    def stats(self) -> dict:
        return {"calls": self.calls, "cost_usd": 0.0, "tokens": {}}

    def ask_json(self, role, system, user, req_id, max_tokens=None):
        raise NotImplementedError("MockLlm не отвечает на запросы — "
                                  "используется подстановка эталона в run.py")


def mock_step_a(pid: str, gold: dict, profile: dict) -> dict:
    pubs = [r for r in gold["publications"] if r["publication_id"] == pid]
    pub = dict(pubs[0]) if pubs else {"publication_id": pid, "title": "",
                                      "year": "", "DOI": "", "authors": "",
                                      "in_scope": "true", "exclusion_reason": ""}
    entities = {}
    for table in extract_a.ENTITY_TABLES:
        entities[table] = [dict(r) for r in gold[table]
                           if r["publication_id"] == pid]
        for it in entities[table]:
            it.setdefault("label", it.get(extract_a.key_field(table), ""))
    return {"publication": pub, "entities": entities}


def mock_step_b(pid: str, gold: dict) -> dict:
    results = []
    for r in gold["results"]:
        if r["publication_id"] != pid or r["extraction_status"] != "extracted":
            continue
        results.append({
            "metric_name": r["metric_name"], "metric_variant": r["metric_variant"],
            "metric_k": r["metric_k"], "raw_value": r["raw_value"],
            "raw_unit": r["raw_unit"], "unit": r["metric_unit"],
            "aggregation": r["aggregation"], "sample_size": r["sample_size"],
            "result_origin": r["result_origin"],
            "cited_reference": r["cited_publication_id"],
            "config_id": r["config_id"], "dataset_id": r["dataset_id"],
            "task_id": r["task_id"], "experiment_id": r["experiment_id"],
            "source_section": r["source_section"], "source_table": r["source_table"],
            "source_figure": r["source_figure"], "source_fragment": r["source_fragment"],
            "note": r["note"], "publication_id": pid,
            "source_page": int(r["source_page"]) if r["source_page"].isdigit() else 1,
        })
    return {"results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description="Конвейер извлечения v2")
    parser.add_argument("--area", choices=["rag", "solar"], required=True)
    parser.add_argument("--set", dest="set_name", choices=["dev", "test", "uploads"],
                        required=True)
    parser.add_argument("--only", nargs="*", help="только эти статьи, напр. D001 D002")
    parser.add_argument("--step", choices=list("abcdef"), help="только один шаг")
    parser.add_argument("--force", action="store_true", help="игнорировать кэш шага")
    parser.add_argument("--mock", action="store_true",
                        help="шаги A/B из dev_gold (только --set dev, без API)")
    args = parser.parse_args()

    cfg = load_config()
    profile = load_profile(args.area)
    area_data = area_cfg(cfg, args.area)
    pdf_dir = Path(area_data[f"{args.set_name}_dir"])
    pids = sorted(p.stem for p in pdf_dir.glob("*.pdf"))
    if args.only:
        pids = [p for p in pids if p in args.only]
    log.info("Область %s, набор %s: %d статей", args.area, args.set_name, len(pids))

    gold = None
    if args.mock:
        if args.set_name != "dev":
            parser.error("--mock работает только с --set dev")
        mock = MockLlm(Path(area_data["dev_gold_dir"]))
        gold = mock.gold
        llm = mock
    else:
        llm = Llm(cfg)
    steps = args.step or "abcdef"

    t0 = time.time()
    interrupted = False
    for pid in pids:
        try:
            if "a" in steps:
                if gold is not None:
                    data = mock_step_a(pid, gold, profile)
                    path = extract_a.work_dir(cfg, args.area, args.set_name, pid) / "step_a.json"
                    path.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
                else:
                    extract_a.run_article(pid, cfg, args.area, args.set_name,
                                          profile, llm, pdf_dir, force=args.force)
            step_a = json.loads((extract_a.work_dir(cfg, args.area, args.set_name, pid)
                                 / "step_a.json").read_text(encoding="utf-8"))
            if "b" in steps:
                if gold is not None:
                    data = mock_step_b(pid, gold)
                    path = extract_a.work_dir(cfg, args.area, args.set_name, pid) / "step_b.json"
                    path.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
                else:
                    extract_b.run_article(pid, cfg, args.area, args.set_name,
                                          profile, llm, pdf_dir, step_a, force=args.force)
            step_b = json.loads((extract_a.work_dir(cfg, args.area, args.set_name, pid)
                                 / "step_b.json").read_text(encoding="utf-8"))
            if "c" in steps:
                verify.run_article(pid, cfg, args.area, args.set_name, profile,
                                   None if gold is not None else llm, pdf_dir,
                                   step_a, step_b, force=args.force)
            if "d" in steps:
                verified = json.loads((extract_a.work_dir(cfg, args.area, args.set_name, pid)
                                       / "verified.json").read_text(encoding="utf-8"))
                normalize.run_article(pid, cfg, args.area, args.set_name, profile,
                                      verified, force=args.force)
            if "e" in steps:
                normalized = json.loads((extract_a.work_dir(cfg, args.area, args.set_name, pid)
                                         / "normalized.json").read_text(encoding="utf-8"))
                checks.run_article(pid, cfg, args.area, args.set_name, profile,
                                   normalized, force=args.force)
        except BudgetExceeded as exc:
            log.error("%s — прогон остановлен на %s", exc, pid)
            interrupted = True
            break
        except Exception:
            log.exception("%s: статья не обработана", pid)

    if "f" in steps:
        publications, entities_by_pid, results, issues = [], {}, [], []
        for pid in pids:
            wdir = extract_a.work_dir(cfg, args.area, args.set_name, pid)
            try:
                step_a = json.loads((wdir / "step_a.json").read_text(encoding="utf-8"))
                publications.append(step_a["publication"])
                entities_by_pid[pid] = step_a["entities"]
                normalized = json.loads((wdir / "normalized.json").read_text(encoding="utf-8"))
                results.extend(normalized.get("results", []))
                iss = json.loads((wdir / "issues.json").read_text(encoding="utf-8"))
                issues.extend(iss.get("issues", []))
            except FileNotFoundError:
                log.warning("%s: нет данных для экспорта — пропускаю", pid)
        out_dir = export.run_set(args.area, args.set_name, cfg, profile,
                                 publications, entities_by_pid, results, issues)
        log.info("Экспорт: %s", out_dir)
        export.run_checker(args.area, args.set_name, cfg, area_data)

    stats = llm.stats()
    log.info("Готово за %.1f мин. Вызовов: %d, стоимость: $%.4f, токены: %s%s",
             (time.time() - t0) / 60, stats["calls"], stats["cost_usd"],
             json.dumps(stats["tokens"]), " [ПРЕРВАНО ПО БЮДЖЕТУ]" if interrupted else "")


if __name__ == "__main__":
    main()
