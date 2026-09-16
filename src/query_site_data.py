"""
[2단계] 데이터 조회: 브이월드(좌표) + 토지이음(지목·면적·용도지역·규제 항목)

To-Be 설계서(../../과제정의서/20260909_설계_To-Be 시스템 설계서 v1.0.md) [2]단계 구현.
조회 결과는 가공 없이 원문 그대로 raw_query_result.json 에 저장한다.
조회 실패/불일치는 예외로 죽이지 않고 status="no_data"로 남겨 다음 단계(사람 검토)로 넘긴다.

토지이음(eum.go.kr)은 공식 공개 API가 아닌 내부 화면용 AJAX를 그대로 사용하므로,
사이트 개편 시 이 파일의 파싱 로직(특히 eum_get_land_detail)이 깨질 수 있다.
"""
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

VWORLD_API_KEY = os.getenv("VWORLD_API_KEY", "")

EUM_BASE = "https://www.eum.go.kr/web"
EUM_DET_URL = f"{EUM_BASE}/ar/lu/luLandDet.jsp"
EUM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": EUM_DET_URL,
    "X-Requested-With": "XMLHttpRequest",
}


def vworld_geocode(address: str) -> dict:
    """브이월드 지오코더 API로 주소 -> 좌표(경위도) 조회. 도로명이 안 되면 지번으로 재시도."""
    url = "https://api.vworld.kr/req/address"
    base_params = {
        "service": "address",
        "request": "getcoord",
        "version": "2.0",
        "crs": "epsg:4326",
        "address": address,
        "format": "json",
        "key": VWORLD_API_KEY,
    }
    for addr_type in ("road", "parcel"):
        try:
            res = requests.get(url, params={**base_params, "type": addr_type}, timeout=10)
            data = res.json()
        except Exception as e:
            return {"status": "no_data", "reason": f"요청 실패: {e}"}

        status = data.get("response", {}).get("status")
        if status == "OK":
            point = data["response"]["result"]["point"]
            return {
                "status": "ok",
                "type": addr_type,
                "lon": float(point["x"]),
                "lat": float(point["y"]),
                "refined_addr": data["response"]["refined"]["text"],
            }

    return {"status": "no_data", "reason": f"주소를 찾을 수 없습니다 ({status})"}


def _parse_node_list(xml_text: str, fields: list) -> list:
    """토지이음 응답의 <root><node><f1>..</f1></node>...</root> XML을 dict 리스트로 변환"""
    if not xml_text or "조회된 내용이 없습니다" in xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    items = []
    for node in root.findall("node"):
        item = {}
        for f in fields:
            el = node.find(f)
            item[f] = el.text if el is not None else None
        items.append(item)
    return items


def eum_resolve_pnu(keyword: str, session: requests.Session) -> dict:
    """자유 텍스트 주소/지번 -> PNU(19자리 필지고유번호) 조회. 결과가 여럿이면 candidates에 모두 담는다."""
    res = session.post(
        f"{EUM_BASE}/am/mp/mpSearchAddrAjaxXml.jsp",
        data={"sId": "selectAdAddrEnter", "keyword": keyword},
        headers=EUM_HEADERS,
        timeout=10,
    )
    res.encoding = "euc-kr"
    try:
        data = res.json()
    except ValueError:
        return {"status": "no_data", "reason": "주소 검색 응답을 해석할 수 없습니다"}

    if not data:
        # 짧은 시간에 요청이 몰리면 토지이음이 빈 응답({})을 돌려주는 경우가 있음(자체 확인)
        return {"status": "no_data", "reason": "빈 응답 (요청 빈도 제한 가능성) - 잠시 후 재시도 필요"}

    sources = [
        ("jibunBonBuList", ["pnu", "fullStr", "bonbun", "bubun"]),
        ("roadBonBuList", ["pnu", "fullStr", "bdbonbun", "bdbubun"]),
        ("bldList", ["pnu", "bldgname", "fullStr"]),
        ("jibunList", ["pnu", "fullStr", "bonbun", "bubun"]),
        ("roadList", ["pnu", "fullStr", "bdbonbun", "bdbubun"]),
    ]
    for key, fields in sources:
        nodes = _parse_node_list(data.get(key), fields)
        if nodes:
            return {"status": "ok", "pnu": nodes[0]["pnu"], "matched_from": key, "candidates": nodes}

    return {"status": "no_data", "reason": "일치하는 주소를 찾을 수 없습니다"}


def eum_get_land_detail(pnu: str, session: requests.Session) -> dict:
    """PNU로 토지이용계획 상세(지목·면적·지역지구 규제 항목) 조회 및 파싱"""
    sgg_cd = pnu[2:5]
    payload = {
        "selGbn": "umd", "isNoScr": "", "s_type": "1", "mode": "search",
        "sggcd": sgg_cd, "pnu": pnu, "ucodes": "", "markUcodes": "",
        "adzoom": "", "scale": "", "scaleFlag": "", "hash": "", "mobile_yn": "",
        "add": "land",
    }
    res = session.post(EUM_DET_URL, data=payload, headers=EUM_HEADERS, timeout=10)
    res.encoding = "euc-kr"
    soup = BeautifulSoup(res.text, "lxml")

    jimok_input = soup.select_one('input[name="jimokCd"]')
    if jimok_input is None:
        return {"status": "no_data", "reason": "상세 정보를 찾을 수 없습니다 (PNU 불일치 또는 조회 실패)"}

    def _top_level_labels(td_id: str) -> list:
        td = soup.select_one(f"#{td_id}")
        if td is None:
            return []
        return [a.get_text(strip=True) for a in td.find_all("a", recursive=False) if a.get_text(strip=True)]

    area_td = soup.select_one("#present_area")
    mark3_td = soup.select_one("#present_mark3")

    return {
        "status": "ok",
        "pnu": pnu,
        "jimok_code": jimok_input.get("value"),
        "area_sqm": area_td.get_text(strip=True) if area_td else None,
        # 「국토의 계획 및 이용에 관한 법률」에 따른 지역·지구등 (원문 그대로, 가공하지 않음)
        "zone_national_law": _top_level_labels("present_mark1"),
        # 다른 법령 등에 따른 지역·지구등
        "zone_other_law": _top_level_labels("present_mark2"),
        # 토지이용규제 기본법 시행령 제9조 제4항 각 호 해당 사항
        "special_notice_raw": mark3_td.get_text(" ", strip=True) if mark3_td else "",
    }


def query_site(address_or_jibun: str, project_type: str, target_capacity_kw: float) -> dict:
    """[1]입력 -> [2]데이터 조회 전체 흐름 실행. raw_query_result 구조를 그대로 반환."""
    result = {
        "input": {
            "address": address_or_jibun,
            "project_type": project_type,
            "target_capacity_kw": target_capacity_kw,
        },
        "vworld": vworld_geocode(address_or_jibun),
        "eum": None,
    }

    session = requests.Session()
    session.get(EUM_DET_URL, headers=EUM_HEADERS, timeout=10)  # 세션(쿠키) 초기화

    pnu_result = eum_resolve_pnu(address_or_jibun, session)
    if pnu_result["status"] != "ok":
        result["eum"] = pnu_result
        return result

    time.sleep(0.3)  # 연속 요청 간 최소 대기
    detail = eum_get_land_detail(pnu_result["pnu"], session)
    detail["candidates"] = pnu_result.get("candidates")
    result["eum"] = detail
    return result


if __name__ == "__main__":
    address = sys.argv[1] if len(sys.argv) > 1 else "목포시 옥암동 1"
    project_type = sys.argv[2] if len(sys.argv) > 2 else "태양광"
    capacity = float(sys.argv[3]) if len(sys.argv) > 3 else 990

    result = query_site(address, project_type, capacity)

    out_dir = BASE_DIR / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "raw_query_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n저장 완료: {out_path}")
