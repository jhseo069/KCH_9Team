# 부지판정자동화

## 폴더 목적/용도
"부지 규제·인허가 저촉 여부 자동 판정표 생성" 과제([과제정의서](../과제정의서/20260908_과제정의서_AX실습_과제정의서_9팀_서장훈%20v1.0.md), [To-Be 설계서](../과제정의서/20260909_설계_To-Be%20시스템%20설계서%20v1.0.md))의 실제 구현 코드를 담는 폴더.

## 폴더 생성일
2026-09-09

## 폴더 내 규칙
- Python 가상환경(`venv`)을 이 폴더 안에서 사용한다. 활성화: `source venv/Scripts/activate` (Git Bash) 또는 `venv\Scripts\Activate.ps1` (PowerShell)
- 새 라이브러리 설치 후에는 `pip freeze > requirements.txt`로 갱신한다
- API 키는 `.env` 파일에 두고 git에 올리지 않는다 (`.gitignore`에 등록됨). 원본은 상위 폴더의 `API 발급키.env`이며, `python -c` 1회성 스크립트로 표준 `KEY=VALUE` 형식(`VWORLD_API_KEY`, `KMA_API_KEY`, `DATA_GO_KR_API_KEY`, `OPENAI_API_KEY`)으로 변환해 두었다
- 그 외 산출물(문서 등)은 상위 [산출물 저장 규칙](../../CLAUDE.md#산출물-저장-규칙)을 따른다: `yyyymmdd_카테고리_파일명 버전(v1.0).확장자`

## 폴더 구성
- `venv/`: Python 가상환경 (커밋 대상 아님)
- `requirements.txt`: 설치된 라이브러리 목록 (requests, beautifulsoup4, lxml, pandas, openpyxl, python-dotenv)
- `.env`: API 키 (커밋 대상 아님)
- `src/query_site_data.py`: **[2단계] 데이터 조회** 스크립트. 브이월드(좌표) + 토지이음(지목·면적·용도지역·규제항목) 조회
- `src/match_regulations.py`: **[3단계] 규칙 매칭** 스크립트. 규제 원문 문구를 `data/rule_table.csv`와 대조
- `src/judge.py`: **[4단계] 판정 계산** 스크립트(규칙엔진, AI 아님). `eval()` 없이 condition_type별 순수 분기로 저촉/비저촉/조건부/판정불가 계산
- `tests/`: pytest 테스트 (TDD로 작성). 실행: `python -m pytest -v`
- `data/raw_query_result.json`: 조회 스크립트 실행 결과 (가공 없이 원문 그대로 저장)
- `data/rule_table.csv`: 규칙표 (법령 개정 시 이 파일만 수정, 코드 수정 불필요)
- `data/matching_result.json`: 규칙 매칭 스크립트 실행 결과
- `data/judgment_result.json`: 판정 계산 스크립트 실행 결과
- `src/export_output.py`: **[5단계] 출력 생성** 스크립트. 5열 판정표(항목/판정/근거조문/출처/비고, CSV/XLSX) + 사람 검토 목록 생성
- `output/`: 최종 판정표(`final_table.csv/.xlsx`), 사람 검토 목록(`human_review_needed.csv`)
- `src/law_lookup.py`: 국가법령정보센터 Open API로 법령 조문 원문 실시간 조회
- `src/gis_lookup.py`: 좌표 → 용도지역 GIS 조회. eum.go.kr 개별 주소 조회가 클라우드에서 막혀있을 때 대체 경로로 쓰인다(HANDOVER.md §5-2). 전남 지역만 지원
- `data/zoning_jeonnam.geojson`: 전남 22개 시군구 용도지역 폴리곤(WGS84) — `scripts/build_zoning_geojson.py`로 생성
- `api/`, `public/`, `vercel.json`, `pyproject.toml`: Vercel 웹앱 배포용(신재생사업본부 팀원 공용). `api/site_judge.py`가 위 파이프라인을 실시간으로 실행하는 API, `public/`이 프론트엔드. 각 폴더 README 참고
- `src/check_law_updates.py`: **[FR-6] 법령 개정 감시** 스크립트. `rule_table.csv`의 조문을 최신 원문과 대조해 new/changed/unchanged/lookup_failed로 분류 → `data/law_update_alerts.json` (rule_table.csv는 자동 수정하지 않음, 사람이 확인 후 반영). `law_lookup.py`는 지자체 조례(자치법규) 조회도 지원한다(FR-7)
- `src/run_summary.py`: **[FR-8] 파이프라인 실행 알림** 스크립트. [2]~[6]단계 결과 중 사람이 확인해야 할 항목(no_data/미매칭/판정불가·조건부/법령 changed·lookup_failed)을 모아 `output/run_alerts.json`으로 저장 + 콘솔 요약
- `PRD.md`: 개발용 상세 명세 (기능요구사항, 데이터 스키마, 완성 기준)
- `HANDOVER.md`: **[FR-9] 인수인계 메모** — 실행 순서, 규칙표 갱신 절차, 장애 대응, 알려진 한계
- `.gitignore`: venv·캐시·.env 제외 설정
- `README.md`: 본 폴더 안내 문서 (현재 파일)

## 사용법
```bash
source venv/Scripts/activate
python src/query_site_data.py "목포시 옥암동 1" "태양광" 990   # [2] 데이터 조회
python src/match_regulations.py                              # [3] 규칙 매칭 (data/raw_query_result.json + data/rule_table.csv 사용)
python src/judge.py                                           # [4] 판정 계산 (data/matching_result.json + data/rule_table.csv 사용)
python src/export_output.py                                   # [5] 출력 생성 (output/final_table.csv, .xlsx, human_review_needed.csv)
python src/check_law_updates.py                                # [FR-6] 법령 개정 감시 (data/law_update_alerts.json)
python src/run_summary.py                                     # [FR-8] 이번 실행 이슈 요약 (output/run_alerts.json)
python -m pytest -v                                           # 테스트 실행 (50개)
```
[2]단계 인자: 주소/지번, 사업종류, 목표설비용량(kW). 결과는 화면 출력과 함께 `data/raw_query_result.json`에 저장된다.

## 알아둘 점 (토지이음 조회 관련)
- 토지이음(eum.go.kr)은 공식 공개 API가 아니라 내부 화면용 AJAX(`mpSearchAddrAjaxXml.jsp`, `luLandDet.jsp`)를 그대로 사용한다. 사이트가 개편되면 `query_site_data.py`의 파싱 로직이 깨질 수 있다.
- 짧은 시간에 요청을 반복하면 토지이음이 빈 응답(`{}`)을 돌려주는 현상을 확인했다(요청 빈도 제한으로 추정). 이 경우 스크립트는 `status: "no_data"`로 표시하고 사유를 남긴다. **주의:** 2026-09-09 개발 중 테스트를 과도하게 반복한 뒤 2026-09-16(1주일 후) 재확인했을 때도 여전히 빈 응답이 지속되는 것을 확인했다 — 단순 "잠시 후 재시도"로 풀리지 않는, 더 긴 기간의 IP 차단이거나 실습용 환경 특성일 가능성이 있다. 실사용 전 반드시 라이브로 재검증 필요(다른 네트워크/기간을 두고 재시도 권장). 어느 쪽이든 부지 여러 건을 연속 조회할 때는 호출 사이에 1~2초 이상 간격을 두는 것을 권장한다.
- 브이월드는 주소 검색(Geocoder) API는 정상 동작하지만, 지적·토지특성정보 API(GetFeature, NED)는 현재 키에 `INCORRECT_KEY`가 발생한다 — 별도 활용신청 승인이 필요하다. 지목·면적은 토지이음 응답에서 함께 얻고 있어 당장은 문제 없다.
- 국가법령정보센터(law.go.kr) Open API는 `OC=test`(비등록 데모 접근)로 정상 동작을 확인했지만, 실사용 시에는 `open.law.go.kr`에서 본인 이메일로 무료 등록한 OC로 `.env`의 `LAW_GO_KR_OC`를 채워 교체할 것을 권장한다.
