"""
[FR-2~FR-5 실제 엔드포인트] 주소를 입력받아 5단계 파이프라인(데이터 조회 -> 규칙 매칭 ->
판정 계산 -> 출력 생성)을 실시간으로 실행하고 5열 판정표(항목/판정/근거조문/출처/비고)를
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
from datetime import date
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.normpath(os.path.join(HERE, ".."))
SRC_DIR = os.path.join(BASE_DIR, "src")
DATA_DIR = os.path.join(BASE_DIR, "data")
RULE_TABLE_PATH = os.path.join(DATA_DIR, "rule_table.csv")

# 모듈 최상단 import가 실패하면(Vercel Root Directory 경계 등으로 src/data를 못 찾는 경우)
# Vercel이 FUNCTION_INVOCATION_FAILED만 보여주고 원인을 알려주지 않으므로,
# 직접 진단 정보를 만들어서 요청이 왔을 때 그대로 돌려준다.
IMPORT_ERROR = None
try:
    sys.path.insert(0, SRC_DIR)
    import pandas as pd  # noqa: E402
    from export_output import generate_output_table  # noqa: E402
    from judge import judge  # noqa: E402
    from law_lookup import lookup_article_text  # noqa: E402
    from match_regulations import match_regulations  # noqa: E402
    from query_site_data import query_site  # noqa: E402
    from setback_check import check_setback, to_judgment_row, unevaluated_judgment_row  # noqa: E402
except Exception as e:
    IMPORT_ERROR = {
        "type": f"{type(e).__name__}: {e}",
        "here": HERE,
        "base_dir": BASE_DIR,
        "src_dir": SRC_DIR,
        "src_dir_exists": os.path.isdir(SRC_DIR),
        "data_dir_exists": os.path.isdir(DATA_DIR),
        "rule_table_exists": os.path.isfile(RULE_TABLE_PATH),
    }


SETBACK_TABLE_PATH = os.path.join(DATA_DIR, "setback_table.csv")


def build_config() -> dict:
    """페이지 로드 시점에 클라이언트가 필요로 하는 공개 설정값.

    브라우저가 Supabase를 직접 호출해 용도지역 레이어를 받아가므로 URL과 공개 키가
    필요하다. publishable 키는 애초에 브라우저 노출용이고 RLS가 읽기만 허용한다.
    SUPABASE_SECRET_KEY(전권 키)는 어떤 경우에도 여기에 넣지 않는다.
    """
    return {
        "vworld_map_key": os.environ.get("VWORLD_API_KEY", ""),
        "supabase_url": os.environ.get("SUPABASE_URL", ""),
        "supabase_key": os.environ.get("SUPABASE_PUBLISHABLE_KEY", ""),
    }


def missing_input_reason(query: dict):
    """판정에 필요한 입력이 없으면 사유를, 있으면 None을 돌려준다.

    지도 클릭은 주소 문자열 없이 좌표만 보낸다. 주소를 필수로 두면 클릭 판정이 막힌다.
    """
    address = (query.get("address") or [""])[0].strip()
    lon = (query.get("lon") or [""])[0].strip()
    lat = (query.get("lat") or [""])[0].strip()
    if address or (lon and lat):
        return None
    return "주소 또는 좌표(lon/lat)가 필요합니다"


def route_for(path: str) -> str:
    """요청 경로(쿼리스트링 포함) -> 처리 이름.

    이 Vercel 프로젝트는 api/ 에 handler 파일을 하나만 둘 수 있어서(pyproject.toml의
    entrypoint로 고정) 엔드포인트를 파일로 늘릴 수 없다. Vercel의 제로 설정 Python
    빌더는 api/site_judge.py를 URL /api/site_judge 하나에만 매핑하므로(하위 경로는
    404) 서브패스가 아니라 쿼리 파라미터(law=1)로 분기한다. 값이 아니라 파라미터
    존재 자체로 판단하므로 address=law 같은 값은 걸리지 않는다.
    """
    return "law" if "law" in parse_qs(urlparse(path).query) else "judge"


def fetch_law(query: dict) -> dict:
    """판정 근거 조문의 원문을 law.go.kr에서 실시간 조회한다.

    규칙표(rule_table.csv)에도 발췌본이 있지만 담아둔 시점의 사본이다. 법령 탭은
    지금 시행 중인 원문을 보여주는 것이 목적이므로 매번 새로 가져온다.
    """
    law_name = (query.get("law_name") or [""])[0].strip()
    law_article = (query.get("law_article") or [""])[0].strip()
    if not law_name or not law_article:
        return {"status": "no_data", "reason": "law_name과 law_article이 필요합니다"}
    try:
        return lookup_article_text(law_name, law_article)
    except Exception as e:
        return {"status": "no_data", "reason": f"조문 조회 실패: {type(e).__name__}: {e}"}


def _judge_setback(eum_result: dict, project_type: str, exemptions: list, apply_date_str: str) -> dict:
    """이격거리 판정 행을 만든다.

    시군구코드를 모르거나(전남 밖 등 GIS 폴백이 안 된 경우) 조례 표 파일이 없어서
    실제로 판정을 실행할 수 없는 경우에도, 행 자체는 항상 돌려준다. 판정표에서 행이
    통째로 빠지면 "검토했는데 문제없음"과 "애초에 검토를 안 함"을 사용자가 구분할
    수 없기 때문이다 - 누락 대신 명시적인 판정불가 행("SETBACK-미검토")을 낸다.
    """
    sgg_cd = eum_result.get("sgg_cd")
    if not sgg_cd:
        return unevaluated_judgment_row(
            "시군구코드를 확인할 수 없어 이격거리 조례를 검토하지 못함 - 해당 주소가 GIS "
            "폴백 조회 가능 지역(현재 전남만 지원) 밖일 수 있음 - 사람 확인 필요"
        )
    if not os.path.isfile(SETBACK_TABLE_PATH):
        return unevaluated_judgment_row("이격거리 조례 표 파일을 찾을 수 없어 검토하지 못함 - 사람 확인 필요")

    try:
        apply_date = date.fromisoformat(apply_date_str) if apply_date_str else date.today()
    except ValueError:
        apply_date = date.today()

    setback_table = pd.read_csv(SETBACK_TABLE_PATH, dtype=str).fillna("")
    result = check_setback(
        sgg_cd=sgg_cd,
        project_type=project_type,
        apply_date=apply_date,
        exemptions=exemptions or [],
        zone_flags=None,   # 보호구역 자동 판별은 아직 없다 -> R6(판정불가)
        setback_table=setback_table,
    )
    return to_judgment_row(result)


def run_pipeline(address: str, project_type: str, capacity_kw: float, vworld_result: dict = None,
                  exemptions: list = None, apply_date_str: str = "") -> dict:
    raw = query_site(address, project_type, capacity_kw, vworld_result=vworld_result)
    eum_result = raw.get("eum") or {}

    response = {
        "input": raw["input"],
        "vworld": raw["vworld"],
        "eum": eum_result,
        "table": [],
        # 지도 위성 타일 표시용(브이월드 WMTS) - 이 키로는 지도 타일만 그리고,
        # CORS로 막혀있는 지오코더 API는 여전히 서버(이 함수)에서만 호출한다.
        "vworld_map_key": os.environ.get("VWORLD_API_KEY", ""),
    }

    if eum_result.get("status") != "ok":
        response["note"] = "용도지역 등 조회 실패 - " + eum_result.get("reason", "사유 불명")
        return response

    rule_table = pd.read_csv(RULE_TABLE_PATH, dtype=str).fillna("")
    matching = match_regulations(eum_result, rule_table)
    judged = judge(matching, rule_table, {"capacity_kw": capacity_kw})

    setback_row = _judge_setback(eum_result, project_type, exemptions, apply_date_str)
    judged.append(setback_row)

    df = generate_output_table(judged)
    response["table"] = df.to_dict(orient="records")
    return response


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)

        if route_for(self.path) == "law":
            if IMPORT_ERROR is not None:
                self._send_json({"status": "no_data", "reason": "서버 모듈 로드 실패"}, status=500)
                return
            self._send_json(fetch_law(query))
            return

        # 지도 타일용 키를 페이지 로드 시점(주소 입력 전)에 미리 받아가기 위한 설정 조회.
        # src/ import 여부와 무관하게 항상 동작해야 하므로 아래 IMPORT_ERROR 체크보다 앞에 둔다.
        if "config" in query:
            self._send_json(build_config())
            return

        address = (query.get("address") or [""])[0].strip()
        project_type = (query.get("project_type") or ["태양광"])[0]
        try:
            capacity_kw = float((query.get("capacity_kw") or ["0"])[0])
        except ValueError:
            capacity_kw = 0.0
        exemptions = [s for s in (query.get("exemptions") or [""])[0].split(",") if s]
        apply_date_str = (query.get("apply_date") or [""])[0].strip()

        if IMPORT_ERROR is not None:
            self._send_json({"error": "import_failed", "detail": IMPORT_ERROR}, status=500)
            return

        reason = missing_input_reason(query)
        if reason:
            self._send_json({"error": reason}, status=400)
            return

        # 브라우저가 브이월드 지오코더를 JSONP로 직접 호출해서 얻은 좌표를 넘겨준 경우
        # (서버 환경에서 지오코더가 막혀있는 문제 우회, HANDOVER.md §5-5) - 있으면 그대로 쓰고
        # 서버에서 다시 지오코딩하지 않는다.
        lon_raw = (query.get("lon") or [""])[0]
        lat_raw = (query.get("lat") or [""])[0]
        vworld_result = None
        if lon_raw and lat_raw:
            try:
                vworld_result = {
                    "status": "ok",
                    "type": "client_jsonp",
                    "lon": float(lon_raw),
                    "lat": float(lat_raw),
                    "refined_addr": (query.get("refined_addr") or [address])[0],
                }
            except ValueError:
                vworld_result = None

        try:
            result = run_pipeline(address, project_type, capacity_kw,
                                   vworld_result=vworld_result,
                                   exemptions=exemptions, apply_date_str=apply_date_str)
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": f"{type(e).__name__}: {e}"}, status=500)

    def _send_json(self, payload: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
