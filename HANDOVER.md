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

## 5-1. 중요 발견: 토지이음 정식 Open API (2026-09-16)

지금 `query_site_data.py`가 쓰는 방식(내부 화면용 AJAX 스크래핑)보다 **훨씬 안정적인 정식 경로**가 있다. 토지이음 "정보마당 > 데이터개방"(`https://www.eum.go.kr/web/op/sv/svItemList.jsp`)에서 아래 항목들을 CSV/API로 공식 제공한다:

| 데이터 | 설명 | 제공형식 |
|---|---|---|
| 개발행위허가정보 | 지역별 개발행위허가 위치·종류 | CSV, API |
| (도시계획)용도지역정보 | 용도지역·지구·구역 별 고시·조서정보 | SHP, CSV |
| 지구단위계획구역 | - | SHP, CSV |
| **토지이용규제 법령정보** | 토지이용규제 관련 법령 및 조례 정보 | CSV, **API** |
| **토지이용규제 행위제한정보** | 지역·지구별 행위규제 사항을 규제 조건·결과 형태로 분석한 자료 | CSV, **API** |
| **고시정보** | (지자체 고시 — 3일차에 "불가능"이라 판단했던 것이 실제로는 여기서 중앙화 제공됨) | CSV, **API** |

**"토지이용규제 행위제한정보"가 특히 중요** — 지금 우리가 [3]단계에서 규칙표로 어렵게 흉내내고 있는 "이 지역·지구에서 이 행위가 되는지"를 토지이음이 이미 분석해서 자료로 제공한다는 뜻이다. 확보하면 [3]~[4]단계를 상당 부분 대체하거나 검증할 수 있다.

**신청 절차 (사람이 해야 함 — API 신청서 양식과 매뉴얼을 사용자에게 전달함, 2026-09-16):**
1. `API연계 신청서` 양식 작성 (다운로드: `https://www.eum.go.kr/web/op/sv/userequest.hwp`)
2. `luris@korea.kr`로 이메일 발송
3. 3영업일 내 연계 KEY + 매뉴얼 수신 (문의: 02-838-4405)

키를 받으면 `query_site_data.py`를 이 정식 API 기반으로 재작성하는 게 다음 개선 우선순위다. **AI가 이 신청서를 대신 제출할 수 없다** — 회사/담당자 명의로 직접 신청해야 한다.

**추가 발견(2026-09-16, 같은 날 오후):** API 신청·대기 없이도 **CSV/XLSX는 "정보 활용 목적"만 선택하면 즉시 다운로드된다** (승인 절차 없음). 실제로 "토지이용규제 행위제한정보" 최신본(전국, 매월 갱신, ~55MB)을 받아서 열어봤는데, 용도지역지구명 × 시설유형(발전소로 사용되는 건축물/태양광 및 풍력 발전시설 등) → 건축가능여부 + 조건이 이미 분석되어 있었다. `rule_table.csv`의 R004·R005·R006(발전시설 관련 용도지역 규칙)을 이 자료로 보정 완료(§PRD.md FR-3 참고). `조례_전남` 시트는 46만 행으로 목포시(시군구코드 12110) 등 개별 지자체 조례까지 포함하므로, 지역별 규칙표 정밀화가 필요할 때 다시 활용할 수 있다. 다운로드 방법은 `svItemDet.jsp`(dataCd/dataTypeCd로 조회) → `svItemAjaxXml.jsp`(selectFileInfo → insertStatInfo) → `map.eum.go.kr:8002/OpenData/opDownloader.jsp`(key+filename) 순서다.

## 5. 알려진 한계 (2026-09-16 기준)

- 브이월드 지적·토지특성정보 API(GetFeature/NED)는 별도 활용신청 미승인 상태 — 지목·면적은 토지이음 응답으로 대체 확보 중
- 토지이음은 공식 API가 아닌 화면용 AJAX를 그대로 사용 — 사이트 개편 시 `query_site_data.py` 파싱 로직이 깨질 수 있음
- `eum.go.kr` 라이브 조회가 1주일 넘게 막혀있는 상태 (§4 참고) — **실사용 투입 전 반드시 재검증 필요**
- `law_lookup.py`의 별표 조회는 가지번호(예: 별표1의2) 없는 대표 별표만 지원
- "지자체 홈페이지에 새 고시가 올라오는지" 자동 감지는 구현하지 않음 — `check_law_updates.py`는 law.go.kr에 등재된 법령·조례의 "조문 내용 변경"만 감지한다. **정정(2026-09-16): 토지이음이 "고시정보"를 API로 이미 중앙 제공하고 있음을 발견함(§5-1) — API 키를 받으면 이 한계는 해소 가능하다**
- 실제 이메일/슬랙 알림 발송은 구현하지 않음 — `run_summary.py`는 파일(`output/run_alerts.json`)과 콘솔 출력까지만 만든다

## 6. 테스트

```bash
python -m pytest -v   # 50개 (2026-09-16 기준), TDD로 작성됨
```
새 기능을 추가할 때는 테스트를 먼저 작성하고 실패를 확인한 뒤 구현하는 방식(TDD)을 유지해왔다.
