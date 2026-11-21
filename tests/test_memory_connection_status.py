"""Read-only Supabase connectivity diagnostics; no real network or secrets."""
import base64
import io
import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis.memory.store import MemoryStore


PROJECT_URL = "https://fzmnqvmfilqizzftphbt.supabase.co"
SECRET_KEY = "sb_" + "secret_synthetic_test_only"


def _jwt(role):
    payload = base64.urlsafe_b64encode(json.dumps({"role": role}).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


def _store(key=SECRET_KEY, url=PROJECT_URL):
    return MemoryStore(supabase_url=url, supabase_key=key)


def test_missing_configuration():
    assert _store(key="").connection_status() == "not_configured"


def test_success_uses_real_read_and_modern_headers():
    with patch("urllib.request.urlopen", return_value=io.BytesIO(b"[]")) as call:
        assert _store().connection_status() == "ok_read_only"
        request = call.call_args.args[0]
        assert request.get_method() == "GET"
        assert "limit=1" in request.full_url
        assert request.get_header("Apikey") == SECRET_KEY
        assert request.get_header("Authorization") is None


def test_unauthorized():
    error = urllib.error.HTTPError(PROJECT_URL, 401, "Unauthorized", {}, None)
    with patch("urllib.request.urlopen", side_effect=error):
        assert _store().connection_status() == "unauthorized_401"


def test_forbidden():
    error = urllib.error.HTTPError(PROJECT_URL, 403, "Forbidden", {}, None)
    with patch("urllib.request.urlopen", side_effect=error):
        assert _store().connection_status() == "forbidden_403"


def test_network_error():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
        assert _store().connection_status() == "network_error"


def test_anon_jwt_rejected_without_network():
    with patch("urllib.request.urlopen") as call:
        assert _store(key=_jwt("anon")).connection_status() == "public_key_rejected"
        call.assert_not_called()


def test_unknown_key_rejected_without_network():
    with patch("urllib.request.urlopen") as call:
        assert _store(key="test-key").connection_status() == "unknown_key_type"
        call.assert_not_called()


def test_wrong_project_rejected_without_network():
    with patch("urllib.request.urlopen") as call:
        assert _store(url="https://example.supabase.co").connection_status() == "unexpected_project_url"
        call.assert_not_called()
