"""
[2단계 보완] 좌표에 걸린 용도지역 폴리곤들로부터 최종 판단을 내리는 규칙.

실제 조회는 zone_db.find_zone_in_db()(Supabase/PostGIS)가 한다. 이 모듈은 그 결과를
해석하는 규칙만 갖는다 - 판정 규칙을 한 곳에 모아두기 위해서다.

0개(좌표가 어떤 폴리곤에도 안 속함) 또는 2개 이상(겹침)일 때 어떤 값을 임의로 고르지
않고 항상 사람 검토로 넘긴다(judge.py의 "불확실하면 비저촉으로 단정하지 않는다"와 동일).

2026-09-17까지는 data/zoning_jeonnam.geojson 파일을 직접 읽었으나, 비도시지역을
포함하면서 265MB가 되어 파일 방식을 쓸 수 없게 됐다(Vercel 배포 한도 250MB).
파일과 그 빌드 스크립트는 제거했다 - 도시지역만 든 낡은 사본을 예비로 남기면
시스템이 반쪽으로 돌고 있다는 사실이 가려진다.
"""


def resolve_matches(matches: list) -> dict:
    """좌표에 걸린 폴리곤 목록 -> 최종 판단(ok / no_match / ambiguous).

    matches의 각 항목은 zone_name/zone_code/sgg_cd/sgg_nm/geometry를 가진 dict이며,
    is_generic이 True면 세부 용도가 정해지지 않은 '광역' 폴리곤이다.

    광역 폴리곤('도시지역', '관리지역')은 구체 폴리곤('제1종일반주거지역')과 반드시
    겹친다 - 같은 땅을 크게 한 번, 세밀하게 한 번 그린 것이기 때문이다. 둘을 동등하게
    세면 해당 지역 전체가 '겹침 -> 판정불가'가 되어 아무 답도 못 낸다. 그래서 구체
    폴리곤이 하나라도 있으면 그쪽만 보고, 광역은 달리 알 길이 없을 때만 쓴다.

    다만 구체 폴리곤끼리 겹치는 경우(오래된 중복 고시 등)는 여전히 판정불가다.
    어느 쪽이 맞는지 코드가 고를 근거가 없고, 잘못 고르면 '비저촉'이 틀리게 나온다.
    """
    specific = [m for m in matches if not m.get("is_generic")]
    candidates = specific or matches

    if len(candidates) == 1:
        m = candidates[0]
        return {
            "status": "ok",
            "zone_name": m["zone_name"],
            "zone_code": m["zone_code"],
            "sgg_nm": m["sgg_nm"],
            "sgg_cd": m["sgg_cd"],
            "is_generic": bool(m.get("is_generic")),
            "geometry": m.get("geometry"),
        }
    if not candidates:
        return {"status": "no_match", "reason": "해당 좌표를 포함하는 용도지역 폴리곤이 없음"}
    return {
        "status": "ambiguous",
        "candidates": candidates,
        "reason": f"{len(candidates)}개 폴리곤이 겹침 (오래된 중복 데이터 가능성) - 사람 확인 필요",
    }
