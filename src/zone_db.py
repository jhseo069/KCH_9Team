"""좌표 -> 용도지역 조회 (Supabase / PostGIS).

왜 파일이 아니라 DB인가:
비도시지역(관리·농림·자연환경보전)까지 포함하면 전남만으로 폴리곤 83,660건,
GeoJSON으로는 약 265MB다. Vercel 배포 한도(250MB)를 넘고, 매 요청마다 통째로 읽어
훑는 기존 방식(gis_lookup.find_zone_by_coordinate)으로는 감당할 수 없다.
공간 인덱스를 가진 DB에 두면 인덱스 조회 한 번으로 끝난다.

겹치는 폴리곤을 DB가 임의로 하나 고르지 않는다. 해당하는 것을 전부 받아서
gis_lookup.resolve_matches()가 판단한다 - 판정 규칙을 한 곳에만 두기 위해서다.
"""
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

from gis_lookup import resolve_matches

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

RPC_TIMEOUT = 8  # Vercel Hobby 플랜 함수 실행시간 한도(10초) 안에 들어와야 한다


class ZoneDbUnavailable(RuntimeError):
    """DB를 조회하지 못했다. '해당 없음'과 명확히 구분하기 위한 별도 예외.

    no_match는 '찾아봤는데 그 좌표에 용도지역이 없다'는 사실이고,
    이 예외는 '아예 확인하지 못했다'는 뜻이다. 후자를 전자로 처리하면
    사람이 봐야 할 사안이 정상 판정으로 둔갑한다.
    """


def load_config():
    return {
        "url": os.getenv("SUPABASE_URL", ""),
        # 브라우저에도 노출되는 읽기 전용 공개 키만 쓴다. 전권 키(SECRET)는 적재
        # 스크립트에서만 쓰고 이 경로에는 절대 들이지 않는다.
        "key": os.getenv("SUPABASE_PUBLISHABLE_KEY", ""),
    }


def find_zone_in_db(lon: float, lat: float, session=None, config=None) -> dict:
    """좌표가 속한 용도지역을 DB에서 찾는다.

    반환은 gis_lookup.find_zone_by_coordinate와 같은 계약
    (ok / no_match / ambiguous). 조회 자체가 실패하면 ZoneDbUnavailable.
    """
    config = config if config is not None else load_config()
    if not config.get("url") or not config.get("key"):
        raise ZoneDbUnavailable(
            "SUPABASE_URL 또는 SUPABASE_PUBLISHABLE_KEY가 설정되지 않아 용도지역 DB를 조회할 수 없습니다"
        )

    session = session or _default_session(config["key"])
    url = f"{config['url'].rstrip('/')}/rest/v1/rpc/zone_at"

    try:
        res = session.post(url, json={"in_lon": lon, "in_lat": lat}, timeout=RPC_TIMEOUT)
    except Exception as e:
        raise ZoneDbUnavailable(f"용도지역 DB 요청 실패: {e}") from e

    if res.status_code >= 400:
        raise ZoneDbUnavailable(f"용도지역 DB 오류 HTTP {res.status_code}: {res.text[:200]}")

    try:
        rows = res.json()
    except Exception as e:
        raise ZoneDbUnavailable(f"용도지역 DB 응답을 해석할 수 없습니다: {e}") from e

    return resolve_matches([_to_match(r) for r in rows])


def _to_match(row: dict) -> dict:
    # PostGIS의 st_asgeojson()은 JSON '문자열'을 준다. 파싱해두지 않으면 지도가 못 그린다.
    geometry = None
    raw = row.get("geojson")
    if raw:
        try:
            geometry = json.loads(raw)
        except (TypeError, ValueError):
            geometry = None

    return {
        "zone_name": row.get("zone_name"),
        "zone_code": row.get("zone_code"),
        "zone_category": row.get("zone_category"),
        "sgg_cd": row.get("sgg_cd"),
        "sgg_nm": row.get("sgg_nm"),
        "is_generic": bool(row.get("is_generic")),
        "area_sqm": row.get("area_sqm"),
        "geometry": geometry,
    }


def _default_session(key: str):
    session = requests.Session()
    session.headers.update({"apikey": key, "Authorization": f"Bearer {key}"})
    return session
