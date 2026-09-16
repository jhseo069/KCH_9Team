from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from judge import judge


def _rule_table(rows):
    columns = ["rule_id", "category", "project_types", "match_keywords",
               "law_name", "law_article", "law_excerpt", "condition_type",
               "threshold_field", "threshold_op", "threshold_value",
               "threshold_unit", "source_url"]
    return pd.DataFrame(rows, columns=columns).fillna("")


def _matched(raw_text, rule_id):
    return {"raw_text": raw_text, "matched_rule_id": rule_id, "confidence": "high", "unmatched_reason": None}


def _unmatched(raw_text, reason="규칙표에 없는 신규 표기 - 사람 검토 필요"):
    return {"raw_text": raw_text, "matched_rule_id": None, "confidence": None, "unmatched_reason": reason}


def test_always_violation_rule_returns_violation_status():
    rule_table = _rule_table([{
        "rule_id": "R001", "condition_type": "always_violation",
        "law_excerpt": "완충녹지에서는 지정 목적에 위배되는 건축물을 설치할 수 없다",
        "source_url": "https://www.law.go.kr/R001",
    }])
    matching_result = [_matched("완충녹지(저촉)", "R001")]

    result = judge(matching_result, rule_table, observed_values={})

    assert result[0]["status"] == "저촉"
    assert result[0]["law_excerpt"] == "완충녹지에서는 지정 목적에 위배되는 건축물을 설치할 수 없다"
    assert result[0]["source_url"] == "https://www.law.go.kr/R001"


def test_always_ok_rule_returns_ok_status():
    rule_table = _rule_table([{"rule_id": "R004", "condition_type": "always_ok"}])
    matching_result = [_matched("계획관리지역", "R004")]

    result = judge(matching_result, rule_table, observed_values={})

    assert result[0]["status"] == "비저촉"


def test_conditional_rule_returns_conditional_status():
    rule_table = _rule_table([{"rule_id": "R003", "condition_type": "conditional"}])
    matching_result = [_matched("지구단위계획구역", "R003")]

    result = judge(matching_result, rule_table, observed_values={})

    assert result[0]["status"] == "조건부"


def test_unmatched_item_is_always_no_judgement_never_ok():
    """DoD-6 안전장치: 미매칭 항목은 절대 비저촉으로 자동 처리되지 않는다."""
    rule_table = _rule_table([])
    matching_result = [_unmatched("테스트미등록규제구역")]

    result = judge(matching_result, rule_table, observed_values={})

    assert result[0]["status"] == "판정불가"
    assert result[0]["status"] != "비저촉"


def test_threshold_under_limit_is_ok():
    rule_table = _rule_table([{
        "rule_id": "R005", "condition_type": "threshold",
        "threshold_field": "capacity_kw", "threshold_op": "<=", "threshold_value": "1000",
    }])
    matching_result = [_matched("이격거리제한구역", "R005")]

    result = judge(matching_result, rule_table, observed_values={"capacity_kw": 990})

    assert result[0]["status"] == "비저촉"


def test_threshold_over_limit_is_violation():
    rule_table = _rule_table([{
        "rule_id": "R005", "condition_type": "threshold",
        "threshold_field": "capacity_kw", "threshold_op": "<=", "threshold_value": "1000",
    }])
    matching_result = [_matched("이격거리제한구역", "R005")]

    result = judge(matching_result, rule_table, observed_values={"capacity_kw": 1200})

    assert result[0]["status"] == "저촉"


def test_threshold_missing_observed_value_is_no_judgement():
    rule_table = _rule_table([{
        "rule_id": "R005", "condition_type": "threshold",
        "threshold_field": "capacity_kw", "threshold_op": "<=", "threshold_value": "1000",
    }])
    matching_result = [_matched("이격거리제한구역", "R005")]

    result = judge(matching_result, rule_table, observed_values={})

    assert result[0]["status"] == "판정불가"


def test_empty_matching_result_returns_empty_list():
    rule_table = _rule_table([])
    assert judge([], rule_table, observed_values={}) == []
