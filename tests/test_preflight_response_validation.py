"""Nyckelfria regressioner för felaktiga svar; inget verkligt nätverk."""
import io
import json
from unittest.mock import patch

import pytest
from jarvis.memory.preflight import run_preflight


@pytest.mark.parametrize("value", [1, 1.0, False, "false", None, [], {}, "TRUE"])
def test_non_boolean_autonomy_never_enables_runtime(value):
    responses = [io.BytesIO(json.dumps(rows).encode()) for rows in ([{"value": value}], [], [])]
    env = {"SUPABASE_URL": "https://fzmnqvmfilqizzftphbt.supabase.co",
           "SUPABASE_SECRET_KEY": "sb_secret_synthetic_test_only"}
    with patch.dict("os.environ", env, clear=True), patch("urllib.request.urlopen", side_effect=responses):
        status, result = run_preflight()
    assert status != "ok_read_only"
    assert result["checks"]["autonomy"] != "enabled"


@pytest.mark.parametrize("probe", [0, 1, 2])
@pytest.mark.parametrize("invalid", [{"error": "synthetic"}, [None], [1], "unexpected"])
def test_malformed_table_response_fails_closed(probe, invalid):
    bodies = [[{"value": True}], [], []]
    bodies[probe] = invalid
    responses = [io.BytesIO(json.dumps(body).encode()) for body in bodies]
    env = {"SUPABASE_URL": "https://fzmnqvmfilqizzftphbt.supabase.co",
           "SUPABASE_SECRET_KEY": "sb_secret_synthetic_test_only"}
    with patch.dict("os.environ", env, clear=True), patch("urllib.request.urlopen", side_effect=responses):
        status, result = run_preflight()
    assert status != "ok_read_only"
    assert "invalid_response" in result["checks"].values()
