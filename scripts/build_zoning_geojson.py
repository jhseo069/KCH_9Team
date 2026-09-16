"""
[일회성 데이터 빌드 스크립트] eum.go.kr 공식 SHP(용도지역정보) -> data/zoning_jeonnam.geojson

입력: eum.go.kr 데이터개방(https://www.eum.go.kr/web/op/sv/svItemList.jsp)에서
"(도시계획)용도지역정보"(dataCd=004) SHP를 받아 전국 zip -> 시도별(전남·광주 통합 = 12000)
zip -> KLIP_C_UQ111.shp(용도지역 폴리곤)까지 압축을 푼 뒤, 그 경로를 SHP_PATH로 지정한다.
파일이 커서(전국 976MB) 저장소에는 원본을 커밋하지 않는다 - 이 스크립트는 새 고시로
데이터가 갱신됐을 때 재실행하기 위한 기록용이다.

좌표계는 실제 .prj 파일로 확인한 EPSG:5174(Korean 1985 / Modified Central Belt,
false_northing=500000) - 흔히 쓰는 EPSG:5186과 다르므로 주의.

전남 22개 시군구코드(12xxx)는 시군구별 대표 폴리곤 중심점을 브이월드 역지오코딩으로
확인해서 얻었다(전남광주통합특별시 산하, 광주 5개 구 12210/12240/12270/12300/12330은 제외).

용도지역 코드->한글명 매핑은 eum.go.kr 데이터개방 매뉴얼
("24-1010_토지이음개방용 KLIP 테이블 목록 및 정의서.xlsx" > 속성테이블 설계 시트)의
공식 코드표를 그대로 사용했다.
"""
import json
import os

import shapefile
from pyproj import Transformer
from shapely.geometry import Polygon, mapping
from shapely.validation import make_valid

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 실행 전 이 경로를 실제로 압축 해제한 KLIP_C_UQ111.shp 위치로 바꿔야 한다.
SHP_PATH = os.path.join(BASE_DIR, "_gis_raw", "jeonnam_gwangju", "KLIP_C_UQ111.shp")
OUT_PATH = os.path.join(BASE_DIR, "data", "zoning_jeonnam.geojson")

JEONNAM_SGG = {
    "12110": "목포시", "12130": "여수시", "12150": "순천시", "12170": "나주시", "12190": "광양시",
    "12710": "담양군", "12720": "곡성군", "12730": "구례군", "12740": "고흥군", "12750": "보성군",
    "12760": "화순군", "12770": "장흥군", "12780": "강진군", "12790": "해남군", "12800": "영암군",
    "12810": "무안군", "12820": "함평군", "12830": "영광군", "12840": "장성군", "12850": "완도군",
    "12860": "진도군", "12870": "신안군",
}

# 공식 코드표 (24-1010_토지이음개방용 KLIP 테이블 목록 및 정의서.xlsx > 속성테이블 설계)
ZONE_CODE_NAME = {
    "UQA111": "제1종전용주거지역", "UQA112": "제2종전용주거지역", "UQA119": "전용주거지역(미분류)",
    "UQA121": "제1종일반주거지역", "UQA122": "제2종일반주거지역", "UQA123": "제3종일반주거지역",
    "UQA129": "일반주거지역(미분류)", "UQA130": "준주거지역", "UQA190": "주거지역(기타)",
    "UQA210": "중심상업지역", "UQA220": "일반상업지역", "UQA230": "근린상업지역", "UQA240": "유통상업지역",
    "UQA290": "상업지역(기타)",
    "UQA310": "전용공업지역", "UQA320": "일반공업지역", "UQA330": "준공업지역", "UQA390": "공업지역(기타)",
    "UQA410": "보전녹지지역", "UQA420": "생산녹지지역", "UQA430": "자연녹지지역", "UQA490": "녹지지역(기타)",
    "UQA500": "도시지역(미지정)", "UQA999": "도시지역(기타)", "UQA000": "도시지역(미분류)",
    "UQA001": "도시지역(국토이용관리법)",
    "UQB300": "보전관리지역", "UQB200": "생산관리지역", "UQB100": "계획관리지역",
    "UQB999": "관리지역(기타)", "UQB000": "관리지역(미분류)",
    "UQB400": "준도시지역(국토이용관리법)", "UQB500": "준농림지역(국토이용관리법)",
    "UQC001": "농림지역", "UQC999": "농림지역(기타)", "UQC000": "농림지역(미분류)",
    "UQD001": "자연환경보전지역", "UQD999": "자연환경보전지역(기타)", "UQD000": "자연환경보전지역(미분류)",
    "UQE000": "미분류", "UQE999": "기타",
}

transformer = Transformer.from_crs("EPSG:5174", "EPSG:4326", always_xy=True)


def signed_area(ring):
    s = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def shape_to_polygons(shp):
    """ESRI shapefile 규약: 시계방향(signed_area<0) 링=외곽, 반시계(양수)=구멍."""
    parts = list(shp.parts) + [len(shp.points)]
    rings = [shp.points[parts[i]:parts[i + 1]] for i in range(len(parts) - 1)]

    polygons = []
    current_exterior = None
    current_holes = []
    for ring in rings:
        wgs_ring = [tuple(transformer.transform(x, y)) for x, y in ring]
        area = signed_area(ring)
        if area < 0:
            if current_exterior is not None:
                polygons.append((current_exterior, current_holes))
            current_exterior = wgs_ring
            current_holes = []
        elif current_exterior is not None:
            current_holes.append(wgs_ring)
        else:
            polygons.append((wgs_ring, []))
    if current_exterior is not None:
        polygons.append((current_exterior, current_holes))

    shapely_polys = []
    for ext, holes in polygons:
        if len(ext) < 4:
            continue
        try:
            p = Polygon(ext, holes)
            if not p.is_valid:
                p = make_valid(p)
            shapely_polys.append(p)
        except Exception:
            continue
    return shapely_polys


def round_coords(obj):
    if isinstance(obj, (list, tuple)):
        if obj and isinstance(obj[0], (int, float)):
            return [round(v, 6) for v in obj]
        return [round_coords(x) for x in obj]
    return obj


def main():
    sf = shapefile.Reader(SHP_PATH, encoding="euc-kr")
    field_names = [f[0] for f in sf.fields[1:]]
    idx_sgg = field_names.index("sgg_cd")
    idx_atrb = field_names.index("atrb_se")
    idx_lclas = field_names.index("lclas_cl")

    features = []
    skipped_unknown_code = set()
    for i, rec in enumerate(sf.iterRecords()):
        sgg = rec[idx_sgg]
        if sgg not in JEONNAM_SGG:
            continue
        shp = sf.shape(i)
        if not shp.points:
            continue
        atrb = rec[idx_atrb] or rec[idx_lclas] or ""
        zone_name = ZONE_CODE_NAME.get(atrb)
        if zone_name is None:
            skipped_unknown_code.add(atrb)
            zone_name = atrb

        for p in shape_to_polygons(shp):
            if p.is_empty:
                continue
            geoms = list(p.geoms) if p.geom_type == "MultiPolygon" else [p]
            for g in geoms:
                geometry = mapping(g)
                geometry["coordinates"] = round_coords(geometry["coordinates"])
                features.append({
                    "type": "Feature",
                    "properties": {
                        "sgg_cd": sgg,
                        "sgg_nm": JEONNAM_SGG[sgg],
                        "zone_code": atrb,
                        "zone_name": zone_name,
                    },
                    "geometry": geometry,
                })

    fc = {"type": "FeatureCollection", "features": features}
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, separators=(",", ":"))

    print(f"features: {len(features)}")
    print(f"unknown codes (수동 확인 필요): {skipped_unknown_code}")
    print(f"output size: {os.path.getsize(OUT_PATH) / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()
