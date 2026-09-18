# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ingest.parcel_contract import split_regulations, parcel_record_to_row


def test_쉼표로_구분된_규제를_항목별로_쪼갠다():
    assert split_regulations("가축사육제한구역, 문화재보호구역") == [
        "가축사육제한구역", "문화재보호구역"
    ]


def test_줄바꿈도_구분자로_본다():
    assert split_regulations("가축사육제한구역\n문화재보호구역") == [
        "가축사육제한구역", "문화재보호구역"
    ]


def test_괄호_안의_쉼표는_쪼개지_않는다():
    # "(전부, 일부)" 같은 표기를 쪼개면 없는 규제 항목이 생긴다
    assert split_regulations("가축사육제한구역(일부, 제한)") == [
        "가축사육제한구역(일부, 제한)"
    ]


def test_빈값과_None은_빈_배열():
    assert split_regulations(None) == []
    assert split_regulations("") == []
    assert split_regulations("  ,  ") == []


def test_레코드를_적재용_행으로_바꾼다():
    record = {
        "pnu": "1287040037101520000",
        "소재지": "전남 신안군 안좌면 마명리",
        "지번": "152",
        "지목": "전",
        "면적_m2": 2013.0,
        "용도지역": "계획관리지역",
        "용도지구": None,
        "규제사항_원문": "가축사육제한구역",
        "개별공시지가": 12000,
        "조회상태": "성공",
        "실패사유": [],
        "데이터출처": ["등기부등본"],
        "조회시각": "2026-09-09T14:32:02",
    }
    row = parcel_record_to_row(record, lon=126.123456, lat=34.812345)
    assert row["pnu"] == "1287040037101520000"
    assert row["규제사항_원문"] == ["가축사육제한구역"]
    assert row["lon"] == 126.123456
    assert row["lat"] == 34.812345


def test_좌표가_없으면_None으로_둔다():
    # 좌표를 못 구했다고 필지 자체를 버리지 않는다. 지도 역조회만 안 될 뿐이다
    record = {
        "pnu": "1", "소재지": "a", "지번": "1", "지목": None, "면적_m2": None,
        "용도지역": None, "용도지구": None, "규제사항_원문": None,
        "개별공시지가": None, "조회상태": "실패",
        "실패사유": ["#조회실패: PNU 조회 실패 - 주소/지번 확인 필요"],
        "데이터출처": [], "조회시각": "2026-09-09T14:32:02",
    }
    row = parcel_record_to_row(record)
    assert row["lon"] is None and row["lat"] is None
    assert row["규제사항_원문"] == []
    assert row["실패사유"] == ["#조회실패: PNU 조회 실패 - 주소/지번 확인 필요"]
