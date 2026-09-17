import importlib.util
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))


def load_api(monkeypatch=None):
    spec = importlib.util.spec_from_file_location("site_judge_api", BASE_DIR / "api" / "site_judge.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_config_includes_supabase_url_and_publishable_key(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "pub-key")
    api = load_api()

    config = api.build_config()

    assert config["supabase_url"] == "https://example.supabase.co"
    assert config["supabase_key"] == "pub-key"


def test_config_never_exposes_the_secret_key(monkeypatch):
    """secret 키는 RLS를 무시하는 전권 키다. 브라우저로 나가면 누구나 데이터를 지울 수 있다."""
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "super-secret-value")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "pub-key")
    api = load_api()

    config = api.build_config()

    assert "super-secret-value" not in str(config)


def test_coordinates_alone_are_enough_to_judge():
    """지도 클릭은 주소 문자열 없이 좌표만 보낸다. 주소를 필수로 두면 클릭 판정이 막힌다."""
    api = load_api()

    assert api.missing_input_reason({"lon": ["126.4"], "lat": ["34.8"]}) is None


def test_request_without_address_and_without_coordinates_is_rejected():
    api = load_api()

    reason = api.missing_input_reason({})

    assert reason is not None
    assert "주소" in reason


def test_law_query_param_is_routed_to_the_law_handler():
    """Vercel의 제로 설정 Python 빌더는 /api/site_judge 로만 매핑한다 - 서브패스(/law)는
    404가 되므로 쿼리 파라미터로 분기해야 실제 배포에서 동작한다."""
    api = load_api()

    assert api.route_for("/api/site_judge?law=1&law_name=x") == "law"
    assert api.route_for("/api/site_judge?address=x") == "judge"
    assert api.route_for("/api/site_judge") == "judge"


def test_address_value_containing_the_text_law_still_routes_to_judge():
    """law 파라미터의 '값'이 아니라 '존재'로 분기해야 한다 - 주소에 law라는 문자열이
    섞여 있어도(예: 부분 문자열 매칭이었다면 오분기했을 케이스) judge로 가야 한다."""
    api = load_api()

    assert api.route_for("/api/site_judge?address=law") == "judge"


def test_law_lookup_returns_article_text(monkeypatch):
    api = load_api()
    monkeypatch.setattr(api, "lookup_article_text",
                        lambda law_name, law_article: {
                            "status": "ok", "text": "① 조문 본문",
                            "article_title": "용도지역에서의 건축 제한",
                            "effective_date": "20260101",
                            "source_url": "https://www.law.go.kr/...",
                        })

    result = api.fetch_law({"law_name": ["국토의 계획 및 이용에 관한 법률"], "law_article": ["제76조"]})

    assert result["status"] == "ok"
    assert result["text"] == "① 조문 본문"


def test_law_lookup_without_parameters_is_rejected():
    api = load_api()

    result = api.fetch_law({})

    assert result["status"] == "no_data"


def test_law_response_never_contains_the_oc_key(monkeypatch):
    """OC는 개인 접근키다. 응답 URL에 섞여 나가면 브라우저에 그대로 노출된다."""
    api = load_api()
    monkeypatch.setattr(api, "lookup_article_text",
                        lambda law_name, law_article: {
                            "status": "ok", "text": "t", "article_title": "a",
                            "effective_date": "20260101",
                            "source_url": "https://www.law.go.kr/DRF/lawService.do?target=law&MST=1&type=HTML",
                        })

    result = api.fetch_law({"law_name": ["법"], "law_article": ["제1조"]})

    assert "OC=" not in result["source_url"]


def _strict_json_loads(body):
    """json.loads는 기본적으로 NaN/Infinity 같은 비표준 상수를 관대하게 받아준다
    (Python requests.json()도 내부적으로 이걸 써서 그동안 bare NaN 버그를 못 잡았다).
    브라우저 JSON.parse가 실제로 거부하는 것과 같은 엄격함을 흉내내려면 parse_constant로
    막아야 한다."""
    def _reject(constant):
        raise ValueError(f"non-standard JSON constant: {constant}")
    return json.loads(body, parse_constant=_reject)


def test_dataframe_to_json_records_is_strict_json_safe():
    """judge()가 만든 행(note 없음)과 이격거리 행(note 있음)이 섞이면 pandas가 없는
    값을 NaN으로 채운다 - 그 NaN이 bare로 직렬화되면 브라우저에서 파싱이 깨진다."""
    api = load_api()
    rows = [
        {"raw_text": "용도지역", "status": "비저촉", "law_excerpt": "제76조", "source_url": "http://x"},
        {"raw_text": "이격거리(조례)", "status": "판정불가", "law_excerpt": "제27조의3",
         "source_url": "http://y", "note": "판정 기준일 2026-09-18"},
    ]
    df = api.generate_output_table(rows)

    records = api.dataframe_to_json_records(df)
    body = json.dumps(records, ensure_ascii=False, allow_nan=False)

    parsed = _strict_json_loads(body)  # NaN이 섞여 있었다면 여기서 raise
    assert len(parsed) == 2


def test_dataframe_to_json_records_uses_none_not_nan_string_for_missing_note():
    api = load_api()
    rows = [{"raw_text": "용도지역", "status": "비저촉", "law_excerpt": "제76조", "source_url": "http://x"}]
    df = api.generate_output_table(rows)

    records = api.dataframe_to_json_records(df)

    assert records[0]["비고"] is None
    assert records[0]["비고"] != "nan"
