from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from law_lookup import (
    parse_article, extract_article_number, extract_article_parts, parse_appendix, extract_appendix_number,
    parse_ordinance_article,
)

FIXTURE = (Path(__file__).resolve().parent / "fixtures" / "sample_law.xml").read_text(encoding="utf-8")
APPENDIX_FIXTURE = (Path(__file__).resolve().parent / "fixtures" / "sample_appendix.xml").read_text(encoding="utf-8")
ORDINANCE_FIXTURE = (Path(__file__).resolve().parent / "fixtures" / "sample_ordinance.xml").read_text(encoding="utf-8")


def test_parse_article_extracts_title_and_full_text():
    result = parse_article(FIXTURE, "76")

    assert result is not None
    assert result["article_title"] == "용도지역 및 용도지구에서의 건축물의 건축 제한 등"
    assert "제36조에 따라 지정된 용도지역" in result["text"]
    assert "제37조에 따라 지정된 용도지구" in result["text"]
    assert result["effective_date"] == "20260701"


def test_parse_article_returns_none_when_article_not_found():
    result = parse_article(FIXTURE, "999")

    assert result is None


def test_parse_article_skips_chapter_heading_with_same_number():
    """조문제목이 없는 장(챕터) 헤더는 조문으로 취급하지 않는다."""
    result = parse_article(FIXTURE, "1")

    assert result is None


def test_parse_article_includes_nested_ho_items_within_paragraph():
    """항 아래 중첩된 호(예: 제76조⑤의 각 호) 내용이 누락되지 않고 포함되어야 한다."""
    result = parse_article(FIXTURE, "76")

    assert "다음 각 호의 어느 하나에 해당하는 경우" in result["text"]
    assert "취락지구의 지정목적 범위에서 대통령령으로 따로 정한다" in result["text"]
    assert "농공단지에서는 같은 법에서 정하는 바에 따른다" in result["text"]


def test_extract_article_number_parses_standard_format():
    assert extract_article_number("제76조") == "76"


def test_extract_article_number_parses_with_surrounding_text():
    assert extract_article_number("국토계획법 제8조") == "8"


def test_extract_article_number_returns_none_for_unrecognizable_format():
    assert extract_article_number("별표20") is None


def test_extract_appendix_number_parses_standard_format():
    assert extract_appendix_number("별표20") == "20"


def test_extract_appendix_number_parses_with_spacing():
    assert extract_appendix_number("별표 20") == "20"


def test_extract_appendix_number_returns_none_for_article_format():
    assert extract_appendix_number("제76조") is None


def test_parse_appendix_extracts_title_and_cleaned_text():
    result = parse_appendix(APPENDIX_FIXTURE, "20")

    assert result is not None
    assert result["article_title"] == "계획관리지역안에서 건축할 수 없는 건축물(제71조제1항제19호 관련)"
    assert "건축할 수 없는 건축물" in result["text"]
    assert "4층을 초과하는 모든 건축물" in result["text"]
    assert result["effective_date"] == "20260908"


def test_parse_appendix_strips_trailing_whitespace_and_collapses_blank_lines():
    result = parse_appendix(APPENDIX_FIXTURE, "20")

    assert "                                                                                  \n" not in result["text"]
    assert "\n\n\n" not in result["text"]


def test_parse_appendix_returns_none_when_number_not_found():
    result = parse_appendix(APPENDIX_FIXTURE, "999")

    assert result is None


def test_parse_ordinance_article_extracts_title_and_text():
    result = parse_ordinance_article(ORDINANCE_FIXTURE, "27")

    assert result is not None
    assert result["article_title"] == "용도지역 안에서의 건축제한"
    assert "영 제71조, 영 제78조제1항" in result["text"]
    assert "제2종 일반주거지역 안에서 건축할 수 있는 건축물 : 별표 6" in result["text"]
    assert result["effective_date"] == "20251229"


def test_parse_ordinance_article_skips_chapter_heading():
    """조문여부가 N인 장(챕터) 헤더는 조문으로 취급하지 않는다."""
    result = parse_ordinance_article(ORDINANCE_FIXTURE, "0")

    assert result is None


def test_parse_ordinance_article_returns_none_when_not_found():
    result = parse_ordinance_article(ORDINANCE_FIXTURE, "999")

    assert result is None


def test_parse_article_with_branch_number_returns_branch_article():
    result = parse_article(FIXTURE, "76", branch_no="2")

    assert result is not None
    assert result["article_title"] == "가지번호 조문 테스트용 제목"
    assert "제76조의2의 내용" in result["text"]


def test_parse_article_without_branch_number_skips_branch_articles():
    result = parse_article(FIXTURE, "76")

    assert result["article_title"] == "용도지역 및 용도지구에서의 건축물의 건축 제한 등"
    assert "제76조의2의 내용" not in result["text"]


def test_extract_article_parts_splits_branch_number():
    assert extract_article_parts("제27조의3") == ("27", "3")
    assert extract_article_parts("제76조") == ("76", None)
    assert extract_article_parts("별표20") is None
