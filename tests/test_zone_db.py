import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from zone_db import ZoneDbUnavailable, find_zone_in_db


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else []
        self.text = text

    def json(self):
        return self._payload


class FakeSession:
    """호출 내용을 기록하는 가짜 HTTP 세션. 네트워크 없이 계약을 검증한다."""

    def __init__(self, response=None, raises=None):
        self.response = response or FakeResponse()
        self.raises = raises
        self.calls = []

    def post(self, url, json=None, timeout=None, headers=None):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        if self.raises:
            raise self.raises
        return self.response


CONFIG = {"url": "https://example.supabase.co", "key": "test-publishable-key"}


def test_calls_zone_at_rpc_with_coordinates():
    session = FakeSession(FakeResponse(payload=[]))

    find_zone_in_db(126.4, 34.8, session=session, config=CONFIG)

    call = session.calls[0]
    assert call["url"] == "https://example.supabase.co/rest/v1/rpc/zone_at"
    assert call["json"] == {"in_lon": 126.4, "in_lat": 34.8}


def test_single_row_returns_ok():
    session = FakeSession(FakeResponse(payload=[{
        "sgg_cd": "12750", "sgg_nm": "보성군", "zone_code": "UQB100",
        "zone_name": "계획관리지역", "zone_category": "관리지역",
        "is_generic": False, "area_sqm": 1397271.08, "geojson": '{"type":"Polygon","coordinates":[]}',
    }]))

    result = find_zone_in_db(127.0, 34.8, session=session, config=CONFIG)

    assert result["status"] == "ok"
    assert result["zone_name"] == "계획관리지역"
    assert result["sgg_cd"] == "12750"


def test_geojson_string_is_parsed_into_geometry():
    """DB는 geometry를 JSON '문자열'로 준다. 그대로 두면 지도가 그리지 못한다."""
    session = FakeSession(FakeResponse(payload=[{
        "sgg_cd": "12110", "sgg_nm": "목포시", "zone_code": "UQA121",
        "zone_name": "제1종일반주거지역", "zone_category": "주거지역",
        "is_generic": False, "area_sqm": None,
        "geojson": '{"type":"Polygon","coordinates":[[[126.0,34.0],[126.1,34.0],[126.1,34.1],[126.0,34.0]]]}',
    }]))

    result = find_zone_in_db(126.05, 34.05, session=session, config=CONFIG)

    assert result["geometry"]["type"] == "Polygon"
    assert result["geometry"]["coordinates"][0][0] == [126.0, 34.0]


def test_no_rows_is_no_match_not_a_guess():
    session = FakeSession(FakeResponse(payload=[]))

    result = find_zone_in_db(126.0, 34.0, session=session, config=CONFIG)

    assert result["status"] == "no_match"


def test_overlapping_specific_rows_are_ambiguous():
    rows = [
        {"sgg_cd": "12110", "sgg_nm": "목포시", "zone_code": "UQA121",
         "zone_name": "제1종일반주거지역", "zone_category": "주거지역",
         "is_generic": False, "area_sqm": None, "geojson": "{}"},
        {"sgg_cd": "12110", "sgg_nm": "목포시", "zone_code": "UQA430",
         "zone_name": "자연녹지지역", "zone_category": "녹지지역",
         "is_generic": False, "area_sqm": None, "geojson": "{}"},
    ]
    session = FakeSession(FakeResponse(payload=rows))

    result = find_zone_in_db(126.0, 34.0, session=session, config=CONFIG)

    assert result["status"] == "ambiguous"


def test_http_error_raises_instead_of_pretending_no_match():
    """DB가 죽었을 때를 '해당 없음'으로 처리하면 판정이 조용히 틀린다.

    no_match는 '찾아봤는데 없다'는 뜻이고, 장애는 '못 찾아봤다'는 뜻이다.
    둘을 섞으면 사람이 확인해야 할 사안이 정상 결과로 둔갑한다.
    """
    session = FakeSession(FakeResponse(status_code=500, text="boom"))

    with pytest.raises(ZoneDbUnavailable):
        find_zone_in_db(126.0, 34.0, session=session, config=CONFIG)


def test_network_failure_raises_zone_db_unavailable():
    session = FakeSession(raises=OSError("연결 끊김"))

    with pytest.raises(ZoneDbUnavailable):
        find_zone_in_db(126.0, 34.0, session=session, config=CONFIG)


def test_missing_config_raises_zone_db_unavailable():
    with pytest.raises(ZoneDbUnavailable):
        find_zone_in_db(126.0, 34.0, session=FakeSession(), config={"url": "", "key": ""})
