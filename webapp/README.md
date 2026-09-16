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

## 현재 단계: 리스크 테스트 (스파이크)
UI를 만들기 전에 **eum.go.kr이 Vercel 서버(보통 해외 리전)에서 접근 가능한지부터 확인 중**이다. 이 프로젝트를 개발한 환경(Claude 서버)에서는 eum.go.kr이 계속 빈 응답을 주고 있어서, Vercel에서도 같은 문제가 있는지 먼저 확인해야 전체 UI 작업이 의미가 있다.

- 테스트 엔드포인트: `api/test_eum.py` → 배포 후 `<배포주소>/api/test_eum` 접속
- `reachable: true`가 나오면 본 UI(주소 입력 폼 + 판정표) 작업 진행
- `reachable: false`이거나 타임아웃/에러면 다른 방안 검토 필요 (예: 사용자 로컬에서 조회 후 결과만 업로드하는 방식 등)

## 폴더 구성
- `api/test_eum.py`: 리스크 테스트용 임시 엔드포인트 (본 UI 완성 후 제거 예정)
- `public/index.html`: 임시 플레이스홀더 페이지
- `public/guestbook.html`: 방명록 페이지 (강사 요구사항). Supabase 연동 — `SUPABASE_URL`/`SUPABASE_KEY`를 채워야 동작한다. 비워두면 "연결 안 됨" 안내만 표시되고 앱은 정상 동작함
- `requirements.txt`: 서버리스 함수용 파이썬 패키지 (requests)
- `vercel.json`: 함수 실행시간 등 Vercel 설정
