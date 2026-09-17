"""
[4단계] 판정 계산 (규칙엔진, AI 아님): 매칭된 규칙의 조건식을 관측값과 비교해 저촉 여부를 계산한다.

To-Be 설계서 [4]단계 / PRD FR-4 구현.
숫자 비교는 절대 AI(LLM)가 하지 않는다 - 이 파일은 순수 조건 분기만 수행하며 eval()을 쓰지 않는다.
매칭되지 않은 항목은 어떤 경우에도 "비저촉"으로 자동 처리하지 않고 "판정불가"로 남긴다.
"""
import json
import operator
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent

_OPERATORS = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}


def _judge_one(item: dict, rule_table: pd.DataFrame, observed_values: dict) -> dict:
    base = {
        "raw_text": item["raw_text"],
        "rule_id": item.get("matched_rule_id"),
        "law_excerpt": None,
        "source_url": None,
    }

    if item.get("matched_rule_id") is None:
        base["status"] = "판정불가"
        base["note"] = item.get("unmatched_reason")
        return base

    rows = rule_table[rule_table["rule_id"] == item["matched_rule_id"]]
    if rows.empty:
        base["status"] = "판정불가"
        base["note"] = "규칙표에서 규칙ID를 찾을 수 없음"
        return base

    rule = rows.iloc[0]
    base["law_excerpt"] = rule["law_excerpt"] or None
    base["source_url"] = rule["source_url"] or None
    condition_type = rule["condition_type"]

    if condition_type == "always_violation":
        base["status"] = "저촉"
    elif condition_type == "always_ok":
        base["status"] = "비저촉"
    elif condition_type == "conditional":
        base["status"] = "조건부"
    elif condition_type == "threshold":
        field = rule["threshold_field"]
        if field not in observed_values:
            base["status"] = "판정불가"
            base["note"] = f"관측값 '{field}'이(가) 없어 임계값을 평가할 수 없음"
        else:
            op_fn = _OPERATORS[rule["threshold_op"]]
            is_within_limit = op_fn(observed_values[field], float(rule["threshold_value"]))
            base["status"] = "비저촉" if is_within_limit else "저촉"
    else:
        base["status"] = "판정불가"
        base["note"] = f"알 수 없는 condition_type: {condition_type}"

    return base


def judge(matching_result: list[dict], rule_table: pd.DataFrame, observed_values: dict) -> list[dict]:
    """AI가 아닌 순수 조건 평가. eval() 사용 금지 - condition_type별 분기 처리."""
    return [_judge_one(item, rule_table, observed_values) for item in matching_result]


if __name__ == "__main__":
    matching_path = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR / "data" / "matching_result.json"
    rule_table_path = Path(sys.argv[2]) if len(sys.argv) > 2 else BASE_DIR / "data" / "rule_table.csv"
    raw_query_path = Path(sys.argv[3]) if len(sys.argv) > 3 else BASE_DIR / "data" / "raw_query_result.json"

    with open(matching_path, encoding="utf-8") as f:
        matching_result = json.load(f)
    rule_table = pd.read_csv(rule_table_path, dtype=str).fillna("")

    observed_values = {}
    if raw_query_path.exists():
        with open(raw_query_path, encoding="utf-8") as f:
            raw_query_result = json.load(f)
        capacity = raw_query_result.get("input", {}).get("target_capacity_kw")
        if capacity is not None:
            observed_values["capacity_kw"] = capacity

    result = judge(matching_result, rule_table, observed_values)

    # FR-10. 이격거리 규정 판정을 같은 판정표에 한 행으로 덧붙인다.
    setback_path = BASE_DIR / "data" / "setback_table.csv"
    sgg_cd = raw_query_result.get("eum", {}).get("sgg_cd") if raw_query_path.exists() else None
    if setback_path.exists() and sgg_cd:
        from datetime import date
        from setback_check import check_setback, to_judgment_row

        setback_table = pd.read_csv(setback_path, dtype=str).fillna("")
        setback_result = check_setback(
            sgg_cd=sgg_cd,
            project_type=raw_query_result.get("input", {}).get("project_type", ""),
            apply_date=date.today(),
            exemptions=[],       # CLI에서는 면제사유를 입력받지 않는다 (웹앱에서만 지원)
            zone_flags=None,     # 보호구역 판별은 아직 자동화되지 않았다 -> R6(판정불가)
            setback_table=setback_table,
        )
        result.append(to_judgment_row(setback_result))

    out_path = BASE_DIR / "data" / "judgment_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n저장 완료: {out_path}")
