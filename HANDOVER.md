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
| **웹앱(Vercel)에서만** `vworld.status: no_data`, 사유가 "요청 실패: Connection aborted" 또는 "응답 파싱 실패(status=502)" | 브이월드 지오코더가 Vercel 트래픽을 차단/불안정 처리하는 것으로 추정(§5-4) — 이 dev 환경/로컬에서는 정상 동작 | **2026-09-16 기준 재시도 로직을 넣어도 안 풀림** — 미해결 상태. §5-4 참고 |
| `check_law_updates.py`에서 `lookup_failed` 다수 발생 | law.go.kr 접근 제한 또는 `OC=test` 데모 접근이 막힘 | **이미 적용됨(2026-09-17)**: 정식 OC 키를 `.env`에 추가 완료. law.go.kr 접근 제한이 있으면 네트워크 확인 |
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

## 5-2. GIS 좌표 기반 용도지역 자동 판별로 전환 (2026-09-16)

토지이음 개별 주소 조회(§4)가 클라우드에서 막혀있는 문제를, **eum.go.kr 공식 SHP 데이터 + GIS 폴리곤 매칭**으로 우회했다. 브이월드 GetFeature/WFS와 공공데이터포털의 관련 API도 모두 시도했으나(추가 승인 필요 또는 애초에 좌표 입력을 지원하지 않음) 막혀서, 최종적으로는 데이터를 직접 받아 로컬(웹앱 배포본에 포함)에서 계산하는 방식으로 확정했다.

**데이터 출처**: eum.go.kr 데이터개방 > "(도시계획)용도지역정보"(dataCd=004) > SHP > 전국 zip(976MB, fileId는 갱신 시마다 바뀜) 안에 시도별로 쪼개진 zip이 들어있음(`KLIP_004_20260801_12000.zip` = 전남·광주 통합, 117MB). 그 안의 `KLIP_C_UQ111.shp`가 용도지역(4대 대분류 + 세분류) 폴리곤이다.

**다운로드 절차** (매뉴얼/실측으로 확인한 실제 AJAX 흐름, `svItemDet.js` 참고):
1. `POST svItemAjaxXml.jsp` `function=selectFileInfo&dataCd=004&dataTypeCd=SHP&fileId=<파일목록에서 확인>` → `key`, `fileNm` 획득
2. `POST svItemAjaxXml.jsp` `function=insertStatInfo&dataCd=004&dataTypeCd=SHP&useType=1&useDesc=<용도설명>` (이용목적 등록, 승인절차 없음)
3. `GET https://map.eum.go.kr:8002/OpenData/opDownloader.jsp?key=<1의 key>&filename=<1의 fileNm>` → zip 다운로드

**좌표계 주의**: .prj를 실제로 열어보면 `Korean 1985 / Modified Central Belt`인데, 표준 EPSG:5186(false_northing=600000)이 아니라 **EPSG:5174(false_northing=500000)**다. 5186으로 잘못 변환하면 좌표가 엉뚱한 곳(제주 남쪽 해상 등)으로 튄다.

**전남 22개 시군구코드**: 이 데이터는 "전남광주통합특별시"(sido 12)로 광주까지 합쳐서 제공된다. 시군구코드(`sgg_cd`)가 실제 어느 시/군인지는 공식 코드-지명 대응표가 없어서, 각 코드의 대표 폴리곤 중심점을 브이월드 역지오코딩(`service=address&request=getAddress`)으로 조회해서 직접 확인했다(`data/zoning_jeonnam.geojson` 생성 스크립트인 `scripts/build_zoning_geojson.py`에 결과 반영됨). 완도군(12850)만 다도해라 중심점이 바다에 걸려 역지오코딩이 실패했는데, 전남 22개 시군구 중 유일하게 안 맞춰진 코드라 소거법으로 확정함.

**용도지역 코드 → 한글명**: eum.go.kr 다운로드 페이지의 "매뉴얼" 링크(`manualDownload.jsp?fileNm=004-SHP.zip`)에서 받은 `24-1010_토지이음개방용 KLIP 테이블 목록 및 정의서.xlsx`의 "속성테이블 설계" 시트에 공식 코드표가 있다(UQA121=제1종일반주거지역, UQB100=계획관리지역 등).

**결과물**: `data/zoning_jeonnam.geojson`(전남 22개 시군구, 4,426개 폴리곤, WGS84, 좌표 소수점 6자리로 반올림해 18.6MB), `src/gis_lookup.py`의 `find_zone_by_coordinate(lon, lat)`. 좌표가 폴리곤 0개 또는 2개 이상(오래된 중복 데이터)과 겹치면 값을 추측하지 않고 항상 `status="no_match"`/`"ambiguous"`로 사람 확인을 요구한다(judge.py와 동일한 안전 원칙).

**남은 일**: `query_site_data.py`의 `resolve_zone_info()`로 [2]단계 파이프라인에 연결 완료(eum.go.kr 실패 시 자동 대체). 다만 §5-4에 적은 대로 브이월드 지오코딩 자체가 Vercel에서 막혀 있어 웹앱에서는 아직 실사용이 안 된다. UQ111(용도지역) 레이어만 사용 중이며, UQ112(용도지구)·UQ113(용도구역) 등은 아직 반영 안 함.

## 5-3. 웹앱(Vercel) 구조: webapp/ 하위폴더 → 프로젝트 루트로 이동 (2026-09-16)

처음엔 `webapp/` 하위폴더에 웹앱 전체(`api/`, `public/`, `requirements.txt` 등)를 두고 Vercel의 **Root Directory를 `webapp`으로 설정**하는 방식으로 시작했다. 그런데 이 방식으로는 `src/`, `data/`(용도지역 GeoJSON 등)가 Root Directory 밖에 있어서 **배포 패키지에 아예 포함되지 않는다**는 걸 실측으로 확인했다(`api/site_judge.py`가 배포 후 `ModuleNotFoundError`, `os.path`로 확인해보니 `/var/task`가 곧 `webapp/`이고 그 위 경로가 존재하지 않았음). `src/`를 중복 구현하지 않고 그대로 재사용하는 게 원래 설계 원칙이었으므로, **`webapp/` 폴더를 없애고 그 안의 파일들을 전부 프로젝트 루트로 옮겼다**(`webapp/api/` → `api/`, `webapp/public/` → `public/`, `webapp/vercel.json` → `vercel.json`, `webapp/pyproject.toml` → `pyproject.toml`, `webapp/requirements.txt`는 루트 `requirements.txt`가 이미 같은 패키지를 다 갖고 있어서 삭제).

**따라서 Vercel 프로젝트 설정에서 Root Directory를 빈 값(저장소 루트 그대로)으로 바꿔야 한다** — 예전에 이 문서에 적혀 있던 "Root Directory를 `나만의 AI Agent 개발/부지판정자동화/webapp`으로 설정"이라는 안내는 애초에 잘못됐다: 실제 GitHub 저장소(jhseo069/KCH_9Team)의 루트가 이미 이 `부지판정자동화` 폴더 자체이고(로컬 디스크 경로일 뿐, 저장소 안에는 `나만의 AI Agent 개발`이라는 폴더가 없음), `webapp`도 이제 없어졌으므로 두 세그먼트 다 빼야 한다.

또 하나 실측으로 확인한 이 Vercel Python 런타임의 제약: `api/`에 handler 파일이 여러 개 있으면 **자동으로 파일마다 라우팅해주지 않고**, `pyproject.toml`의 `[tool.vercel] entrypoint`로 정확히 하나를 명시해야 한다(빌드 로그: `Error: No python entrypoint found in default locations, but found potential entrypoints: ...`). 그래서 서버리스 함수는 `api/site_judge.py` 하나만 유지한다(§api/README.md 참고).

## 5-4. 새로운 차단 확인: 브이월드 지오코더도 Vercel에서 막힘 (2026-09-16)

`api/`, `src/`, `data/` 경로 문제를 다 해결하고 실제로 웹앱에서 주소를 입력해보니, 이번엔 **브이월드 지오코더 API(`api.vworld.kr`, 주소→좌표 변환)가 Vercel(icn1, 서울 리전)에서 호출될 때마다 실패**하는 걸 확인했다 — 이 Claude 개발환경에서 호출하면 항상 정상 동작하는 바로 그 주소/키로도, Vercel에서는:
- 어떤 때는 연결이 중간에 끊김(`RemoteDisconnected: Remote end closed connection without response`)
- 어떤 때는 `502 Bad Gateway` (브이월드 서버가 빈 응답)

`vworld_geocode()`에 네트워크 오류 시 짧게 재시도하는 로직을 추가해서(방식별 최대 2회, `src/query_site_data.py`) 배포 후 4연속 테스트했지만 **매번 다른 방식으로 계속 실패** — 일시적 속도제한이 아니라 지속적인 차단으로 판단된다. eum.go.kr의 개별 조회 차단(§4)과 같은 패턴(클라우드/서버리스 트래픽에 대한 차단으로 추정)이지만, 이번엔 이미 만들어둔 GIS 용도지역 조회(§5-2)가 애초에 입력으로 필요로 하는 "주소→좌표 변환" 그 자체가 막힌 것이라 GIS 우회로도 해결이 안 된다.

**현재 상태**: 웹앱(`api/site_judge.py`)은 배포되어 정상적으로 실행되지만, 좌표를 못 구해서 사실상 모든 주소 조회가 실패한다. **다음에 이어서 풀어야 할 문제**: 좌표 변환을 브이월드가 아닌 다른 경로로 하거나(예: 브이월드도 eum.go.kr처럼 공식 대용량 데이터 다운로드 경로가 있는지 확인), 이 프로젝트 개발환경(또는 사용자 로컬)에서 좌표만 미리 계산해서 넘기는 방식 등을 검토할 것.

## 5-6. 이격거리 규정 판정 운영 (FR-10, 2026-09-17)

**데이터 갱신 절차**
1. `python scripts/collect_setback_draft.py` — 전남 22개 시군구 조례에서 이격거리 조문 초안 수집 → `data/setback_table_draft.csv`
2. 초안의 조문을 읽고 `distance_m`, `min_house_count`, `target`, `gosi_date`를 확정
3. 확정한 행을 `data/setback_table.csv`로 옮기고 `verified_by`, `verified_at`을 채운다
4. **`verified_by`가 비어 있으면 판정에 사용되지 않는다** — 미완성 상태로 배포해도 잘못된 판정이 나가지 않는다

**판정 규칙 요약** (상세: docs/20260916_설계_FR-10 …)

| 규칙 | 조건 | 결과 |
|---|---|---|
| R1 | 주민참여형·지붕형·자가소비용 | 비저촉 (법 제27조의3제3항) |
| R2 | 조례 미확인 | 판정불가 |
| R2-b | 조례 행은 확인됨(verified_by 있음) 그러나 distance_m 또는 min_house_count에 파싱 불가한 값(비숫자) 포함 | 판정불가 (데이터 입력 오류) |
| R3 | 조례에 이격거리 규정 없음(확인 완료) | 비저촉 |
| R4 | 허가신청일 < 2026-09-18 | 조건부 (종전 조례 적용) |
| R5-a | 시행 후 + 역사문화환경보존지역·생태경관보전지역 | 조건부 |
| R5-b | 시행 후 + 그 외 | 판정불가 (시행령 미비) |
| R6 | 보호구역 여부 미확인 | 판정불가 |

**알아둘 점**
- 시행일 상수(`STATUTE_EFFECTIVE_DATE`)는 부칙 "공포 후 6개월 경과일"에 근거한 사람 확정값이다. 법령 API가 `efYd`를 무시해 실증하지 못했다
- 보호구역(역사문화환경보존지역·생태경관보전지역) 자동 판별은 아직 없다. 그래서 시행 후 신청분은 대부분 R5-b/R6으로 판정불가가 된다 — 정상 동작이며, 사람이 확인해야 한다는 뜻이다

### 5-7. 지도 중심 화면 (2026-09-17)

`public/index.html`은 3단 레이아웃(좌: 사업 조건·레이어 / 중: 지도 / 우: 결과 탭 4종)이다.

**용도지역 레이어는 브라우저가 Supabase를 직접 호출한다.** Vercel을 거치지 않는다 —
지도를 움직일 때마다 나는 잦은 요청이 함수 호출 한도와 10초 제한을 건드리지 않게 하기
위해서다. 필요한 값은 `/api/site_judge?config=1`이 내려준다(`supabase_url`,
`supabase_key`). 여기 담기는 것은 **publishable 키뿐이며**, secret 키는 절대 넣지 않는다.

**표시용 도형과 판정용 도형은 다르다.** 지도에 그리는 폴리곤은 `zoning_in_bbox`가
단순화한 것으로, 줌 12에서는 경계가 55m까지 어긋난다. 판정은 항상 `zone_at`이 원본
정밀도로 한다. 화면 색과 판정이 경계 근처에서 다를 수 있는데, 이것은 의도된 동작이다 —
보이는 대로 판정하면 "비저촉"이 틀리게 나온다.

**줌 11 이하에서는 레이어를 로드하지 않는다.** 전남 전체에 폴리곤이 83,660건이라
그려도 뭉개지고 브라우저만 느려진다. **1,000건**을 넘으면 잘라내되 조용히 하지 않고
"확대하세요"를 띄운다 — 조용히 자르면 사용자가 빈 곳을 "용도지역이 없는 땅"으로 오해한다.

1,000은 우리가 고른 숫자가 아니다. **Supabase(PostgREST)가 응답을 1,000건에서 자른다.**
처음엔 3,000으로 잡았는데, 서버가 1,000에서 자르니 "확대하세요" 안내가 영원히 뜨지 않고
지도가 조용히 잘리고 있었다(2026-09-17 브라우저 점검에서 발견). 이 값을 올리려면 서버의
`db-max-rows` 설정을 바꿔야 하며, 브라우저 쪽 상수만 올리면 같은 버그가 재발한다.

**법령 탭**은 `/api/site_judge?law=1&law_name=...&law_article=...`로 law.go.kr에서 조문을
실시간 조회한다. 하위 경로(`/api/site_judge/law`)가 아니라 **쿼리 파라미터**로 분기한다 —
Vercel의 Python 빌더는 `api/site_judge.py`를 `/api/site_judge` 하나에만 매핑해서 하위 경로는
404가 난다. 처음엔 하위 경로로 만들었다가 최종 리뷰에서 발견해 고쳤다. `api/` 폴더에 handler
파일을 늘릴 수 없는 것(`pyproject.toml` entrypoint 고정)과 같은 이유다.

### 5-8. Supabase 자동정지 방지 (2026-09-18)

**Supabase 무료 플랜은 7일간 DB 활동이 없으면 프로젝트를 정지시킨다.** 정지되면 용도지역
조회가 전부 실패해 모든 판정이 판정불가로 나온다.

`.github/workflows/supabase-keepalive.yml`이 **월·목 12:00(KST)**에
`https://kch-9-team.vercel.app/api/site_judge?ping=1`을 호출한다. 이 엔드포인트
(`site_judge.py`의 `ping_database`)는 목포시 시가지 좌표로 **실제 DB 조회를 1회** 한다 —
정적 페이지나 설정 조회로는 DB 활동이 생기지 않아 정지를 못 막는다.

주 1회가 아니라 주 2회인 이유: 정지 기준이 7일이라 주 1회면 한 번만 실패해도 바로 넘긴다.
월·목이면 최대 간격이 4일이라 한 번 실패해도 여유가 있다.

Supabase를 직접 부르지 않고 우리 API를 거치는 이유: 그래야 Supabase 키를 GitHub Secrets에
또 복사할 필요가 없다. 키는 Vercel 환경변수 한 곳에만 있다.

**실패하면 반드시 알림이 온다.** ping은 조회 실패뿐 아니라 "접속은 되는데 알려진 좌표에서
아무것도 안 나오는" 경우(테이블이 비었거나 망가짐)도 503으로 응답하고, 워크플로는 3번 재시도
후에도 실패하면 job을 실패시킨다. GitHub이 저장소 소유자에게 실패 메일을 보낸다.

**실패 메일을 받았을 때:**
1. GitHub → `Actions` 탭 → 실패한 실행의 로그에서 HTTP 코드와 사유 확인
2. 사유가 `용도지역 DB`로 시작하면 Supabase 쪽 문제다. 대시보드에서 프로젝트가
   **Paused** 상태인지 확인하고, 그렇다면 `Restore project`를 누른다. **이미 정지된
   프로젝트는 API 호출로 깨울 수 없다** — 사람이 눌러야 한다
3. 사유가 `알려진 좌표에서 용도지역이 조회되지 않음`이면 DB는 살아있고 데이터가 문제다.
   `zoning` 테이블 건수를 확인한다(정상 83,660건). 비었으면 `scripts/load_zoning_to_supabase.py`로
   재적재한다
4. 복구 후 `Actions` → `Supabase keepalive` → `Run workflow`로 수동 실행해 초록불을 확인한다

**주의 — 예약 실행은 `main` 브랜치에 있어야만 동작한다.** 그리고 **공개 저장소는 60일간
활동이 없으면 GitHub이 예약 워크플로를 자동으로 끈다**(비공개 저장소는 해당 없음).
저장소를 공개로 전환했다면 `Actions` 탭에서 가끔 워크플로가 켜져 있는지 확인할 것.

## 5. 알려진 한계 (2026-09-17 기준)

- ~~국가법령정보센터(law.go.kr) Open API를 `OC=test` 데모 접근으로 사용~~ → **해소됨(2026-09-17)**: 정식 OC 키를 발급받아 `.env`의 `LAW_GO_KR_OC`에 적용. 다만 시행일자별 조회(`efYd` 파라미터)는 정식 키로도 동작하지 않는 것을 확인했다 — 특정 시행일 시점의 조문 버전을 가져오는 용도로는 쓸 수 없다
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
