import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gis_lookup import resolve_matches


def zone(name, code="UQA121", generic=False, sgg_cd="12110", sgg_nm="목포시"):
    return {"zone_name": name, "zone_code": code, "is_generic": generic,
            "sgg_cd": sgg_cd, "sgg_nm": sgg_nm, "geometry": {"type": "Polygon", "coordinates": []}}


def test_single_match_returns_ok():
    result = resolve_matches([zone("제1종일반주거지역")])

    assert result["status"] == "ok"
    assert result["zone_name"] == "제1종일반주거지역"
    assert result["sgg_cd"] == "12110"


def test_no_match_never_guesses():
    result = resolve_matches([])

    assert result["status"] == "no_match"


def test_two_specific_matches_are_ambiguous():
    """서로 다른 구체 용도지역이 겹치면 어느 쪽인지 단정할 수 없다 - 사람이 본다."""
    result = resolve_matches([zone("제1종일반주거지역"), zone("자연녹지지역", code="UQA430")])

    assert result["status"] == "ambiguous"
    assert len(result["candidates"]) == 2


def test_generic_polygon_loses_to_specific_one():
    """'도시지역'(광역)은 '제1종일반주거지역'(구체)과 늘 겹친다.

    둘을 동등하게 보면 전남 도시지역 전체가 겹침 -> 판정불가가 되어버린다.
    광역 폴리곤은 구체 폴리곤이 없을 때만 쓴다.
    """
    result = resolve_matches([
        zone("도시지역", code="UQA01X", generic=True),
        zone("제1종일반주거지역"),
    ])

    assert result["status"] == "ok"
    assert result["zone_name"] == "제1종일반주거지역"


def test_generic_polygon_is_used_when_it_is_the_only_information():
    """구체 폴리곤이 없으면 광역 폴리곤이라도 알려준다. 다만 그 사실을 숨기지 않는다."""
    result = resolve_matches([zone("관리지역", code="UQB001", generic=True)])

    assert result["status"] == "ok"
    assert result["zone_name"] == "관리지역"
    assert result["is_generic"] is True


def test_two_generic_matches_are_still_ambiguous():
    result = resolve_matches([
        zone("도시지역", code="UQA01X", generic=True),
        zone("관리지역", code="UQB001", generic=True),
    ])

    assert result["status"] == "ambiguous"


def test_three_specific_matches_report_all_candidates():
    result = resolve_matches([
        zone("제1종일반주거지역"),
        zone("자연녹지지역", code="UQA430"),
        zone("계획관리지역", code="UQB100"),
    ])

    assert result["status"] == "ambiguous"
    assert len(result["candidates"]) == 3
    assert "3개" in result["reason"]


def test_non_urban_zone_resolves_normally():
    """계획관리지역은 태양광 부지에서 가장 흔한 용도지역이다(전남 9,739건)."""
    result = resolve_matches([zone("계획관리지역", code="UQB100", sgg_cd="12750", sgg_nm="보성군")])

    assert result["status"] == "ok"
    assert result["zone_name"] == "계획관리지역"
    assert result["sgg_cd"] == "12750"
