# -*- coding: utf-8 -*-
"""시연 직전 점검. 배포된 경로가 실제로 응답하는지 확인한다.

실행:
    python scripts/demo_smoke_check.py https://<배포도메인>
"""
from __future__ import annotations

import os
import sys
import time

import requests
from dotenv import load_dotenv

# 판정 API 점검(check_judge_api)은 실제 시연 부지가 아니라 "판정 파이프라인이
# 어떤 좌표로든 살아서 응답하는지"만 확인하는 별개 관심사라 고정 좌표를 그대로 둔다
# (전남 권역 안이면 충분 - demo_sites 시드 좌표와 결합될 이유가 없다). 반면 필지 조회
# 점검(check_parcel)은 아래에서 demo_sites 테이블의 실제 좌표를 읽어 쓰도록 바뀌었다.
DEMO_LON, DEMO_LAT = 126.123456, 34.812345


def summarize(results: list[dict]) -> tuple[bool, str]:
    if not results:
        # 점검이 한 건도 안 돌았다고 "정상"으로 보고하면, 검증이 아예 안 됐다는
        # 사실이 감춰진다 - 이는 실패를 보고하는 것보다 더 위험하므로 실패로 취급한다
        return False, "확인한 항목이 없다 - 점검이 실행되지 않았다"
    lines = []
    ok_all = True
    for r in results:
        mark = "정상" if r["ok"] else "실패"
        if not r["ok"]:
            ok_all = False
        lines.append(f"[{mark}] {r['name']}: {r['detail']}")
    return ok_all, "\n".join(lines)


def check_judge_api(base_url: str) -> dict:
    url = (f"{base_url.rstrip('/')}/api/site_judge"
           f"?lon={DEMO_LON}&lat={DEMO_LAT}&project_type=태양광&capacity_kw=3000")
    started = time.time()
    try:
        res = requests.get(url, timeout=15)
        elapsed = time.time() - started
        # HTTP 200만으로는 부족하다 - 파이프라인은 돌았지만 table이 비어 있으면
        # 시연에서 쓸 수 있는 결과가 아니므로 "살아있다"로 볼 수 없다
        ok = res.status_code == 200 and bool(res.json().get("table"))
        return {"name": "판정 API", "ok": ok, "detail": f"{elapsed:.1f}초, HTTP {res.status_code}"}
    except Exception as e:
        return {"name": "판정 API", "ok": False, "detail": str(e)}


def check_parcel(supabase_url: str, key: str) -> dict:
    # DEMO_LON/DEMO_LAT(하드코딩된 자리표시자)을 그대로 쓰면, HANDOVER.md가 시키는 대로
    # demo_sites_seed.sql의 좌표를 진짜 시연 좌표로 바꿔도 이 점검은 여전히 옛 자리표시자
    # 지점만 찔러본다 - 그러면 "필지 조회" 항목이 영원히 실패로 나오고, 운영자는 그 줄을
    # "원래 저런 것"으로 여기고 무시하는 법을 학습하게 된다. 그래서 매번 demo_sites
    # 테이블에서 실제로 등록된 첫 시연 부지의 좌표를 읽어와 그 지점을 검증한다 - 이게
    # 바로 시연이 실제로 의존하는 좌표이기 때문이다.
    try:
        site_res = requests.get(
            supabase_url.rstrip("/") + "/rest/v1/demo_sites?select=lon,lat&order=display_ord&limit=1",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=15,
        )
        sites = site_res.json() if site_res.status_code == 200 else []
        if not sites:
            return {"name": "필지 조회", "ok": False,
                    "detail": "demo_sites에 등록된 시연 부지가 없어 검증할 좌표를 구하지 못했다"}
        lon, lat = sites[0]["lon"], sites[0]["lat"]
    except Exception as e:
        return {"name": "필지 조회", "ok": False, "detail": f"demo_sites 조회 실패: {e}"}

    try:
        res = requests.post(
            supabase_url.rstrip("/") + "/rest/v1/rpc/parcel_at",
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
            # 임의의 값이 아니라 실제 시연 화면(public/index.html의 fetchParcel)이
            # parcel_at을 호출할 때 쓰는 반경과 동일하게 맞춰, 시연이 실제로 의존할
            # 허용오차를 그대로 검증한다
            json={"in_lon": lon, "in_lat": lat, "radius_m": 50},
            timeout=15,
        )
        rows = res.json() if res.status_code == 200 else []
        return {"name": "필지 조회", "ok": bool(rows), "detail": f"{len(rows)}건 (지점: {lon}, {lat})"}
    except Exception as e:
        return {"name": "필지 조회", "ok": False, "detail": str(e)}


def check_demo_sites(supabase_url: str, key: str) -> dict:
    try:
        res = requests.get(
            supabase_url.rstrip("/") + "/rest/v1/demo_sites?select=site_name",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=15,
        )
        rows = res.json() if res.status_code == 200 else []
        # 몇 건이 등록돼 있는지는 이 점검의 관심사가 아니다 - 안전망 목록 테이블에
        # 접근 가능하고 비어있지 않은지만 확인하면 되므로 정확한 개수를 요구하지 않는다
        return {"name": "시연용 부지", "ok": len(rows) >= 1, "detail": f"{len(rows)}건"}
    except Exception as e:
        return {"name": "시연용 부지", "ok": False, "detail": str(e)}


def main() -> None:
    if len(sys.argv) < 2:
        print("사용법: python scripts/demo_smoke_check.py https://<배포도메인>")
        raise SystemExit(1)
    load_dotenv()
    base = sys.argv[1]
    sb_url = os.environ.get("SUPABASE_URL", "")
    sb_key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")

    results = [check_judge_api(base), check_parcel(sb_url, sb_key),
               check_demo_sites(sb_url, sb_key)]
    ok, text = summarize(results)
    print(text)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
