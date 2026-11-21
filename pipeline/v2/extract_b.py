"""Шаг B. Постранично: результаты со связями и дословными цитатами.

Результат: cache/v2/<area>/<set>/<pid>/pages/page_NN.json (кэш каждой страницы)
и сводный step_b.json: {"results": [...]}.
source_page проставляет код по номеру страницы — модели не доверяем.
"""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import pages as pages_mod
from .extract_a import entities_listing, work_dir
from .llm import BudgetExceeded

log = logging.getLogger(__name__)

RESULT_KEYS = [
    "metric_name", "metric_variant", "metric_k", "raw_value", "raw_unit", "unit",
    "aggregation", "sample_size", "result_origin", "cited_reference",
    "config_id", "dataset_id", "task_id", "experiment_id",
    "source_section", "source_table", "source_figure", "source_fragment", "note",
]


def _page_request(llm, profile: dict, pid: str, page: dict, listing: str,
                  out_path: Path, force: bool) -> list[dict]:
    """Результаты одной страницы (с кэшем)."""
    if out_path.exists() and not force:
        return json.loads(out_path.read_text(encoding="utf-8"))
    text = pages_mod.page_text(page)
    system = profile["prompt_text"]["step_b"]
    user = f"{listing}\n\n=== Page {page['page']} ===\n{text}"
    data = llm.ask_json("page", system, user, req_id=f"{pid}_p{page['page']:02d}")
    results = []
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        results = [r for r in data["results"] if isinstance(r, dict)]
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    return results


def run_article(pid: str, cfg: dict, area: str, set_name: str, profile: dict,
                llm, pdf_dir: Path, step_a: dict, force: bool = False) -> dict:
    """Шаг B для одной статьи (кэш постраничный, страницы — параллельно)."""
    out_path = work_dir(cfg, area, set_name, pid) / "step_b.json"
    if out_path.exists() and not force:
        return json.loads(out_path.read_text(encoding="utf-8"))

    publication = step_a["publication"]
    if publication["in_scope"] != "true":
        out_path.write_text(json.dumps({"results": []}, ensure_ascii=False), encoding="utf-8")
        log.info("%s: шаг B — статья вне области, пропуск", pid)
        return {"results": []}

    doc = pages_mod.load_pages(pid, cfg, area, pdf_dir)
    listing = entities_listing(step_a["entities"])
    skip_no_digits = profile.get("skip_pages_without_digits", True)

    pages_dir = work_dir(cfg, area, set_name, pid) / "pages"
    pages_dir.mkdir(exist_ok=True)

    todo = []
    for page in doc["pages"]:
        text = pages_mod.page_text(page)
        if not text.strip():
            continue  # скан без OCR-текста
        if skip_no_digits and not pages_mod.has_digits(text):
            continue
        todo.append(page)

    results: list[dict] = []
    workers = int(cfg["model"]["api"].get("max_parallel", 4))

    def one(page):
        cache = pages_dir / f"page_{page['page']:02d}.json"
        return page["page"], _page_request(llm, profile, pid, page, listing, cache, force)

    try:
        if workers > 1 and len(todo) > 1:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                page_results = list(pool.map(one, todo))
        else:
            page_results = [one(p) for p in todo]
    except BudgetExceeded:
        log.warning("%s: шаг B прерван лимитом бюджета — сохраняю частичный результат", pid)
        page_results = []
        for page in todo:  # подхватываем то, что успело записаться в кэш
            cache = pages_dir / f"page_{page['page']:02d}.json"
            if cache.exists():
                page_results.append((page["page"], json.loads(cache.read_text(encoding="utf-8"))))

    for pno, items in sorted(page_results):
        for r in items:
            clean = {k: r.get(k) for k in RESULT_KEYS}
            clean["publication_id"] = pid
            clean["source_page"] = pno
            results.append(clean)

    out = {"results": results}
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("%s: шаг B — %d результатов с %d страниц", pid, len(results), len(page_results))
    return out
