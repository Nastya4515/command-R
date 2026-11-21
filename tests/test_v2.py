"""Тесты конвейера v2: нормализация цитат, единицы, направление, дедупликация."""
from __future__ import annotations

import pytest

from pipeline.v2 import normalize, verify
from pipeline.v2.profile import load_profile


@pytest.fixture(scope="module")
def profile():
    return load_profile("rag")


# --- нормализация цитат (как в check_submission.py областей) ----------------

def test_norm_rag_keeps_case_and_glues_hyphens():
    assert verify.norm_rag("Exact\nMatch") == "Exact Match"
    assert verify.norm_rag("retrieval-\naugmented") == "retrievalaugmented"
    assert verify.norm_rag("EM  =  0.452") == "EM = 0.452"
    assert verify.norm_rag("soft­hyphen") == "softhyphen"


def test_norm_solar_aggressive():
    assert verify.norm_solar("PCE = 12.5 %") == "pce12.5%"
    assert verify.norm_solar("Voc − 1.05 V") == "voc1.05v"  # '-' не входит в [a-z0-9.%]


def test_skip_quote_solar():
    solar = {"quote_norm": "solar"}
    rag = {"quote_norm": "rag"}
    assert verify._skip_quote(solar, "Table 3. Results")
    assert verify._skip_quote(solar, "Supplementary Table 1")
    assert not verify._skip_quote(solar, "The PCE reached 12.5%")
    assert not verify._skip_quote(rag, "Table 3. Results")


# --- единицы и пересчёт -----------------------------------------------------

def test_unit_aliases(profile):
    assert normalize.normalize_unit("percent", "45.2", profile) == "%"
    assert normalize.normalize_unit(None, "45.2%", profile) == "%"
    assert normalize.normalize_unit("seconds", "1.2", profile) == "s"


def test_time_conversion(profile):
    assert normalize.convert("1.2", "s", profile) == ("1200", "ms")
    assert normalize.convert("2", "min", profile) == ("120000", "ms")
    # проценты и доли не пересчитываются — шкала источника сохраняется
    assert normalize.convert("0.71", "fraction", profile) == ("0.71", "fraction")
    assert normalize.convert("71", "%", profile) == ("71", "%")


# --- направление метрик ------------------------------------------------------

def test_metric_direction(profile):
    assert normalize.metric_direction("Answer F1", profile) == "higher_is_better"
    assert normalize.metric_direction("NDCG@5", profile) == "higher_is_better"
    assert normalize.metric_direction("latency", profile) == "lower_is_better"
    assert normalize.metric_direction("hallucination rate", profile) == "lower_is_better"
    assert normalize.metric_direction("custom unknown metric", profile) == ""


# --- duplicate_of -------------------------------------------------------------

def test_same_at_reported_precision():
    assert normalize.same_at_reported_precision("0.452", "0.45")
    assert normalize.same_at_reported_precision("71", "71.0")
    assert not normalize.same_at_reported_precision("0.452", "0.46")
    assert not normalize.same_at_reported_precision("abc", "0.45")


def _result(rid_value, **kw):
    base = {"metric_name": "EM", "metric_variant": "", "metric_k": "",
            "metric_unit": "fraction", "metric_value": rid_value,
            "aggregation": "", "sample_size": "", "result_origin": "primary",
            "cited_publication_id": "", "experiment_id": "E1", "config_id": "C1",
            "dataset_id": "DS1", "task_id": "T1", "raw_value": rid_value,
            "raw_unit": "", "source_page": 1, "source_fragment": "x",
            "source_section": "", "source_table": "", "source_figure": "",
            "note": "", "publication_id": "D001", "extraction_status": "extracted"}
    base.update(kw)
    return base


def test_duplicate_of_links_repeats(profile, tmp_path, monkeypatch):
    import pipeline.v2.normalize as nm
    monkeypatch.setattr(nm, "work_dir",
                        lambda cfg, area, set_name, pid: tmp_path)
    verified = {"results": [_result("0.452"), _result("0.45"), _result("0.9")]}
    out = nm.run_article("D001", {}, "rag", "dev", profile, verified)
    res = out["results"]
    assert res[0]["duplicate_of"] == ""
    assert res[1]["duplicate_of"] == res[0]["result_id"]  # 0.45 == 0.452 с округлением
    assert res[2]["duplicate_of"] == ""                   # другое значение — не дубль
