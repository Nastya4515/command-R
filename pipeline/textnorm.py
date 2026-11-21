"""Нормализация текста и чисел — общий модуль для всех шагов конвейера.

Правила чисел (ТЗ, раздел 7):
  .452          -> 0.452      (ведущий ноль)
  −3.2 / –3.2   -> -3.2       (все виды минуса -> ASCII)
  45,2          -> 45.2       (десятичная запятая -> точка)
  45.2% (45.2) 45.2† -> 45.2  (убрать знаки вокруг числа)
"""
from __future__ import annotations

import re
import unicodedata

# Все варианты минуса/тире, встречающиеся в PDF
_MINUS_CHARS = "−–—‒‐‑﹣－"

# Лигатуры, которые pdfplumber/pypdf выдают как один символ
_LIGATURES = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
    "ﬅ": "st", "ﬆ": "st",
}

_NUMBER_RE = re.compile(
    r"[+-]?[−–—‒‐‑]?(?:\d{1,3}(?:[ \u00A0]\d{3})+|\d+)(?:[.,]\d+)?"  # 1 234 | 43.6 | 45,2
    r"|[+-]?\.\d+"  # .452
)


def normalize_minus(s: str) -> str:
    """Все виды минуса и тире -> ASCII '-'."""
    for ch in _MINUS_CHARS:
        s = s.replace(ch, "-")
    return s


def normalize_ligatures(s: str) -> str:
    """Лигатуры -> обычные буквы (fi, fl, ff...)."""
    for lig, plain in _LIGATURES.items():
        s = s.replace(lig, plain)
    return s


def normalize_space(s: str) -> str:
    """Схлопнуть все пробельные последовательности в один пробел."""
    return re.sub(r"\s+", " ", s).strip()


def normalize_text(s: str) -> str:
    """Полная нормализация текста для сравнения цитат."""
    s = unicodedata.normalize("NFC", s)
    s = normalize_ligatures(s)
    s = normalize_minus(s)
    return normalize_space(s)


def normalize_number(raw: str) -> str | None:
    """Число 'как напечатано' -> нормализованная строка. None, если не число.

    Примеры: '.452' -> '0.452', '−3.2' -> '-3.2', '45,2%' -> '45.2',
    '(45.2)' -> '45.2', '45.2†' -> '45.2', '1,234' -> '1234' (тысячи).
    """
    if raw is None:
        return None
    s = normalize_minus(str(raw).strip())
    # убрать знаки вокруг: %, †, ‡, *, стрелки, скобки, ≈, ~, <, >, ≤, ≥
    s = re.sub(r"^[()<>≤≥≈~±↓↑▲▼△▽\s]+|[()%†‡*°↓↑▲▼△▽\s]+$", "", s).strip()
    if not s:
        return None
    # запятая как разделитель тысяч: 1,234 или 12,345,678
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", s):
        s = s.replace(",", "")
    # десятичная запятая: 45,2 (но не 1,234)
    elif re.fullmatch(r"-?\d+,\d+", s):
        s = s.replace(",", ".")
    # убрать пробелы-разделители тысяч: 1 234
    s = re.sub(r"(?<=\d)\s(?=\d{3}\b)", "", s)
    # ведущий ноль: .452 -> 0.452, -.452 -> -0.452
    s = re.sub(r"^(-?)\.(\d)", r"\g<1>0.\2", s)
    # хвостовая точка: '45.' -> '45'
    s = re.sub(r"\.$", "", s)
    if not re.fullmatch(r"-?\d+(\.\d+)?", s):
        return None
    # убрать незначащие нули дробной части: 0.50 -> 0.5
    if "." in s:
        head, tail = s.lstrip("-").split(".")
        tail = tail.rstrip("0") or "0"
        sign = "-" if s.startswith("-") else ""
        s = f"{sign}{head}.{tail}"
    return s


def numbers_equal(raw_a: str, raw_b: str) -> bool:
    """Два сырых представления одного числа после нормализации."""
    na, nb = normalize_number(raw_a), normalize_number(raw_b)
    return na is not None and na == nb


def find_numbers(text: str) -> list[tuple[str, int, int]]:
    """Все числа в тексте: (сырое представление, start, end)."""
    return [(m.group(), m.start(), m.end()) for m in _NUMBER_RE.finditer(text)]


def contains_number(text: str, raw_value: str) -> bool:
    """Есть ли число raw_value в тексте (после нормализации обеих сторон)."""
    target = normalize_number(raw_value)
    if target is None:
        return False
    return any(normalize_number(raw) == target for raw, _, _ in find_numbers(text))
