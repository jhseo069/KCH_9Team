"""
[3단계] 규칙 매칭 (AI 담당): 토지이음 원문 규제 문구 <-> 규칙표(rule_table.csv) 대조

To-Be 설계서 [3]단계 / PRD FR-3 구현.
AI는 여기서 저촉 여부를 계산하지 않는다 - 오직 raw_text -> rule_id 매핑만 한다.
확신이 없으면(미매칭·모호매칭) 절대 강제로 매칭하지 않고 unmatched_reason을 남긴다.
"""
import json
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent


def _find_matches(raw_text: str, rule_table: pd.DataFrame) -> list[str]:
    """raw_text와 match_keywords(파이프 구분)가 하나라도 부분일치하는 rule_id 목록"""
    matched_ids = []
    for _, row in rule_table.iterrows():
        keywords = [k for k in str(row["match_keywords"]).split("|") if k]
        if any(keyword in raw_text for keyword in keywords):
            matched_ids.append(row["rule_id"])
    return matched_ids


def match_regulations(eum_result: dict, rule_table: pd.DataFrame) -> list[dict]:
    """eum_result의 zone_national_law + zone_other_law 각 문구를
    rule_table.match_keywords와 대조. 확신 없으면 미매칭으로 남긴다."""
    raw_texts = list(eum_result.get("zone_national_law", [])) + \
        list(eum_result.get("zone_other_law", []))

    results = []
    for raw_text in raw_texts:
        matched_ids = _find_matches(raw_text, rule_table)

        if len(matched_ids) == 1:
            results.append({
                "raw_text": raw_text,
                "matched_rule_id": matched_ids[0],
                "confidence": "high",
                "unmatched_reason": None,
            })
        elif len(matched_ids) == 0:
            results.append({
                "raw_text": raw_text,
                "matched_rule_id": None,
                "confidence": None,
                "unmatched_reason": "규칙표에 없는 신규 표기 - 사람 검토 필요",
            })
        else:
            results.append({
                "raw_text": raw_text,
                "matched_rule_id": None,
                "confidence": None,
                "unmatched_reason": f"여러 규칙과 동시 매칭됨({', '.join(matched_ids)}) - 사람 검토 필요",
            })

    return results


if __name__ == "__main__":
    in_path = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR / "data" / "raw_query_result.json"
    rule_table_path = Path(sys.argv[2]) if len(sys.argv) > 2 else BASE_DIR / "data" / "rule_table.csv"

    with open(in_path, encoding="utf-8") as f:
        raw_query_result = json.load(f)

    rule_table = pd.read_csv(rule_table_path, dtype=str).fillna("")
    result = match_regulations(raw_query_result.get("eum", {}), rule_table)

    out_path = BASE_DIR / "data" / "matching_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n저장 완료: {out_path}")
