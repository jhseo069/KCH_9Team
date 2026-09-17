from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from export_output import generate_output_table, export_outputs


def _judgment_result_3items():
    return [
        {"raw_text": "완충녹지(저촉)", "rule_id": "R001", "law_excerpt": "완충녹지 조문", "source_url": "https://law.go.kr/R001", "status": "저촉"},
        {"raw_text": "계획관리지역", "rule_id": "R004", "law_excerpt": "계획관리지역 조문", "source_url": "https://law.go.kr/R004", "status": "비저촉"},
        {"raw_text": "테스트미등록규제구역", "rule_id": None, "law_excerpt": None, "source_url": None, "status": "판정불가", "note": "규칙표에 없는 신규 표기 - 사람 검토 필요"},
    ]


def test_generate_output_table_has_correct_columns():
    df = generate_output_table(_judgment_result_3items())

    assert list(df.columns) == ["항목", "판정", "근거조문", "출처", "비고"]


def test_generate_output_table_maps_fields_correctly():
    df = generate_output_table(_judgment_result_3items())

    first_row = df.iloc[0]
    assert first_row["항목"] == "완충녹지(저촉)"
    assert first_row["판정"] == "저촉"
    assert first_row["근거조문"] == "완충녹지 조문"
    assert first_row["출처"] == "https://law.go.kr/R001"


def test_generate_output_table_carries_note_into_bigo_column():
    df = generate_output_table(_judgment_result_3items())

    # 세 번째 항목은 note가 있음 - 비고 열에 그대로 나와야 사람이 판정불가 사유를 알 수 있다.
    third_row = df.iloc[2]
    assert third_row["항목"] == "테스트미등록규제구역"
    assert third_row["비고"] == "규칙표에 없는 신규 표기 - 사람 검토 필요"


def test_generate_output_table_note_missing_yields_empty_bigo():
    # note가 없는 행(첫 번째 항목)은 예외 없이 빈 값(None)이어야 한다.
    df = generate_output_table(_judgment_result_3items())

    first_row = df.iloc[0]
    assert first_row["비고"] is None or pd.isna(first_row["비고"])


def test_export_outputs_creates_csv_and_xlsx_with_matching_row_count(tmp_path):
    judgment_result = _judgment_result_3items()
    df = generate_output_table(judgment_result)

    export_outputs(df, judgment_result, tmp_path)

    csv_path = tmp_path / "final_table.csv"
    xlsx_path = tmp_path / "final_table.xlsx"
    assert csv_path.exists()
    assert xlsx_path.exists()

    csv_df = pd.read_csv(csv_path)
    xlsx_df = pd.read_excel(xlsx_path)
    assert len(csv_df) == 3
    assert len(xlsx_df) == 3
    assert list(csv_df.columns) == ["항목", "판정", "근거조문", "출처", "비고"]


def test_human_review_needed_contains_only_judgeless_and_conditional(tmp_path):
    judgment_result = _judgment_result_3items()
    df = generate_output_table(judgment_result)

    export_outputs(df, judgment_result, tmp_path)

    review_df = pd.read_csv(tmp_path / "human_review_needed.csv")
    assert len(review_df) == 1
    assert review_df.iloc[0]["항목"] == "테스트미등록규제구역"
    assert "저촉" not in review_df["판정"].values
    assert "비저촉" not in review_df["판정"].values


def test_human_review_needed_includes_conditional_status(tmp_path):
    judgment_result = _judgment_result_3items() + [
        {"raw_text": "지구단위계획구역", "rule_id": "R003", "law_excerpt": "지구단위 조문", "source_url": "https://law.go.kr/R003", "status": "조건부"},
    ]
    df = generate_output_table(judgment_result)

    export_outputs(df, judgment_result, tmp_path)

    review_df = pd.read_csv(tmp_path / "human_review_needed.csv")
    assert len(review_df) == 2
    assert set(review_df["판정"]) == {"판정불가", "조건부"}
