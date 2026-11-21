"""Тесты нормализации чисел и текста (ТЗ, раздел 11)."""
from pipeline.textnorm import contains_number, normalize_number, normalize_text


def test_leading_zero():
    assert normalize_number(".452") == "0.452"
    assert normalize_number("-.452") == "-0.452"


def test_minus_variants():
    assert normalize_number("−3.2") == "-3.2"  # длинный минус
    assert normalize_number("–3.2") == "-3.2"  # среднее тире


def test_decimal_comma_and_percent():
    assert normalize_number("45,2%") == "45.2"
    assert normalize_number("45,2") == "45.2"


def test_strip_surrounding_signs():
    assert normalize_number("(45.2)") == "45.2"
    assert normalize_number("45.2†") == "45.2"
    assert normalize_number("45.2%") == "45.2"


def test_thousands_separator():
    assert normalize_number("1,234") == "1234"
    assert normalize_number("12,345,678") == "12345678"


def test_trailing_zeros():
    assert normalize_number("0.50") == "0.5"
    assert normalize_number("38.20") == "38.2"


def test_not_a_number():
    assert normalize_number("abc") is None
    assert normalize_number("") is None


def test_contains_number_normalizes():
    assert contains_number("EM reaches .452 on dev", "0.452")
    assert contains_number("F1 = 45,2 %", "45.2")
    assert not contains_number("value 43.6", "43.7")


def test_normalize_text_spaces_and_ligatures():
    assert normalize_text("ﬁrst  line\nsecond") == "first line second"
