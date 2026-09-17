import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from setback_check import STATUTE_EFFECTIVE_DATE, check_setback, to_judgment_row

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
