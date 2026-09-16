from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from run_summary import summarize_alerts


def test_no_issues_when_everything_ok():
    result = summarize_alerts(
        raw_query_result={"vworld": {"status": "ok"}, "eum": {"status": "ok"}},
        matching_result=[{"raw_text": "완충녹지", "matched_rule_id": "R001"}],
        judgment_result=[{"raw_text": "완충녹지", "status": "저촉"}],
    )

    assert result["total_issues"] == 0
    assert result["issues"] == []


def test_vworld_no_data_is_flagged():
    result = summarize_alerts(
        raw_query_result={"vworld": {"status": "no_data", "reason": "주소 못 찾음"}, "eum": {"status": "ok"}},
        matching_result=[],
        judgment_result=[],
    )

    assert result["total_issues"] == 1
    assert result["issues"][0]["stage"] == "2-vworld"
    assert result["issues"][0]["reason"] == "주소 못 찾음"


def test_eum_no_data_is_flagged():
    result = summarize_alerts(
        raw_query_result={"vworld": {"status": "ok"}, "eum": {"status": "no_data", "reason": "빈 응답"}},
        matching_result=[],
        judgment_result=[],
    )

    assert result["total_issues"] == 1
    assert result["issues"][0]["stage"] == "2-eum"


def test_unmatched_regulation_is_flagged():
    result = summarize_alerts(
        raw_query_result={"vworld": {"status": "ok"}, "eum": {"status": "ok"}},
        matching_result=[{"raw_text": "신규규제", "matched_rule_id": None, "unmatched_reason": "규칙표에 없음"}],
        judgment_result=[],
    )

    assert result["total_issues"] == 1
    assert result["issues"][0]["stage"] == "3-matching"
    assert result["issues"][0]["raw_text"] == "신규규제"


def test_judgeless_and_conditional_status_are_flagged():
    result = summarize_alerts(
        raw_query_result={"vworld": {"status": "ok"}, "eum": {"status": "ok"}},
        matching_result=[],
        judgment_result=[
            {"raw_text": "A", "status": "저촉"},
            {"raw_text": "B", "status": "판정불가"},
            {"raw_text": "C", "status": "조건부"},
        ],
    )

    assert result["total_issues"] == 2
    stages_flagged = [i["raw_text"] for i in result["issues"]]
    assert stages_flagged == ["B", "C"]


def test_law_alerts_changed_and_lookup_failed_are_flagged_but_unchanged_and_new_are_not():
    result = summarize_alerts(
        raw_query_result={"vworld": {"status": "ok"}, "eum": {"status": "ok"}},
        matching_result=[],
        judgment_result=[],
        law_alerts=[
            {"rule_id": "R001", "status": "unchanged"},
            {"rule_id": "R002", "status": "new"},
            {"rule_id": "R003", "status": "changed"},
            {"rule_id": "R004", "status": "lookup_failed"},
        ],
    )

    assert result["total_issues"] == 2
    flagged_ids = [i["rule_id"] for i in result["issues"]]
    assert flagged_ids == ["R003", "R004"]


def test_law_alerts_is_optional():
    result = summarize_alerts(
        raw_query_result={"vworld": {"status": "ok"}, "eum": {"status": "ok"}},
        matching_result=[],
        judgment_result=[],
    )

    assert result["total_issues"] == 0
