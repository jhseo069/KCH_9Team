# -*- coding: utf-8 -*-
import json
import re
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.load_parcels_to_supabase import build_batches, build_rows


def test_배치_크기대로_나눈다():
    rows = [{"pnu": str(i)} for i in range(1200)]
    batches = build_batches(rows, batch_size=500)
    assert [len(b) for b in batches] == [500, 500, 200]


def test_빈_입력은_빈_배치():
    assert build_batches([], batch_size=500) == []


def test_배치보다_적으면_한_묶음():
    rows = [{"pnu": "1"}, {"pnu": "2"}]
    assert build_batches(rows, batch_size=500) == [rows]


def test_배열_필드는_키가_없거나_None이어도_null이_되지_않는다():
    # upsert_parcels_batch(scripts/supabase_schema_parcels.sql)는 규제사항_원문/실패사유/
    # 데이터출처를 jsonb_array_elements_text로 펼친다. 이 함수는 스칼라(명시적 null 포함)를
    # 받으면 예외를 던지고, 배치 하나가 통째로(insert 전체가) 롤백된다 - 잘못된 필지 1건이
    # 아니라 같은 배치의 정상 필지까지 전부 못 들어간다. 그래서 이 스크립트가 만드는 payload는
    # 키가 아예 없거나 값이 None인 입력에도 반드시 빈 배열을 내보내야 한다.
    records = [
        {  # 세 필드 키 자체가 없는 레코드
            "pnu": "1", "소재지": "a", "지번": "1", "조회상태": "실패",
            "조회시각": "2026-09-09T00:00:00",
        },
        {  # 세 필드가 명시적으로 None인 레코드
            "pnu": "2", "소재지": "b", "지번": "2", "조회상태": "실패",
            "규제사항_원문": None, "실패사유": None, "데이터출처": None,
            "조회시각": "2026-09-09T00:00:00",
        },
    ]
    rows = build_rows(records)

    for row in rows:
        for field in ("규제사항_원문", "실패사유", "데이터출처"):
            assert row[field] == []

    # requests가 실제로 내보내는 것과 같은 직렬화로, 문자 그대로 null이 없는지도 확인한다
    payload_json = json.dumps({"rows": rows}, ensure_ascii=False)
    for field in ("규제사항_원문", "실패사유", "데이터출처"):
        assert not re.search(rf'"{field}"\s*:\s*null', payload_json)
