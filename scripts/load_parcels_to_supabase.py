# -*- coding: utf-8 -*-
"""토지조서 파이프라인 산출물을 Supabase parcels 테이블에 적재한다.

이 스크립트는 로컬에서만 실행한다. 등기부등본처럼 클라우드에서 재생성할 수 없는
출처가 섞여 있어서, 웹앱이 실시간으로 대신 만들어낼 수 있는 데이터가 아니다.
(설계문서 §5.2 참고)

실행:
    python scripts/load_parcels_to_supabase.py <토지조서_결과.json>
"""
from __future__ import annotations

import json
import os
import sys

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from ingest.parcel_contract import parcel_record_to_row  # noqa: E402


def build_batches(rows: list[dict], batch_size: int = 500) -> list[list[dict]]:
    return [rows[i:i + batch_size] for i in range(0, len(rows), batch_size)]


def build_rows(records: list[dict]) -> list[dict]:
    """레코드를 적재용 행으로 바꾼다.

    HTTP 요청 이전 단계만 따로 떼어 놓아, 네트워크 없이(테스트에서) 이 스크립트가
    만드는 payload가 upsert_parcels_batch가 기대하는 모양과 맞는지 확인할 수 있게 한다.
    실제 null 안전성 보장 자체는 parcel_record_to_row(ingest/parcel_contract.py)가 한다.
    """
    return [
        parcel_record_to_row(r, lon=r.get("lon"), lat=r.get("lat")) for r in records
    ]


def load_records(
    records: list[dict], supabase_url: str, secret_key: str, batch_size: int = 500
) -> int:
    rows = build_rows(records)

    # lon/lat이 없는 행은 geom이 null로 적재된다. parcel_at()은
    # `where p.geom is not null`로 걸러내므로, 이런 행은 Supabase에 올라가도 앱
    # 화면(필지 탭)에는 영원히 나타나지 않는다 - 그런데 이 스크립트는 "적재 완료:
    # N건"만 찍고 끝나서, 사람이 보기엔 성공한 것처럼 보인다. 강경미 ParcelRecord에는
    # 원래 좌표 필드가 없어(별도 토지조서자동화 프로젝트 산출물) 이 조건이 항상 참일
    # 수 있다 - 조용히 넘어가면 "적재했는데 화면엔 안 보인다"는 문제를 아무도 못 알아챈다.
    missing_coords = sum(1 for r in rows if r.get("lon") is None and r.get("lat") is None)
    if missing_coords > 0:
        print(
            f"경고: {missing_coords}건은 좌표(lon/lat)가 없다 - 이 행들은 Supabase에 "
            "적재되어도 parcel_at()이 geom is not null로 걸러내기 때문에 필지 탭에 "
            "영원히 나타나지 않는다. HANDOVER.md §5-9 참고.",
            file=sys.stderr,
        )

    endpoint = supabase_url.rstrip("/") + "/rest/v1/rpc/upsert_parcels_batch"
    total = 0
    for batch in build_batches(rows, batch_size):
        res = requests.post(
            endpoint,
            headers={
                "apikey": secret_key,
                "Authorization": f"Bearer {secret_key}",
                "Content-Type": "application/json",
            },
            json={"rows": batch},
            timeout=60,
        )
        res.raise_for_status()
        total += int(res.json())
    return total


def main() -> None:
    if len(sys.argv) < 2:
        print("사용법: python scripts/load_parcels_to_supabase.py <토지조서_결과.json>")
        raise SystemExit(1)

    load_dotenv()
    url = os.environ.get("SUPABASE_URL", "")
    secret = os.environ.get("SUPABASE_SECRET_KEY", "")
    if not url or not secret:
        print("SUPABASE_URL 과 SUPABASE_SECRET_KEY 를 .env 에 설정해야 한다")
        raise SystemExit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        records = json.load(f)

    count = load_records(records, url, secret)
    print(f"적재 완료: {count}건")


if __name__ == "__main__":
    main()
