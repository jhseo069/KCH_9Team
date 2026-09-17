"""
[5단계] 출력 생성: 판정 결과를 5열 판정표(CSV/XLSX)와 사람 검토 목록으로 내보낸다.

To-Be 설계서 [5]단계 / PRD FR-5 구현.
"""
import json
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent

HUMAN_REVIEW_STATUSES = {"판정불가", "조건부"}


def generate_output_table(judgment_result: list[dict]) -> pd.DataFrame:
    """항목 | 판정 | 근거조문 | 출처 | 비고 5열 DataFrame 반환.

    비고는 item["note"]를 그대로 옮긴다 - 판정불가/조건부인 이유(예: 시군구코드 미확인,
    조례 표 파일 없음, 판정 기준일 등)가 판정 자체(항목/판정)만 봐서는 드러나지 않으면
    사람이 다음 행동을 정할 수 없기 때문이다. note가 없는 행은 빈 값(None)으로 둔다.
    """
    rows = [{
        "항목": item["raw_text"],
        "판정": item["status"],
        "근거조문": item.get("law_excerpt"),
        "출처": item.get("source_url"),
        "비고": item.get("note"),
    } for item in judgment_result]
    return pd.DataFrame(rows, columns=["항목", "판정", "근거조문", "출처", "비고"])


def export_outputs(df: pd.DataFrame, judgment_result: list[dict], out_dir: Path) -> None:
    """final_table.csv/.xlsx 저장 + status가 '판정불가' 또는 '조건부'인 행만
    human_review_needed.csv로 별도 저장"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df.to_csv(out_dir / "final_table.csv", index=False, encoding="utf-8-sig")
    df.to_excel(out_dir / "final_table.xlsx", index=False)

    review_df = df[df["판정"].isin(HUMAN_REVIEW_STATUSES)]
    review_df.to_csv(out_dir / "human_review_needed.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    judgment_path = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR / "data" / "judgment_result.json"
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else BASE_DIR / "output"

    with open(judgment_path, encoding="utf-8") as f:
        judgment_result = json.load(f)

    df = generate_output_table(judgment_result)
    export_outputs(df, judgment_result, out_dir)

    print(df.to_string(index=False))
    print(f"\n저장 완료: {out_dir}/final_table.csv, final_table.xlsx, human_review_needed.csv")
