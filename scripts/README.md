# scripts

## 폴더 목적/용도
평소 파이프라인 실행(`src/`)에는 안 쓰이고, 데이터 자체를 새로 만들거나 갱신할 때만 한 번씩 실행하는 일회성 빌드 스크립트를 모아둔다.

## 폴더 생성일
2026-09-16

## 폴더 내 규칙
특별한 파일명 규칙 없음 — 상위 [산출물 저장 규칙](../../../CLAUDE.md#산출물-저장-규칙)을 따르되, 이 폴더의 파일은 "산출물"이 아니라 산출물(`data/` 안의 파일)을 만드는 도구이므로 예외로 둔다.

## 폴더 내 파일
- `build_zoning_geojson.py`: eum.go.kr 데이터개방에서 받은 전국 용도지역 SHP(`(도시계획)용도지역정보`, dataCd=004)의 전남·광주 통합 시도(12000) 구간을 잘라, 전남 22개 시군구만 남기고 WGS84 GeoJSON(`../data/zoning_jeonnam.geojson`)으로 변환한다. 원본 SHP(전국 976MB)는 용량 때문에 저장소에 커밋하지 않으므로, 데이터를 다시 받아 이 스크립트를 재실행하려면 `HANDOVER.md`의 "eum.go.kr 데이터개방 다운로드 절차"를 따라 원본을 내려받은 뒤 스크립트 상단 `SHP_PATH`를 실제 경로로 바꿔서 실행한다.
- eum.go.kr이 이 데이터를 주기적으로 갱신하므로(고시·변경 반영), 정확도를 유지하려면 몇 달에 한 번씩 재실행을 권장한다.
- `collect_setback_draft.py`: 전남 22개 시군구 도시계획 조례에서 이격거리 조문 초안을 수집해 `../data/setback_table_draft.csv`로 저장한다. 수집 결과는 `verified_by`가 비어 있는 **초안**이며, 사람이 조문을 읽고 수치를 확정해 `../data/setback_table.csv`로 옮겨야 판정에 반영된다.
- `supabase_schema_parcels.sql`: 필지·시연부지 테이블 정의 (Supabase / PostGIS). `supabase_schema.sql`(zoning)과 별도 파일이며, 같은 보안 패턴(공개 키는 읽기만, 적재는 secret 키 전용 함수로)을 따른다.
