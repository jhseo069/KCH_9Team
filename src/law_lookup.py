"""
법령 조문 조회: 국가법령정보센터(law.go.kr) Open API로 법령명+조문번호에 해당하는
조문 원문을 실시간으로 가져온다.

주의: OC=test는 등록 없이 쓸 수 있는 임시/데모 접근으로 확인됐다. 실사용 시에는
open.law.go.kr에서 본인 이메일로 무료 등록한 OC로 교체할 것을 권장한다(.env의
LAW_GO_KR_OC로 오버라이드 가능).
"""
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

LAW_SEARCH_URL = "https://www.law.go.kr/DRF/lawSearch.do"
LAW_SERVICE_URL = "https://www.law.go.kr/DRF/lawService.do"
DEFAULT_OC = os.getenv("LAW_GO_KR_OC", "test")

_ARTICLE_NO_PATTERN = re.compile(r"제(\d+)조(?:의\s*(\d+))?")
_APPENDIX_NO_PATTERN = re.compile(r"별표\s*(\d+)")


def extract_article_number(law_article: str) -> str | None:
    """'제76조', '국토계획법 제8조' 같은 표기에서 조문번호만 추출. '별표20' 등은 None."""
    match = _ARTICLE_NO_PATTERN.search(law_article or "")
    return match.group(1) if match else None


def extract_article_parts(law_article: str) -> tuple[str, str | None] | None:
    """'제27조의3' -> ('27', '3'), '제76조' -> ('76', None), '별표20' -> None.

    law.go.kr XML은 가지번호 조문을 <조문번호>27</조문번호><조문가지번호>3</조문가지번호>로
    표현한다. 조문번호만 비교하면 제27조와 제27조의2·의3이 전부 같은 조문으로 취급된다.
    """
    match = _ARTICLE_NO_PATTERN.search(law_article or "")
    if match is None:
        return None
    return match.group(1), match.group(2)


def extract_appendix_number(law_article: str) -> str | None:
    """'별표20', '별표 20' 같은 표기에서 별표번호만 추출. '제76조' 등은 None."""
    match = _APPENDIX_NO_PATTERN.search(law_article or "")
    return match.group(1) if match else None


def _paragraph_full_text(hang: ET.Element) -> str:
    """항 하나의 전체 텍스트: 항내용 + 그 아래 중첩된 호/목 내용까지 순서대로 포함"""
    parts = []
    hang_text = hang.findtext("항내용")
    if hang_text:
        parts.append(hang_text)
    for ho in hang.findall("호"):
        ho_text = ho.findtext("호내용")
        if ho_text:
            parts.append(ho_text)
        for mok in ho.findall("목"):
            mok_text = mok.findtext("목내용")
            if mok_text:
                parts.append(mok_text)
    return "\n".join(parts)


def parse_article(xml_text: str, article_no: str, branch_no: str | None = None) -> dict | None:
    """법령 전문 XML에서 article_no(+가지번호)에 해당하는 조문만 추출.
    각 항에 중첩된 호ㆍ목(세부 목록)까지 포함해 누락 없이 가져온다."""
    root = ET.fromstring(xml_text)
    effective_date = root.findtext(".//기본정보/시행일자")

    for unit in root.findall(".//조문/조문단위"):
        title = unit.findtext("조문제목")
        if title is None:
            continue  # 조문제목이 없으면 장/절 헤더 - 실제 조문이 아님
        if unit.findtext("조문번호") != article_no:
            continue
        if (unit.findtext("조문가지번호") or None) != branch_no:
            continue

        paragraphs = [_paragraph_full_text(p) for p in unit.findall("항")]
        paragraphs = [p for p in paragraphs if p]
        text = "\n".join(paragraphs) if paragraphs else (unit.findtext("조문내용") or "")

        return {"article_title": title, "text": text, "effective_date": effective_date}

    return None


def _clean_appendix_text(raw_text: str) -> str:
    """별표 본문은 HWP 고정폭 서식이 <![CDATA[]]> 줄 단위로 그대로 들어온다.
    줄 끝 공백을 지우고 연속된 빈 줄은 하나로 줄인다."""
    lines = [line.rstrip() for line in raw_text.split("\n")]
    cleaned = []
    prev_blank = False
    for line in lines:
        is_blank = line == ""
        if is_blank and prev_blank:
            continue
        cleaned.append(line)
        prev_blank = is_blank
    return "\n".join(cleaned).strip()


def parse_appendix(xml_text: str, appendix_no: str) -> dict | None:
    """법령 전문 XML에서 별표번호(가지번호 00)에 해당하는 별표 제목·본문을 추출"""
    root = ET.fromstring(xml_text)
    effective_date = root.findtext(".//기본정보/시행일자")
    padded_no = appendix_no.zfill(4)

    for unit in root.findall(".//별표/별표단위"):
        if unit.findtext("별표번호") != padded_no:
            continue
        if unit.findtext("별표가지번호") not in (None, "00"):
            continue  # 가지번호 있는 세부 별표(예: 별표1의2)는 별도 처리 대상 - 현재 범위 밖

        title = unit.findtext("별표제목")
        raw_text = unit.findtext("별표내용") or ""

        return {"article_title": title, "text": _clean_appendix_text(raw_text), "effective_date": effective_date}

    return None


def search_law_mst(law_name: str, oc: str = DEFAULT_OC) -> dict:
    """법령명으로 MST(법령일련번호) 검색. 이름이 정확히 일치하는 결과를 우선한다."""
    try:
        res = requests.get(LAW_SEARCH_URL, params={
            "OC": oc, "target": "law", "type": "XML", "query": law_name,
        }, timeout=10)
        res.encoding = "utf-8"
        root = ET.fromstring(res.text)
    except Exception as e:
        return {"status": "no_data", "reason": f"법령 검색 실패: {e}"}

    exact = None
    for law in root.findall("law"):
        name = law.findtext("법령명한글")
        if name == law_name:
            exact = law
            break
    chosen = exact if exact is not None else root.find("law")
    if chosen is None:
        return {"status": "no_data", "reason": f"'{law_name}' 법령을 찾을 수 없음"}

    return {"status": "ok", "mst": chosen.findtext("법령일련번호"), "matched_name": chosen.findtext("법령명한글")}


def fetch_law_xml(mst: str, oc: str = DEFAULT_OC) -> str:
    res = requests.get(LAW_SERVICE_URL, params={
        "OC": oc, "target": "law", "MST": mst, "type": "XML",
    }, timeout=15)
    res.encoding = "utf-8"
    return res.text


def _lookup(law_name: str, oc: str, parse_fn, not_found_reason: str) -> dict:
    """법령 검색 -> 원문 조회 -> parse_fn으로 파싱하는 공통 흐름. 실패는 예외 대신 status: no_data로 반환."""
    search_result = search_law_mst(law_name, oc)
    if search_result["status"] != "ok":
        return search_result

    try:
        xml_text = fetch_law_xml(search_result["mst"], oc)
    except Exception as e:
        return {"status": "no_data", "reason": f"조회 실패: {e}"}

    try:
        parsed = parse_fn(xml_text)
    except ET.ParseError as e:
        return {"status": "no_data", "reason": f"응답 파싱 실패: {e}"}

    if parsed is None:
        return {"status": "no_data", "reason": not_found_reason}

    return {
        "status": "ok",
        "text": parsed["text"],
        "article_title": parsed["article_title"],
        "effective_date": parsed["effective_date"],
        # OC는 개인 접근키이므로 저장/노출되는 URL에는 절대 포함하지 않는다(I6) -
        # 이 URL은 draft CSV -> setback_table.csv -> 웹앱 출처 링크로 그대로 흘러간다.
        "source_url": f"{LAW_SERVICE_URL}?target=law&MST={search_result['mst']}&type=HTML",
    }


def search_ordinance_mst(ordinance_name: str, oc: str = DEFAULT_OC) -> dict:
    """자치법규(조례)명으로 MST(자치법규일련번호) 검색. 이름이 정확히 일치하는 결과를 우선한다."""
    try:
        res = requests.get(LAW_SEARCH_URL, params={
            "OC": oc, "target": "ordin", "type": "XML", "query": ordinance_name,
        }, timeout=10)
        res.encoding = "utf-8"
        root = ET.fromstring(res.text)
    except Exception as e:
        return {"status": "no_data", "reason": f"자치법규 검색 실패: {e}"}

    exact = None
    for law in root.findall("law"):
        name = law.findtext("자치법규명")
        if name == ordinance_name:
            exact = law
            break
    chosen = exact if exact is not None else root.find("law")
    if chosen is None:
        return {"status": "no_data", "reason": f"'{ordinance_name}' 자치법규를 찾을 수 없음"}

    return {"status": "ok", "mst": chosen.findtext("자치법규일련번호"), "matched_name": chosen.findtext("자치법규명")}


def fetch_ordinance_xml(mst: str, oc: str = DEFAULT_OC) -> str:
    res = requests.get(LAW_SERVICE_URL, params={
        "OC": oc, "target": "ordin", "MST": mst, "type": "XML",
    }, timeout=15)
    res.encoding = "utf-8"
    return res.text


def parse_ordinance_article(xml_text: str, article_no: str, branch_no: str | None = None) -> dict | None:
    """자치법규 전문 XML에서 article_no(+가지번호)에 해당하는 조문을 추출.
    국가법령과 스키마가 달라 별도 구현 - 항/호 구분 없이 조내용 하나에 전문이 들어 있고,
    조문번호는 '조번호*100 + 가지번호'를 6자리로 0-패딩한 형식이다
    (예: 제27조 -> '002700', 제17조의4 -> '001704'). scripts/collect_setback_draft.py의
    _article_label()이 divmod(n, 100)으로 이 인코딩을 반대로 복원하고 있으므로, 여기서도
    같은 관계를 사용한다. 가지번호를 무시하면 제17조 조회가 제17조의4 조문과 뒤섞인다.
    조문여부가 'Y'인 것만 실제 조문(장/절 헤더는 'N')이다."""
    root = ET.fromstring(xml_text)
    effective_date = root.findtext(".//자치법규기본정보/시행일자")
    branch = int(branch_no) if branch_no else 0
    padded_no = f"{int(article_no) * 100 + branch:06d}"

    for jo in root.findall(".//조문/조"):
        if jo.findtext("조문번호") != padded_no:
            continue
        if jo.findtext("조문여부") != "Y":
            continue  # 장/절 헤더 - 실제 조문이 아님

        title = jo.findtext("조제목")
        text = (jo.findtext("조내용") or "").strip()
        return {"article_title": title, "text": text, "effective_date": effective_date}

    return None


def lookup_ordinance_text(ordinance_name: str, law_article: str, oc: str = DEFAULT_OC) -> dict:
    """자치법규(조례)명+조문번호 표기 -> 조문 원문 조회. 국가법령과 API 스키마가 달라 별도 구현.

    국가법령 경로(lookup_article_text)처럼 가지번호를 구분한다(I4) - extract_article_number만
    쓰면 '제17조의4'가 '17'로 뭉개져 제17조 본문이 조용히 반환된다."""
    parts = extract_article_parts(law_article)
    if parts is None:
        return {"status": "no_data", "reason": f"조문번호를 해석할 수 없음: '{law_article}'"}
    article_no, branch_no = parts
    label = f"제{article_no}조" + (f"의{branch_no}" if branch_no else "")

    search_result = search_ordinance_mst(ordinance_name, oc)
    if search_result["status"] != "ok":
        return search_result

    try:
        xml_text = fetch_ordinance_xml(search_result["mst"], oc)
    except Exception as e:
        return {"status": "no_data", "reason": f"조회 실패: {e}"}

    try:
        parsed = parse_ordinance_article(xml_text, article_no, branch_no)
    except ET.ParseError as e:
        return {"status": "no_data", "reason": f"응답 파싱 실패: {e}"}

    if parsed is None:
        return {"status": "no_data", "reason": f"{ordinance_name}에서 {label}를 찾을 수 없음"}

    return {
        "status": "ok",
        "text": parsed["text"],
        "article_title": parsed["article_title"],
        "effective_date": parsed["effective_date"],
        # OC는 개인 접근키이므로 저장/노출되는 URL에는 절대 포함하지 않는다(I6).
        "source_url": f"{LAW_SERVICE_URL}?target=ordin&MST={search_result['mst']}&type=HTML",
    }


def lookup_article_text(law_name: str, law_article: str, oc: str = DEFAULT_OC) -> dict:
    """법령명+조문/별표 표기 -> 원문 전체 조회. '별표NN'이면 별표를, 그 외엔 조문을 조회한다."""
    appendix_no = extract_appendix_number(law_article)
    if appendix_no is not None:
        return _lookup(law_name, oc, lambda xml: parse_appendix(xml, appendix_no),
                        not_found_reason=f"{law_name}에서 별표{appendix_no}를 찾을 수 없음")

    parts = extract_article_parts(law_article)
    if parts is None:
        return {"status": "no_data", "reason": f"조문번호를 해석할 수 없음: '{law_article}'"}

    article_no, branch_no = parts
    label = f"제{article_no}조" + (f"의{branch_no}" if branch_no else "")
    return _lookup(law_name, oc, lambda xml: parse_article(xml, article_no, branch_no),
                    not_found_reason=f"{law_name}에서 {label}를 찾을 수 없음")
