"""Шаг 2. Поиск таблиц и текстовых фрагментов для отправки в модель.

Результат: cache/fragments/<pid>.json — список фрагментов
{"fragment_id", "kind": "table"|"text", "page", "table", "text", "rows", "section"}
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from .textnorm import find_numbers

log = logging.getLogger(__name__)

_CAPTION_RE = re.compile(r"^(Table|TABLE|Tab\.?)\s+([0-9]+|[IVXLC]+)\s*[:.]?", re.IGNORECASE)
_SECTION_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+[A-ZА-Я]")
_ARXIV_RE = re.compile(r"arXiv:\d{4}\.\d{4,5}", re.IGNORECASE)
_REF_RE = re.compile(r"\[\d+(?:[-,]\s*\d+)*\]")
_YEAR_RE = re.compile(r"^(19|20)\d{2}$")


def _is_number_row(text: str) -> bool:
    """Строка похожа на строку таблицы: не меньше двух чисел."""
    return len(find_numbers(text)) >= 2


def _stitch_lines(lines: list[dict], tolerance: float) -> list[dict]:
    """Склейка половин строк, разрезанных межколонным разрезом.

    Куски с одинаковой top (±tolerance) — одна строка, слева направо.
    """
    by_top: list[list[dict]] = []
    for line in sorted(lines, key=lambda l: (l["top"], l["line_id"])):
        for group in by_top:
            if abs(group[0]["top"] - line["top"]) <= tolerance:
                group.append(line)
                break
        else:
            by_top.append([line])
    stitched = []
    for group in by_top:
        group.sort(key=lambda l: min(l.get("word_idx", [0])))
        stitched.append({
            "text": " ".join(l["text"] for l in group),
            "line_ids": [l["line_id"] for l in group],
            "top": group[0]["top"],
        })
    return stitched


def _table_caption(text: str) -> str | None:
    """Подпись таблицы в начале строки, напр. 'Table 3'."""
    m = _CAPTION_RE.match(text.strip())
    return f"Table {m.group(2)}" if m else None


def _find_tables(rows: list[dict], max_rows: int, max_numbers: int) -> list[dict]:
    """Непрерывные блоки числовых строк рядом с подписью Table N."""
    caption_idx = {i: _table_caption(r["text"]) for i, r in enumerate(rows)}
    blocks: list[dict] = []
    i = 0
    while i < len(rows):
        if caption_idx.get(i) is None and not _is_number_row(rows[i]["text"]):
            i += 1
            continue
        start = i
        block_rows = []
        j = i
        while j < len(rows) and (_is_number_row(rows[j]["text"]) or caption_idx.get(j)):
            block_rows.append(rows[j])
            j += 1
        caption = next((caption_idx[k] for k in range(start, j) if caption_idx.get(k)), None)
        if caption or sum(len(find_numbers(r["text"])) for r in block_rows) >= 4:
            blocks.append({"caption": caption, "rows": block_rows})
        i = j
    return [_split_table(b, max_rows, max_numbers) for b in blocks]


def _split_table(block: dict, max_rows: int, max_numbers: int) -> dict:
    """Разметка частей длинной таблицы (не больше max_rows строк / max_numbers чисел)."""
    block["parts"] = []
    current: list[dict] = []
    count = 0
    for row in block["rows"]:
        n = len(find_numbers(row["text"]))
        if current and (len(current) >= max_rows or count + n > max_numbers):
            block["parts"].append(current)
            current, count = [], 0
        current.append(row)
        count += n
    if current:
        block["parts"].append(current)
    return block


def _is_noise_number(raw: str, context: str) -> bool:
    """Числа, которые в модель не отправляем: годы у ссылок, разделы, ссылки."""
    if _YEAR_RE.match(raw) and (_REF_RE.search(context) or "et al" in context):
        return True
    if _REF_RE.search(context) and raw.isdigit() and len(raw) <= 3:
        return True
    return bool(_ARXIV_RE.search(context))


def _text_fragments(page: dict, rows: list[dict], in_table: set[int], window: int) -> list[dict]:
    """Окна ±window слов вокруг чисел в обычном тексте (не таблица)."""
    fragments = []
    for row in rows:
        if row["line_ids"][0] in in_table:
            continue
        text = row["text"]
        if _CAPTION_RE.match(text.strip()) or len(text) < 30:
            continue
        words = text.split()
        for raw, _, _ in find_numbers(text):
            if _is_noise_number(raw, text):
                continue
            # пометить число [[...]] и взять окно по словам
            marked, start_w = _mark_number(words, raw)
            if start_w is None:
                continue
            lo, hi = max(0, start_w - window), min(len(marked), start_w + window + 1)
            fragments.append({
                "text": " ".join(marked[lo:hi]),
                "raw": raw,
                "line_ids": row["line_ids"],
            })
    # дедупликация по помеченному числу и окну
    seen, unique = set(), []
    for f in fragments:
        key = (f["raw"], f["text"])
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


def _mark_number(words: list[str], raw: str) -> tuple[list[str], int | None]:
    """Обернуть первое вхождение числа в [[ ]] внутри списка слов."""
    for i, w in enumerate(words):
        if raw in w and "[[" not in w:
            marked = words[:]
            marked[i] = w.replace(raw, f"[[{raw}]]", 1)
            return marked, i
    return words, None


def _section_of(rows: list[dict], row_top: float) -> str | None:
    """Ближайший заголовок раздела выше строки."""
    section = None
    for r in rows:
        if r["top"] > row_top:
            break
        m = _SECTION_RE.match(r["text"].strip())
        if m:
            section = r["text"].strip()
    return section


def extract_fragments(pages_data: dict, cfg: dict) -> list[dict]:
    """Построить фрагменты для одной статьи (данные шага 1)."""
    pid = pages_data["publication_id"]
    stitch_tol = cfg["lines"]["stitch_tolerance"]
    max_rows = cfg["fragments"]["max_table_rows"]
    max_numbers = cfg["fragments"]["max_table_numbers"]
    window = cfg["fragments"]["text_window_words"]

    fragments: list[dict] = []
    t_counter = 0  # глобальный по статье: id фрагментов должны быть уникальны
    for page in pages_data["pages"]:
        if page["is_scan"]:
            continue
        rows = _stitch_lines(page["lines"], stitch_tol)
        blocks = _find_tables(rows, max_rows, max_numbers)
        in_table: set[int] = set()
        for block in blocks:
            header = [r["text"] for r in block["rows"][:3]]
            for pno, part in enumerate(block["parts"]):
                t_counter += 1
                in_table.update(lid for r in part for lid in r["line_ids"])
                caption = block["caption"] or f"block@{page['page']}"
                text_lines = ([f"{caption}"] if block["caption"] else []) + header + [r["text"] for r in part]
                fragments.append({
                    "fragment_id": f"{pid}_t{t_counter}_p{pno}",
                    "kind": "table",
                    "page": page["page"],
                    "table": block["caption"],
                    "text": "\n".join(text_lines),
                    "rows": [{"row": i, "text": r["text"], "line_ids": r["line_ids"]}
                             for i, r in enumerate(part)],
                    "section": _section_of(page["lines"], part[0]["top"]),
                })
        for x_counter, tf in enumerate(_text_fragments(page, rows, in_table, window)):
            fragments.append({
                "fragment_id": f"{pid}_x{page['page']}_{x_counter}",
                "kind": "text",
                "page": page["page"],
                "table": None,
                "text": tf["text"],
                "raw": tf["raw"],
                "rows": [],
                "line_ids": tf["line_ids"],
                "section": None,
            })
    return fragments


def run(set_name: str, cfg: dict, only: list[str] | None = None) -> list[Path]:
    """Построить фрагменты для всех статей набора."""
    pages_dir = Path(cfg["work"]["cache_dir"]) / "pages"
    out_dir = Path(cfg["work"]["cache_dir"]) / "fragments"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for pages_file in sorted(pages_dir.glob("*.json")):
        pid = pages_file.stem
        if only and pid not in only:
            continue
        out_path = out_dir / f"{pid}.json"
        if out_path.exists():
            written.append(out_path)
            continue
        pages_data = json.loads(pages_file.read_text(encoding="utf-8"))
        fragments = extract_fragments(pages_data, cfg)
        out_path.write_text(json.dumps(fragments, ensure_ascii=False, indent=1), encoding="utf-8")
        n_tables = sum(1 for f in fragments if f["kind"] == "table")
        log.info("%s: %d фрагментов (%d табличных)", pid, len(fragments), n_tables)
        written.append(out_path)
    return written
