"""
법령 개정 감시: rule_table.csv의 각 규칙이 참조하는 법령 조문을 law_lookup으로 다시 조회해
저장된 law_excerpt와 비교하고, 최초확인(new)/개정감지(changed)/변동없음(unchanged)/조회실패
(lookup_failed)로 분류한다.

rule_table.csv는 이 스크립트가 절대 직접 수정하지 않는다 - 결과는 law_update_alerts.json으로만
남기고, 반영 여부는 사람이 확인 후 결정한다.
"""
import json
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent

_PLACEHOLDER_VALUES = {"", "(확인 필요)"}


def classify_update(stored_excerpt: str, fetched_text: str) -> str:
    stored = (stored_excerpt or "").strip()
    fetched = (fetched_text or "").strip()

    if stored in _PLACEHOLDER_VALUES:
        return "new"
    if stored != fetched:
        return "changed"
    return "unchanged"


def check_updates(rule_table: pd.DataFrame, lookup_fn) -> list[dict]:
    """rule_table의 각 행에 대해 lookup_fn(law_name, law_article)을 호출해 최신 조문과 대조한다.
    lookup_fn은 law_lookup.lookup_article_text와 같은 시그니처의 함수를 주입받는다(테스트 용이성)."""
    alerts = []
    for _, row in rule_table.iterrows():
        law_name = row.get("law_name", "")
        law_article = row.get("law_article", "")
        if not law_name or not law_article:
            continue

        result = lookup_fn(law_name, law_article)

        if result["status"] != "ok":
            alerts.append({
                "rule_id": row["rule_id"],
                "law_name": law_name,
                "law_article": law_article,
                "status": "lookup_failed",
                "reason": result.get("reason"),
            })
            continue

        alerts.append({
            "rule_id": row["rule_id"],
            "law_name": law_name,
            "law_article": law_article,
            "status": classify_update(row.get("law_excerpt", ""), result["text"]),
            "stored_text": row.get("law_excerpt"),
            "fetched_text": result["text"],
            "effective_date": result.get("effective_date"),
            "source_url": result.get("source_url"),
        })

    return alerts


if __name__ == "__main__":
    from law_lookup import lookup_article_text

    rule_table_path = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR / "data" / "rule_table.csv"
    rule_table = pd.read_csv(rule_table_path, dtype=str).fillna("")

    alerts = check_updates(rule_table, lookup_article_text)

    out_path = BASE_DIR / "data" / "law_update_alerts.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)

    counts = {}
    for a in alerts:
        counts[a["status"]] = counts.get(a["status"], 0) + 1
    print(f"조회 완료: {counts}")
    print(f"저장 완료: {out_path}")
