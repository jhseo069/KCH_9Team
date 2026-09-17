from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import law_lookup
from law_lookup import (
    parse_article, extract_article_number, extract_article_parts, parse_appendix, extract_appendix_number,
    parse_ordinance_article, lookup_article_text, lookup_ordinance_text,
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


def test_parse_article_skips_branch_article_even_when_it_comes_first():
    """역순 배치에서도 가지번호를 건너뛰고 기본 조문을 반환해야 한다.
    제80조의2가 제80조보다 먼저 나오는 픽스처에서 제80조를 요청하면
    제80조의2를 스킵하고 제80조를 반환해야 한다."""
    result = parse_article(FIXTURE, "80")

    assert result["article_title"] == "역순 테스트용 제80조 제목"
    assert "제80조의2의 내용" not in result["text"]
    assert "제80조의 내용이며" in result["text"]


# ---------------------------------------------------------------------------
# I4. 조례 조문번호도 가지번호를 구분해야 한다 (제17조 vs 제17조의4).
# ---------------------------------------------------------------------------

def test_parse_ordinance_article_distinguishes_branch_number_from_base_article():
    base = parse_ordinance_article(ORDINANCE_FIXTURE, "17")
    branch = parse_ordinance_article(ORDINANCE_FIXTURE, "17", branch_no="4")

    assert base is not None
    assert branch is not None
    assert base["text"] != branch["text"]
    assert "제17조의4" not in base["text"]
    assert "가지번호 조문이며" in branch["text"]


def test_parse_ordinance_article_without_branch_no_still_finds_base_article():
    result = parse_ordinance_article(ORDINANCE_FIXTURE, "27")

    assert result is not None
    assert result["article_title"] == "용도지역 안에서의 건축제한"


# ---------------------------------------------------------------------------
# I6. 반환되는 source_url에 OC(접근키) 파라미터가 들어가면 안 된다.
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, text):
        self.text = text
        self.encoding = "utf-8"


def test_lookup_article_text_source_url_has_no_oc_param(monkeypatch):
    search_xml = (
        "<LawSearch><law><법령명한글>테스트법</법령명한글>"
        "<법령일련번호>1</법령일련번호></law></LawSearch>"
    )

    def fake_get(url, params=None, timeout=None):
        if params.get("target") == "law" and "query" in params:
            return _FakeResponse(search_xml)
        return _FakeResponse(FIXTURE)

    monkeypatch.setattr(law_lookup.requests, "get", fake_get)

    result = lookup_article_text("테스트법", "제76조", oc="realsecretkey")

    assert result["status"] == "ok"
    assert "OC=" not in result["source_url"]
    assert "realsecretkey" not in result["source_url"]


def test_lookup_ordinance_text_source_url_has_no_oc_param(monkeypatch):
    search_xml = (
        "<LawSearch><law><자치법규명>목포시 도시계획 조례</자치법규명>"
        "<자치법규일련번호>1</자치법규일련번호></law></LawSearch>"
    )

    def fake_get(url, params=None, timeout=None):
        if params.get("target") == "ordin" and "query" in params:
            return _FakeResponse(search_xml)
        return _FakeResponse(ORDINANCE_FIXTURE)

    monkeypatch.setattr(law_lookup.requests, "get", fake_get)

    result = lookup_ordinance_text("목포시 도시계획 조례", "제27조", oc="realsecretkey")

    assert result["status"] == "ok"
    assert "OC=" not in result["source_url"]
    assert "realsecretkey" not in result["source_url"]


def test_lookup_ordinance_text_is_branch_aware(monkeypatch):
    """제17조의4 조회가 제17조 본문을 잘못 반환하던 버그(I4)의 재발 방지."""
    search_xml = (
        "<LawSearch><law><자치법규명>목포시 도시계획 조례</자치법규명>"
        "<자치법규일련번호>1</자치법규일련번호></law></LawSearch>"
    )

    def fake_get(url, params=None, timeout=None):
        if params.get("target") == "ordin" and "query" in params:
            return _FakeResponse(search_xml)
        return _FakeResponse(ORDINANCE_FIXTURE)

    monkeypatch.setattr(law_lookup.requests, "get", fake_get)

    result = lookup_ordinance_text("목포시 도시계획 조례", "제17조의4", oc="test")

    assert result["status"] == "ok"
    assert "가지번호 조문이며" in result["text"]
