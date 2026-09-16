# webapp

## 폴더 목적/용도
부지판정자동화를 신재생사업본부 팀원들이 웹에서 쓸 수 있도록 만드는 웹앱. 주소를 입력하면 서버에서 [2]~[5]단계 파이프라인을 실시간으로 실행해 판정표를 보여준다. Vercel 배포 대상.

## 폴더 생성일
2026-09-16

## 폴더 내 규칙
- Python 서버리스 함수는 `api/*.py`에, `http.server.BaseHTTPRequestHandler`를 상속한 `handler` 클래스로 작성한다 (Vercel Python 런타임 규칙)
- 정적 프론트엔드 파일은 `public/`에 둔다
- 상위 폴더의 `src/`(query_site_data.py 등) 파이프라인 코드를 그대로 재사용한다 — 중복 구현하지 않는다
- API 키 등은 Vercel 대시보드의 환경변수로만 설정한다. 절대 코드/git에 커밋하지 않는다

## 배포 절차 (사람이 해야 함)
1. [vercel.com](https://vercel.com)에서 본인 GitHub 계정으로 로그인
2. "Add New Project" → 이 저장소(jhseo069/KCH_9Team) import
3. **Root Directory**를 `나만의 AI Agent 개발/부지판정자동화/webapp`으로 설정
4. Environment Variables에 `.env`와 동일한 키 등록 (VWORLD_API_KEY 등)
5. Deploy

## 현재 단계: 실사용 가능 (2026-09-16)
리스크 테스트 결과 eum.go.kr 개별 주소 조회는 Vercel에서 막혀있는 게 확인됐고(§5-1), 이를 GIS 좌표 기반 조회(HANDOVER.md §5-2, 현재 전남 지역만 가능)로 우회하는 `api/site_judge.py`를 실제 엔드포인트로 붙였다. 메인 페이지(`public/index.html`)에서 주소를 입력하면 이 엔드포인트를 실시간으로 호출해 판정표를 보여준다.

**중요**: 이 Vercel Python 런타임은 `api/` 안에 handler 파일이 여러 개 있으면 반드시 `pyproject.toml`의 `[tool.vercel] entrypoint`로 그중 하나를 명시해야 한다(자동으로 파일마다 라우팅해주지 않음, 2026-09-16 실측). 그래서 서버리스 함수는 **`api/site_judge.py` 하나만** 유지한다 — 진단용 임시 파일(`test_eum.py`, `test_import.py`)은 역할이 끝나서 제거했다. 엔드포인트를 더 추가하려면 `site_judge.py` 안에서 `self.path`로 분기하거나, `pyproject.toml`의 entrypoint를 바꿔가며 다시 검증해야 한다.

## 폴더 구성
- `api/site_judge.py`: 실제 판정 API. `GET /api/site_judge?address=...&project_type=...&capacity_kw=...` → `src/`의 5단계 파이프라인(브이월드 지오코딩 → eum.go.kr 시도 → 실패 시 GIS 자동 대체 → 규칙 매칭 → 판정)을 실행해 4열 판정표 JSON 반환
- `public/index.html`: 주소 입력 폼 + 판정표 렌더링
- `public/guestbook.html`: 방명록 페이지 (강사 요구사항). Supabase 연동 — `SUPABASE_URL`/`SUPABASE_KEY`를 채워야 동작한다. 비워두면 "연결 안 됨" 안내만 표시되고 앱은 정상 동작함
- `requirements.txt`: 서버리스 함수용 파이썬 패키지 (`src/`의 파이프라인이 쓰는 것과 동일: requests, shapely, pandas, beautifulsoup4, lxml, python-dotenv)
- `pyproject.toml`: Vercel Python 엔트리포인트 지정(`api.site_judge:handler`) — 위 설명 참고
- `vercel.json`: 함수 실행시간 등 Vercel 설정 (Hobby 무료 플랜 한도인 10초로 맞춰둠)

## 환경변수 (Vercel 대시보드 > Settings > Environment Variables)
- `VWORLD_API_KEY`: 브이월드 지오코더 키. 없으면 좌표 변환부터 실패해 판정표가 안 나온다 — 배포 전 반드시 등록 확인
