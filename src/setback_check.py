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

# 신청일이 이 날짜들에 걸리면 시행일 경계 자체가 확정적이지 않으므로, 판정 사유에
# "정확한 시행일을 확인하라"는 안내를 덧붙인다(설계서 §6-2).
_BOUNDARY_DATES = (date(2026, 9, 17), date(2026, 9, 18))
_BOUNDARY_NOTE = (
    " (2026-09-17~18은 법 제27조의3 시행일 경계이므로 정확한 시행일자를 확인할 것)"
)

STATUTE = {
    "name": "신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법",
    "article": "제27조의3",
    "effective_date": STATUTE_EFFECTIVE_DATE.isoformat(),
}

# 법 제27조의3제3항 각 호 - 해당하면 조례 이격거리가 적용되지 않는다.
# project_type이 None이면 사업유형과 무관하게 적용되고(주민참여형), 값이 있으면 그
# 사업유형일 때만 적용된다(지붕형·자가소비용은 조문상 '태양광발전설비'로 한정된다).
STATUTORY_EXEMPTIONS = {
    "주민참여형": {"basis": "제27조의3제3항제1호(주민 참여형 발전설비)", "project_type": None},
    "지붕형": {"basis": "제27조의3제3항제2호(지붕형 태양광발전설비)", "project_type": "태양광"},
    "자가소비용": {"basis": "제27조의3제3항제3호(자가소비용 태양광발전설비)", "project_type": "태양광"},
}

# 법 제27조의3제1항 각 호 - 해당하면 지자체가 이격거리를 적용할 수 있다
PROTECTED_ZONE_FLAGS = {
    "역사문화환경보존지역": "제27조의3제1항제1호(역사문화환경 보존지역·보호구역)",
    "생태경관보전지역": "제27조의3제1항제2호(생태ㆍ경관보전지역)",
}


def _to_int(value):
    """CSV에서 읽은 값을 정수로. 빈 값이면 None.

    "inf"/"1e400"처럼 float()까지는 통과하지만 int() 변환에서 OverflowError를 내는
    값, 그리고 애초에 문자열로 바꿀 수 없는 값(TypeError)도 파싱 실패로 취급한다 -
    요청을 죽이는 대신 조용히 None(=파싱 불가)을 돌려주고, 호출부(R2-b)가 이를
    "확인되지 않은 값"으로 판정불가 처리한다."""
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (ValueError, OverflowError, TypeError):
        return None


def _ordinance_payload(row):
    """조례 표 한 행 -> ordinance 딕셔너리. 필요한 열이 없으면(KeyError) None을 돌려줘
    호출부가 판정불가로 처리하게 한다 - 열 하나가 빠졌다고 판정 전체가 죽으면 안 된다."""
    try:
        return {
            "name": str(row["ordinance_name"]).strip(),
            "article": str(row["article"]).strip(),
            "distance_m": _to_int(row["distance_m"]),
            "min_house_count": _to_int(row["min_house_count"]),
            "excerpt": str(row["law_excerpt"]).strip(),
            "source_url": str(row["source_url"]).strip(),
        }
    except KeyError:
        return None


def _with_boundary_note(reason, apply_date):
    if apply_date in _BOUNDARY_DATES:
        return reason + _BOUNDARY_NOTE
    return reason


def unevaluated_judgment_row(reason: str) -> dict:
    """이격거리 판정을 아예 실행하지 못했을 때(시군구코드 미확인, 조례 표 파일 없음 등)
    쓰는 공용 판정불가 행. CLI(src/judge.py)와 웹앱(api/site_judge.py)이 각자 다른
    dict 리터럴을 만들면 같은 입력에도 한쪽은 행이 아예 빠지는(I5) 문제가 생기므로,
    두 경로 모두 이 함수를 호출해야 한다. 원인 문구(reason)만 다르게 넘기면 된다."""
    return {
        "raw_text": "이격거리(조례)",
        "rule_id": "SETBACK-미검토",
        "status": "판정불가",
        "law_excerpt": None,
        "source_url": None,
        "note": reason,
    }


def check_setback(sgg_cd, project_type, apply_date, exemptions, zone_flags, setback_table):
    """조례 이격거리가 실제로 적용되는지 판정한다.

    확실하지 않으면 판정불가를 돌려준다 - 이 함수는 어떤 경우에도 '저촉'을 반환하지 않는다.
    반경 내 주택 실측이 범위 밖이라 저촉을 확정할 근거가 없기 때문이다.

    반환값은 status/rule/reason/ordinance/statute와 함께 apply_date(판정에 사용한
    기준일, ISO 문자열)를 모든 경로에서 포함한다 - R4/R5 분기를 결정한 날짜가
    결과에서 드러나지 않으면 사람이 판정 근거를 검증할 수 없기 때문이다.

    distance_m/min_house_count 셀의 빈 값과 파싱 불가 값은 의미가 다르다: 빈 셀은
    "사람이 확인한 결과 규정이 없음"(R3, 비저촉)이고, "약 100"처럼 숫자로 읽을 수
    없는 비어있지 않은 값은 확인되지 않은 데이터 오류(R2-b, 판정불가)다. 후자를
    빈 값과 같이 취급해 비저촉으로 단정하지 않는다.

    호출부가 setback_table에 .fillna("")를 미리 적용했다고 가정하지 않는다 - 원본
    pd.read_csv 결과(NaN 포함)가 그대로 들어와도 안전하게 동작해야 한다.
    """
    setback_table = setback_table.fillna("")

    # I2. 사업유형을 모르면 무엇이 지어지는지 모른다는 뜻이다 - 필터를 그냥 건너뛰고
    # 아무 조례나 매칭시키면(과거 버그) 엉뚱한 사업유형의 조례가 비저촉으로 확정될 수
    # 있다. 사업유형 미상은 그 자체로 불확실성이므로 즉시 판정불가로 둔다.
    if not str(project_type or "").strip():
        return {
            "status": "판정불가",
            "rule": "R0",
            "reason": "사업유형이 확인되지 않아 어떤 조례를 적용할지 판단할 수 없음 - 사업유형 확인 필요",
            "ordinance": None,
            "statute": STATUTE,
            "apply_date": apply_date.isoformat(),
        }

    # I3(a). 법 제27조의3제3항의 적용 배제(R1)는 그 법 자체가 시행된 뒤에만 근거가 될
    # 수 있다. 시행 전 신청분은 예외 체크박스와 무관하게 종전 조례가 그대로 적용되므로
    # (부칙 제3조 적용례), 시행일 이후일 때만 R1을 평가한다 - 그렇지 않으면 시행 전
    # 신청인데도 "지붕형이라 비저촉"처럼 아직 존재하지 않는 법 조항을 근거로 삼게 된다.
    if apply_date >= STATUTE_EFFECTIVE_DATE:
        for name in exemptions or []:
            exemption = STATUTORY_EXEMPTIONS.get(name)
            if exemption is None:
                continue
            # I3(b). 지붕형·자가소비용은 조문상 '태양광발전설비'에 한정된다(제27조의3제3항
            # 제2호·제3호). 주민참여형(제1호)만 사업유형과 무관하게 적용된다.
            required_type = exemption["project_type"]
            if required_type is not None and required_type != project_type:
                continue
            return {
                "status": "비저촉",
                "rule": "R1",
                "reason": _with_boundary_note(
                    f"법 {exemption['basis']}에 해당해 조례 이격거리가 적용되지 않음", apply_date,
                ),
                "ordinance": None,
                "statute": STATUTE,
                "apply_date": apply_date.isoformat(),
            }

    # R2. 사람이 확정한 조례 데이터가 없으면 판정하지 않는다.
    # 사업유형이 명시됐는데 해당 유형(또는 all)의 조례 행이 없다면, 다른 유형의
    # 조례를 대신 적용해서는 안 된다 (예: 풍력 조례를 태양광에 적용 금지).
    # 좁힌 결과가 비어도 그대로 두어 아래에서 R2(판정불가)로 떨어지게 한다.
    matched = setback_table[
        (setback_table["sgg_cd"].astype(str) == str(sgg_cd))
        & (setback_table["verified_by"].astype(str).str.strip() != "")
        & (setback_table["project_type"].isin([project_type, "all"]))
    ]
    if matched.empty:
        return {
            "status": "판정불가",
            "rule": "R2",
            "reason": "해당 시군구의 조례 이격거리 규정이 아직 확인되지 않음 - 사람 확인 필요",
            "ordinance": None,
            "statute": STATUTE,
            "apply_date": apply_date.isoformat(),
        }

    # 행 순서(CSV에 적힌 순서)가 판정을 좌우하면 안 된다(C1) - 정렬해서 이후의 "첫 행"
    # 선택이 모두 결정적이 되게 한다.
    matched = matched.sort_values(by=["article", "target"], kind="stable")

    # R2-b. 빈 셀("확인 결과 규정 없음")과 파싱 불가 값("사람이 적었지만 숫자로
    # 못 읽는 값", 예: "약 100")은 서로 다르다. 빈 셀은 R3(비저촉)으로 확정할 수
    # 있지만, 파싱 불가 값은 데이터 확인 실패이지 규정이 없다는 뜻이 아니므로
    # 절대 비저촉으로 단정하지 않고 판정불가로 둔다. 매칭된 행이 여럿이면 그중
    # 하나라도 파싱 불가 값이 있으면 전체를 판정불가로 둔다 - 나머지 행만으로
    # 판단하면 "데이터가 의심스러운데 넘어갔다"는 사실이 감춰지기 때문이다.
    for _, candidate in matched.iterrows():
        for column, label in (("distance_m", "이격거리"), ("min_house_count", "밀집 기준 호수")):
            raw = str(candidate[column]).strip()
            if raw and _to_int(candidate[column]) is None:
                ordinance = _ordinance_payload(candidate)
                return {
                    "status": "판정불가",
                    "rule": "R2-b",
                    "reason": f"{label} 값을 숫자로 해석할 수 없음: '{raw}' - 조례 표 데이터 확인 필요",
                    "ordinance": ordinance,
                    "statute": STATUTE,
                    "apply_date": apply_date.isoformat(),
                }

    # C1. 시군구 하나에 여러 조례 행(도로/주택/공공시설 등 target별)이 있을 수 있다.
    # distance_m이 있는 행과 없는 행을 나눠서, "확인된 모든 행이 이격거리 없음에
    # 동의하는 경우"에만 R3(비저촉)으로 확정한다. 하나라도 이격거리가 있으면 CSV
    # 행 순서와 무관하게 가장 엄격한(distance_m이 가장 작은) 행을 적용한다.
    rows_with_distance = []
    rows_without_distance = []
    for _, candidate in matched.iterrows():
        payload = _ordinance_payload(candidate)
        if payload is None:
            return {
                "status": "판정불가",
                "rule": "R2-c",
                "reason": "조례 표에 필요한 열이 없어 판정할 수 없음 - 조례 표 데이터 형식 확인 필요",
                "ordinance": None,
                "statute": STATUTE,
                "apply_date": apply_date.isoformat(),
            }
        if payload["distance_m"] is None:
            rows_without_distance.append((candidate, payload))
        else:
            rows_with_distance.append((candidate, payload))

    if not rows_with_distance:
        # R3. 확인 결과 조례에 이격거리 규정 자체가 없는 경우 (매칭된 모든 행이 동의)
        row, ordinance = rows_without_distance[0]
        return {
            "status": "비저촉",
            "rule": "R3",
            "reason": f"{ordinance['name']}에 이격거리 규정 없음 ({str(row['verified_at']).strip()} 확인)",
            "ordinance": ordinance,
            "statute": STATUTE,
            "apply_date": apply_date.isoformat(),
        }

    # 가장 엄격한(최댓값 이격거리) 행을 적용한다. sort_values로 이미 안정 정렬을
    # 해뒀으므로 distance_m이 같은 행이 여럿이어도 결과는 결정적이다.
    rows_with_distance.sort(key=lambda pair: pair[1]["distance_m"])
    row, ordinance = rows_with_distance[0]
    # C1. 여러 조문이 매칭됐다면 어느 것을 적용했는지, 나머지도 있다는 사실이 이유
    # 문구(reason)에 드러나야 한다 - 사람이 판정표만 보고도 "확인해야 할 조문이 더
    # 있다"는 걸 알 수 있어야 한다.
    multi_row_note = (
        f" (이격거리 규정이 있는 조문 {len(rows_with_distance)}건 중 가장 엄격한 "
        f"'{ordinance['article']}'을 적용함 - 나머지 조문도 확인 필요)"
        if len(rows_with_distance) > 1 else ""
    )

    # R4. 법 시행 전 신청분은 종전 조례가 그대로 적용된다 (부칙 제3조 적용례)
    if apply_date < STATUTE_EFFECTIVE_DATE:
        return {
            "status": "조건부",
            "rule": "R4",
            "reason": _with_boundary_note(
                f"법 제27조의3 시행({STATUTE_EFFECTIVE_DATE.isoformat()}) 전 신청분이므로 "
                f"종전 조례가 그대로 적용됨 - 실제 저촉 여부는 현장 확인 필요{multi_row_note}",
                apply_date,
            ),
            "ordinance": ordinance,
            "statute": STATUTE,
            "apply_date": apply_date.isoformat(),
        }

    # R6. 보호구역 해당 여부를 모르면 R5 판단 자체가 불가능하다
    if zone_flags is None:
        return {
            "status": "판정불가",
            "rule": "R6",
            "reason": "역사문화환경보존지역·생태경관보전지역 해당 여부를 확인할 수 없어 판단 불가 - "
                      f"사람 확인 필요{multi_row_note}",
            "ordinance": ordinance,
            "statute": STATUTE,
            "apply_date": apply_date.isoformat(),
        }

    # R5-a. 법 제1항 각 호에 해당하면 지자체가 이격거리를 적용할 수 있다
    for flag, basis in PROTECTED_ZONE_FLAGS.items():
        if zone_flags.get(flag):
            return {
                "status": "조건부",
                "rule": "R5-a",
                "reason": _with_boundary_note(
                    f"법 {basis}에 해당해 조례 이격거리를 적용할 수 있음 - "
                    f"실제 저촉 여부는 현장 확인 필요{multi_row_note}",
                    apply_date,
                ),
                "ordinance": ordinance,
                "statute": STATUTE,
                "apply_date": apply_date.isoformat(),
            }

    # R5-b. 원칙적으로 적용 불가지만, 예외를 정할 대통령령이 아직 없다
    return {
        "status": "판정불가",
        "rule": "R5-b",
        "reason": _with_boundary_note(
            "법 제27조의3제1항에 따라 원칙적으로 이격거리를 적용할 수 없으나, "
            "같은 조 제1항제3호·제2항이 위임한 대통령령이 확인되지 않아 예외 해당 여부를 "
            f"확정할 수 없음 - 사람 확인 필요{multi_row_note}",
            apply_date,
        ),
        "ordinance": ordinance,
        "statute": STATUTE,
        "apply_date": apply_date.isoformat(),
    }


def to_judgment_row(result):
    """check_setback 결과를 기존 판정표 행 구조로 변환한다.

    note 끝에 판정에 사용한 기준일(apply_date)을 덧붙인다 - 판정 결과(특히 R4/R5
    분기)가 어떤 날짜를 기준으로 내려졌는지가 판정표만 봐서는 드러나지 않으면 안 되기
    때문이다.
    """
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
        "note": f"{result['reason']} (판정 기준일: {result['apply_date']})",
    }
