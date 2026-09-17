"""[데이터 적재] 용도지역 SHP 5개 레이어 -> Supabase(PostGIS) zoning 테이블.

실행 전 준비:
  1) scripts/download_zoning_shp.py 로 원본을 받고 _gis_raw/jeonnam_gwangju/ 에 풀어둔다
  2) Supabase SQL Editor에서 scripts/supabase_schema.sql 을 실행해둔다
  3) .env 에 SUPABASE_DB_URL=postgresql://... 을 넣어둔다 (git에 올라가지 않음)

실행:
  python scripts/load_zoning_to_supabase.py            # 전남 22개 시군구 적재
  python scripts/load_zoning_to_supabase.py --dry-run  # DB 접속 없이 건수만 확인

왜 GeoJSON 파일이 아니라 DB인가:
비도시지역까지 포함하면 전남만으로 폴리곤 83,662건 / 좌표 1,171만 점이고 GeoJSON으로는
약 265MB다. Vercel 배포 한도(250MB)를 넘고, 브라우저로 내려보낼 수도 없으며, 매 요청마다
통째로 읽어 훑는 지금 방식은 더더욱 불가능하다. 공간 인덱스를 가진 DB에 두면 좌표 조회가
인덱스 한 번으로 끝난다.
"""
import argparse
import collections
import os
import sys

import shapefile
from dotenv import load_dotenv
from pyproj import Transformer
from shapely.geometry import MultiPolygon, Polygon
from shapely.validation import make_valid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zoning_codes import assert_known_codes, is_generic_zone, zone_category, zone_name

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHP_DIR = os.path.join(BASE_DIR, "_gis_raw", "jeonnam_gwangju")
load_dotenv(os.path.join(BASE_DIR, ".env"))

# 용도지역 레이어만 싣는다. UQ121 이후는 용도'지구'/'구역'이라 다른 개념이다.
LAYERS = ["UQ111", "UQ112", "UQ113", "UQ114", "UQ115"]

# 좌표계는 원본 .prj 실측값 EPSG:5174 (Korean 1985 / Modified Central Belt).
# 흔히 쓰는 5186으로 잘못 잡으면 좌표가 제주 남쪽 바다로 날아간다(2026-09-16에 겪음).
TRANSFORMER = Transformer.from_crs("EPSG:5174", "EPSG:4326", always_xy=True)

JEONNAM_SGG = {
    "12110": "목포시", "12130": "여수시", "12150": "순천시", "12170": "나주시", "12190": "광양시",
    "12710": "담양군", "12720": "곡성군", "12730": "구례군", "12740": "고흥군", "12750": "보성군",
    "12760": "화순군", "12770": "장흥군", "12780": "강진군", "12790": "해남군", "12800": "영암군",
    "12810": "무안군", "12820": "함평군", "12830": "영광군", "12840": "장성군", "12850": "완도군",
    "12860": "진도군", "12870": "신안군",
}


def signed_area(ring):
    s = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def shape_to_multipolygon(shp):
    """shapefile의 파트(외곽선/구멍)를 WGS84 MultiPolygon 하나로 합친다.

    shapefile은 외곽선과 구멍을 부호 있는 면적으로만 구분한다(음수=외곽선). 원본에 자기교차
    같은 결함이 있으면 make_valid로 고친다 - 여기서 버리면 그 필지가 조회에서 사라진다.
    """
    parts = list(shp.parts) + [len(shp.points)]
    rings = [shp.points[parts[i]:parts[i + 1]] for i in range(len(parts) - 1)]

    grouped = []
    exterior, holes = None, []
    for ring in rings:
        wgs = [tuple(TRANSFORMER.transform(x, y)) for x, y in ring]
        if signed_area(ring) < 0:
            if exterior is not None:
                grouped.append((exterior, holes))
            exterior, holes = wgs, []
        elif exterior is not None:
            holes.append(wgs)
        else:
            grouped.append((wgs, []))
    if exterior is not None:
        grouped.append((exterior, holes))

    polys = []
    for ext, hs in grouped:
        if len(ext) < 4:
            continue
        try:
            p = Polygon(ext, hs)
            if not p.is_valid:
                p = make_valid(p)
        except Exception:
            continue
        for g in (p.geoms if p.geom_type in ("MultiPolygon", "GeometryCollection") else [p]):
            if g.geom_type == "Polygon" and not g.is_empty:
                polys.append(g)

    if not polys:
        return None
    return MultiPolygon(polys)


def iter_rows(shp_dir=SHP_DIR, layers=LAYERS):
    """적재할 행을 (속성..., MultiPolygon)으로 하나씩 내놓는다."""
    code_counts = collections.Counter()
    skipped_no_geom = 0

    for layer in layers:
        path = os.path.join(shp_dir, f"KLIP_C_{layer}.shp")
        sf = shapefile.Reader(path, encoding="euc-kr")
        fields = [f[0] for f in sf.fields[1:]]
        i_sgg, i_code, i_area = fields.index("sgg_cd"), fields.index("atrb_se"), fields.index("dgm_ar")

        for n, rec in enumerate(sf.iterRecords()):
            sgg = rec[i_sgg]
            if sgg not in JEONNAM_SGG:
                continue
            code = rec[i_code] or ""
            code_counts[code] += 1
            if not code:
                continue

            geom = shape_to_multipolygon(sf.shape(n))
            if geom is None:
                skipped_no_geom += 1
                continue

            try:
                area = float(rec[i_area]) if rec[i_area] else None
            except (TypeError, ValueError):
                area = None

            yield {
                "sgg_cd": sgg,
                "sgg_nm": JEONNAM_SGG[sgg],
                "zone_code": code,
                "zone_name": zone_name(code),
                "zone_category": zone_category(code),
                "is_generic": is_generic_zone(code),
                "area_sqm": area,
                "wkb": geom.wkb.hex(),
            }

    # 모르는 코드가 하나라도 있으면 여기서 실패한다. 조용히 버리지 않는 것이 핵심이다.
    report = assert_known_codes(code_counts)
    if report["blank"]:
        print(f"  (코드가 빈 행 {report['blank']}건은 건너뜀 - 원본 결함)")
    if skipped_no_geom:
        print(f"  (도형을 만들 수 없는 행 {skipped_no_geom}건 건너뜀)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="DB 접속 없이 건수만 확인")
    ap.add_argument("--batch", type=int, default=500)
    ap.add_argument("--resume", action="store_true",
                    help="이미 들어간 건수 다음부터 이어서 적재 (중단된 작업 재개용)")
    args = ap.parse_args()

    if args.dry_run:
        counts = collections.Counter()
        total = 0
        for row in iter_rows():
            counts[row["zone_category"]] += 1
            total += 1
        print(f"\n적재 대상 {total:,}건")
        for k, v in counts.most_common():
            print(f"  {k:<22}{v:>7,}")
        return 0

    base_url = os.getenv("SUPABASE_URL")
    secret = os.getenv("SUPABASE_SECRET_KEY")
    if not base_url or not secret:
        print("SUPABASE_URL 또는 SUPABASE_SECRET_KEY가 .env에 없습니다.")
        print("Supabase 대시보드 > Project Settings > API 에서 확인해 .env에 넣어주세요.")
        return 1

    import requests

    # secret 키는 RLS를 무시하는 전권 키다. 서버(이 스크립트)에서만 쓰고 절대
    # 브라우저로 내려보내지 않는다 - 브라우저용은 PUBLISHABLE 키뿐이다.
    session = requests.Session()
    session.headers.update({
        "apikey": secret,
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
    })
    rpc = f"{base_url.rstrip('/')}/rest/v1/rpc/insert_zoning_batch"

    # Supabase 앞단(Cloudflare)이 간헐적으로 520/502를 돌려준다. 8만 건을 넣는 동안
    # 한 번만 나와도 전체가 멈추므로, 일시적인 오류는 잠깐 쉬었다 다시 보낸다.
    # 데이터 문제(4xx)는 다시 보내도 같으므로 즉시 실패시킨다.
    RETRYABLE = {429, 500, 502, 503, 504, 520, 521, 522, 524}

    def send(rows, max_attempts=5):
        import time
        last = None
        for attempt in range(max_attempts):
            try:
                res = session.post(rpc, json={"rows": rows}, timeout=180)
            except Exception as e:
                last = f"요청 실패: {e}"
            else:
                if res.status_code < 400:
                    return res.json()
                if res.status_code not in RETRYABLE:
                    raise RuntimeError(f"적재 실패 HTTP {res.status_code}: {res.text[:400]}")
                last = f"HTTP {res.status_code}"
            if attempt < max_attempts - 1:
                wait = 3 * (attempt + 1)
                print(f"    ({last}) {wait}초 후 재시도 {attempt + 2}/{max_attempts}", flush=True)
                time.sleep(wait)
        raise RuntimeError(f"적재 실패(재시도 {max_attempts}회 소진): {last}")

    # 기존 데이터 확인 (같은 데이터를 두 번 넣으면 좌표 하나가 여러 폴리곤에 걸려
    # 전부 '겹침 -> 판정불가'가 되어버린다)
    head = session.get(f"{base_url.rstrip('/')}/rest/v1/zoning",
                       params={"select": "id", "limit": "1"},
                       headers={"Prefer": "count=exact"}, timeout=60)
    if head.status_code >= 400:
        print(f"zoning 테이블 조회 실패 HTTP {head.status_code}: {head.text[:300]}")
        print("scripts/supabase_schema.sql 을 SQL Editor에서 먼저 실행하셨는지 확인해주세요.")
        return 1
    existing_text = head.headers.get("content-range", "*/0").split("/")[-1]
    existing = 0 if existing_text in ("0", "*") else int(existing_text)
    skip = 0
    if existing:
        if not args.resume:
            print(f"zoning 테이블에 이미 {existing:,}건이 있습니다.")
            print("중복 적재는 좌표가 여러 폴리곤에 걸려 전부 판정불가가 되므로 중단합니다.")
            print("이어받으려면 --resume, 처음부터 다시 넣으려면 SQL Editor에서")
            print("'truncate table zoning;' 을 먼저 실행하세요.")
            return 1
        # 배치는 하나의 SQL 문이라 전부 성공하거나 전부 실패한다. 따라서 현재 건수가
        # 곧 '성공한 행 수'이고, 원본을 같은 순서로 읽으면 그 다음부터 이어붙일 수 있다.
        skip = existing
        print(f"이어받기: 이미 {existing:,}건 -> 앞의 {skip:,}건을 건너뛰고 계속합니다.")

    batch, total, seen = [], 0, 0
    for row in iter_rows():
        seen += 1
        if seen <= skip:
            continue
        batch.append(row)
        if len(batch) >= args.batch:
            send(batch)
            total += len(batch)
            batch = []
            if total % 5000 == 0:
                print(f"  {total:,}건 적재", flush=True)
    if batch:
        send(batch)
        total += len(batch)

    print(f"\n적재 완료: {total:,}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
