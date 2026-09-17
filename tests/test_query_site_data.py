import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import query_site_data
from query_site_data import eum_get_land_detail, eum_resolve_pnu, query_site, resolve_zone_info
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


# ---------------------------------------------------------------------------
# 지도 클릭(빈 주소) -> 토지이음이 PNU 없는 노드를 돌려주는 경우
# (2026-09-17 map-first-ui에서 발견된 크래시: eum_resolve_pnu가 status="ok"와
#  pnu=None을 같이 반환해서 eum_get_land_detail이 pnu[2:5]에서 TypeError로 죽었다)
# ---------------------------------------------------------------------------

class _FakeResponse:
    """requests.Response 흉내 - .encoding 대입, .json() 만 있으면 충분"""

    def __init__(self, json_data):
        self._json_data = json_data
        self.encoding = None
        self.status_code = 200
        self.text = ""

    def json(self):
        return self._json_data


def test_eum_resolve_pnu_returns_no_data_when_nodes_carry_no_pnu():
    """실제 파싱 경로(_parse_node_list)를 거치도록 XML 응답을 그대로 흉내낸다.

    노드는 있지만 <pnu> 엘리먼트가 없는 경우 - eum.go.kr이 빈 키워드(지도 클릭)에
    이런 응답을 준다. status는 절대 "ok"가 되면 안 된다.
    """
    xml_without_pnu = "<root><node><fullStr>부산 어딘가</fullStr></node></root>"

    class FakeSession:
        def post(self, url, data=None, headers=None, timeout=None):
            return _FakeResponse({
                "jibunBonBuList": xml_without_pnu,
                "roadBonBuList": None,
                "bldList": None,
                "jibunList": None,
                "roadList": None,
            })

    result = eum_resolve_pnu("", FakeSession())

    assert result["status"] != "ok"
    assert "PNU" in result["reason"] or "필지고유번호" in result["reason"]


def test_eum_get_land_detail_with_none_pnu_returns_no_data_instead_of_raising():
    result = eum_get_land_detail(None, session=None)

    assert result["status"] == "no_data"
    assert result["reason"]


def test_query_site_map_click_outside_coverage_does_not_raise():
    """query_site 전체 흐름: 지도에서 커버리지 밖을 클릭 -> address="" 로 들어온다.

    이 테스트가 있었다면 리포트된 크래시(TypeError: 'NoneType' object is not
    subscriptable)를 잡아냈을 것이다. 500 대신 사람이 읽을 수 있는 사유가 나와야 한다.
    """
    xml_without_pnu = "<root><node><fullStr>부산 어딘가</fullStr></node></root>"

    class FakeSession:
        def get(self, url, headers=None, timeout=None):
            return _FakeResponse({})

        def post(self, url, data=None, headers=None, timeout=None):
            return _FakeResponse({
                "jibunBonBuList": xml_without_pnu,
                "roadBonBuList": None,
                "bldList": None,
                "jibunList": None,
                "roadList": None,
            })

    def fake_zone_lookup_no_match(lon, lat):
        return {"status": "no_match", "reason": "해당 좌표를 포함하는 용도지역 폴리곤이 없음"}

    orig_session_cls = query_site_data.requests.Session
    orig_find_zone_in_db = query_site_data.find_zone_in_db
    query_site_data.requests.Session = FakeSession
    query_site_data.find_zone_in_db = fake_zone_lookup_no_match
    try:
        result = query_site("", "태양광", 990.0, vworld_result={
            "status": "ok", "type": "client_jsonp",
            "lon": 129.0756, "lat": 35.1796, "refined_addr": "부산",
        })
    finally:
        query_site_data.requests.Session = orig_session_cls
        query_site_data.find_zone_in_db = orig_find_zone_in_db

    assert result["eum"]["status"] != "ok"
    reason = result["eum"]["reason"]
    assert isinstance(reason, str) and len(reason) > 0


# ---------------------------------------------------------------------------
# 지도 클릭(빈 주소) -> eum.go.kr을 아예 건드리지 않아야 함
# (2026-09-18 프로덕션 504: eum.go.kr이 Vercel에서 응답하지 않아 세션 초기화 +
#  PNU 조회가 각각 최대 10초씩 낭비되다 함수 실행시간 한도(10초)를 넘겼다.
#  주소가 없으면 애초에 eum이 조회할 대상이 없으므로 이 경로 자체를 건너뛴다)
# ---------------------------------------------------------------------------

class _ExplodingSession:
    """생성되는 순간 실패 - 주소가 없을 때 세션조차 만들어지면 안 된다"""

    def __init__(self, *args, **kwargs):
        raise AssertionError("주소가 없는데 requests.Session()이 생성되었다")


def _exploding_eum_resolve_pnu(keyword, session):
    raise AssertionError("주소가 없는데 eum_resolve_pnu가 호출되었다")


def test_query_site_empty_address_does_not_touch_eum():
    orig_session_cls = query_site_data.requests.Session
    orig_eum_resolve_pnu = query_site_data.eum_resolve_pnu
    orig_find_zone_in_db = query_site_data.find_zone_in_db
    query_site_data.requests.Session = _ExplodingSession
    query_site_data.eum_resolve_pnu = _exploding_eum_resolve_pnu
    query_site_data.find_zone_in_db = lookup_ok()
    try:
        # 예외 없이 끝나야 한다 - 예외가 나면 eum 경로가 건드려졌다는 뜻
        query_site("", "태양광", 990.0, vworld_result=COORDS)
    finally:
        query_site_data.requests.Session = orig_session_cls
        query_site_data.eum_resolve_pnu = orig_eum_resolve_pnu
        query_site_data.find_zone_in_db = orig_find_zone_in_db


def test_query_site_empty_address_still_resolves_zone_via_coordinates():
    orig_session_cls = query_site_data.requests.Session
    orig_eum_resolve_pnu = query_site_data.eum_resolve_pnu
    orig_find_zone_in_db = query_site_data.find_zone_in_db
    query_site_data.requests.Session = _ExplodingSession
    query_site_data.eum_resolve_pnu = _exploding_eum_resolve_pnu
    query_site_data.find_zone_in_db = lookup_ok("계획관리지역", sgg_cd="46110")
    try:
        result = query_site("", "태양광", 990.0, vworld_result=COORDS)
    finally:
        query_site_data.requests.Session = orig_session_cls
        query_site_data.eum_resolve_pnu = orig_eum_resolve_pnu
        query_site_data.find_zone_in_db = orig_find_zone_in_db

    assert result["eum"]["status"] == "ok"
    assert result["eum"]["source"] == "gis"
    assert result["eum"]["zone_national_law"] == ["계획관리지역"]
    assert result["eum"]["sgg_cd"] == "46110"


def test_query_site_with_address_still_attempts_eum_path():
    """주소가 있으면 지금처럼 eum 경로를 그대로 타야 한다.

    이 테스트가 없으면 "주소 유무와 상관없이 eum을 항상 건너뛴다"로 잘못
    단순화된 수정도 통과해버린다 - eum은 주소가 있을 때는 지목·면적 등
    좌표 조회보다 더 상세한 정보를 주므로 그 경우엔 기다릴 가치가 있다.
    """
    calls = {"get": 0, "post": 0}

    class FakeSession:
        def get(self, url, headers=None, timeout=None):
            calls["get"] += 1
            return _FakeResponse({})

        def post(self, url, data=None, headers=None, timeout=None):
            calls["post"] += 1
            return _FakeResponse({
                "jibunBonBuList": None,
                "roadBonBuList": None,
                "bldList": None,
                "jibunList": None,
                "roadList": None,
            })

    orig_session_cls = query_site_data.requests.Session
    orig_find_zone_in_db = query_site_data.find_zone_in_db
    query_site_data.requests.Session = FakeSession
    # eum이 PNU를 못 찾아 좌표 폴백으로 넘어가면 find_zone_in_db도 requests.Session()을
    # 만드는데(zone_db.py), 위에서 바꿔치기한 FakeSession은 그 용도가 아니므로 막아준다.
    query_site_data.find_zone_in_db = lookup_no_match
    try:
        query_site("목포시 옥암동 1", "태양광", 990.0, vworld_result=COORDS)
    finally:
        query_site_data.requests.Session = orig_session_cls
        query_site_data.find_zone_in_db = orig_find_zone_in_db

    assert calls["get"] == 1, "eum 세션 초기화(session.get)가 호출되지 않았다"
    assert calls["post"] == 1, "eum PNU 조회(session.post)가 호출되지 않았다"
