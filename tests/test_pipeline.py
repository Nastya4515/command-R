"""Тесты разбора ответов модели, защиты от выдумок, склейки строк и повторов."""
from pipeline.assemble import _link_duplicates
from pipeline.fragments import _stitch_lines
from pipeline.model_client import parse_response


def test_parse_response_skips_bad_lines():
    output = "Ours | EM | | | 43.6\nBad | Row\nNaive | F1 | | | 49.5"
    rows = parse_response(output, "table")
    assert rows == [["Ours", "EM", "", "", "43.6"], ["Naive", "F1", "", "", "49.5"]]


def test_parse_response_no_answer():
    assert parse_response("нет", "table") == []
    assert parse_response("", "text") == []


def test_parse_response_text_task_needs_3_fields():
    rows = parse_response("EM | 43.6 | primary\nEM | 43.6", "text")
    assert rows == [["EM", "43.6", "primary"]]


def test_hallucination_guard():
    from pipeline.assemble import _value_in_fragment

    assert _value_in_fragment("Ours 43.6 55.4", "43.6")
    assert not _value_in_fragment("Ours 43.6 55.4", "99.9")


def test_stitch_lines_by_vertical_position():
    lines = [
        {"line_id": 0, "text": "Ours 43.6", "top": 100.0, "word_idx": [0, 1]},
        {"line_id": 1, "text": "55.4 61.2", "top": 100.2, "word_idx": [5, 6]},
        {"line_id": 2, "text": "Other text", "top": 150.0, "word_idx": [2, 3]},
    ]
    stitched = _stitch_lines(lines, 3.5)
    assert len(stitched) == 2
    assert stitched[0]["text"] == "Ours 43.6 55.4 61.2"
    assert stitched[0]["line_ids"] == [0, 1]


def test_duplicate_linking():
    records = [
        {"source_table": "Table 1", "metric_name": "EM", "metric_value": "43.6"},
        {"source_table": "", "metric_name": "EM", "metric_value": "43.6"},
        {"source_table": "", "metric_name": "EM", "metric_value": "50.0"},
    ]
    _link_duplicates(records)
    assert records[1]["duplicate_of"] == 0
    assert records[2]["duplicate_of"] == ""


def test_quote_found_in_page_text():
    from pipeline.assemble import _quote_in_page

    page_texts = ["Some text Ours 43.6 more text", ""]
    assert _quote_in_page("Ours 43.6", page_texts)
    assert not _quote_in_page("Ours 99.9", page_texts)
