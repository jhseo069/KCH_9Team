# PRD — 부지 규제·인허가 저촉 여부 자동 판정 시스템

| 항목 | 내용 |
|---|---|
| 작성일 | 2026-09-09 |
| 작성자 | 서장훈 매니저 (신재생사업본부 목포지사) / Claude 정리 |
| 관련 문서 | [과제정의서](../과제정의서/20260908_과제정의서_AX실습_과제정의서_9팀_서장훈%20v1.0.md), [To-Be 설계서](../과제정의서/20260909_설계_To-Be%20시스템%20설계서%20v1.0.md) |
| 현재 구현 상태 | [2]~[9]단계(FR-1~9) 전체 구현 완료, 전 구간 pytest 50개 통과. 코드 기준 DoD-1~9 충족 확인. **DoD-10(실주소 라이브 E2E)은 2026-09-16 기준 여전히 미검증 상태** — 2026-09-09 개발 중 반복 요청 이후 토지이음이 계속 빈 응답을 주고 있고, 1주일 뒤 재시도해도 동일함을 확인(README/HANDOVER 참고). 단순 대기로 풀리는 문제가 아닐 수 있어 별도 확인 필요 |

---

## 1. 목적 (한 줄)

**부지 주소만 입력하면, 토지이음·브이월드를 사람이 직접 오가며 확인하던 규제·인허가 저촉 여부를, 근거 조문과 출처가 함께 붙은 판정표로 자동 생성한다.**

---

## 2. 배경 / 문제 정의

신재생사업본부(목포지사)는 태양광·풍력 부지 검토 요청이 들어올 때마다 다음을 반복한다:

1. 토지이음(eum.go.kr)에서 용도지역·규제 항목 조회
2. 국가법령정보센터에서 관련 법령 조문 확인
3. 조문 기준과 부지 값을 사람이 직접 대조해 저촉 여부 판단
4. 결과를 엑셀로 수기 정리

**병목:** 2~4단계는 매 부지마다 같은 사이트를 다시 열고 같은 항목을 대조하는 반복 작업이다. 규제 항목의 표기가 사이트·지자체마다 달라(예: "계획관리지역" vs "국토계획법상 계획관리지역") 사람이 문맥으로 매칭해야 하지만, 저촉 여부 계산 자체는 규칙으로 고정할 수 있다.

---

## 3. 목표 사용자 및 범위

- **주 사용자:** 신재생사업본부 목포지사 팀 (팀 단위 공용 도구)
- **MVP 목표 레벨:** 과제정의서 4장의 "목표 성공" 레벨 — *"인허가 저촉 여부가 판정표로 나오고 항목마다 근거 조문과 출처가 함께 표기된다"*
- **Out of scope (이번 PRD 범위 밖):**
  - 일사량·기상 데이터 연계 경제성 검토 초안 (이상적 성공 단계)
  - 관청 고시 변경 자동 감지·알림 (3일차 stretch, 별도 PRD)
  - 지역 조례의 자동 반영 판단 (사람이 결정)

---

## 4. 시스템 아키텍처 (5단계 파이프라인)

```
[1] 입력 수집
      │
      ▼
[2] 데이터 조회  ──── 브이월드 API / 토지이음 웹조회        ✅ 구현 완료
      │                (data/raw_query_result.json)
      ▼
[3] 규칙 매칭 (AI)  ── 원문 문구 ↔ 규칙표 대조              ✅ 구현 완료
      │                (data/matching_result.json)
      ▼
[4] 판정 계산 (규칙엔진, AI 아님)                            ✅ 구현 완료
      │                (data/judgment_result.json)
      ▼
[5] 출력 생성  ──── 판정표 5열(비고 추가) + 사람 검토 목록   ✅ 구현 완료
                     (output/final_table.csv, .xlsx)
```

**불변 원칙:** 저촉 여부의 "계산"은 항상 [4] 규칙엔진이 담당한다. AI는 [3] 문구 매칭과 [5] 문장 서술만 맡는다. `eval()` 등으로 AI가 직접 조건식을 실행하게 하지 않는다. 각 단계 산출물은 반드시 파일로 남긴다.

---

## 5. 기능 요구사항 (단계별 상세 스펙)

### FR-1. 입력 (구현 완료, `query_site()`의 인자)

| 필드 | 타입 | 예시 |
|---|---|---|
| `address` | str | `"목포시 옥암동 1"` |
| `project_type` | str | `"태양광"` \| `"육상풍력"` \| `"해상풍력"` |
| `target_capacity_kw` | float | `990` |

### FR-2. 데이터 조회 (✅ 구현 완료 — [src/query_site_data.py](src/query_site_data.py))

**함수:** `query_site(address_or_jibun: str, project_type: str, target_capacity_kw: float) -> dict`

**브이월드 지오코더** (`vworld_geocode`): `GET https://api.vworld.kr/req/address?service=address&request=getcoord&version=2.0&type=road|parcel&address=...&key=...` — 도로명으로 실패하면 지번으로 재시도. `VWORLD_API_KEY`는 `.env`에 있음 (실제 호출 확인됨).

**토지이음 조회** (`eum_resolve_pnu` → `eum_get_land_detail`): 공식 API가 없어 화면용 AJAX를 그대로 사용. 반드시 `requests.Session()`으로 쿠키를 유지한 채 2단계로 호출해야 한다.
1. `POST /web/am/mp/mpSearchAddrAjaxXml.jsp` (`sId=selectAdAddrEnter&keyword=<주소>`) → PNU(19자리 필지고유번호) 추출
2. `POST /web/ar/lu/luLandDet.jsp` (`mode=search&sggcd=<PNU[2:5]>&pnu=<PNU>&add=land&...`) → HTML 파싱 (`jimokCd`, `#present_area`, `#present_mark1`(국토계획법 지역지구), `#present_mark2`(다른 법령), `#present_mark3`(토지이용규제 기본법))

**출력 스키마** (`data/raw_query_result.json`):
```json
{
  "input": {"address": "...", "project_type": "...", "target_capacity_kw": 990.0},
  "vworld": {"status": "ok|no_data", "lon": 126.44, "lat": 34.80, "refined_addr": "...", "reason": "(no_data일 때만)"},
  "eum": {
    "status": "ok|no_data",
    "pnu": "1211016400100010000",
    "jimok_code": "02",
    "area_sqm": "400",
    "zone_national_law": ["제2종일반주거지역", "완충녹지(저촉)", "지구단위계획구역"],
    "zone_other_law": ["가축사육제한구역<가축분뇨의 관리 및 이용에 관한 법률>", "도시개발구역<도시개발법>"],
    "special_notice_raw": "토지거래계약에관한허가구역(...)",
    "reason": "(no_data일 때만)"
  }
}
```

**확인된 제약 (실측):**
- 브이월드 지적·토지특성정보 API(GetFeature/NED)는 현재 키로 `INCORRECT_KEY` — 별도 활용신청 필요. 지목·면적은 토지이음 응답(`jimok_code`, `area_sqm`)으로 대체 확보.
- 토지이음에 짧은 간격으로 연속 요청하면 빈 응답(`{}`)이 오는 현상 확인(요청 빈도 제한 추정) → 코드가 `status: "no_data"`로 안전 처리함. 연속 조회 시 0.3~1초 이상 간격 권장.

### FR-3. 규칙 매칭 (✅ 구현 완료 — [src/match_regulations.py](src/match_regulations.py))

**입력:** `data/raw_query_result.json`, `data/rule_table.csv`
**출력:** `data/matching_result.json`

**구현 방식 결정:** LLM 호출 없이 **단순 키워드 부분일치**로 구현했다(개발 중 논의 후 확정). `match_keywords` 중 하나라도 원문에 포함되면 후보. 후보가 정확히 1개면 매칭, 0개면 미매칭, 2개 이상(모호)이면 어느 쪽도 확신할 수 없으므로 미매칭으로 처리 — LLM 없이도 "확신 없으면 미매칭" 원칙을 결정적(deterministic)으로 구현했다. 향후 표기 편차가 커져 단순 매칭의 한계가 드러나면 이 함수 내부만 LLM 호출로 교체하면 되도록 인터페이스(`match_regulations(eum_result, rule_table) -> list[dict]`)를 그대로 유지한다.

**테스트:** `tests/test_match_regulations.py` (pytest, TDD로 작성, 6개 테스트 모두 통과 — 정확매칭/미매칭/모호매칭/빈리스트/파이프구분키워드/두 zone리스트 처리)

**규칙표 스키마** (`data/rule_table.csv`, 코드 밖 파일):

| 컬럼 | 설명 | 예시 |
|---|---|---|
| `rule_id` | 고유 ID | `R001` |
| `category` | 규제유형 | `용도지역` |
| `project_types` | 적용 사업종류(쉼표구분, `all`=공통) | `태양광,육상풍력` |
| `match_keywords` | 매칭 키워드/패턴(파이프 구분, 이 중 하나라도 부분일치하면 후보) | `완충녹지` |
| `law_name` | 법령명 | `국토의 계획 및 이용에 관한 법률` |
| `law_article` | 조문번호 | `제76조` |
| `law_excerpt` | 조문 원문 발췌(판정표에 그대로 인용) | `완충녹지에서는 지정 목적에 위배되는 건축물 또는 공작물을 설치할 수 없다` |
| `condition_type` | 판정조건 유형 | `always_violation` \| `always_ok` \| `threshold` |
| `threshold_field` / `threshold_op` / `threshold_value` / `threshold_unit` | `condition_type=threshold`일 때만 사용 | `capacity_kw` / `<=` / `1000` / `kW` |
| `source_url` | 출처 URL | `https://www.law.go.kr/...` |

**규칙표 현황** (`data/rule_table.csv`, 2026-09-09 기준 14개 행 — 테스트에서 실제 관측된 규제 문구 전량 기반. 조문 원문·기준값은 **자리표시자이며 법무/도시계획 검토 후 확정 필요**):

| rule_id | match_keywords | condition_type |
|---|---|---|
| R001 | 완충녹지 | always_violation |
| R002 | 가축사육제한구역\|전부제한 | always_violation |
| R003 | 지구단위계획구역 | conditional |
| R004 | 계획관리지역 (태양광만) | always_ok (공식 데이터 확인, 2026-09-16) |
| R005 | 제3종일반주거지역 | always_ok (공식 데이터 확인, 2026-09-16) |
| R006 | 자연녹지지역 | always_ok (공식 데이터 확인, 2026-09-16) |
| R007 | 도시개발구역 | conditional |
| R008 | 토지거래계약에관한허가구역 | conditional |
| R009 | 상대보호구역\|절대보호구역 | conditional |
| R010 | 대공방어협조구역 | conditional |
| R011 | 과밀억제권역 | always_ok (담당자 확인, 2026-09-16) |
| R012 | 장애물제한표면구역 (태양광만) | conditional |
| R013 | 가로구역별 최고높이 제한지역 | conditional |
| R014 | 정비구역 | conditional |

R001·R002·R004를 제외한 신규 행은 실제 위반 여부를 검증할 법률 근거가 아직 없어 안전하게 `conditional`(사람 판단)로 두었다 — 확실하지 않은 규칙을 `always_violation`/`always_ok`로 임의 단정하지 않는다는 FR-3/FR-4의 안전 원칙을 규칙표 작성에도 그대로 적용한 것이다.

**2026-09-16 갱신:** FR-6(아래)으로 조회한 실제 법령 원문을 `law_excerpt`에 반영했다. 처음엔 R004(별표20)만 조문번호 형식이 아니라 자동조회에 실패했으나, `law_lookup.py`에 별표 조회 기능을 추가해 **R001~R014 전체(14개 행) 실제 원문 확보 완료**.

**2026-09-16 2차 갱신 — 토지이음 공식 데이터개방 자료로 발전시설 관련 규칙 보정:** 토지이음 "정보마당 > 데이터개방"(`토지이용규제 행위제한정보`, 국토교통부 공식 자료, CSV/API 제공, 신청 없이 즉시 다운로드 가능)를 실제로 다운로드해 확인한 결과, "용도지역지구명 × 시설유형(발전소로 사용되는 건축물) → 건축가능여부 + 조건"이 전국 단위로 이미 분석되어 있음을 발견했다. 이를 근거로:
- **R005(제3종일반주거지역): `conditional` → `always_ok`** — 공식 자료에 "건축 가능(조건 없음)"으로 명시
- **R006(자연녹지지역): `conditional` → `always_ok`** — "건축 가능(4층 이하에 한함)"으로 명시. 태양광·풍력 설비는 통상 층수 개념이 없어 조건이 사실상 항상 충족된다고 보고 승격
- **R004(계획관리지역)**: 기존 `always_ok` 유지, `law_name`/`law_article`을 실제 근거인 `건축법 시행령 별표1(제25호)`로 정정(기존 "국토계획법 시행령 별표20"은 부정확한 인용이었음)
- 세 규칙 모두 `law_excerpt`를 공식 데이터의 원문으로 교체, `source_url`을 데이터개방 페이지로 갱신
- 이 자료는 목포시 등 시군구 단위 조례까지 세분화되어 있어(`조례_전남` 시트 46만행), 추후 규칙표를 지역별로 정밀화할 때도 활용 가능

**같은 날 2차 검토 — `condition_type` 확정 시도:** R003·R005~R014를 실제 원문으로 재검토한 결과, `always_violation`/`always_ok`로 확정할 근거가 있는 조문은 없었다(전부 위임조문이거나 허가제 구조). 다만 검토 과정에서 두 가지 개선을 반영했다:
- **인용 조문 자체가 틀린 경우를 발견해 수정함**: R005(제76조→시행령 별표6), R006(제76조→시행령 별표17), R009(제8조→제9조), R011(제6조→제7조), R012(제2조→제34조). 원래 조문은 "위임/정의/지정절차" 조문이라 실제 제한 내용이 없었다
- **파서 버그 발견·수정**: `parse_article()`이 항(項) 아래 중첩된 호(號)·목(目) 목록을 누락하고 있었다(R001·R002·R003·R007·R008에 영향) → 수정 후 전체 재조회
- `condition_type`은 R003·R005~R010·R012~R014는 `conditional`로 유지 — 저촉/비저촉 해석은 여전히 사람 몫이다.
- **R011(과밀억제권역)은 담당자가 태양광·풍력 적용 제외 여부를 확인해 `always_ok`로 확정함(2026-09-16).** 실제 금지행위 목록("학교·공공청사·연수시설 등 인구집중유발시설의 신설·증설", "공업지역의 지정")에 발전시설이 포함되지 않는다는 점과 일치한다.

**함수 시그니처:**
```python
def match_regulations(eum_result: dict, rule_table: "pd.DataFrame") -> list[dict]:
    """eum_result의 zone_national_law + zone_other_law 각 문구를
    rule_table.match_keywords와 대조. 확신 없으면 미매칭으로 남긴다."""
```

**출력 스키마** (`data/matching_result.json`, 리스트):
```json
[
  {"raw_text": "완충녹지(저촉)", "matched_rule_id": "R001", "confidence": "high", "unmatched_reason": null},
  {"raw_text": "임시축사시설지구", "matched_rule_id": null, "confidence": null, "unmatched_reason": "규칙표에 없는 신규 표기 - 사람 검토 필요"}
]
```

**매칭 규칙:**
- `match_keywords`의 하나 이상이 `raw_text`에 부분 문자열로 포함되면 후보. 후보가 2개 이상이면 AI가 문맥으로 1개 선택하거나 미매칭 처리.
- 신뢰도가 낮으면(`confidence: "low"` 이하) 강제로 매칭하지 않고 `matched_rule_id: null` + `unmatched_reason` 필수 기재.
- AI가 직접 저촉/비저촉을 판단하지 않는다 — 오직 `raw_text → rule_id` 매핑만 수행.

### FR-4. 판정 계산 (✅ 구현 완료 — [src/judge.py](src/judge.py))

**입력:** `data/matching_result.json`, `data/rule_table.csv`, `data/raw_query_result.json`(관측값)
**출력:** `data/judgment_result.json`

**테스트:** `tests/test_judge.py` (pytest, TDD, 8개 테스트 통과) — always_violation/always_ok/conditional/threshold(상한 이내·초과)/미매칭 안전장치(DoD-6)/threshold 관측값 누락 시 판정불가/빈 리스트

**함수 시그니처:**
```python
def judge(matching_result: list[dict], rule_table: "pd.DataFrame",
          observed_values: dict) -> list[dict]:
    """AI가 아닌 순수 조건 평가. eval() 사용 금지 — condition_type별 분기 처리."""
```

**판정 로직 (condition_type별 순수 함수 분기, eval 금지):**
- `always_violation` → `저촉`
- `always_ok` → `비저촉`
- `conditional` → `조건부` (사람이 조건 충족 여부 판단)
- `threshold` → `observed_values[threshold_field]`와 `threshold_op`/`threshold_value` 비교 → `저촉`/`비저촉`
- `matched_rule_id`가 `null`(미매칭) 또는 규칙표에 해당 항목 자체가 없음 → **`판정불가`** (절대 `비저촉`으로 자동 처리 금지)

**출력 스키마** (`data/judgment_result.json`):
```json
[
  {"raw_text": "완충녹지(저촉)", "rule_id": "R001", "status": "저촉",
   "law_excerpt": "...", "source_url": "...", "observed_value": null, "threshold": null},
  {"raw_text": "임시축사시설지구", "rule_id": null, "status": "판정불가",
   "law_excerpt": null, "source_url": null, "note": "규칙표에 없는 신규 표기"}
]
```

### FR-5. 출력 생성 (✅ 구현 완료 — [src/export_output.py](src/export_output.py))

**입력:** `data/judgment_result.json`
**출력:** `output/final_table.csv`, `output/final_table.xlsx`, `output/human_review_needed.csv`

**테스트:** `tests/test_export_output.py` (pytest, TDD, 5개 테스트 통과) — 컬럼명 정확성, 필드 매핑, CSV/XLSX 행수 일치(DoD-8), 사람 검토 목록에 판정불가/조건부만 포함되고 저촉/비저촉 제외(DoD-9)

**함수 시그니처:**
```python
def generate_output_table(judgment_result: list[dict]) -> "pd.DataFrame":
    """항목 | 판정 | 근거조문 | 출처 | 비고 5열 DataFrame 반환"""

def export_outputs(df: "pd.DataFrame", judgment_result: list[dict], out_dir: Path) -> None:
    """final_table.csv/.xlsx 저장 + status가 '판정불가' 또는 '조건부'인 행만
    human_review_needed.csv로 별도 저장"""
```

- AI는 이 단계에서 판정 결과를 검토 자료용 자연스러운 한 문장으로 서술(예: "본 부지는 완충녹지에 해당하여 국토의 계획 및 이용에 관한 법률 제76조에 따라 저촉됩니다")하는 역할을 겸한다. 문장 서술도 숫자·판정 자체를 바꾸지 않는다.

---

## 6. 비기능 요구사항

| 항목 | 요구사항 |
|---|---|
| 성능 | 토지이음 연속 호출 시 0.3초 이상 간격(실측된 rate limit 대응). 부지 1건 전체 파이프라인 처리 10초 이내 목표 |
| 에러 처리 | 모든 외부 API/스크래핑 호출은 try/except로 감싸고 예외를 던지지 않음. 실패는 `status: "no_data"` + `reason`으로 다음 단계에 전달 |
| 보안 | API 키는 `.env`로만 관리, 코드에 하드코딩 금지(`.gitignore` 등록됨). 규칙엔진에서 `eval()`/`exec()` 사용 금지 |
| 로깅/추적성 | [2][3][4] 각 단계 결과를 반드시 파일로 저장 — 한 판정이 어떤 값·어떤 조문에서 나왔는지 파일만 열어 역추적 가능해야 함 |
| 재현성 | 동일 입력에 대해 규칙엔진([4]단계) 결과는 항상 동일해야 함 (AI 비결정성이 최종 판정에 영향을 주면 안 됨) |

---

## 6-1. FR-6. 법령 조문 자동 확인·개정 감시 (✅ 구현 완료 — [src/law_lookup.py](src/law_lookup.py), [src/check_law_updates.py](src/check_law_updates.py))

개발 중 논의를 거쳐, `law_excerpt` 스냅샷 방식의 한계("갱신되면 API가 알아서 최신을 준다"는 오해 정정)를 보완하기 위해 추가한 기능이다. 3가지 방식 중 **C안(스냅샷 + 주기적 자동 갱신 감시)**을 채택했다.

- **`law_lookup.py`**: 국가법령정보센터(law.go.kr) **정식 Open API**로 법령명+조문번호 → 조문 원문(항 단위) 실시간 조회. `OC=test`(비등록 데모 접근)로 정상 동작 확인됨 — 실사용 시 `open.law.go.kr`에서 무료 등록한 본인 OC로 `.env`의 `LAW_GO_KR_OC`를 교체 권장
- **`check_law_updates.py`**: `rule_table.csv`의 모든 행을 순회하며 최신 조문을 조회, 저장된 `law_excerpt`와 비교해 `new`(최초 확인)/`changed`(개정 감지)/`unchanged`/`lookup_failed`로 분류 → `data/law_update_alerts.json`에 저장. **`rule_table.csv`는 절대 자동으로 덮어쓰지 않는다** — 사람이 alerts를 보고 확정해서 반영
- **별표(부속서) 조회 지원 (2026-09-16 추가):** law.go.kr 응답 XML에는 조문(`<조문>`)뿐 아니라 별표(`<별표>`)도 함께 포함되어 있음을 확인, `extract_appendix_number()`("별표20"→"20") + `parse_appendix()`로 별표 제목·본문(고정폭 서식 정리 포함)까지 조회 가능하도록 확장. `lookup_article_text()`가 `law_article`이 "별표"로 시작하면 자동으로 별표 조회 경로로 분기
- **한계:** 가지번호가 있는 세부 별표(예: 별표1의2)는 현재 범위 밖 — 가지번호 `00`(대표 별표)만 지원
- **파서 완전성 개선 (2026-09-16):** `parse_article()`이 항(項) 아래 중첩된 호(號)·목(目) 목록을 누락하던 버그를 TDD로 발견·수정 (`_paragraph_full_text()` 추가)
- **테스트:** `tests/test_law_lookup.py`, `tests/test_check_law_updates.py` (pytest, TDD, 실제 law.go.kr 응답을 그대로 저장한 `tests/fixtures/sample_law.xml`·`tests/fixtures/sample_appendix.xml` 픽스처 사용) — 40개 테스트 통과
- **실행 결과 (2026-09-16, 14개 규칙 전체 재조회):** R001~R014 **전부 실제 원문 확보 완료**. 기존 13개는 `unchanged`(저장된 값과 라이브 조회 결과 일치 재확인), R004(별표20)는 신규로 `new` → 반영 완료

**실행:** `python src/check_law_updates.py` → `data/law_update_alerts.json`

## 6-2. FR-7. 자치법규(조례) 개정 감시 확장 (✅ 구현 완료 — [src/law_lookup.py](src/law_lookup.py))

3일차 확장 범위로 추가. "관청 고시 감시"의 실현 가능한 부분만 정직하게 범위에 넣었다 — 실제로 토지이음에서 "목포시 도시계획 조례 제27조" 같은 지자체 조례가 근거법령으로 나오는 것을 확인했고, law.go.kr Open API가 `target=ordin`으로 자치법규도 지원함을 확인했다.

- **`search_ordinance_mst()` / `fetch_ordinance_xml()` / `parse_ordinance_article()` / `lookup_ordinance_text()`**: 국가법령과 API는 같지만 응답 스키마가 달라(항/호 구분 없이 `조내용` 하나에 전문이 들어있고, 조문번호가 `조번호×100`을 6자리로 0-패딩한 형식) 별도 구현
- 라이브 확인: "목포시 도시계획 조례" 제27조(용도지역 안에서의 건축제한) 실제 원문 조회 성공
- 현재 `rule_table.csv` 14개 행은 전부 국가법령이라 이 기능은 아직 실사용 전 — 지자체 조례를 인용하는 규칙을 추가할 때부터 의미가 생긴다
- **테스트:** `tests/test_law_lookup.py` (실제 응답을 저장한 `tests/fixtures/sample_ordinance.xml` 픽스처) — 3개 테스트 추가, 전체 43개 통과

## 6-3. FR-8. 파이프라인 실행 알림 (✅ 구현 완료 — [src/run_summary.py](src/run_summary.py))

**범위를 솔직하게 좁힌 부분:** "관청 홈페이지에 새 고시가 올라오면 자동 감지"는 지자체마다 사이트·형식이 제각각이라 구조화된 API가 없어 구현하지 않았다. 실제 이메일/슬랙 등 알림 채널 발송도 조직의 채널 결정이 필요해 범위 밖이다. 대신 **"우리 파이프라인이 이미 만든 결과 중 사람이 놓치면 안 되는 것"을 빠짐없이 모아 보여주는 것**까지만 구현했다.

- `summarize_alerts(raw_query_result, matching_result, judgment_result, law_alerts=None) -> dict`: [2]단계의 no_data, [3]단계의 미매칭, [4]단계의 판정불가/조건부, [6]단계(FR-6)의 changed/lookup_failed를 모두 모아 `{total_issues, issues}` 반환
- CLI: `python src/run_summary.py` → `data/`의 최근 실행 결과 파일들을 읽어 `output/run_alerts.json` 저장 + 콘솔에 요약 출력
- **테스트:** `tests/test_run_summary.py` (pytest, TDD, 7개 테스트) — 정상케이스/각 단계별 이슈 플래깅/law_alerts 선택적 처리 검증. 전체 50개 통과

## 6-4. FR-9. 인수인계 메모 (✅ 작성 완료 — [HANDOVER.md](HANDOVER.md))

시스템 개요, 평소 실행 순서, 규칙표 갱신 절차(서장훈 매니저 담당), 장애 대응표(eum.go.kr 장기 차단 포함), 알려진 한계, 테스트 실행법을 정리했다.

## 6-5. FR-10. 이격거리 규정 판정 (✅ 구현 완료 — [src/setback_check.py](src/setback_check.py))

「신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법」 제27조의3(2026-09-18 시행)에 따라 지자체 조례의 이격거리 적용이 원칙적으로 금지된다. 부지의 시군구 조례가 실제로 적용되는지를 판정해 판정표에 한 행으로 추가한다.

- 조례 수치는 사람이 확정한 `data/setback_table.csv`에서 읽는다. `verified_by`가 빈 행은 판정에 쓰지 않는다
- 판정 규칙 R1~R6은 [설계서](docs/20260916_설계_FR-10%20이격거리%20규정%20판정%20v1.0.md) §6-2 참조
- **시행령에 이격거리 조문이 없어** 예외 범위를 확정할 수 없는 구간(R5-b)은 판정불가로 둔다
- 반경 내 주택 실측은 범위 밖이므로 이 기능은 `저촉`을 반환하지 않는다
- 엔진은 판정 시점의 날짜(`apply_date`)를 기록하며, 판정표 비고 열에 표시하므로 어느 기준일 기준으로 판정됐는지 확인할 수 있다

## 7. 데이터 계약 요약

| 파일 | 생성 단계 | 스키마 |
|---|---|---|
| `data/raw_query_result.json` | [2] (구현완료) | 위 FR-2 참고 |
| `data/rule_table.csv` | 사람이 작성/관리 | 위 FR-3 컬럼 정의 |
| `data/matching_result.json` | [3] | 위 FR-3 출력 스키마 |
| `data/judgment_result.json` | [4] | 위 FR-4 출력 스키마 |
| `output/final_table.csv/.xlsx` | [5] | 항목, 판정, 근거조문, 출처 |
| `output/human_review_needed.csv` | [5] | judgment_result 중 판정불가/조건부만 |
| `data/law_update_alerts.json` | FR-6/FR-7 | 위 FR-6 참고 (new/changed/unchanged/lookup_failed) |
| `output/run_alerts.json` | FR-8 | `{total_issues, issues: [{stage, ...}]}` |

---

## 8. 마일스톤 (과제정의서 일정 기준)

| 회차 | 목표 | 본 PRD 대응 |
|---|---|---|
| 1일차 (9/9) | 토지이음·브이월드 조회 자동화 | ✅ FR-1, FR-2 완료 |
| 2일차 (9/16) | 판정 규칙표 연결, 항목별 저촉여부+근거조문 표시 | ✅ FR-3, FR-4, FR-5 완료 |
| 3일차 (9/23) | 관청 고시 변경 감시, 응답 실패 알림, 인수인계 메모 | ✅ FR-6(법령), FR-7(자치법규 조례) — "고시" 자체가 아닌 "법령/조례 조문 개정" 감시로 범위를 명확히 함. FR-8(파이프라인 결과 알림, 실제 발송은 범위 밖). FR-9(HANDOVER.md) 완료 |

---

## 9. 완성 기준 (Definition of Done)

아래 각 항목은 **실제 입력을 넣어 참/거짓으로 판정 가능한 문장**이다. 모두 참이면 해당 단계는 완성으로 본다.

**DoD-1 (데이터 조회 — 이미 충족):**
> 터미널에서 `python src/query_site_data.py "목포시 옥암동 1" "태양광" 990`을 실행하면, `data/raw_query_result.json` 파일이 생성되고 그 안의 `vworld.status` 값이 `"ok"`이다.

**DoD-2 (데이터 조회 안정성 — 이미 충족):**
> 위와 같은 명령을 연속 실행해도 프로세스가 예외(traceback)로 비정상 종료되지 않으며, `eum.status`는 항상 `"ok"` 또는 `"no_data"` 둘 중 하나이다.

**DoD-3 (규칙 매칭):**
> `data/rule_table.csv`에 `rule_id=R001`, `match_keywords=완충녹지`가 등록된 상태에서, `eum.zone_national_law`에 `"완충녹지(저촉)"`가 포함된 `raw_query_result.json`을 `match_regulations()`에 넣으면, `data/matching_result.json`에 `raw_text="완충녹지(저촉)"` 항목의 `matched_rule_id`가 `"R001"`로 기록된다.

**DoD-4 (미매칭 안전장치):**
> `data/rule_table.csv`에 존재하지 않는 문구 `"테스트미등록규제구역"`을 `zone_national_law`에 넣고 `match_regulations()`를 실행하면, 해당 항목의 `matched_rule_id`는 `null`이고 `unmatched_reason`이 채워진다(빈 문자열이 아님).

**DoD-5 (판정 계산):**
> `rule_id=R001`, `condition_type=always_violation`인 규칙과 매칭된 항목을 `judge()`에 넣으면, `data/judgment_result.json`에서 해당 항목의 `status`가 `"저촉"`으로 기록된다.

**DoD-6 (판정불가 안전장치 — 핵심 요구사항):**
> `matched_rule_id=null`인 매칭 결과를 `judge()`에 넣으면, 해당 항목의 `status`는 `"판정불가"`이며, 어떤 경우에도 `"비저촉"`으로 자동 처리되지 않는다.

**DoD-7 (임계값 판정):**
> `rule_id=R00X`, `condition_type=threshold`, `threshold_field=capacity_kw`, `threshold_op=<=`, `threshold_value=1000`인 규칙에 대해 `observed_values={"capacity_kw": 990}`을 넣고 `judge()`를 실행하면 `status`가 `"비저촉"`이고, `observed_values={"capacity_kw": 1200}`을 넣으면 `status`가 `"저촉"`이다.

**DoD-8 (출력 생성):**
> 판정 항목이 3개(저촉 1, 비저촉 1, 판정불가 1) 있는 `judgment_result.json`으로 `export_outputs()`를 실행하면, `output/final_table.csv`와 `output/final_table.xlsx`가 각각 생성되고 두 파일의 행 수가 3(헤더 제외)이며, 컬럼명이 정확히 `["항목", "판정", "근거조문", "출처", "비고"]`이다.

**DoD-9 (사람 검토 목록):**
> 위와 같은 입력으로 `export_outputs()`를 실행하면, `output/human_review_needed.csv`에는 `status`가 `"판정불가"`인 1개 행만 존재하고, `"저촉"`/`"비저촉"` 행은 포함되지 않는다.

**DoD-10 (엔드투엔드):**
> 실제 부지 주소 `"목포시 옥암동 1"`, 사업종류 `"태양광"`, 용량 `990`을 [2]→[3]→[4]→[5] 전체 파이프라인에 순서대로 통과시키면, 예외 없이 `output/final_table.csv`가 생성되고, 그 파일을 열었을 때 최소 1개 이상의 행이 존재한다.

---

## 10. 리스크 및 제약사항 (실측 기반)

- **토지이음 비공식 API 의존:** 사이트 개편 시 파싱 로직(`eum_get_land_detail`) 전면 수정 필요. 실제로 반복 요청 시 빈 응답(`{}`)이 오는 rate limit 유사 현상을 확인했다.
- **브이월드 GetFeature/NED 미승인:** 현재 API 키로는 지적·토지특성정보 API 접근 불가(`INCORRECT_KEY`). 별도 활용신청 필요 — 승인 전까지는 지목·면적을 토지이음 응답으로 대체.
- **실습 환경 데이터 불일치 관찰:** 개발/테스트 중 "전남광주통합특별시"처럼 실제로 존재하지 않는 통합 행정구역명, 그리고 동일 PNU로 재조회해도 반환되는 지역지구 목록이 매번 달라지는 현상을 관찰했다. 이는 훈련/실습용 환경의 특성으로 추정되며, **실제 서비스 데이터로 전환 시 위 DoD들을 반드시 재검증해야 한다.**
- **규칙표 신뢰도:** 본 PRD의 예시 규칙표(FR-3)는 실제 관측된 규제 문구를 기반으로 하되, 조문 원문·기준값은 자리표시자다. 법무/도시계획 담당자 검토 없이 실사용 판정에 쓰면 안 된다.

---

## 11. 결정 사항 (2026-09-16 확정)

| 항목 | 결정 |
|---|---|
| 구현 경로 | **코드 기반(Python)으로 확정.** [2]~[6]단계 전체가 이미 Python으로 구현·테스트(40개)되어 있어 시트 노코드 경로는 채택하지 않는다 |
| 규칙표(`rule_table.csv`) 관리 주체 | **서장훈 매니저 본인.** 법령 개정 반영, `condition_type` 확정 등 규칙표 변경은 본인이 직접 승인·수정한다 |
| 최종 판정표 저장 형식 | **로컬 CSV/XLSX 그대로.** `output/final_table.csv`·`.xlsx`를 이메일/공유폴더로 전달하는 방식 — 구글시트 자동 업로드나 사내 시스템 연동은 하지 않는다 |
