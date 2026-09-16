# api

## 폴더 목적/용도
Vercel Python 서버리스 함수. 신재생사업본부 팀원들이 웹에서 주소를 입력하면 실시간으로 부지 판정 파이프라인을 실행하는 API. `src/`의 코드를 그대로 재사용한다(별도 복사본 없음).

## 폴더 생성일
2026-09-16 (`webapp/api/`에서 프로젝트 루트로 이동, 2026-09-16)

## 폴더 내 규칙
- 서버리스 함수는 `http.server.BaseHTTPRequestHandler`를 상속한 `handler` 클래스로 작성한다 (Vercel Python 런타임 규칙)
- **이 Vercel 프로젝트의 Python 런타임은 `api/`에 handler 파일이 2개 이상 있으면 반드시 `pyproject.toml`의 `[tool.vercel] entrypoint`로 그중 하나를 명시해야 한다 — 파일마다 자동 라우팅해주지 않는다(2026-09-16 빌드 로그로 실측 확인).** 그래서 서버리스 함수는 **`site_judge.py` 하나만** 유지한다. 엔드포인트를 늘리려면 `site_judge.py` 안에서 `self.path`로 분기하거나, `pyproject.toml`의 entrypoint를 바꿔가며 다시 검증해야 한다.
- 상위 폴더 `src/`(`query_site_data.py` 등) 파이프라인 코드를 `sys.path`에 추가해서 그대로 재사용한다 — 중복 구현하지 않는다. Vercel의 Root Directory가 이 프로젝트 루트(빈 값)로 설정되어 있어야 `src/`, `data/`가 배포 패키지에 포함된다 — 하위 폴더(예: 예전의 `webapp/`)로 Root Directory를 좁히면 그 상위 폴더는 배포에서 통째로 빠진다(2026-09-16 실측으로 확인한 문제, 그래서 `webapp/`을 없애고 이 위치로 옮김).
- API 키 등은 Vercel 대시보드의 환경변수로만 설정한다. 절대 코드/git에 커밋하지 않는다

## 폴더 내 파일
- `site_judge.py`: `GET /api/site_judge?address=...&project_type=...&capacity_kw=...` → `src/`의 5단계 파이프라인(브이월드 지오코딩 → eum.go.kr 시도 → 실패 시 GIS 자동 대체, 현재 전남만 가능 → 규칙 매칭 → 판정)을 실행해 4열 판정표(항목/판정/근거조문/출처) JSON 반환. 모듈 최상단 import가 실패하면(경로 문제 등) 원인을 그대로 응답으로 돌려주는 진단 로직이 들어있다.
