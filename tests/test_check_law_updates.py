from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from check_law_updates import classify_update, check_updates


def _rule_table(rows):
    columns = ["rule_id", "category", "project_types", "match_keywords",
               "law_name", "law_article", "law_excerpt", "condition_type",
               "threshold_field", "threshold_op", "threshold_value",
               "threshold_unit", "source_url"]
    return pd.DataFrame(rows, columns=columns).fillna("")


def test_classify_update_placeholder_is_new():
    assert classify_update("(확인 필요)", "실제 조문 내용") == "new"


def test_classify_update_empty_is_new():
    assert classify_update("", "실제 조문 내용") == "new"


def test_classify_update_identical_text_is_unchanged():
    assert classify_update("완충녹지에서는 안 된다", "완충녹지에서는 안 된다") == "unchanged"


def test_classify_update_different_text_is_changed():
    assert classify_update("완충녹지에서는 안 된다(구법)", "완충녹지에서는 안 된다(신법, 2026개정)") == "changed"


def test_check_updates_builds_ok_alert_using_injected_lookup_fn():
    rule_table = _rule_table([{
        "rule_id": "R001", "law_name": "국토의 계획 및 이용에 관한 법률",
        "law_article": "제76조", "law_excerpt": "(확인 필요)",
    }])

    def fake_lookup(law_name, law_article):
        return {"status": "ok", "text": "완충녹지 관련 실제 조문", "effective_date": "20260701",
                "source_url": "https://www.law.go.kr/x"}

    alerts = check_updates(rule_table, fake_lookup)

    assert len(alerts) == 1
    assert alerts[0]["rule_id"] == "R001"
    assert alerts[0]["status"] == "new"
    assert alerts[0]["fetched_text"] == "완충녹지 관련 실제 조문"


def test_check_updates_marks_lookup_failure():
    rule_table = _rule_table([{
        "rule_id": "R099", "law_name": "존재하지않는법", "law_article": "제1조", "law_excerpt": "",
    }])

    def fake_lookup(law_name, law_article):
        return {"status": "no_data", "reason": "법령을 찾을 수 없음"}

    alerts = check_updates(rule_table, fake_lookup)

    assert alerts[0]["status"] == "lookup_failed"
    assert alerts[0]["reason"] == "법령을 찾을 수 없음"


def test_check_updates_skips_rows_without_law_article():
    rule_table = _rule_table([
        {"rule_id": "R001", "law_name": "", "law_article": "", "law_excerpt": ""},
    ])

    def fake_lookup(law_name, law_article):
        raise AssertionError("법령명/조문이 없는 행은 조회하면 안 된다")

    alerts = check_updates(rule_table, fake_lookup)

    assert alerts == []


def test_check_updates_never_modifies_rule_table_in_place():
    rule_table = _rule_table([{
        "rule_id": "R001", "law_name": "국토의 계획 및 이용에 관한 법률",
        "law_article": "제76조", "law_excerpt": "(확인 필요)",
    }])
    original = rule_table.copy(deep=True)

    check_updates(rule_table, lambda n, a: {"status": "ok", "text": "새 내용",
                                             "effective_date": "20260701", "source_url": "u"})

    pd.testing.assert_frame_equal(rule_table, original)
