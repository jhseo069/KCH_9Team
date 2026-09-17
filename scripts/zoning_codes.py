"""용도지역 코드 해석 (이름 / 지도 색상 대분류 / 광역-세부 겹침 판별).

이름표의 출처:
eum.go.kr 데이터개방 "(도시계획)용도지역정보" SHP(2026-08-19, 전남·광주 KLIP_C_UQ111~115)의
`dgm_nm` 필드에서 **코드별 최빈값을 실측**해서 만들었다. 사람이 기억으로 적은 표가 아니다.
새 고시본에 모르는 코드가 나오면 assert_known_codes()가 건수와 함께 실패시키므로,
그때 원본의 dgm_nm을 다시 실측해서 이 표에 추가한다.

왜 이렇게까지 하는가 (2026-09-17 사고 기록):
이전 빌드는 코드표에 없는 코드를 조용히 버렸고, SHP도 UQ111(도시지역) 레이어 하나만 읽었다.
그 결과 관리·농림·자연환경보전지역 약 8만 건이 통째로 빠졌는데 아무도 알아채지 못했다.
태양광 부지는 대부분 그 빠진 영역에 있어서, 정작 실무에서 쓰는 주소가 전부 판정불가로
떨어지고 있었다. 침묵이 문제였으므로 이 모듈은 모르는 코드를 만나면 반드시 소리를 낸다.
"""

# 코드 -> 한글명 (원본 dgm_nm 실측값)
ZONE_NAME = {
    # 도시지역 (KLIP_C_UQ111, atrb_se = UQA*)
    "UQA111": "제1종전용주거지역",
    "UQA112": "제2종전용주거지역",
    "UQA120": "일반주거지역",
    "UQA121": "제1종일반주거지역",
    "UQA122": "제2종일반주거지역",
    "UQA123": "제3종일반주거지역",
    "UQA130": "준주거지역",
    "UQA210": "중심상업지역",
    "UQA220": "일반상업지역",
    "UQA230": "근린상업지역",
    "UQA240": "유통상업지역",
    "UQA320": "일반공업지역",
    "UQA330": "준공업지역",
    "UQA410": "보전녹지지역",
    "UQA420": "생산녹지지역",
    "UQA430": "자연녹지지역",
    "UQA000": "도시지역(미분류)",
    "UQA01X": "도시지역",
    "UQA500": "도시지역미지정",
    # 관리지역 (KLIP_C_UQ112, UQB*)
    "UQB001": "관리지역",
    "UQB100": "계획관리지역",
    "UQB200": "생산관리지역",
    "UQB300": "보전관리지역",
    # 농림지역 (KLIP_C_UQ113)
    "UQC001": "농림지역",
    # 자연환경보전지역 (KLIP_C_UQ114)
    "UQD001": "자연환경보전지역",
    # 국토이용관리법 시절 미분류 (KLIP_C_UQ115)
    "UQE000": "국토이용용도지역미분류",
}

# 지도에서 색으로 구분할 대분류.
# 17종을 전부 다른 색으로 칠하면 읽기 어려워지므로 국토계획법의 용도지역 체계대로 묶는다.
# 도시지역 안의 구분은 코드 넷째 자리(UQA1=주거, 2=상업, 3=공업, 4=녹지)가 그대로 알려준다.
_URBAN_CATEGORY = {"1": "주거지역", "2": "상업지역", "3": "공업지역", "4": "녹지지역"}
_PREFIX_CATEGORY = {
    "UQB": "관리지역",
    "UQC": "농림·자연환경보전지역",
    "UQD": "농림·자연환경보전지역",
}

# 세부 용도가 정해지지 않은 '광역' 코드.
# 이 폴리곤들은 구체 폴리곤과 좌표가 겹친다 - 같은 점이 '도시지역'과 '제1종일반주거지역'에
# 동시에 걸린다. 동등하게 취급하면 겹침(2건)으로 보고 전부 판정불가가 되므로, 조회할 때
# 구체 폴리곤을 우선하고 이쪽은 다른 후보가 없을 때만 쓴다.
GENERIC_ZONE_CODES = frozenset({"UQA000", "UQA01X", "UQA500", "UQB001", "UQE000"})

UNCLASSIFIED_CATEGORY = "미분류"


class UnknownZoneCodeError(RuntimeError):
    """코드표에 없는 용도지역 코드를 만났을 때. 조용히 버리지 않기 위해 존재한다."""


def zone_name(code):
    """코드의 한글 용도지역명. 모르는 코드면 None."""
    return ZONE_NAME.get(code)


def zone_category(code):
    """지도 색상용 대분류. 모르는 코드면 None."""
    if code not in ZONE_NAME:
        return None
    if code in GENERIC_ZONE_CODES:
        return UNCLASSIFIED_CATEGORY
    if code.startswith("UQA"):
        return _URBAN_CATEGORY.get(code[3], UNCLASSIFIED_CATEGORY)
    return _PREFIX_CATEGORY.get(code[:3], UNCLASSIFIED_CATEGORY)


def is_generic_zone(code):
    """세부 용도가 정해지지 않아 구체 폴리곤과 겹치는 광역 폴리곤인지."""
    return code in GENERIC_ZONE_CODES


def assert_known_codes(code_counts):
    """등장한 코드가 전부 코드표에 있는지 확인한다. 하나라도 모르면 건수와 함께 실패.

    code_counts: {코드: 건수}
    반환: {"blank": 코드가 빈 행 수}  (원본에 실제로 있으며, 실패 사유로는 보지 않는다)
    """
    unknown = {}
    blank = 0
    for code, count in code_counts.items():
        if not code:
            blank += count
            continue
        if code not in ZONE_NAME:
            unknown[code] = count

    if unknown:
        detail = ", ".join(f"{c}={n}건" for c, n in sorted(unknown.items(), key=lambda kv: -kv[1]))
        raise UnknownZoneCodeError(
            f"코드표에 없는 용도지역 코드 {len(unknown)}종이 있습니다: {detail}. "
            "원본 SHP의 dgm_nm 필드에서 실제 이름을 확인해 scripts/zoning_codes.py의 "
            "ZONE_NAME에 추가하세요 - 임의로 버리면 해당 지역이 통째로 조회되지 않습니다."
        )

    return {"blank": blank}
