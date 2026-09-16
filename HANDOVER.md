# 인수인계 메모 — 부지판정자동화

> 작성일: 2026-09-16 | 관리 담당: 서장훈 매니저 (신재생사업본부 목포지사)
> 관련 문서: [PRD.md](PRD.md) (상세 기능명세·완성기준), [README.md](README.md) (설치·실행법)

## 1. 이 시스템은 무엇인가

부지 주소를 입력하면 토지 규제·인허가 저촉 여부를 근거 조문과 함께 자동으로 판정표로 만들어주는 도구. 5단계 파이프라인(데이터 조회 → 규칙 매칭 → 판정 계산 → 출력 생성)에 법령 개정 감시(FR-6)와 실행 알림(FR-8)이 붙어 있다.

## 2. 평소 실행 순서

```bash
cd 부지판정자동화
source venv/Scripts/activate

python src/query_site_data.py "부지주소" "사업종류" 용량kW   # [2] 데이터 조회
python src/match_regulations.py                              # [3] 규칙 매칭
python src/judge.py                                           # [4] 판정 계산
python src/export_output.py                                   # [5] 출력 생성 -> output/final_table.csv
python src/run_summary.py                                     # [8] 이번 실행에서 확인해야 할 항목 요약
```

결과물: `output/final_table.csv`(판정표), `output/human_review_needed.csv`(사람 검토 필요 항목), `output/run_alerts.json`(이번 실행 전체 이슈 요약).

## 3. 규칙표(`data/rule_table.csv`) 갱신 절차 — **관리 담당: 서장훈 매니저 본인**

1. 새 규제 항목이 필요하면 행을 추가한다. 컬럼 정의는 [PRD.md FR-3](PRD.md#fr-3-규칙-매칭--구현-완료--srcmatch_regulationspy)절 참고
2. 조문 원문을 직접 못 찾았으면 `law_excerpt`를 `(확인 필요)`로 두고, 다음 명령으로 자동 조회:
   ```bash
   python src/check_law_updates.py
   ```
   결과가 `data/law_update_alerts.json`에 `new`(최초 확인) 또는 `changed`(기존과 다름)로 표시된 행만, 확인 후 `law_excerpt`에 수동 반영한다. **이 스크립트는 `rule_table.csv`를 절대 자동으로 고치지 않는다** — 항상 사람이 확인 후 반영.
3. `condition_type`(저촉/비저촉/조건부/임계값)은 조문을 읽고 직접 정한다. 확신이 없으면 반드시 `conditional`로 둔다 — 잘못 `always_violation`/`always_ok`로 단정하면 안 됨.
4. 국가법령(target=law)뿐 아니라 지자체 조례(자치법규)도 같은 방식으로 조회 가능하다: `law_lookup.lookup_ordinance_text("목포시 도시계획 조례", "제27조")`.

## 4. 장애 대응

| 증상 | 원인 | 대응 |
|---|---|---|
| `query_site_data.py` 실행 시 `eum.status: no_data`, 사유 "빈 응답" | 토지이음(eum.go.kr) 요청 빈도 제한 또는 서버측 차단 | **2026-09-16 기준 1주일이 지나도 안 풀리는 것을 확인함** — 단순 대기로 해결 안 될 수 있음. 다른 네트워크(자택/모바일 핫스팟 등)에서 재시도해보고, 그래도 안 되면 토지이음 담당(헬프데스크 02-838-4405) 문의 고려 |
| `vworld.status: no_data` | 브이월드 지오코더 주소 인식 실패 또는 API 키 문제 | 주소 표기를 도로명/지번 다른 형식으로 재시도. API 키 만료 여부는 `.env`의 `VWORLD_API_KEY` 확인 |
| `check_law_updates.py`에서 `lookup_failed` 다수 발생 | law.go.kr 접근 제한 또는 `OC=test` 데모 접근이 막힘 | `open.law.go.kr`에서 본인 이메일로 무료 OC 등록 후 `.env`에 `LAW_GO_KR_OC=<발급받은 OC>` 추가 |
| 판정표에 예상보다 "판정불가"가 많음 | 정상 동작(안전장치) — 규칙표에 없는 신규 표기이거나 매칭이 모호한 경우 의도적으로 판정불가 처리됨 | `output/human_review_needed.csv` 확인 후, 반복되는 항목이면 규칙표에 새 규칙 추가 |

## 5. 알려진 한계 (2026-09-16 기준)

- 브이월드 지적·토지특성정보 API(GetFeature/NED)는 별도 활용신청 미승인 상태 — 지목·면적은 토지이음 응답으로 대체 확보 중
- 토지이음은 공식 API가 아닌 화면용 AJAX를 그대로 사용 — 사이트 개편 시 `query_site_data.py` 파싱 로직이 깨질 수 있음
- `eum.go.kr` 라이브 조회가 1주일 넘게 막혀있는 상태 (§4 참고) — **실사용 투입 전 반드시 재검증 필요**
- `law_lookup.py`의 별표 조회는 가지번호(예: 별표1의2) 없는 대표 별표만 지원
- "지자체 홈페이지에 새 고시가 올라오는지" 자동 감지는 구현하지 않음 — 지자체마다 사이트·형식이 달라 구조화된 API가 없음. `check_law_updates.py`는 law.go.kr에 등재된 법령·조례의 "조문 내용 변경"만 감지한다
- 실제 이메일/슬랙 알림 발송은 구현하지 않음 — `run_summary.py`는 파일(`output/run_alerts.json`)과 콘솔 출력까지만 만든다

## 6. 테스트

```bash
python -m pytest -v   # 50개 (2026-09-16 기준), TDD로 작성됨
```
새 기능을 추가할 때는 테스트를 먼저 작성하고 실패를 확인한 뒤 구현하는 방식(TDD)을 유지해왔다.
