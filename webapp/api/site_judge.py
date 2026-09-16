"""
[FR-2~FR-5 실제 엔드포인트] 주소를 입력받아 5단계 파이프라인(데이터 조회 -> 규칙 매칭 ->
판정 계산 -> 출력 생성)을 실시간으로 실행하고 4열 판정표(항목/판정/근거조문/출처)를
JSON으로 반환한다.

eum.go.kr 개별 주소 조회는 이 서버(Vercel) 환경에서 막혀있으므로(HANDOVER.md §4),
query_site_data.resolve_zone_info()가 자동으로 GIS 좌표 기반 조회(현재 전남 지역만
가능, HANDOVER.md §5-2)로 대체한다. 전남 밖 주소는 eum도 GIS도 안 되므로 사람이
직접 확인해야 한다는 안내를 그대로 반환한다 - 이 API가 임의로 "비저촉"을 추측하지
않는다는 원칙(judge.py)은 그대로 유지된다.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.normpath(os.path.join(HERE, "..", ".."))
SRC_DIR = os.path.join(BASE_DIR, "src")
sys.path.insert(0, SRC_DIR)

import pandas as pd  # noqa: E402
from export_output import generate_output_table  # noqa: E402
from judge import judge  # noqa: E402
from match_regulations import match_regulations  # noqa: E402
from query_site_data import query_site  # noqa: E402

RULE_TABLE_PATH = os.path.join(BASE_DIR, "data", "rule_table.csv")


def run_pipeline(address: str, project_type: str, capacity_kw: float) -> dict:
    raw = query_site(address, project_type, capacity_kw)
    eum_result = raw.get("eum") or {}

    response = {
        "input": raw["input"],
        "vworld": raw["vworld"],
        "eum": eum_result,
        "table": [],
    }

    if eum_result.get("status") != "ok":
        response["note"] = "용도지역 등 조회 실패 - " + eum_result.get("reason", "사유 불명")
        return response

    rule_table = pd.read_csv(RULE_TABLE_PATH, dtype=str).fillna("")
    matching = match_regulations(eum_result, rule_table)
    judged = judge(matching, rule_table, {"capacity_kw": capacity_kw})
    df = generate_output_table(judged)
    response["table"] = df.to_dict(orient="records")
    return response


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        address = (query.get("address") or [""])[0].strip()
        project_type = (query.get("project_type") or ["태양광"])[0]
        try:
            capacity_kw = float((query.get("capacity_kw") or ["0"])[0])
        except ValueError:
            capacity_kw = 0.0

        if not address:
            self._send_json({"error": "address 파라미터가 필요합니다"}, status=400)
            return

        try:
            result = run_pipeline(address, project_type, capacity_kw)
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": f"{type(e).__name__}: {e}"}, status=500)

    def _send_json(self, payload: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
