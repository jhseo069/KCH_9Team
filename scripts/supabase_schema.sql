-- 용도지역 공간 테이블 (Supabase / PostGIS)
--
-- 실행 방법: Supabase 대시보드 > SQL Editor 에 통째로 붙여넣고 Run.
-- 여러 번 실행해도 안전하다(이미 있으면 건너뜀). 단, 마지막 DROP/재적재는 하지 않는다.
--
-- 왜 파일로 두는가: 데이터베이스 구조를 대시보드에서 손으로 만들면 무엇이 왜 그런지가
-- 아무데도 안 남는다. 이 파일이 구조의 근거 기록이다.

create extension if not exists postgis;

-- ---------------------------------------------------------------------------
-- 용도지역 폴리곤
-- ---------------------------------------------------------------------------
create table if not exists zoning (
  id            bigint generated always as identity primary key,
  sgg_cd        text not null,                  -- 시군구코드 (12110 = 목포시)
  sgg_nm        text not null,
  zone_code     text not null,                  -- UQA121 등 (원본 atrb_se)
  zone_name     text not null,                  -- 제1종일반주거지역
  zone_category text not null,                  -- 지도 색상 대분류 (주거지역/관리지역/...)
  -- 세부 용도가 안 정해진 광역 폴리곤인지. 이런 폴리곤은 구체 폴리곤과 좌표가 겹치므로
  -- 조회할 때 구체 폴리곤을 우선하고 이쪽은 다른 후보가 없을 때만 쓴다.
  is_generic    boolean not null default false,
  area_sqm      double precision,               -- 원본 dgm_ar (고시 면적)
  geom          geometry(MultiPolygon, 4326) not null
);

-- 좌표 포함 검색(ST_Contains)과 화면범위 검색(&&) 둘 다 이 인덱스를 쓴다
create index if not exists zoning_geom_idx     on zoning using gist (geom);
create index if not exists zoning_sgg_idx      on zoning (sgg_cd);
create index if not exists zoning_category_idx on zoning (zone_category);

-- ---------------------------------------------------------------------------
-- 보안: 누구나 읽을 수 있고, 아무도 쓸 수 없다
-- ---------------------------------------------------------------------------
-- publishable(anon) 키는 브라우저에 그대로 노출되는 공개 키다. 키를 숨겨서 지키는 게
-- 아니라 아래 정책으로 지킨다. 읽기만 허용하고 쓰기 정책은 아예 만들지 않으므로,
-- 공개 키로는 SELECT만 된다. 데이터 적재는 별도의 DB 접속(비밀번호)으로만 가능하다.
alter table zoning enable row level security;

drop policy if exists "zoning은 누구나 읽기 가능" on zoning;
create policy "zoning은 누구나 읽기 가능"
  on zoning for select
  to anon, authenticated
  using (true);

-- ---------------------------------------------------------------------------
-- 좌표 -> 용도지역 조회
-- ---------------------------------------------------------------------------
-- 겹치는 폴리곤을 임의로 하나 고르지 않는다. 해당하는 것을 전부 돌려주고, 0건인지
-- 2건 이상인지에 대한 판단(=판정불가로 넘길지)은 애플리케이션이 한다. DB가 조용히
-- 하나를 골라버리면 "확실하지 않으면 판정하지 않는다"는 원칙이 여기서 깨진다.
-- 정렬만 거들어서, 광역 폴리곤(is_generic)은 뒤로 보낸다.
create or replace function zone_at(in_lon double precision, in_lat double precision)
returns table (
  sgg_cd text, sgg_nm text, zone_code text, zone_name text,
  zone_category text, is_generic boolean, area_sqm double precision, geojson text
)
language sql
stable
as $$
  select z.sgg_cd, z.sgg_nm, z.zone_code, z.zone_name,
         z.zone_category, z.is_generic, z.area_sqm,
         st_asgeojson(z.geom) as geojson
  from zoning z
  where st_contains(z.geom, st_setsrid(st_makepoint(in_lon, in_lat), 4326))
  order by z.is_generic asc, z.area_sqm asc nulls last;
$$;

-- ---------------------------------------------------------------------------
-- 적재용: WKB(16진 문자열) 묶음을 한 번에 넣는다
-- ---------------------------------------------------------------------------
-- DB에 직접 접속(비밀번호)하는 대신 secret 키로 이 함수를 호출해서 넣는다.
-- security definer가 아니라 기본(invoker) 권한이므로, secret 키(service_role)로만
-- 호출된다. 공개 키(anon)에는 실행 권한을 주지 않는다 - 아래 revoke/grant 참고.
create or replace function insert_zoning_batch(rows jsonb)
returns integer
language sql
as $$
  with ins as (
    insert into zoning (sgg_cd, sgg_nm, zone_code, zone_name, zone_category,
                        is_generic, area_sqm, geom)
    select r->>'sgg_cd', r->>'sgg_nm', r->>'zone_code', r->>'zone_name',
           r->>'zone_category', (r->>'is_generic')::boolean,
           nullif(r->>'area_sqm','')::double precision,
           st_setsrid(st_geomfromwkb(decode(r->>'wkb','hex')), 4326)
    from jsonb_array_elements(rows) as r
    returning 1
  )
  select count(*)::integer from ins;
$$;

revoke all on function insert_zoning_batch(jsonb) from public, anon, authenticated;
grant execute on function insert_zoning_batch(jsonb) to service_role;

-- ---------------------------------------------------------------------------
-- 지도 표시용: 화면 범위 안의 폴리곤을 단순화해서 반환
-- ---------------------------------------------------------------------------
-- 판정에는 절대 쓰지 않는다. 단순화한 경계로 판정하면 경계 근처 부지에서 용도지역이
-- 뒤바뀔 수 있다. 화면에 그리는 용도로만 쓴다(그래서 zone_code 같은 판정용 속성은
-- 최소한만 싣는다).
-- tolerance 단위는 도(degree)다. 줌이 멀수록 크게 준다: 0.0001도 ~= 11m.
create or replace function zoning_in_bbox(
  min_lon double precision, min_lat double precision,
  max_lon double precision, max_lat double precision,
  tolerance double precision default 0.0001,
  max_rows integer default 3000
)
returns table (zone_category text, zone_name text, geojson text)
language sql
stable
as $$
  select z.zone_category, z.zone_name,
         st_asgeojson(st_simplifypreservetopology(z.geom, tolerance)) as geojson
  from zoning z
  where z.geom && st_makeenvelope(min_lon, min_lat, max_lon, max_lat, 4326)
  order by z.area_sqm desc nulls last
  limit max_rows;
$$;
