"""
[일회성 수집 스크립트] 전남 22개 시군구 도시계획 조례에서 이격거리 조문 초안을 모은다.

결과는 data/setback_table_draft.csv 로 저장되며, verified_by 가 비어 있으므로
판정 엔진(src/setback_check.py)은 이 초안을 판정에 사용하지 않는다.
사람이 조문을 읽고 수치를 확정한 뒤 data/setback_table.csv 로 옮겨야 한다.

주의: 조례 명칭은 지자체마다 다르다("OO시 도시계획 조례", "OO군 도시계획 조례" 등).
      조회에 실패한 시군구는 실패 사유와 함께 행으로 남겨 누락을 눈에 보이게 한다.
"""
import csv
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from law_lookup import lookup_ordinance_text  # noqa: E402

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

# 조례에서 이격거리 규정이 있을 법한 조문 후보. 지자체마다 조문 번호가 달라 여러 개를 시도한다.
CANDIDATE_ARTICLES = ["제27조", "제28조", "제29조", "제30조", "제31조", "제32조"]

COLUMNS = [
    "sgg_cd", "sgg_nm", "project_type", "target", "distance_m", "min_house_count",
    "ordinance_name", "article", "law_excerpt", "gosi_date", "source_url",
    "verified_by", "verified_at",
]


def collect_one(sgg_nm):
    """한 시군구의 조례에서 '이격거리'가 언급된 조문을 모두 찾아 돌려준다."""
    ordinance_name = f"{sgg_nm} 도시계획 조례"
    found = []
    for article in CANDIDATE_ARTICLES:
        result = lookup_ordinance_text(ordinance_name, article)
        if result.get("status") != "ok":
            continue
        text = result.get("text", "")
        if "이격" in text:
            found.append({
                "article": article,
                "law_excerpt": text,
                "source_url": result.get("source_url", ""),
            })
        time.sleep(0.3)  # 연속 호출 간 최소 대기
    return ordinance_name, found


def main():
    rows = []
    for sgg_cd, sgg_nm in sorted(JEONNAM_SGG.items()):
        ordinance_name, found = collect_one(sgg_nm)
        if not found:
            # 못 찾은 것도 행으로 남겨서 "확인 안 함"이 눈에 보이게 한다
            rows.append({
                "sgg_cd": sgg_cd, "sgg_nm": sgg_nm, "project_type": "태양광",
                "target": "", "distance_m": "", "min_house_count": "",
                "ordinance_name": ordinance_name, "article": "",
                "law_excerpt": "(자동수집 실패 - 조문번호 후보에서 '이격' 언급 없음)",
                "gosi_date": "", "source_url": "", "verified_by": "", "verified_at": "",
            })
            print(f"{sgg_nm}: 후보 조문에서 찾지 못함")
            continue
        for item in found:
            rows.append({
                "sgg_cd": sgg_cd, "sgg_nm": sgg_nm, "project_type": "태양광",
                "target": "", "distance_m": "", "min_house_count": "",
                "ordinance_name": ordinance_name, "article": item["article"],
                "law_excerpt": item["law_excerpt"], "gosi_date": "",
                "source_url": item["source_url"], "verified_by": "", "verified_at": "",
            })
        print(f"{sgg_nm}: {len(found)}건 수집")

    with open(OUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n초안 저장: {OUT_PATH} ({len(rows)}행)")
    print("verified_by 가 비어 있어 판정에는 사용되지 않는다. 사람이 확정 후 setback_table.csv 로 옮길 것.")


if __name__ == "__main__":
    main()
