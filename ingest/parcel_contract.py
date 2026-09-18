# -*- coding: utf-8 -*-
"""강경미 ParcelRecord -> Supabase parcels 적재 행 변환.

규제사항을 쪼개는 규칙이 이 파일의 핵심이다. 서장훈 judge.py는 규제 항목 하나당
한 건(raw_text)을 기대하는데 ParcelRecord는 단일 문자열로 갖고 있어서, 여기서
쪼갠 결과가 곧 판정 단위가 된다. 잘못 쪼개면 없는 규제가 생기거나 있는 규제가
사라진다.

쪼개기 규칙(괄호 밖 쉼표·세미콜론·줄바꿈 기준)이 data/rule_table.csv의
match_keywords와 실제로 맞물리는지는 서장훈 확인 대기 중 — 확인 전까지는
잠정 규칙으로 취급한다.
"""
from __future__ import annotations

import re

# 괄호 밖의 쉼표·줄바꿈·세미콜론만 구분자로 본다. "가축사육제한구역(일부, 제한)"의
# 괄호 안 쉼표까지 쪼개면 "제한)"이라는 존재하지 않는 규제 항목이 만들어진다.
_SPLIT_PATTERN = re.compile(r"[,;\n](?![^(]*\))")


def split_regulations(raw: str | None) -> list[str]:
    if not raw:
        return []
    # 괄호 개수가 안 맞으면 원문이 잘렸거나 손상된 것으로 본다. 이 상태로 정규식을
    # 적용하면 lookahead가 닫는 괄호를 못 찾아 괄호 안 구분자까지 쪼개버리고,
    # 그러면 아무도 쓰지 않은 규제 항목이 생겨난다 — 쪼개지 않고 통째로 반환해
    # 판정 쪽에서 "미매칭"으로 걸러지게 둔다.
    if raw.count("(") != raw.count(")"):
        stripped = raw.strip()
        return [stripped] if stripped else []
    parts = (p.strip() for p in _SPLIT_PATTERN.split(raw))
    return [p for p in parts if p]


def parcel_record_to_row(
    record: dict, lon: float | None = None, lat: float | None = None
) -> dict:
    return {
        "pnu": record.get("pnu"),
        "소재지": record.get("소재지"),
        "지번": record.get("지번"),
        "지목": record.get("지목"),
        "면적_m2": record.get("면적_m2"),
        "용도지역": record.get("용도지역"),
        "용도지구": record.get("용도지구"),
        "규제사항_원문": split_regulations(record.get("규제사항_원문")),
        "개별공시지가": record.get("개별공시지가"),
        "조회상태": record.get("조회상태"),
        "실패사유": list(record.get("실패사유") or []),
        "데이터출처": list(record.get("데이터출처") or []),
        "조회시각": record.get("조회시각"),
        "lon": lon,
        "lat": lat,
    }
