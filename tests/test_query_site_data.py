import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from query_site_data import resolve_zone_info

ZONING_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample_zoning.geojson"

# sample_zoning.geojson 안의 제1종일반주거지역 폴리곤(0,0)-(1,1) 내부의 점
POINT_INSIDE = {"lon": 0.5, "lat": 0.5}
# 어떤 폴리곤에도 속하지 않는 점
POINT_OUTSIDE = {"lon": 50.0, "lat": 50.0}


def test_eum_ok_is_returned_unchanged_without_gis_fallback():
    eum_result = {"status": "ok", "zone_national_law": ["완충녹지(저촉)"]}
    vworld_result = {"status": "ok", "lon": POINT_INSIDE["lon"], "lat": POINT_INSIDE["lat"]}

    result = resolve_zone_info(vworld_result, eum_result, geojson_path=ZONING_FIXTURE)

    assert result is eum_result


def test_eum_failed_falls_back_to_gis_zone_lookup():
    eum_result = {"status": "no_data", "reason": "빈 응답"}
    vworld_result = {"status": "ok", "lon": POINT_INSIDE["lon"], "lat": POINT_INSIDE["lat"]}

    result = resolve_zone_info(vworld_result, eum_result, geojson_path=ZONING_FIXTURE)

    assert result["status"] == "ok"
    assert result["source"] == "gis"
    assert result["zone_national_law"] == ["제1종일반주거지역"]
    assert result["zone_other_law"] == []


def test_eum_failed_falls_back_to_gis_includes_zone_geometry_for_map_display():
    eum_result = {"status": "no_data", "reason": "빈 응답"}
    vworld_result = {"status": "ok", "lon": POINT_INSIDE["lon"], "lat": POINT_INSIDE["lat"]}

    result = resolve_zone_info(vworld_result, eum_result, geojson_path=ZONING_FIXTURE)

    assert result["zone_geometry"]["type"] == "Polygon"


def test_eum_failed_and_gis_no_match_keeps_original_eum_reason():
    eum_result = {"status": "no_data", "reason": "빈 응답"}
    vworld_result = {"status": "ok", "lon": POINT_OUTSIDE["lon"], "lat": POINT_OUTSIDE["lat"]}

    result = resolve_zone_info(vworld_result, eum_result, geojson_path=ZONING_FIXTURE)

    assert result["status"] == "no_data"
    assert "빈 응답" in result["reason"]
    assert "GIS" in result["reason"]


def test_eum_failed_and_no_coordinates_returns_eum_unchanged():
    eum_result = {"status": "no_data", "reason": "빈 응답"}
    vworld_result = {"status": "no_data", "reason": "주소를 찾을 수 없습니다"}

    result = resolve_zone_info(vworld_result, eum_result, geojson_path=ZONING_FIXTURE)

    assert result is eum_result


def test_gis_fallback_passes_sgg_cd_for_setback_check():
    eum_result = {"status": "no_data", "reason": "빈 응답"}
    vworld_result = {"status": "ok", "lon": POINT_INSIDE["lon"], "lat": POINT_INSIDE["lat"]}

    result = resolve_zone_info(vworld_result, eum_result, geojson_path=ZONING_FIXTURE)

    assert result["sgg_cd"] == "12110"
