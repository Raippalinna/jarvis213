"""Tests for all required read-only Supabase preflight probes."""
import io
import json
import os
import sys
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis.memory.preflight import run_preflight


PROJECT_URL = "https://fzmnqvmfilqizzftphbt.supabase.co"
SECRET_KEY = "sb_" + "secret_synthetic_test_only"


def _env(**overrides):
    values = {"SUPABASE_URL": PROJECT_URL, "SUPABASE_SECRET_KEY": SECRET_KEY}
    values.update(overrides)
    return patch.dict(os.environ, values, clear=True)


def test_all_required_reads_pass():
    responses = [
        io.BytesIO(json.dumps([{"value": True}]).encode()),
        io.BytesIO(b"[]"),
        io.BytesIO(b"[]"),
    ]
    with _env(), patch("urllib.request.urlopen", side_effect=responses) as network:
        status, result = run_preflight()
    assert status == "ok_read_only"
    assert result["checks"] == {
        "autonomy": "enabled",
        "memory_read": "read_ok_write_untested",
        "audit_read": "read_ok_write_untested",
    }
    assert network.call_count == 3
    for call in network.call_args_list:
        request = call.args[0]
        assert request.get_method() == "GET"
        assert request.get_header("Authorization") is None


def test_autonomy_false_fails():
    responses = [io.BytesIO(b'[{"value": false}]'), io.BytesIO(b"[]"), io.BytesIO(b"[]")]
    with _env(), patch("urllib.request.urlopen", side_effect=responses):
        status, _ = run_preflight()
    assert status == "autonomy_stopped_or_unknown"


def test_unauthorized_fails_without_exposing_body():
    error = urllib.error.HTTPError(PROJECT_URL, 401, "secret", {}, io.BytesIO(b"sensitive"))
    responses = [error, io.BytesIO(b"[]"), io.BytesIO(b"[]")]
    with _env(), patch("urllib.request.urlopen", side_effect=responses):
        status, result = run_preflight()
    assert status == "backend_access_failed"
    assert result["checks"]["autonomy"] == "unauthorized_401"
    assert "sensitive" not in json.dumps(result)


def test_public_key_and_wrong_project_stop_before_network():
    with _env(SUPABASE_SECRET_KEY="sb_" + "publishable_test"), patch("urllib.request.urlopen") as network:
        assert run_preflight()[0] == "public_key_rejected"
        network.assert_not_called()
    with _env(SUPABASE_URL="https://example.supabase.co"), patch("urllib.request.urlopen") as network:
        assert run_preflight()[0] == "unexpected_project_url"
        network.assert_not_called()
