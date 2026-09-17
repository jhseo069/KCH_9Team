import importlib.util
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
