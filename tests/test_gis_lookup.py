import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gis_lookup import find_zone_by_coordinate

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample_zoning.geojson"


def test_point_inside_single_polygon_returns_ok():
    result = find_zone_by_coordinate(0.5, 0.5, geojson_path=FIXTURE)

    assert result["status"] == "ok"
    assert result["zone_name"] == "제1종일반주거지역"
    assert result["zone_code"] == "UQA121"
    assert result["sgg_nm"] == "목포시"


def test_point_inside_single_polygon_returns_geometry_for_map_display():
    result = find_zone_by_coordinate(0.5, 0.5, geojson_path=FIXTURE)

    assert result["geometry"]["type"] == "Polygon"
    assert result["geometry"]["coordinates"] == [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]


def test_point_outside_all_polygons_returns_no_match():
    result = find_zone_by_coordinate(50.0, 50.0, geojson_path=FIXTURE)

    assert result["status"] == "no_match"


def test_point_inside_two_overlapping_polygons_returns_ambiguous():
    result = find_zone_by_coordinate(10.5, 10.5, geojson_path=FIXTURE)

    assert result["status"] == "ambiguous"
    assert len(result["candidates"]) == 2
    zone_names = {c["zone_name"] for c in result["candidates"]}
    assert zone_names == {"계획관리지역", "자연녹지지역"}
