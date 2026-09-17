"""
[2단계 보완] GIS 좌표 기반 용도지역 자동 판별.

eum.go.kr의 개별 주소 실시간 조회(mpSearchAddrAjaxXml.jsp)가 클라우드/서버리스
환경에서 차단되어 있어(HANDOVER.md §4 참고), 대신 eum.go.kr 데이터개방에서 받은
전남 22개 시군구 용도지역 공식 SHP(도시계획 용도지역정보, KLIP_C_UQ111)를
WGS84 GeoJSON으로 미리 변환해두고(data/zoning_jeonnam.geojson), 좌표가 그 안의
어느 폴리곤에 속하는지 계산해서 용도지역을 구한다.

0개(좌표가 어떤 폴리곤에도 안 속함) 또는 2개 이상(오래된 중복 폴리곤 등으로
겹침) 매칭되는 경우, 어떤 값을 임의로 고르지 않고 항상 사람 검토로 넘긴다
(judge.py의 "불확실하면 비저촉으로 단정하지 않는다" 원칙과 동일).
"""
import json
from pathlib import Path

from shapely.geometry import Point, shape

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_GEOJSON_PATH = BASE_DIR / "data" / "zoning_jeonnam.geojson"


def resolve_matches(matches: list) -> dict:
    """좌표에 걸린 폴리곤 목록 -> 최종 판단(ok / no_match / ambiguous).

    matches의 각 항목은 zone_name/zone_code/sgg_cd/sgg_nm/geometry를 가진 dict이며,
    is_generic이 True면 세부 용도가 정해지지 않은 '광역' 폴리곤이다.

    광역 폴리곤('도시지역', '관리지역')은 구체 폴리곤('제1종일반주거지역')과 반드시
    겹친다 - 같은 땅을 크게 한 번, 세밀하게 한 번 그린 것이기 때문이다. 둘을 동등하게
    세면 해당 지역 전체가 '겹침 -> 판정불가'가 되어 아무 답도 못 낸다. 그래서 구체
    폴리곤이 하나라도 있으면 그쪽만 보고, 광역은 달리 알 길이 없을 때만 쓴다.

    다만 구체 폴리곤끼리 겹치는 경우(오래된 중복 고시 등)는 여전히 판정불가다.
    어느 쪽이 맞는지 코드가 고를 근거가 없고, 잘못 고르면 '비저촉'이 틀리게 나온다.
    """
    specific = [m for m in matches if not m.get("is_generic")]
    candidates = specific or matches

    if len(candidates) == 1:
        m = candidates[0]
        return {
            "status": "ok",
            "zone_name": m["zone_name"],
            "zone_code": m["zone_code"],
            "sgg_nm": m["sgg_nm"],
            "sgg_cd": m["sgg_cd"],
            "is_generic": bool(m.get("is_generic")),
            "geometry": m.get("geometry"),
        }
    if not candidates:
        return {"status": "no_match", "reason": "해당 좌표를 포함하는 용도지역 폴리곤이 없음"}
    return {
        "status": "ambiguous",
        "candidates": candidates,
        "reason": f"{len(candidates)}개 폴리곤이 겹침 (오래된 중복 데이터 가능성) - 사람 확인 필요",
    }


def find_zone_by_coordinate(lon: float, lat: float, geojson_path: Path = DEFAULT_GEOJSON_PATH) -> dict:
    """좌표(lon, lat)가 속한 용도지역 폴리곤을 찾는다.

    반환:
    - 정확히 1개 매칭: {"status": "ok", "zone_name": ..., "zone_code": ..., "sgg_nm": ..., "sgg_cd": ...}
    - 0개 매칭: {"status": "no_match", "reason": "..."}
    - 2개 이상 매칭: {"status": "ambiguous", "candidates": [매칭된 properties, ...], "reason": "..."}
    """
    with open(geojson_path, encoding="utf-8") as f:
        fc = json.load(f)

    point = Point(lon, lat)
    matches = []
    for feature in fc["features"]:
        geom = shape(feature["geometry"])
        if geom.intersects(point):
            matches.append(feature)

    return resolve_matches([{**m["properties"], "geometry": m["geometry"]} for m in matches])
