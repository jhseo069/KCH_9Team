"""
[스파이크] Vercel 서버리스 환경에서 eum.go.kr에 접근 가능한지 확인하는 테스트 엔드포인트.
UI를 만들기 전에 먼저 이것부터 배포해서 확인한다 - 본 프로젝트를 개발한 환경(Claude 서버)에서는
eum.go.kr이 계속 빈 응답을 줘서, Vercel(보통 해외 리전)에서는 다른지 확인이 필요하다.
"""
from http.server import BaseHTTPRequestHandler
import json

import requests


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        result = {}
        try:
            session = requests.Session()
            init_res = session.get(
                "https://www.eum.go.kr/web/ar/lu/luLandDet.jsp", timeout=10
            )
            search_res = session.post(
                "https://www.eum.go.kr/web/am/mp/mpSearchAddrAjaxXml.jsp",
                data={"sId": "selectAdAddrEnter", "keyword": "서울특별시 중구 세종대로 110"},
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": "https://www.eum.go.kr/web/ar/lu/luLandDet.jsp",
                    "User-Agent": "Mozilla/5.0",
                },
                timeout=10,
            )
            search_res.encoding = "euc-kr"
            result = {
                "init_status": init_res.status_code,
                "search_status": search_res.status_code,
                "search_body_preview": search_res.text[:500],
                "reachable": search_res.text.strip() not in ("", "{}"),
            }
        except Exception as e:
            result = {"error": f"{type(e).__name__}: {e}"}

        self.send_response(200)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8"))
