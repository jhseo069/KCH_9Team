"""
[FR-8] 파이프라인 실행 알림: [2]~[6]단계 실행 결과 중 사람이 확인해야 할 항목을 모아
하나의 요약으로 남긴다.

주의(범위): "지자체 홈페이지에 새 고시가 올라오는지" 자동 감지는 지자체마다 사이트·형식이
제각각이라 이 스크립트의 범위 밖이다. 여기서 하는 일은 "우리 파이프라인이 이미 만든 결과
중 사람이 놓치면 안 되는 것"을 빠짐없이 모아 보여주는 것뿐이다. 실제 이메일/슬랙 발송 등
알림 채널 연동도 범위 밖 - 이 파일은 output/run_alerts.json 파일과 콘솔 요약까지만 만든다.
"""
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

_JUDGMENT_REVIEW_STATUSES = {"판정불가", "조건부"}
_LAW_ALERT_REVIEW_STATUSES = {"changed", "lookup_failed"}


def summarize_alerts(raw_query_result: dict, matching_result: list[dict],
                      judgment_result: list[dict], law_alerts: list[dict] | None = None) -> dict:
    """각 단계 결과를 훑어 사람이 확인해야 할 항목 목록을 만든다. law_alerts는 선택(FR-6 실행 시에만)."""
    issues = []

    vworld = raw_query_result.get("vworld", {})
    if vworld.get("status") == "no_data":
        issues.append({"stage": "2-vworld", "reason": vworld.get("reason")})

    eum = raw_query_result.get("eum", {})
    if eum.get("status") == "no_data":
        issues.append({"stage": "2-eum", "reason": eum.get("reason")})

    for item in matching_result:
        if item.get("matched_rule_id") is None:
            issues.append({
                "stage": "3-matching",
                "raw_text": item.get("raw_text"),
                "reason": item.get("unmatched_reason"),
            })

    for item in judgment_result:
        if item.get("status") in _JUDGMENT_REVIEW_STATUSES:
            issues.append({
                "stage": "4-judgment",
                "raw_text": item.get("raw_text"),
                "status": item.get("status"),
            })

    for alert in (law_alerts or []):
        if alert.get("status") in _LAW_ALERT_REVIEW_STATUSES:
            issues.append({
                "stage": "6-law_update",
                "rule_id": alert.get("rule_id"),
                "status": alert.get("status"),
            })

    return {"total_issues": len(issues), "issues": issues}


if __name__ == "__main__":
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR / "data"

    def _load(name):
        path = data_dir / name
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    raw_query_result = _load("raw_query_result.json") or {}
    matching_result = _load("matching_result.json") or []
    judgment_result = _load("judgment_result.json") or []
    law_alerts = _load("law_update_alerts.json")

    summary = summarize_alerts(raw_query_result, matching_result, judgment_result, law_alerts)

    out_path = BASE_DIR / "output"
    out_path.mkdir(exist_ok=True)
    with open(out_path / "run_alerts.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"이번 실행에서 사람이 확인해야 할 항목: {summary['total_issues']}건")
    for issue in summary["issues"]:
        print(f"  - [{issue['stage']}] {issue}")
    print(f"\n저장 완료: {out_path / 'run_alerts.json'}")
