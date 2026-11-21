"""Шаг 1. Чтение PDF: слова с координатами, сборка строк, тексты страниц.

Результат: cache/pages/<pid>.json
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pdfplumber

log = logging.getLogger(__name__)


def _extract_page_words(page) -> list[dict]:
    """Слова страницы с координатами и размером шрифта (pdfplumber)."""
    words = page.extract_words(extra_attrs=["fontname", "size"], x_tolerance=1.5)
    return [
        {
            "text": w["text"],
            "x0": round(w["x0"], 1),
            "x1": round(w["x1"], 1),
            "top": round(w["top"], 1),
            "bottom": round(w["bottom"], 1),
            "size": round(float(w.get("size", 0)), 1),
            "conf": 100,
        }
        for w in words
    ]


def _page_texts(pdf_path: Path) -> tuple[list[str], list[str]]:
    """Сплошной текст страниц через pypdf и PyMuPDF (для поиска цитат)."""
    texts_pypdf: list[str] = []
    texts_pymupdf: list[str] = []
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        texts_pypdf = [(p.extract_text() or "") for p in reader.pages]
    except Exception as exc:  # noqa: BLE001 — статья не должна ронять прогон
        log.warning("pypdf failed for %s: %s", pdf_path.name, exc)
    try:
        import fitz

        with fitz.open(str(pdf_path)) as doc:
            texts_pymupdf = [p.get_text() for p in doc]
    except Exception as exc:  # noqa: BLE001
        log.warning("pymupdf failed for %s: %s", pdf_path.name, exc)
    return texts_pypdf, texts_pymupdf


def _column_cuts(words: list[dict], page_width: float, margin_ratio: float = 0.15) -> list[float]:
    """X-координаты вертикальных промежутков (колонки).

    Ищем широкую пустую вертикальную полосу внутри страницы (не у полей):
    если между правым краем одного слова и левым краем другого нет ни одного
    слова на всей высоте — это межколонный разрез.
    """
    if not words:
        return []
    left = page_width * margin_ratio
    right = page_width * (1 - margin_ratio)
    edges = sorted({w["x0"] for w in words if left < w["x0"] < right})
    cuts = []
    for x in edges:
        band = [w for w in words if x - 20 < w["x0"] < x + 1]
        if not band:
            continue
        gap_left = max((w["x1"] for w in words if w["x1"] <= x), default=None)
        if gap_left is None or x - gap_left < 15:
            continue
        cuts.append((gap_left + x) / 2)
    return cuts[:1]  # две колонки — один разрез


def _assemble_lines(words: list[dict], y_tol: float, cuts: list[float]) -> list[dict]:
    """Слова -> строки: близкий top (±y_tol) и одинаковая колонка."""
    if not words:
        return []

    def col_of(w: dict) -> int:
        return sum(w["x0"] > c for c in cuts)

    ordered = sorted(words, key=lambda w: (col_of(w), w["top"], w["x0"]))
    lines: list[dict] = []
    for w in ordered:
        for line in reversed(lines[-5:]):
            same_col = col_of(w) == line["_col"]
            close_y = abs(w["top"] - line["top"]) <= y_tol
            if same_col and close_y and w["x0"] >= line["_max_x1"] - 2:
                line["word_idx"].append(w["_idx"])
                line["_max_x1"] = max(line["_max_x1"], w["x1"])
                break
        else:
            lines.append({"word_idx": [w["_idx"]], "top": w["top"],
                          "_col": col_of(w), "_max_x1": w["x1"]})
    lines.sort(key=lambda l: (l["_col"], l["top"]))
    for i, line in enumerate(lines):
        line["line_id"] = i
    return lines


def read_pdf(pdf_path: Path, cfg: dict) -> dict:
    """Прочитать один PDF -> структура для cache/pages/<pid>.json."""
    pid = pdf_path.stem
    y_tol = cfg["lines"]["y_tolerance"]
    threshold = cfg["pdf"]["scan_char_threshold"]

    texts_pypdf, texts_pymupdf = _page_texts(pdf_path)
    pages = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            words = _extract_page_words(page)
            plain_text = " ".join(w["text"] for w in words)
            is_scan = len(plain_text) < threshold
            # битая кодировка шрифта: «(cid:NN)» вместо букв — как скан
            if not is_scan and words:
                cid = sum(1 for w in words if "(cid:" in w["text"])
                if cid / len(words) > 0.01:
                    log.warning("%s p.%d: битая кодировка (%d%% cid) -> vision-OCR",
                                pid, pno, round(100 * cid / len(words)))
                    is_scan = True
                    words = []
            ocr_mark = ""
            if is_scan and cfg["pdf"]["ocr_enabled"] and cfg["pdf"].get("ocr_backend") == "vision":
                from . import vision_ocr
                text = vision_ocr.transcribe_page(
                    pdf_path, pno, cfg, Path(cfg["work"]["cache_dir"]) / "ocr")
                if text.strip():
                    words = vision_ocr.text_to_pseudo_words(
                        text, float(page.width), float(page.height))
                    # цитаты ищутся по тексту страницы — подменяем оба движка
                    while len(texts_pypdf) < pno:
                        texts_pypdf.append("")
                    while len(texts_pymupdf) < pno:
                        texts_pymupdf.append("")
                    texts_pypdf[pno - 1] = text
                    texts_pymupdf[pno - 1] = text
                    is_scan = False
                    ocr_mark = "vision"
                else:
                    log.warning("%s p.%d: скан, vision-OCR не дал текста", pid, pno)
            elif is_scan and not cfg["pdf"]["ocr_enabled"]:
                log.warning("%s p.%d: скан (%d символов), OCR выключен", pid, pno, len(plain_text))
            cuts = _column_cuts(words, float(page.width)) if cfg["lines"]["two_column_gap"] else []
            for idx, w in enumerate(words):
                w["_idx"] = idx
            lines = _assemble_lines(words, y_tol, cuts)
            pages.append({
                "page": pno,
                "width": float(page.width),
                "height": float(page.height),
                "is_scan": is_scan,
                "ocr": ocr_mark,
                "words": [{k: v for k, v in w.items() if not k.startswith("_")} for w in words],
                "lines": [
                    {
                        "line_id": l["line_id"],
                        "text": " ".join(words[i]["text"] for i in l["word_idx"]),
                        "word_idx": l["word_idx"],
                        "top": l["top"],
                    }
                    for l in lines
                ],
                "text_pypdf": texts_pypdf[pno - 1] if pno - 1 < len(texts_pypdf) else "",
                "text_pymupdf": texts_pymupdf[pno - 1] if pno - 1 < len(texts_pymupdf) else "",
            })
    return {"publication_id": pid, "pages": pages}


def _strip_surrogates(obj):
    """В PDF встречаются битые символы (lone surrogates) — JSON их не терпит."""
    if isinstance(obj, str):
        return obj.encode("utf-8", "ignore").decode("utf-8")
    if isinstance(obj, list):
        return [_strip_surrogates(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _strip_surrogates(v) for k, v in obj.items()}
    return obj


def run(set_name: str, cfg: dict, only: list[str] | None = None) -> list[Path]:
    """Обработать все PDF набора (dev|test) -> cache/pages/<pid>.json."""
    src_dir = Path(cfg["data"][f"{set_name}_dir"])
    out_dir = Path(cfg["work"]["cache_dir"]) / "pages"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for pdf_path in sorted(src_dir.glob("*.pdf")):
        pid = pdf_path.stem
        if only and pid not in only:
            continue
        out_path = out_dir / f"{pid}.json"
        if out_path.exists():  # повторный запуск продолжает с места остановки
            written.append(out_path)
            continue
        try:
            data = read_pdf(pdf_path, cfg)
        except Exception as exc:  # noqa: BLE001
            log.error("%s: шаг read_pdf упал: %s", pid, exc)
            continue
        out_path.write_text(json.dumps(_strip_surrogates(data), ensure_ascii=False), encoding="utf-8")
        log.info("%s: %d страниц", pid, len(data["pages"]))
        written.append(out_path)
    return written
