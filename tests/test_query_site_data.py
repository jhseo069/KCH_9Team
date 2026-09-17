import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from query_site_data import resolve_zone_info
from zone_db import ZoneDbUnavailable

COORDS = {"status": "ok", "lon": 126.39, "lat": 34.81}
NO_COORDS = {"status": "no_data", "reason": "주소를 찾을 수 없습니다"}


def lookup_ok(zone_name="제1종일반주거지역", sgg_cd="12110"):
    def _lookup(lon, lat):
        return {
            "status": "ok",
            "zone_name": zone_name,
            "zone_code": "UQA121",
            "sgg_nm": "목포시",
            "sgg_cd": sgg_cd,
            "is_generic": False,
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        }
    return _lookup


def lookup_no_match(lon, lat):
    return {"status": "no_match", "reason": "해당 좌표를 포함하는 용도지역 폴리곤이 없음"}


def lookup_unavailable(lon, lat):
    raise ZoneDbUnavailable("용도지역 DB 오류 HTTP 503")


def test_eum_ok_is_returned_unchanged_without_gis_fallback():
    eum_result = {"status": "ok", "zone_national_law": ["완충녹지(저촉)"]}

    result = resolve_zone_info(COORDS, eum_result, zone_lookup=lookup_ok())

    assert result is eum_result


def test_eum_failed_falls_back_to_zone_lookup():
    eum_result = {"status": "no_data", "reason": "빈 응답"}

    result = resolve_zone_info(COORDS, eum_result, zone_lookup=lookup_ok())

    assert result["status"] == "ok"
    assert result["source"] == "gis"
    assert result["zone_national_law"] == ["제1종일반주거지역"]
    assert result["zone_other_law"] == []


def test_fallback_includes_zone_geometry_for_map_display():
    eum_result = {"status": "no_data", "reason": "빈 응답"}

    result = resolve_zone_info(COORDS, eum_result, zone_lookup=lookup_ok())

    assert result["zone_geometry"]["type"] == "Polygon"


def test_fallback_passes_sgg_cd_for_setback_check():
    eum_result = {"status": "no_data", "reason": "빈 응답"}

    result = resolve_zone_info(COORDS, eum_result, zone_lookup=lookup_ok())

    assert result["sgg_cd"] == "12110"


def test_non_urban_zone_resolves_through_fallback():
    """계획관리지역은 태양광 부지에서 가장 흔한 용도지역이다.

    2026-09-17 이전에는 데이터에 비도시지역이 없어 이 경로가 항상 no_match였다.
    """
    eum_result = {"status": "no_data", "reason": "빈 응답"}

    result = resolve_zone_info(COORDS, eum_result,
                               zone_lookup=lookup_ok("계획관리지역", sgg_cd="12750"))

    assert result["zone_national_law"] == ["계획관리지역"]
    assert result["sgg_cd"] == "12750"


def test_no_match_keeps_original_eum_reason():
    eum_result = {"status": "no_data", "reason": "빈 응답"}

    result = resolve_zone_info(COORDS, eum_result, zone_lookup=lookup_no_match)

    assert result["status"] == "no_data"
    assert "빈 응답" in result["reason"]
    assert "GIS" in result["reason"]


def test_no_coordinates_returns_eum_unchanged():
    eum_result = {"status": "no_data", "reason": "빈 응답"}

    result = resolve_zone_info(NO_COORDS, eum_result, zone_lookup=lookup_ok())

    assert result is eum_result


def test_db_outage_is_reported_as_an_outage_not_as_no_match():
    """DB 장애를 '해당 없음'처럼 처리하면 사람이 봐야 할 사안이 정상 결과로 둔갑한다.

    어느 쪽이든 판정은 나오지 않지만, 사유가 다르면 대응이 다르다 -
    '이 땅에는 용도지역이 없다'와 '조회를 못 했으니 다시 해봐야 한다'는 다른 말이다.
    """
    eum_result = {"status": "no_data", "reason": "빈 응답"}

    result = resolve_zone_info(COORDS, eum_result, zone_lookup=lookup_unavailable)

    assert result["status"] == "no_data"
    assert "용도지역 DB" in result["reason"]
    assert "503" in result["reason"]
