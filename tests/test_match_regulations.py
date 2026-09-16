import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from match_regulations import match_regulations


def _rule_table(rows):
    """테스트용 규칙표 DataFrame. 지정 안 한 컬럼은 빈 문자열로 채운다."""
    columns = ["rule_id", "category", "project_types", "match_keywords",
               "law_name", "law_article", "law_excerpt", "condition_type",
               "threshold_field", "threshold_op", "threshold_value",
               "threshold_unit", "source_url"]
    return pd.DataFrame(rows, columns=columns).fillna("")


def test_exact_keyword_match_returns_rule_id():
    rule_table = _rule_table([
        {"rule_id": "R001", "match_keywords": "완충녹지"},
    ])
    eum_result = {"zone_national_law": ["완충녹지(저촉)"], "zone_other_law": []}

    result = match_regulations(eum_result, rule_table)

    assert len(result) == 1
    assert result[0]["raw_text"] == "완충녹지(저촉)"
    assert result[0]["matched_rule_id"] == "R001"
    assert result[0]["confidence"] == "high"
    assert result[0]["unmatched_reason"] is None


def test_no_keyword_match_is_left_unmatched():
    rule_table = _rule_table([
        {"rule_id": "R001", "match_keywords": "완충녹지"},
    ])
    eum_result = {"zone_national_law": ["테스트미등록규제구역"], "zone_other_law": []}

    result = match_regulations(eum_result, rule_table)

    assert len(result) == 1
    assert result[0]["matched_rule_id"] is None
    assert result[0]["confidence"] is None
    assert result[0]["unmatched_reason"] != ""
    assert result[0]["unmatched_reason"] is not None


def test_ambiguous_match_across_multiple_rules_is_left_unmatched():
    rule_table = _rule_table([
        {"rule_id": "R001", "match_keywords": "녹지"},
        {"rule_id": "R002", "match_keywords": "완충녹지"},
    ])
    eum_result = {"zone_national_law": ["완충녹지(저촉)"], "zone_other_law": []}

    result = match_regulations(eum_result, rule_table)

    assert len(result) == 1
    assert result[0]["matched_rule_id"] is None
    assert "여러 규칙" in result[0]["unmatched_reason"]


def test_empty_zone_lists_return_empty_result():
    rule_table = _rule_table([{"rule_id": "R001", "match_keywords": "완충녹지"}])
    eum_result = {"zone_national_law": [], "zone_other_law": []}

    result = match_regulations(eum_result, rule_table)

    assert result == []


def test_pipe_separated_keywords_match_either_alternative():
    rule_table = _rule_table([
        {"rule_id": "R002", "match_keywords": "가축사육제한구역|전부제한"},
    ])
    eum_result = {"zone_national_law": [], "zone_other_law": ["전부제한(2011.6.24)"]}

    result = match_regulations(eum_result, rule_table)

    assert result[0]["matched_rule_id"] == "R002"


def test_both_zone_lists_are_processed():
    rule_table = _rule_table([{"rule_id": "R001", "match_keywords": "완충녹지"}])
    eum_result = {
        "zone_national_law": ["완충녹지(저촉)"],
        "zone_other_law": ["가축사육제한구역<가축분뇨의 관리 및 이용에 관한 법률>"],
    }

    result = match_regulations(eum_result, rule_table)

    assert len(result) == 2
    raw_texts = [r["raw_text"] for r in result]
    assert "완충녹지(저촉)" in raw_texts
    assert "가축사육제한구역<가축분뇨의 관리 및 이용에 관한 법률>" in raw_texts
