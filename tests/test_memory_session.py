"""Testar ren sessionsmodul utan att importera befintlig modellkedja."""
import asyncio
import importlib.util
import io
import json
from pathlib import Path
import sys
import urllib.error
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

path = Path(__file__).resolve().parents[1] / "src/jarvis/memory/session.py"
spec = importlib.util.spec_from_file_location("jarvis_memory_session_test", path)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
T = "11111111-1111-4111-8111-111111111111"
U = "22222222-2222-4222-8222-222222222222"
V = "33333333-3333-4333-8333-333333333333"
TOKEN = "synthetic.user.token"
KEY = "sb_publishable_synthetic_fixture"

@pytest.fixture
def auth(monkeypatch):
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = json.dumps({"id": U, "role": "authenticated"}).encode()
    opener = SimpleNamespace(open=Mock(return_value=response))
    build = Mock(return_value=opener)
    monkeypatch.setattr(m.urllib.request, "build_opener", build)
    return response, opener, build

def verify(**kw):
    args = dict(access_token=TOKEN, requested_tenant_id=T, publishable_key=KEY)
    args.update(kw)
    return m.verify_session(**args)

def test_auth_identity_and_headers(auth):
    response, opener, build = auth
    session = verify()
    request = opener.open.call_args.args[0]
    assert request.full_url == m.ORIGIN + "/auth/v1/user"
    assert request.get_header("Authorization") == "Bearer " + TOKEN
    assert request.get_header("Apikey") == KEY
    assert session.user_id == U and session.tenant_id == T
    assert opener.open.call_count == 1
    assert TOKEN not in repr(session) and KEY not in repr(session)
    assert any(isinstance(h, m._NoRedirect) for h in build.call_args.args)
    assert any(isinstance(h, m.urllib.request.ProxyHandler) and h.proxies == {} for h in build.call_args.args)

@pytest.mark.parametrize("field,value", [
    ("access_token", ""), ("access_token", None),
    ("access_token", "header\ninjection"), ("access_token", "x" * 16385),
    ("requested_tenant_id", "cloud"), ("requested_tenant_id", None),
    ("requested_tenant_id", "00000000-0000-0000-0000-000000000000"),
    ("publishable_key", "sb_secret_not_allowed"),
    ("publishable_key", "sb_publishable_x\n"),
])
def test_invalid_input_never_uses_network(auth, field, value):
    with pytest.raises(m.MemorySessionError): verify(**{field: value})
    auth[1].open.assert_not_called()

@pytest.mark.parametrize("status,code", [(401,"authentication_failed"), (403,"authentication_failed"), (302,"authentication_unavailable"), (500,"authentication_unavailable")])
def test_http_errors_sanitized(auth, status, code):
    auth[1].open.side_effect = urllib.error.HTTPError(m.ORIGIN, status, TOKEN, {}, io.BytesIO(TOKEN.encode()))
    with pytest.raises(m.MemorySessionError) as error: verify()
    assert error.value.code == code
    assert TOKEN not in str(error.value)
    assert auth[1].open.call_count == 1

@pytest.mark.parametrize("error", [TimeoutError(TOKEN), urllib.error.URLError(TOKEN), OSError(TOKEN)])
def test_transport_error(auth, error):
    auth[1].open.side_effect = error
    with pytest.raises(m.MemorySessionError, match="authentication_unavailable"): verify()
    assert auth[1].open.call_count == 1

@pytest.mark.parametrize("body", [b"", b"not json", b"[]", b"null", b"x" * 128001, b'{"id":"cloud","role":"authenticated"}', b'{"role":"authenticated"}', b'{"id":"22222222-2222-4222-8222-222222222222","role":"service_role"}'])
def test_bad_auth_response(auth, body):
    auth[0].read.return_value = body
    with pytest.raises(m.MemorySessionError): verify()

def test_empty_context_denied():
    with pytest.raises(m.MemorySessionError, match="session_required"): m.current_session()

def test_reset_after_exception(auth):
    session = verify()
    with pytest.raises(RuntimeError):
        with m.bind_session(session):
            assert m.current_session() is session
            raise RuntimeError("test")
    with pytest.raises(m.MemorySessionError): m.current_session()

def test_nested_restore(auth):
    a = verify()
    b = m.AuthenticatedMemorySession(T,V,KEY,TOKEN)
    with m.bind_session(a):
        with m.bind_session(b): assert m.current_session() is b
        assert m.current_session() is a
    with pytest.raises(m.MemorySessionError): m.current_session()

def test_parallel_sessions_and_cancellation(auth):
    a = verify()
    b = m.AuthenticatedMemorySession(T,V,KEY,TOKEN)
    async def worker(session):
        with m.bind_session(session):
            await asyncio.sleep(0)
            return m.current_session().user_id
    async def cancelled():
        with m.bind_session(a): raise asyncio.CancelledError()
    async def run():
        assert await asyncio.gather(worker(a), worker(b)) == [U,V]
        with pytest.raises(asyncio.CancelledError): await cancelled()
        with pytest.raises(m.MemorySessionError): m.current_session()
    asyncio.run(run())

def test_wrong_bound_object():
    with pytest.raises(m.MemorySessionError, match="session_invalid"):
        with m.bind_session({"user_id": U}): pass
