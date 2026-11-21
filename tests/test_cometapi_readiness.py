"""Nyckelfri katalogkontroll: listning är inte samma sak som fungerande modell."""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.error import URLError

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import cometapi_catalog_check  # noqa: E402
from cometapi_catalog_check import check_catalog  # noqa: E402
from jarvis.routing.providers import ProviderCatalog  # noqa: E402


def test_public_catalog_omission_is_a_warning_not_proof_of_outage():
    catalog = ProviderCatalog()
    assert catalog.get("comet_low").base_url == "https://api.cometapi.com/v1"
    assert catalog.get("comet_low").api_key_env == "COMET_API_KEY"
    result = check_catalog({
        "success": True, "total": 2,
        "data": [{"id": "gpt-4o"}, {"id": "gpt-6-luna"}],
    }, catalog)
    assert result["status"] == "catalog_warning"
    assert "gpt-4o-mini" in result["model_ids_not_listed"]
    assert "gpt-4o-mini" in result["active_model_ids_not_listed"]
    assert "gpt-4o" not in result["model_ids_not_listed"]
    assert "Ett olistat alias kan ändå fungera" in result["scope"]


def test_catalog_full_coverage_is_reported_without_auth_claim():
    catalog = ProviderCatalog()
    all_ids = {
        model.id for provider in catalog.providers.values()
        if provider.base_url == "https://api.cometapi.com/v1"
        for model in provider.models
    }
    result = check_catalog({
        "success": True, "data": [{"id": model_id} for model_id in all_ids],
    }, catalog)
    assert result["status"] == "catalog_ok"
    assert result["model_ids_not_listed"] == []
    assert result["active_model_ids_not_listed"] == []
    assert "inte API-nyckel" in result["scope"]


def test_bad_catalog_and_network_failure_never_look_green(monkeypatch, capsys):
    with pytest.raises(ValueError, match="giltig"):
        check_catalog({"success": False, "data": []}, ProviderCatalog())
    with pytest.raises(ValueError, match="ofullständig"):
        check_catalog({"success": True, "total": 314, "data": []}, ProviderCatalog())

    def unavailable(*_args, **_kwargs):
        raise URLError("private-request-parameter")

    monkeypatch.setattr(cometapi_catalog_check, "urlopen", unavailable)
    assert cometapi_catalog_check.main() == 2
    output = capsys.readouterr().out
    assert '"status": "unavailable"' in output
    assert "private-request-parameter" not in output


def test_catalog_warning_returns_distinct_exit_status(monkeypatch, capsys):
    from io import BytesIO

    class Response(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    payload = b'{"success":true,"total":1,"data":[{"id":"gpt-4o"}]}'
    monkeypatch.setattr(cometapi_catalog_check, "urlopen", lambda *_args, **_kwargs: Response(payload))
    assert cometapi_catalog_check.main() == 1
    assert '"status": "catalog_warning"' in capsys.readouterr().out
