"""
[스파이크] Vercel 서버리스 환경에서 eum.go.kr의 두 가지 다른 경로 중 어느 쪽이 접근 가능한지 확인.

1) 주소검색 AJAX(mpSearchAddrAjaxXml.jsp) - 개별 주소 실시간 조회용, 이전 테스트에서 막힘 확인됨
2) 데이터개방 다운로드 AJAX(svItemAjaxXml.jsp) - 대용량 공식 데이터 다운로드용, Claude 개발환경에서는 정상 동작 확인됨

둘 다 안 되면 "웹에서 실시간 eum.go.kr 조회"는 완전히 불가능하다는 뜻이고,
2번만 되면 "미리 받아둔 공식 데이터로 판정하는 구조"로 전환해야 한다.
"""
from http.server import BaseHTTPRequestHandler
import json

import requests


def test_address_search():
    try:
        session = requests.Session()
        session.get("https://www.eum.go.kr/web/ar/lu/luLandDet.jsp", timeout=10)
        res = session.post(
            "https://www.eum.go.kr/web/am/mp/mpSearchAddrAjaxXml.jsp",
            data={"sId": "selectAdAddrEnter", "keyword": "서울특별시 중구 세종대로 110"},
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.eum.go.kr/web/ar/lu/luLandDet.jsp",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=10,
        )
        res.encoding = "euc-kr"
        return {
            "status_code": res.status_code,
            "body_preview": res.text[:300],
            "reachable": res.text.strip() not in ("", "{}"),
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def test_bulk_data_endpoint():
    try:
        res = requests.post(
            "https://www.eum.go.kr/web/op/sv/svItemAjaxXml.jsp",
            data={"function": "selectFileInfo", "dataCd": "007", "dataTypeCd": "CSV", "refDt": "", "fileId": "654"},
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.eum.go.kr/web/op/sv/svItemDet.jsp",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=10,
        )
        res.encoding = "utf-8"
        return {
            "status_code": res.status_code,
            "body_preview": res.text[:300],
            "reachable": res.text.strip() not in ("", "{}"),
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        result = {
            "1_address_search_ajax": test_address_search(),
            "2_bulk_data_download_ajax": test_bulk_data_endpoint(),
        }

        self.send_response(200)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8"))
