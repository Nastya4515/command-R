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

# Поля, которые модель может вернуть, но которые не уходят в CSV напрямую
_EXTRA_KEYS = {"label", "unit", "cited_reference"}
# Поля, которые назначает код (модель их не заполняет)
_CODE_KEYS = {"publication_id", "result_id", "duplicate_of", "extraction_status",
              "metric_value", "metric_unit", "normalized_value", "normalized_unit"}


def result_keys(profile: dict) -> list[str]:
    """Поля результата из схемы области + служебные поля модели."""
    cols = [c for c in profile["schema"]["tables"]["results"] if c not in _CODE_KEYS]
    return cols + sorted(_EXTRA_KEYS - set(cols))


def _split_page_text(text: str, max_chars: int = 2500) -> list[str]:
    """Делим плотную страницу (сотни чисел) на куски по строкам.

    gpt-4o-mini склонна «обобщать» гигантские таблицы вместо полного списка —
    поэтому страница с большим числом чисел уходит модели частями.
    """
    if len(text) <= max_chars or text.count("\n") < 10:
        return [text]
    chunks, current, size = [], [], 0
    for line in text.splitlines():
        if size + len(line) > max_chars and current:
            chunks.append("\n".join(current))
            current, size = [], 0
        current.append(line)
        size += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks


def _count_digits(text: str) -> int:
    return sum(c.isdigit() for c in text)


def _row_mode_plan(page: dict, min_row_digits: int = 8, min_rows: int = 5):
    """Плотная таблица -> построчный режим.

    Строка таблицы — строка с min_row_digits+ цифрами (метка + значения).
    Если таких строк min_rows+, страница уходит модели по одной строке:
    контекст — заголовок таблицы (все нечисловые строки) + сама строка.
    Возвращает (header, rows) или None.
    """
    lines = [l["text"] for l in page.get("lines", []) if l["text"].strip()]
    if not lines:
        return None
    dense_idx = [i for i, t in enumerate(lines) if _count_digits(t) >= min_row_digits]
    if len(dense_idx) < min_rows:
        return None
    dense = set(dense_idx)
    header = "\n".join(t for i, t in enumerate(lines) if i not in dense)
    rows = [lines[i] for i in dense_idx]
    return header, rows


_ROW_ADDENDUM = (
    "\n\nThe text below is ONE ROW of a dense results table, preceded by the table's "
    "caption and column headers. Extract EVERY numeric value in the row as a separate "
    "result object, using the headers to determine each value's metric and dataset. "
    "Quote the row itself as source_fragment.")


def _ask_results(llm, profile: dict, req_id: str, user: str,
                 out_path: Path, force: bool, max_tokens: int | None = None) -> list[dict]:
    """Один запрос шага B с кэшем -> список результатов."""
    if out_path.exists() and not force:
        return json.loads(out_path.read_text(encoding="utf-8"))
    data = llm.ask_json("page", profile["prompt_text"]["step_b"], user,
                        req_id=req_id, max_tokens=max_tokens)
    part = []
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        part = [r for r in data["results"] if isinstance(r, dict)]
    out_path.write_text(json.dumps(part, ensure_ascii=False, indent=1), encoding="utf-8")
    return part


def _page_request(llm, profile: dict, pid: str, page: dict, listing: str,
                  cache_dir: Path, force: bool) -> list[dict]:
    """Результаты одной страницы: построчно для плотных таблиц, иначе кусками."""
    pno = page["page"]
    plan = _row_mode_plan(page)
    results: list[dict] = []
    if plan:
        header, rows = plan
        for ri, row in enumerate(rows, start=1):
            user = (f"{listing}\n\n=== Page {pno}, table row {ri}/{len(rows)} ===\n"
                    f"[table header]\n{header}\n[row]\n{row}{_ROW_ADDENDUM}")
            results.extend(_ask_results(llm, profile, f"{pid}_p{pno:02d}_r{ri:02d}", user,
                                        cache_dir / f"page_{pno:02d}_r{ri:02d}.json", force))
        return results
    text = pages_mod.page_text(page)
    chunks = _split_page_text(text)
    for ci, chunk in enumerate(chunks, start=1):
        header = f"Part {ci}/{len(chunks)} of page {pno}" if len(chunks) > 1 \
            else f"Page {pno}"
        user = f"{listing}\n\n=== {header} ===\n{chunk}"
        results.extend(_ask_results(llm, profile, f"{pid}_p{pno:02d}_c{ci}", user,
                                    cache_dir / f"page_{pno:02d}_c{ci}.json", force))
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
    listing = entities_listing(step_a["entities"], profile)
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
        return page["page"], _page_request(llm, profile, pid, page, listing,
                                           pages_dir, force)

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
            collected = []
            for cache in sorted(pages_dir.glob(f"page_{page['page']:02d}_*.json")):
                collected.extend(json.loads(cache.read_text(encoding="utf-8")))
            if collected:
                page_results.append((page["page"], collected))

    rkeys = result_keys(profile)
    for pno, items in sorted(page_results):
        for r in items:
            clean = {k: r.get(k) for k in rkeys}
            clean["publication_id"] = pid
            clean["source_page"] = pno
            results.append(clean)

    out = {"results": results}
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("%s: шаг B — %d результатов с %d страниц", pid, len(results), len(page_results))
    return out
