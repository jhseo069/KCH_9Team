import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pytest

from zoning_codes import (
    UnknownZoneCodeError,
    assert_known_codes,
    is_generic_zone,
    zone_category,
    zone_name,
)


# --- 코드 -> 한글명 ------------------------------------------------------------
# 이름표는 추측이 아니라 원본 SHP의 dgm_nm 필드에서 코드별 최빈값으로 확인한 것이다
# (2026-08-19 기준 전남·광주 KLIP_C_UQ111~115). 근거는 scripts/zoning_codes.py 참고.

def test_zone_name_covers_urban_codes():
    assert zone_name("UQA121") == "제1종일반주거지역"
    assert zone_name("UQA430") == "자연녹지지역"


def test_zone_name_covers_non_urban_codes():
    """비도시지역이 빠져서 실제 태양광 부지가 판정불가로 떨어졌던 문제(2026-09-17)의 회귀 방지."""
    assert zone_name("UQB100") == "계획관리지역"
    assert zone_name("UQB200") == "생산관리지역"
    assert zone_name("UQB300") == "보전관리지역"
    assert zone_name("UQC001") == "농림지역"
    assert zone_name("UQD001") == "자연환경보전지역"


def test_zone_name_returns_none_for_unknown_code():
    assert zone_name("UQZ999") is None


# --- 지도 색상 대분류 ----------------------------------------------------------

@pytest.mark.parametrize("code,expected", [
    ("UQA111", "주거지역"),
    ("UQA130", "주거지역"),
    ("UQA210", "상업지역"),
    ("UQA240", "상업지역"),
    ("UQA320", "공업지역"),
    ("UQA410", "녹지지역"),
    ("UQA430", "녹지지역"),
    ("UQB100", "관리지역"),
    ("UQB300", "관리지역"),
    ("UQC001", "농림·자연환경보전지역"),
    ("UQD001", "농림·자연환경보전지역"),
])
def test_zone_category_groups_by_code_structure(code, expected):
    assert zone_category(code) == expected


def test_zone_category_puts_unspecified_codes_in_its_own_bucket():
    """세부 지역이 정해지지 않은 코드는 색을 주지 않고 중립 분류로 모은다."""
    assert zone_category("UQA01X") == "미분류"
    assert zone_category("UQA000") == "미분류"
    assert zone_category("UQA500") == "미분류"
    assert zone_category("UQB001") == "미분류"
    assert zone_category("UQE000") == "미분류"


def test_zone_category_returns_none_for_unknown_code():
    assert zone_category("UQZ999") is None


# --- 광역/세부 겹침 판별 -------------------------------------------------------

def test_generic_zones_are_flagged():
    """'도시지역'(UQA01X)처럼 세부 용도가 안 정해진 폴리곤은 구체 폴리곤과 좌표가 겹친다.

    겹친 채로 동등하게 두면 점 하나가 2개 폴리곤에 걸려 전부 '판정불가'가 되어버린다.
    광역 폴리곤임을 표시해두고 조회 시 구체 폴리곤을 우선하게 한다.
    """
    assert is_generic_zone("UQA01X") is True
    assert is_generic_zone("UQA000") is True
    assert is_generic_zone("UQA500") is True
    assert is_generic_zone("UQB001") is True
    assert is_generic_zone("UQE000") is True


def test_specific_zones_are_not_generic():
    assert is_generic_zone("UQA121") is False
    assert is_generic_zone("UQB100") is False
    assert is_generic_zone("UQC001") is False


# --- 모르는 코드는 조용히 넘어가지 않는다 --------------------------------------
# 2026-09-17: 빌드가 모르는 코드를 조용히 버리도록 되어 있어서, 레이어 하나만 읽고 있다는
# 사실이 드러나지 않았다. 앞으로는 모르는 코드가 나오면 건수와 함께 즉시 실패시킨다.

def test_assert_known_codes_passes_when_all_codes_known():
    assert_known_codes({"UQA121": 10, "UQB100": 5})


def test_assert_known_codes_raises_and_names_the_unknown_codes():
    with pytest.raises(UnknownZoneCodeError) as excinfo:
        assert_known_codes({"UQA121": 10, "UQZ999": 3, "UQY000": 1})

    message = str(excinfo.value)
    assert "UQZ999" in message
    assert "3" in message
    assert "UQY000" in message


def test_assert_known_codes_ignores_blank_code_but_reports_it():
    """원본에 코드가 빈 행이 실제로 있다(1건). 실패시키지는 않되 조용히 넘기지도 않는다."""
    report = assert_known_codes({"UQA121": 10, "": 1})

    assert report["blank"] == 1
