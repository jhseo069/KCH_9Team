-- 필지·시연부지 테이블 (Supabase / PostGIS)
--
-- 실행 방법: Supabase 대시보드 > SQL Editor 에 통째로 붙여넣고 Run.
-- 여러 번 실행해도 안전하다(이미 있으면 건너뜀). 단, 마지막 DROP/재적재는 하지 않는다.
--
-- 왜 파일로 두는가: 데이터베이스 구조를 대시보드에서 손으로 만들면 무엇이 왜 그런지가
-- 아무데도 안 남는다. 이 파일이 구조의 근거 기록이다.
--
-- 이 파일은 scripts/supabase_schema.sql(zoning)과 별도 파일이다. 서장훈 님이 zoning에
-- 적용한 보안 패턴(공개 키는 읽기만, 적재는 secret 키 전용 함수로)을 그대로 복제한다.
-- 새 보안 모델을 발명하지 않는다.
--
-- 근거: 나만의 AI Agent/사업부지_통합에이전트/2026.09.18_통합에이전트_클라우드배포_설계_v1.md §6

create extension if not exists postgis;

-- ---------------------------------------------------------------------------
-- 필지 (강경미 ParcelRecord의 클라우드 사본)
-- ---------------------------------------------------------------------------
-- 이 테이블은 "조회 결과의 캐시"가 아니라 "사전 조사 결과의 보관소"다. 등기부등본처럼
-- 클라우드에서 재생성할 수 없는 출처가 섞여 있으므로, 비었다고 해서 다시 조회하면
-- 채워지는 성질의 데이터가 아니다.
create table if not exists parcels (
  pnu          text primary key,
  소재지        text not null,
  지번          text not null,
  지목          text,
  면적_m2       double precision,
  용도지역      text,
  용도지구      text,
  규제사항_원문  text[] not null default '{}',   -- 서장훈 judge.py의 raw_text 입력 단위와 1:1
  개별공시지가   bigint,
  조회상태      text not null,                   -- 성공 | 부분성공 | 실패
  실패사유      text[] not null default '{}',    -- "#조회실패: …" 원문 그대로
  데이터출처    text[] not null default '{}',
  조회시각      timestamptz not null,
  geom         geometry(Point, 4326)            -- 지도 클릭 → 필지 역조회용. 없으면 null
);

create index if not exists parcels_geom_idx on parcels using gist (geom);

alter table parcels enable row level security;

drop policy if exists "parcels는 누구나 읽기 가능" on parcels;
create policy "parcels는 누구나 읽기 가능"
  on parcels for select to anon, authenticated using (true);

-- ---------------------------------------------------------------------------
-- 좌표 -> 필지 조회
-- ---------------------------------------------------------------------------
-- zone_at과 같은 원칙: 가까운 것을 임의로 하나 고르지 않는다. 반경 안에 있는 것만
-- 거리순으로 돌려주고, 0건인지 여러 건인지에 대한 판단은 화면이 한다.
create or replace function parcel_at(
  in_lon double precision, in_lat double precision,
  radius_m double precision default 50
)
returns setof parcels
language sql stable as $$
  select p.* from parcels p
  where p.geom is not null
    and st_dwithin(p.geom::geography,
                   st_setsrid(st_makepoint(in_lon, in_lat), 4326)::geography,
                   radius_m)
  order by p.geom::geography <-> st_setsrid(st_makepoint(in_lon, in_lat), 4326)::geography;
$$;

-- ---------------------------------------------------------------------------
-- 적재용 (secret 키 전용) — insert_zoning_batch와 같은 방식
-- ---------------------------------------------------------------------------
create or replace function upsert_parcels_batch(rows jsonb)
returns integer
language sql as $$
  with ins as (
    insert into parcels (pnu, 소재지, 지번, 지목, 면적_m2, 용도지역, 용도지구,
                         규제사항_원문, 개별공시지가, 조회상태, 실패사유,
                         데이터출처, 조회시각, geom)
    select r->>'pnu', r->>'소재지', r->>'지번', r->>'지목',
           nullif(r->>'면적_m2','')::double precision,
           r->>'용도지역', r->>'용도지구',
           coalesce((select array_agg(value::text) from jsonb_array_elements_text(r->'규제사항_원문')), '{}'),
           nullif(r->>'개별공시지가','')::bigint,
           r->>'조회상태',
           coalesce((select array_agg(value::text) from jsonb_array_elements_text(r->'실패사유')), '{}'),
           coalesce((select array_agg(value::text) from jsonb_array_elements_text(r->'데이터출처')), '{}'),
           (r->>'조회시각')::timestamptz,
           case when r->>'lon' is null or r->>'lon' = '' then null
                else st_setsrid(st_makepoint((r->>'lon')::double precision,
                                             (r->>'lat')::double precision), 4326) end
    from jsonb_array_elements(rows) as r
    on conflict (pnu) do update set
      지목 = excluded.지목, 면적_m2 = excluded.면적_m2,
      용도지역 = excluded.용도지역, 용도지구 = excluded.용도지구,
      규제사항_원문 = excluded.규제사항_원문,
      개별공시지가 = excluded.개별공시지가,
      조회상태 = excluded.조회상태, 실패사유 = excluded.실패사유,
      데이터출처 = excluded.데이터출처, 조회시각 = excluded.조회시각,
      geom = coalesce(excluded.geom, parcels.geom)
    returning 1
  )
  select count(*)::integer from ins;
$$;

revoke all on function upsert_parcels_batch(jsonb) from public, anon, authenticated;
grant execute on function upsert_parcels_batch(jsonb) to service_role;

-- ---------------------------------------------------------------------------
-- 시연용 부지
-- ---------------------------------------------------------------------------
-- 시연 중 외부 조회가 실패했을 때 즉시 꺼내 쓰는 준비된 시나리오.
create table if not exists demo_sites (
  id          bigint generated always as identity primary key,
  display_ord integer not null default 0,
  site_name   text not null,          -- "신안군 안좌면 마명리 (12필지)"
  address     text not null,
  lon         double precision not null,
  lat         double precision not null,
  project_type text not null,          -- 태양광 | 풍력 …
  capacity_kw  double precision,
  note         text                     -- 시연 시 설명할 포인트
);

alter table demo_sites enable row level security;
drop policy if exists "demo_sites는 누구나 읽기 가능" on demo_sites;
create policy "demo_sites는 누구나 읽기 가능"
  on demo_sites for select to anon, authenticated using (true);
