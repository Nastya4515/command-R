"""Vision-OCR сканов через OpenAI: страница -> текст с сохранением раскладки.

Зачем: Tesseract ломает таблицы (колонки слипаются), а vision-модель
возвращает таблицу с выравниванием — конвейер дальше работает как обычно.
Внешних зависимостей нет: рендер страницы — PyMuPDF, вызов — OpenAI API.

Результат кэшируется в cache/ocr/<pid>_p<страница>.txt — повтор бесплатен.
"""
from __future__ import annotations

import base64
import logging
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)

PROMPT = (
    "This is a scanned page of a scientific article. Transcribe ALL text exactly, "
    "preserving the visual layout: keep tables aligned in columns using spaces "
    "(as in a monospace font), keep original line breaks. "
    "Output only the transcription — no descriptions, no comments."
)
DPI = 170
MAX_RETRIES = 4


def load_api_key() -> str:
    """Ключ OpenAI из .env или окружения (в коде не храним)."""
    import os
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("OPENAI_API_KEY", "")


def _strip_code_fences(text: str) -> str:
    """Модель иногда оборачивает транскрипцию в ``` — убираем."""
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


def _render_png_b64(pdf_path: Path, pno: int) -> str:
    import fitz

    with fitz.open(str(pdf_path)) as doc:
        pix = doc[pno - 1].get_pixmap(dpi=DPI)
        return base64.b64encode(pix.tobytes("png")).decode("ascii")


def transcribe_page(pdf_path: Path, pno: int, cfg: dict, cache_dir: Path) -> str:
    """Транскрибация одной страницы-скана (с кэшем). Пустая строка при сбое."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{pdf_path.stem}_p{pno}.txt"
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")

    key = load_api_key()
    if not key:
        log.error("Vision-OCR: нет OPENAI_API_KEY в .env")
        return ""

    image_b64 = _render_png_b64(pdf_path, pno)
    payload = {
        "model": cfg["pdf"].get("ocr_model", "gpt-4o-mini"),
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
            ],
        }],
        "temperature": 0,
        "max_tokens": 4000,
    }
    delay = 2.0
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json=payload, timeout=180)
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"] or ""
                text = _strip_code_fences(text)
                cache_path.write_text(text, encoding="utf-8")
                log.info("Vision-OCR %s p.%d: %d символов", pdf_path.stem, pno, len(text))
                return text
            if resp.status_code in (429, 500, 502, 503, 504):
                log.warning("Vision-OCR: HTTP %s, пауза %.0f с", resp.status_code, delay)
                time.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            log.error("Vision-OCR: HTTP %s: %s", resp.status_code, resp.text[:200])
            return ""
        except requests.RequestException as exc:
            log.warning("Vision-OCR: %s, пауза %.0f с", exc, delay)
            time.sleep(delay)
            delay = min(delay * 2, 60)
    log.error("Vision-OCR %s p.%d: не выполнено после %d попыток",
              pdf_path.stem, pno, MAX_RETRIES)
    return ""


def text_to_pseudo_words(text: str, page_width: float, page_height: float) -> list[dict]:
    """Моноширинная раскладка текста в псевдо-слова с координатами.

    Vision возвращает текст с выравниванием пробелами — переводим отступы
    в координаты: таблицы дальше распознаются обычной логикой конвейера.
    """
    char_w = max(page_width / 120.0, 4.0)   # ~120 символов в строке
    lines = text.splitlines() or [""]
    line_h = min(page_height / max(len(lines), 1), 14.0)
    words: list[dict] = []
    for row, line in enumerate(lines):
        top = row * line_h
        for token in line.split(" "):
            offset = line.find(token)  # позиция первого вхождения
            if not token:
                continue
            x0 = offset * char_w
            words.append({
                "text": token,
                "x0": round(x0, 1),
                "x1": round(x0 + len(token) * char_w, 1),
                "top": round(top, 1),
                "bottom": round(top + line_h * 0.8, 1),
                "size": 10.0,
                "conf": 90,  # ниже 100: пометка, что текст из OCR
            })
            line = line.replace(token, " " * len(token), 1)  # следующее вхождение
    return words
