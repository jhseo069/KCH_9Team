"""
[일회성 수집 스크립트] 전남 22개 시군구 도시계획 조례에서 이격거리 조문 초안을 모은다.

결과는 data/setback_table_draft.csv 로 저장되며, verified_by 가 비어 있으므로
판정 엔진(src/setback_check.py)은 이 초안을 판정에 사용하지 않는다.
사람이 조문을 읽고 수치를 확정한 뒤 data/setback_table.csv 로 옮겨야 한다.

주의: 조례 명칭은 지자체마다 다르다("OO시 도시계획 조례", "OO군 도시계획 조례" 등).
      조문 번호도 지자체마다 제각각이고(태양광 이격거리 조문이 가지번호 조문인 경우도 흔함,
      예: 목포시 제17조의4) lookup_ordinance_text는 가지번호 조문을 조회하지 못하므로,
      후보 조문번호를 추측하는 대신 조례 XML 전문을 한 번에 받아 모든 조문을 스캔한다.
      조회에 실패한 시군구는 실패 사유와 함께 행으로 남겨 누락을 눈에 보이게 한다.
"""
import csv
import os
import sys
import time
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from law_lookup import search_ordinance_mst, fetch_ordinance_xml, LAW_SERVICE_URL, DEFAULT_OC  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(BASE_DIR, "data", "setback_table_draft.csv")

# zoning_jeonnam.geojson 과 동일한 시군구코드 체계
JEONNAM_SGG = {
    "12110": "목포시", "12130": "여수시", "12150": "순천시", "12170": "나주시", "12190": "광양시",
    "12710": "담양군", "12720": "곡성군", "12730": "구례군", "12740": "고흥군", "12750": "보성군",
    "12760": "화순군", "12770": "장흥군", "12780": "강진군", "12790": "해남군", "12800": "영암군",
    "12810": "무안군", "12820": "함평군", "12830": "영광군", "12840": "장성군", "12850": "완도군",
    "12860": "진도군", "12870": "신안군",
}

COLUMNS = [
    "sgg_cd", "sgg_nm", "project_type", "target", "distance_m", "min_house_count",
    "ordinance_name", "article", "law_excerpt", "gosi_date", "source_url",
    "verified_by", "verified_at",
]


def _article_label(jo):
    """조문번호(6자리, 조번호*100+가지번호)를 '제N조' 또는 '제N조의M' 표기로 변환."""
    n = int(jo.findtext("조문번호"))
    base, branch = divmod(n, 100)
    return f"제{base}조" + (f"의{branch}" if branch else "")


def collect_one(sgg_nm):
    """한 시군구의 조례 전문을 한 번에 받아, '이격'이 언급된 조문을 모두 찾아 돌려준다."""
    ordinance_name = f"{sgg_nm} 도시계획 조례"

    search_result = search_ordinance_mst(ordinance_name)
    if search_result.get("status") != "ok":
        return ordinance_name, [], search_result.get("reason", "조례 검색 실패")

    mst = search_result["mst"]
    try:
        xml_text = fetch_ordinance_xml(mst)
        root = ET.fromstring(xml_text)
    except Exception as e:
        return ordinance_name, [], f"조례 원문 조회/파싱 실패: {e}"

    source_url = f"{LAW_SERVICE_URL}?OC={DEFAULT_OC}&target=ordin&MST={mst}&type=HTML"

    found = []
    for jo in root.findall(".//조문/조"):
        if jo.findtext("조문여부") != "Y":
            continue  # 장/절 헤더 - 실제 조문이 아님
        text = (jo.findtext("조내용") or "").strip()
        title = jo.findtext("조제목") or ""
        if "이격" in text or "이격" in title:
            found.append({
                "article": _article_label(jo),
                "law_excerpt": text,
                "source_url": source_url,
            })

    return ordinance_name, found, None


def main():
    rows = []
    for sgg_cd, sgg_nm in sorted(JEONNAM_SGG.items()):
        ordinance_name, found, fail_reason = collect_one(sgg_nm)
        if fail_reason is not None:
            rows.append({
                "sgg_cd": sgg_cd, "sgg_nm": sgg_nm, "project_type": "태양광",
                "target": "", "distance_m": "", "min_house_count": "",
                "ordinance_name": ordinance_name, "article": "",
                "law_excerpt": f"(자동수집 실패 - {fail_reason})",
                "gosi_date": "", "source_url": "", "verified_by": "", "verified_at": "",
            })
            print(f"{sgg_nm}: 조례 조회 실패 - {fail_reason}")
        elif not found:
            # 조례는 찾았지만 이격 언급 조문이 없는 경우도 행으로 남겨서 "확인 안 함"이 눈에 보이게 한다
            rows.append({
                "sgg_cd": sgg_cd, "sgg_nm": sgg_nm, "project_type": "태양광",
                "target": "", "distance_m": "", "min_house_count": "",
                "ordinance_name": ordinance_name, "article": "",
                "law_excerpt": "(자동수집 실패 - 조례 전문에서 '이격' 언급 조문 없음)",
                "gosi_date": "", "source_url": "", "verified_by": "", "verified_at": "",
            })
            print(f"{sgg_nm}: 이격 언급 조문 없음")
        else:
            for item in found:
                rows.append({
                    "sgg_cd": sgg_cd, "sgg_nm": sgg_nm, "project_type": "태양광",
                    "target": "", "distance_m": "", "min_house_count": "",
                    "ordinance_name": ordinance_name, "article": item["article"],
                    "law_excerpt": item["law_excerpt"], "gosi_date": "",
                    "source_url": item["source_url"], "verified_by": "", "verified_at": "",
                })
            print(f"{sgg_nm}: {len(found)}건 수집")

        time.sleep(0.3)  # 연속 호출(시군구) 간 최소 대기

    with open(OUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n초안 저장: {OUT_PATH} ({len(rows)}행)")
    print("verified_by 가 비어 있어 판정에는 사용되지 않는다. 사람이 확정 후 setback_table.csv 로 옮길 것.")


if __name__ == "__main__":
    main()
