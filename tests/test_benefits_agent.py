import importlib.util
from pathlib import Path
import sys
import pytest

path = Path(__file__).resolve().parents[1] / "src/jarvis/agents/benefits.py"
spec = importlib.util.spec_from_file_location("benefits_under_test", path)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
S = m.Source("https://offers.example/news", "demo")
HOSTS = {"offers.example"}

def test_candidates_are_not_verified_or_savings():
    r = m.scan([S], lambda *_: "<p>Free credits available</p>", HOSTS)
    c = r["candidates"][0]
    assert c["status"] == "unverified"
    assert c["account_eligible"] == "unknown"
    assert c["realized_savings_sek"] == 0
    assert c["requires_approval"] is True

@pytest.mark.parametrize("url", ["http://offers.example", "https://evil.example", "https://offers.example.evil.example", "https://u:p@offers.example", "https://offers.example:444"])
def test_rejected_sources_never_fetch(url):
    def forbidden(*_):
        pytest.fail("fetch must not run")
    r = m.scan([m.Source(url, "demo")], forbidden, HOSTS)
    assert r["errors"] and not r["candidates"]

def test_dedup_and_seen():
    fetch = lambda *_: "<p>Free credits</p><p>Free credits</p>"
    r = m.scan([S, S], fetch, HOSTS)
    assert len(r["candidates"]) == 1
    assert not m.scan([S], fetch, HOSTS, seen=[r["candidates"][0]["id"]])["candidates"]

@pytest.mark.parametrize("body", ["", "<p>Hello</p>", "<script>free credits</script>", "<style>promo</style>"])
def test_empty_or_hidden(body):
    assert not m.scan([S], lambda *_: body, HOSTS)["candidates"]

def test_error_fallback():
    def fetch(url, limit):
        if url.endswith("news"):
            raise TimeoutError("private error details")
        return "<p>Promo credits</p>"
    r = m.scan([S, m.Source("https://offers.example/other", "demo")], fetch, HOSTS)
    assert len(r["candidates"]) == 1
    assert r["errors"] == [{"provider": "demo", "error_type": "TimeoutError"}]

@pytest.mark.parametrize("body", [None, "x" * (m.MAX_BYTES + 1)])
def test_invalid_body(body):
    assert m.scan([S], lambda *_: body, HOSTS)["errors"]

def test_cancelled():
    def forbidden(*_):
        pytest.fail("fetch must not run")
    r = m.scan([S], forbidden, HOSTS, cancelled=lambda: True)
    assert r["cancelled"] and not r["candidates"]

def test_cancel_after_fetch():
    state = {"stop": False}
    def fetch(*_):
        state["stop"] = True
        return "free credits"
    r = m.scan([S], fetch, HOSTS, cancelled=lambda: state["stop"])
    assert r["cancelled"] and not r["candidates"]
