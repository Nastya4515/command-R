"""Общий доступ к страницам: кэш cache/v2_pages/<area>/<pid>.json.

Читатель PDF — шаг read_pdf из конвейера v1 (слова, строки, тексты двух
парсеров, vision-OCR сканов). Кэш v2 отделён от v1: имена D001/P001
пересекаются между областями.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

_DIGIT = re.compile(r"\d")


def pages_cache_dir(cfg: dict, area: str) -> Path:
    path = Path(cfg["work"]["cache_dir"]) / "v2_pages" / area
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_pages(pid: str, cfg: dict, area: str, pdf_dir: Path) -> dict:
    """Страницы статьи; при отсутствии кэша — чтение PDF на месте.

    Для области rag переиспользуется кэш конвейера v1 (cache/pages/):
    он построен из тех же PDF и уже содержит OCR.
    """
    path = pages_cache_dir(cfg, area) / f"{pid}.json"
    legacy = Path(cfg["work"]["cache_dir"]) / "pages" / f"{pid}.json"
    if not path.exists() and area == "rag" and legacy.exists():
        path.write_bytes(legacy.read_bytes())
        return json.loads(path.read_text(encoding="utf-8"))
    if not path.exists():
        from ..read_pdf import _strip_surrogates, read_pdf
        log.info("%s: читаю PDF (кэша нет)", pid)
        data = read_pdf(pdf_dir / f"{pid}.pdf", cfg)
        path.write_text(json.dumps(_strip_surrogates(data), ensure_ascii=False),
                        encoding="utf-8")
        log.info("%s: %d страниц", pid, len(data["pages"]))
    return json.loads(path.read_text(encoding="utf-8"))


def page_text(page: dict) -> str:
    """Лучший доступный текст страницы: pymupdf -> pypdf -> сборка по строкам."""
    for key in ("text_pymupdf", "text_pypdf"):
        text = (page.get(key) or "").strip()
        if text:
            return text
    return "\n".join(l["text"] for l in page.get("lines", []))


def has_digits(text: str) -> bool:
    return bool(_DIGIT.search(text))


def full_document_text(pages: list[dict], max_chars: int = 350_000) -> str:
    """Весь документ с метками страниц; при переполнении — голова и хвост."""
    parts = [f"=== Page {p['page']} ===\n{page_text(p)}" for p in pages]
    text = "\n\n".join(parts)
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    log.warning("Документ %d символов — в шаг A идут голова и хвост по %d",
                len(text), half)
    return text[:half] + "\n\n[...MIDDLE TRUNCATED...]\n\n" + text[-half:]
