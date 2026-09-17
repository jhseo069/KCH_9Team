"""[로컬 개발 서버] public/ 정적 파일 + api/site_judge.py 를 그대로 띄운다.

왜 필요한가:
지금까지 화면을 고칠 때마다 "로컬에 dev 서버가 없어 확인 불가"로 남겨야 했다. Vercel
Preview는 Deployment Protection 때문에 로그인 없이는 열리지 않고, 운영에 올려서 확인하는
것은 순서가 거꾸로다. 이 스크립트는 배포본과 같은 핸들러(api/site_judge.py)를 그대로
불러쓰므로, 여기서 되면 배포에서도 된다.

실행:
  python scripts/dev_server.py          # http://localhost:8000
  python scripts/dev_server.py 8080     # 포트 지정

.env의 SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY / VWORLD_API_KEY 를 그대로 쓴다.
"""
import importlib.util
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
sys.path.insert(0, os.path.join(BASE_DIR, "src"))

_spec = importlib.util.spec_from_file_location("site_judge_api", os.path.join(BASE_DIR, "api", "site_judge.py"))
site_judge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(site_judge)


class DevHandler(SimpleHTTPRequestHandler):
    """/api/* 는 배포와 동일한 핸들러로, 나머지는 public/ 정적 파일로 넘긴다."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def do_GET(self):
        if self.path.startswith("/api/"):
            # Vercel은 api/site_judge.py를 /api/site_judge 로 서비스한다. 같은 handler를
            # 그대로 호출하되, 인스턴스를 새로 만들지 않고 메서드만 빌려 쓴다.
            site_judge.handler.do_GET(self)
            return
        super().do_GET()

    def _send_json(self, payload, status=200):
        site_judge.handler._send_json(self, payload, status)

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    if site_judge.IMPORT_ERROR is not None:
        print("경고: api/site_judge.py 의 모듈 로드 실패 -", site_judge.IMPORT_ERROR)
    cfg = site_judge.build_config()
    print(f"public/  -> {PUBLIC_DIR}")
    print(f"설정: vworld={'있음' if cfg['vworld_map_key'] else '없음'} "
          f"supabase={'있음' if cfg['supabase_url'] and cfg['supabase_key'] else '없음'}")
    print(f"\nhttp://localhost:{port}/  (Ctrl+C 로 종료)")
    # 스레드 서버여야 한다. 판정 경로는 eum.go.kr을 최대 10초씩 기다리는데,
    # 단일 스레드면 그 한 건이 정적 파일 요청까지 전부 막아 서버가 멈춘 것처럼 보인다.
    ThreadingHTTPServer(("127.0.0.1", port), DevHandler).serve_forever()


if __name__ == "__main__":
    main()
