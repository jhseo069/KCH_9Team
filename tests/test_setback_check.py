import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from setback_check import STATUTE_EFFECTIVE_DATE, check_setback, to_judgment_row, unevaluated_judgment_row

COLUMNS = ["sgg_cd", "sgg_nm", "project_type", "target", "distance_m", "min_house_count",
           "ordinance_name", "article", "law_excerpt", "gosi_date", "source_url",
           "verified_by", "verified_at"]


def _table(rows):
    return pd.DataFrame(rows, columns=COLUMNS).fillna("")


CONFIRMED_MOKPO = {
    "sgg_cd": "12110", "sgg_nm": "목포시", "project_type": "태양광", "target": "주택",
    "distance_m": "100", "min_house_count": "10",
    "ordinance_name": "목포시 도시계획 조례", "article": "제27조",
    "law_excerpt": "주택 10호 이상 밀집지역 경계로부터 100미터",
    "gosi_date": "20220315", "source_url": "https://www.law.go.kr/test",
    "verified_by": "서장훈", "verified_at": "2026-09-17",
}

BEFORE = date(2026, 9, 1)
AFTER = date(2026, 10, 1)


def test_roof_mounted_solar_is_exempt_by_statute():
    result = check_setback("12110", "태양광", AFTER, ["지붕형"], {}, _table([CONFIRMED_MOKPO]))

    assert result["status"] == "비저촉"
    assert result["rule"] == "R1"
    assert "제27조의3" in result["statute"]["article"]


def test_resident_participation_is_exempt_by_statute():
    result = check_setback("12110", "태양광", AFTER, ["주민참여형"], {}, _table([CONFIRMED_MOKPO]))

    assert result["status"] == "비저촉"
    assert result["rule"] == "R1"


def test_unverified_row_is_not_used_for_judgment():
    draft = dict(CONFIRMED_MOKPO, verified_by="")
    result = check_setback("12110", "태양광", AFTER, [], {}, _table([draft]))

    assert result["status"] == "판정불가"
    assert result["rule"] == "R2"


def test_missing_sgg_returns_undecidable():
    result = check_setback("12999", "태양광", AFTER, [], {}, _table([CONFIRMED_MOKPO]))

    assert result["status"] == "판정불가"
    assert result["rule"] == "R2"


def test_confirmed_no_ordinance_rule_is_not_violating():
    none_row = dict(CONFIRMED_MOKPO, distance_m="", min_house_count="",
                    law_excerpt="이격거리 규정 없음")
    result = check_setback("12110", "태양광", AFTER, [], {}, _table([none_row]))

    assert result["status"] == "비저촉"
    assert result["rule"] == "R3"


def test_unparseable_distance_is_undecidable_not_no_restriction():
    bad_row = dict(CONFIRMED_MOKPO, distance_m="약 100")
    result = check_setback("12110", "태양광", AFTER, [], {}, _table([bad_row]))

    assert result["status"] != "비저촉"
    assert result["status"] == "판정불가"
    assert result["rule"] == "R2-b"
    assert "약 100" in result["reason"]


def test_unparseable_min_house_count_is_undecidable_not_no_restriction():
    bad_row = dict(CONFIRMED_MOKPO, min_house_count="다섯")
    result = check_setback("12110", "태양광", AFTER, [], {}, _table([bad_row]))

    assert result["status"] != "비저촉"
    assert result["status"] == "판정불가"
    assert result["rule"] == "R2-b"


def test_application_before_statute_keeps_ordinance():
    result = check_setback("12110", "태양광", BEFORE, [], {}, _table([CONFIRMED_MOKPO]))

    assert result["status"] == "조건부"
    assert result["rule"] == "R4"
    assert result["ordinance"]["distance_m"] == 100
    assert result["apply_date"] == BEFORE.isoformat()


def test_protected_zone_allows_ordinance_after_statute():
    flags = {"역사문화환경보존지역": False, "생태경관보전지역": True}
    result = check_setback("12110", "태양광", AFTER, [], flags, _table([CONFIRMED_MOKPO]))

    assert result["status"] == "조건부"
    assert result["rule"] == "R5-a"


def test_ordinary_zone_after_statute_is_undecidable_due_to_missing_decree():
    flags = {"역사문화환경보존지역": False, "생태경관보전지역": False}
    result = check_setback("12110", "태양광", AFTER, [], flags, _table([CONFIRMED_MOKPO]))

    assert result["status"] == "판정불가"
    assert result["rule"] == "R5-b"
    assert "대통령령" in result["reason"]
    assert result["apply_date"] == AFTER.isoformat()


def test_unknown_zone_flags_are_undecidable():
    result = check_setback("12110", "태양광", AFTER, [], None, _table([CONFIRMED_MOKPO]))

    assert result["status"] == "판정불가"
    assert result["rule"] == "R6"


def test_effective_date_is_the_statute_boundary():
    flags = {"역사문화환경보존지역": False, "생태경관보전지역": False}
    on_the_day = check_setback("12110", "태양광", STATUTE_EFFECTIVE_DATE, [], flags,
                                _table([CONFIRMED_MOKPO]))

    assert on_the_day["rule"] == "R5-b"


def test_judgment_row_matches_existing_table_shape():
    result = check_setback("12110", "태양광", BEFORE, [], {}, _table([CONFIRMED_MOKPO]))
    row = to_judgment_row(result)

    assert row["raw_text"] == "이격거리(조례)"
    assert row["status"] == "조건부"
    assert "목포시 도시계획 조례" in row["law_excerpt"]
    assert row["source_url"] == "https://www.law.go.kr/test"
    assert f"판정 기준일: {BEFORE.isoformat()}" in row["note"]


# ---------------------------------------------------------------------------
# C1. 여러 조례 행(도로/주택 등)이 있을 때 판정이 CSV 행 순서에 의존하면 안 된다.
# ---------------------------------------------------------------------------

YEOSU_ROAD_NO_DISTANCE = {
    "sgg_cd": "12130", "sgg_nm": "여수시", "project_type": "태양광", "target": "도로",
    "distance_m": "", "min_house_count": "",
    "ordinance_name": "여수시 도시계획 조례", "article": "제10조",
    "law_excerpt": "도로 관련 규정 (이격거리 없음)",
    "gosi_date": "20220101", "source_url": "https://www.law.go.kr/test-yeosu-1",
    "verified_by": "서장훈", "verified_at": "2026-09-17",
}

YEOSU_HOUSE_100M = dict(
    YEOSU_ROAD_NO_DISTANCE,
    target="주택", distance_m="100", article="제11조",
    law_excerpt="주택 밀집지역 경계로부터 100미터",
    source_url="https://www.law.go.kr/test-yeosu-2",
)

YEOSU_PUBLIC_50M = dict(
    YEOSU_ROAD_NO_DISTANCE,
    target="공공시설", distance_m="50", article="제12조",
    law_excerpt="공공시설 경계로부터 50미터",
    source_url="https://www.law.go.kr/test-yeosu-3",
)


def test_multiple_rows_with_a_distance_row_ignore_row_order():
    flags = {"역사문화환경보존지역": False, "생태경관보전지역": False}

    forward = check_setback("12130", "태양광", AFTER, [], flags,
                             _table([YEOSU_ROAD_NO_DISTANCE, YEOSU_HOUSE_100M]))
    reversed_ = check_setback("12130", "태양광", AFTER, [], flags,
                               _table([YEOSU_HOUSE_100M, YEOSU_ROAD_NO_DISTANCE]))

    assert forward["status"] == reversed_["status"] == "판정불가"
    assert forward["rule"] == reversed_["rule"] == "R5-b"
    assert forward["ordinance"]["distance_m"] == 100
    assert reversed_["ordinance"]["distance_m"] == 100


def test_multiple_distance_rows_pick_most_restrictive_regardless_of_order():
    """이격거리는 클수록 엄격하다 - 더 멀리 떨어져야 하므로 입지할 수 있는 땅이 줄어든다.

    2026-09-18 이전에는 이 테스트가 50m(작은 쪽)를 '가장 엄격한' 조문으로 고정하고
    있었다. 그 결과 판정표가 주택 100m 규정이 있는 시군에서도 공공시설 50m 조문을
    근거로 인용해, 실제로 넘어야 할 제약을 절반으로 보여주고 있었다.
    """
    flags = {"역사문화환경보존지역": False, "생태경관보전지역": False}

    forward = check_setback("12130", "태양광", AFTER, [], flags,
                             _table([YEOSU_HOUSE_100M, YEOSU_PUBLIC_50M]))
    reversed_ = check_setback("12130", "태양광", AFTER, [], flags,
                               _table([YEOSU_PUBLIC_50M, YEOSU_HOUSE_100M]))

    assert forward["ordinance"]["distance_m"] == 100
    assert reversed_["ordinance"]["distance_m"] == 100
    assert "2건" in forward["reason"]
    assert "2건" in reversed_["reason"]
    assert forward["reason"] == reversed_["reason"]


def test_equal_distance_rows_cite_the_same_article_regardless_of_order():
    """최댓값이 둘 이상이면 어느 조문을 인용할지가 CSV 행 순서에 따라 흔들리면 안 된다.

    같은 입력에 대해 판정표에 적히는 근거 조문이 매번 달라지면 사람이 검토할 수 없다.
    """
    flags = {"역사문화환경보존지역": False, "생태경관보전지역": False}
    public_100 = dict(YEOSU_PUBLIC_50M, distance_m="100")

    forward = check_setback("12130", "태양광", AFTER, [], flags,
                             _table([YEOSU_HOUSE_100M, public_100]))
    reversed_ = check_setback("12130", "태양광", AFTER, [], flags,
                               _table([public_100, YEOSU_HOUSE_100M]))

    assert forward["ordinance"]["article"] == reversed_["ordinance"]["article"]
    assert forward["reason"] == reversed_["reason"]


def test_multiple_rows_all_without_distance_return_no_restriction_regardless_of_order():
    only_road_rows = [
        dict(YEOSU_ROAD_NO_DISTANCE),
        dict(YEOSU_ROAD_NO_DISTANCE, target="공공시설", article="제12조",
             source_url="https://www.law.go.kr/test-yeosu-3"),
    ]

    forward = check_setback("12130", "태양광", AFTER, [], {}, _table(only_road_rows))
    reversed_ = check_setback("12130", "태양광", AFTER, [], {}, _table(list(reversed(only_road_rows))))

    assert forward["status"] == reversed_["status"] == "비저촉"
    assert forward["rule"] == reversed_["rule"] == "R3"


# ---------------------------------------------------------------------------
# I2. project_type 이 빈 문자열이면 필터가 통째로 빠져 엉뚱한 조례가 적용된다.
# ---------------------------------------------------------------------------

def test_blank_project_type_is_undecidable_not_matched_to_everything():
    result = check_setback("12110", "", AFTER, [], {}, _table([CONFIRMED_MOKPO]))

    assert result["status"] == "판정불가"
    assert result["status"] != "비저촉"


# ---------------------------------------------------------------------------
# I3(a). R1(법정 적용 배제)은 시행일 이후에만 근거가 될 수 있다.
# ---------------------------------------------------------------------------

def test_exemption_before_statute_effective_date_falls_to_R4_not_R1():
    result = check_setback("12110", "태양광", BEFORE, ["지붕형"], {}, _table([CONFIRMED_MOKPO]))

    assert result["status"] == "조건부"
    assert result["rule"] == "R4"


# ---------------------------------------------------------------------------
# I3(b). 지붕형/자가소비용 면제는 태양광에만 적용되고, 주민참여형은 사업유형과 무관하다.
# ---------------------------------------------------------------------------

WIND_ROW = dict(
    CONFIRMED_MOKPO,
    project_type="풍력", ordinance_name="목포시 도시계획 조례", article="제28조",
)


def test_roof_mounted_exemption_does_not_apply_to_non_solar():
    flags = {"역사문화환경보존지역": False, "생태경관보전지역": False}
    result = check_setback("12110", "풍력", AFTER, ["지붕형"], flags, _table([WIND_ROW]))

    assert result["rule"] != "R1"
    assert result["status"] != "비저촉"


def test_self_consumption_exemption_does_not_apply_to_non_solar():
    flags = {"역사문화환경보존지역": False, "생태경관보전지역": False}
    result = check_setback("12110", "풍력", AFTER, ["자가소비용"], flags, _table([WIND_ROW]))

    assert result["rule"] != "R1"
    assert result["status"] != "비저촉"


def test_resident_participation_exemption_applies_regardless_of_project_type():
    result = check_setback("12110", "풍력", AFTER, ["주민참여형"], {}, _table([WIND_ROW]))

    assert result["status"] == "비저촉"
    assert result["rule"] == "R1"


# ---------------------------------------------------------------------------
# 부칙(시행일 경계) 안내 문구
# ---------------------------------------------------------------------------

def test_boundary_date_note_present_for_day_before_effective():
    result = check_setback("12110", "태양광", date(2026, 9, 17), [], {}, _table([CONFIRMED_MOKPO]))

    assert "시행일" in result["reason"]


def test_boundary_date_note_present_on_effective_date():
    flags = {"역사문화환경보존지역": False, "생태경관보전지역": False}
    result = check_setback("12110", "태양광", date(2026, 9, 18), [], flags, _table([CONFIRMED_MOKPO]))

    assert "시행일" in result["reason"]


# ---------------------------------------------------------------------------
# 방어적 정규화 및 누락 열 처리 (minor fixes)
# ---------------------------------------------------------------------------

def test_check_setback_normalizes_nan_even_without_caller_fillna():
    import math
    raw_row = dict(CONFIRMED_MOKPO)
    raw_table = pd.DataFrame([raw_row], columns=COLUMNS)
    raw_table.loc[0, "verified_by"] = math.nan  # 사람이 확인하지 않은 원본 CSV를 흉내

    result = check_setback("12110", "태양광", AFTER, [], {}, raw_table)

    assert result["status"] == "판정불가"
    assert result["rule"] == "R2"


def test_missing_ordinance_column_returns_undecidable_instead_of_crashing():
    partial_columns = [c for c in COLUMNS if c != "law_excerpt"]
    row = {k: v for k, v in CONFIRMED_MOKPO.items() if k != "law_excerpt"}
    table = pd.DataFrame([row], columns=partial_columns).fillna("")

    result = check_setback("12110", "태양광", AFTER, [], {}, table)

    assert result["status"] == "판정불가"


def test_to_int_handles_overflow_and_inf_strings_without_crashing():
    from setback_check import _to_int

    assert _to_int("inf") is None
    assert _to_int("1e400") is None


# ---------------------------------------------------------------------------
# I5. CLI/웹앱이 판정을 실행할 수 없을 때도 공유 폴백 행을 낸다.
# ---------------------------------------------------------------------------

def test_unevaluated_judgment_row_shape():
    row = unevaluated_judgment_row("시군구코드를 확인할 수 없어 이격거리 조례를 검토하지 못함 - 사람 확인 필요")

    assert row["raw_text"] == "이격거리(조례)"
    assert row["rule_id"] == "SETBACK-미검토"
    assert row["status"] == "판정불가"
    assert row["law_excerpt"] is None
    assert row["source_url"] is None
    assert "시군구코드" in row["note"]
