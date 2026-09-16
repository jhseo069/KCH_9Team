"""
[스파이크] Vercel의 Root Directory가 webapp/로 설정된 상태에서, 상위 폴더(src/, data/)에
있는 GIS 판정 로직/데이터에 접근할 수 있는지 확인한다.

접근이 안 되면(파일을 못 찾으면) Root Directory를 프로젝트 루트로 바꾸거나
webapp/ 안에 필요한 것만 복사해 넣는 방향으로 전환해야 한다.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "src"))
DATA_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "data"))


def test_paths_and_import():
    result = {
        "src_dir": SRC_DIR,
        "src_dir_exists": os.path.isdir(SRC_DIR),
        "data_dir": DATA_DIR,
        "data_dir_exists": os.path.isdir(DATA_DIR),
    }
    if result["data_dir_exists"]:
        try:
            result["data_dir_listing"] = os.listdir(DATA_DIR)
        except Exception as e:
            result["data_dir_listing_error"] = str(e)

    sys.path.insert(0, SRC_DIR)
    try:
        import gis_lookup  # noqa
        zone = gis_lookup.find_zone_by_coordinate(126.44610514616278, 34.80924646756152)
        result["import_ok"] = True
        result["sample_lookup"] = zone
    except Exception as e:
        result["import_ok"] = False
        result["import_error"] = f"{type(e).__name__}: {e}"
    return result


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        result = test_paths_and_import()
        self.send_response(200)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8"))
