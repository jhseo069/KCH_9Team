"""
[FR-10] 이격거리 규정 판정.

「신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법」 제27조의3(2026-09-18 시행)에 따라
지자체 조례의 이격거리 적용이 원칙적으로 금지된다. 이 모듈은 부지의 시군구 조례가
실제로 적용되는지를 판정한다.

설계 근거: docs/20260916_설계_FR-10 이격거리 규정 판정 v1.0.md

핵심 제약(2026-09-16 확인): 법 제27조의3 제1항제3호·제2항이 위임한 대통령령에
이격거리 조문이 아직 없다. 따라서 "원칙적으로 적용 불가지만 예외에 해당하는지"를
확정할 수 없는 구간이 존재하며, 그 구간은 판정불가로 둔다(R5-b).
확인되지 않은 수치를 근거로 비저촉/저촉을 단정하지 않는다.
"""
from datetime import date

import pandas as pd

# 법 제27조의3 시행일.
# 부칙(법률 제21462호, 2026.3.17) 제1조 "공포 후 6개월이 경과한 날"에 근거한 값이다.
# law.go.kr 상세조회가 efYd 파라미터를 무시해(OC=test 제약) API로 실증하지는 못했고,
# 2026-09-17 사람 판단으로 확정했다. 값이 바뀌면 이 상수만 고치면 된다.
STATUTE_EFFECTIVE_DATE = date(2026, 9, 18)

STATUTE = {
    "name": "신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법",
    "article": "제27조의3",
    "effective_date": STATUTE_EFFECTIVE_DATE.isoformat(),
}

# 법 제27조의3제3항 각 호 - 해당하면 조례 이격거리가 적용되지 않는다
STATUTORY_EXEMPTIONS = {
    "주민참여형": "제27조의3제3항제1호(주민 참여형 발전설비)",
    "지붕형": "제27조의3제3항제2호(지붕형 태양광발전설비)",
    "자가소비용": "제27조의3제3항제3호(자가소비용 태양광발전설비)",
}

# 법 제27조의3제1항 각 호 - 해당하면 지자체가 이격거리를 적용할 수 있다
PROTECTED_ZONE_FLAGS = {
    "역사문화환경보존지역": "제27조의3제1항제1호(역사문화환경 보존지역·보호구역)",
    "생태경관보전지역": "제27조의3제1항제2호(생태ㆍ경관보전지역)",
}


def _to_int(value):
    """CSV에서 읽은 값을 정수로. 빈 값이면 None."""
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _ordinance_payload(row):
    return {
        "name": str(row["ordinance_name"]).strip(),
        "article": str(row["article"]).strip(),
        "distance_m": _to_int(row["distance_m"]),
        "min_house_count": _to_int(row["min_house_count"]),
        "excerpt": str(row["law_excerpt"]).strip(),
        "source_url": str(row["source_url"]).strip(),
    }


def check_setback(sgg_cd, project_type, apply_date, exemptions, zone_flags, setback_table):
    """조례 이격거리가 실제로 적용되는지 판정한다.

    확실하지 않으면 판정불가를 돌려준다 - 이 함수는 어떤 경우에도 '저촉'을 반환하지 않는다.
    반경 내 주택 실측이 범위 밖이라 저촉을 확정할 근거가 없기 때문이다.
    """
    # R1. 법이 정한 적용 배제 대상 (조례 내용과 무관하게 확정)
    for name in exemptions or []:
        if name in STATUTORY_EXEMPTIONS:
            return {
                "status": "비저촉",
                "rule": "R1",
                "reason": f"법 {STATUTORY_EXEMPTIONS[name]}에 해당해 조례 이격거리가 적용되지 않음",
                "ordinance": None,
                "statute": STATUTE,
            }

    # R2. 사람이 확정한 조례 데이터가 없으면 판정하지 않는다
    matched = setback_table[
        (setback_table["sgg_cd"].astype(str) == str(sgg_cd))
        & (setback_table["verified_by"].astype(str).str.strip() != "")
    ]
    if project_type:
        # 사업유형이 명시됐는데 해당 유형(또는 all)의 조례 행이 없다면, 다른 유형의
        # 조례를 대신 적용해서는 안 된다 (예: 풍력 조례를 태양광에 적용 금지).
        # 좁힌 결과가 비어도 그대로 두어 아래에서 R2(판정불가)로 떨어지게 한다.
        matched = matched[matched["project_type"].isin([project_type, "all"])]
    if matched.empty:
        return {
            "status": "판정불가",
            "rule": "R2",
            "reason": "해당 시군구의 조례 이격거리 규정이 아직 확인되지 않음 - 사람 확인 필요",
            "ordinance": None,
            "statute": STATUTE,
        }

    row = matched.iloc[0]
    ordinance = _ordinance_payload(row)

    # R3. 확인 결과 조례에 이격거리 규정 자체가 없는 경우
    if ordinance["distance_m"] is None:
        return {
            "status": "비저촉",
            "rule": "R3",
            "reason": f"{ordinance['name']}에 이격거리 규정 없음 ({str(row['verified_at']).strip()} 확인)",
            "ordinance": ordinance,
            "statute": STATUTE,
        }

    # R4. 법 시행 전 신청분은 종전 조례가 그대로 적용된다 (부칙 제3조 적용례)
    if apply_date < STATUTE_EFFECTIVE_DATE:
        return {
            "status": "조건부",
            "rule": "R4",
            "reason": (
                f"법 제27조의3 시행({STATUTE_EFFECTIVE_DATE.isoformat()}) 전 신청분이므로 "
                f"종전 조례가 그대로 적용됨 - 실제 저촉 여부는 현장 확인 필요"
            ),
            "ordinance": ordinance,
            "statute": STATUTE,
        }

    # R6. 보호구역 해당 여부를 모르면 R5 판단 자체가 불가능하다
    if zone_flags is None:
        return {
            "status": "판정불가",
            "rule": "R6",
            "reason": "역사문화환경보존지역·생태경관보전지역 해당 여부를 확인할 수 없어 판단 불가 - 사람 확인 필요",
            "ordinance": ordinance,
            "statute": STATUTE,
        }

    # R5-a. 법 제1항 각 호에 해당하면 지자체가 이격거리를 적용할 수 있다
    for flag, basis in PROTECTED_ZONE_FLAGS.items():
        if zone_flags.get(flag):
            return {
                "status": "조건부",
                "rule": "R5-a",
                "reason": f"법 {basis}에 해당해 조례 이격거리를 적용할 수 있음 - 실제 저촉 여부는 현장 확인 필요",
                "ordinance": ordinance,
                "statute": STATUTE,
            }

    # R5-b. 원칙적으로 적용 불가지만, 예외를 정할 대통령령이 아직 없다
    return {
        "status": "판정불가",
        "rule": "R5-b",
        "reason": (
            "법 제27조의3제1항에 따라 원칙적으로 이격거리를 적용할 수 없으나, "
            "같은 조 제1항제3호·제2항이 위임한 대통령령이 확인되지 않아 예외 해당 여부를 "
            "확정할 수 없음 - 사람 확인 필요"
        ),
        "ordinance": ordinance,
        "statute": STATUTE,
    }


def to_judgment_row(result):
    """check_setback 결과를 기존 판정표 행 구조로 변환한다."""
    ordinance = result.get("ordinance")
    if ordinance:
        excerpt = f"[{ordinance['name']} {ordinance['article']}] {ordinance['excerpt']}"
        source_url = ordinance["source_url"] or None
    else:
        excerpt = None
        source_url = None

    statute = result["statute"]
    law_excerpt = f"{excerpt}\n\n[{statute['name']} {statute['article']}] 시행 {statute['effective_date']}" \
        if excerpt else f"[{statute['name']} {statute['article']}] 시행 {statute['effective_date']}"

    return {
        "raw_text": "이격거리(조례)",
        "rule_id": f"SETBACK-{result['rule']}",
        "status": result["status"],
        "law_excerpt": law_excerpt,
        "source_url": source_url,
        "note": result["reason"],
    }
