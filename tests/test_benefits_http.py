import importlib.util
from pathlib import Path
from unittest.mock import patch
import pytest

p = Path(__file__).resolve().parents[1] / "src/jarvis/agents/benefits_http.py"
spec = importlib.util.spec_from_file_location("benefits_http_test", p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "192.168.1.1", "0.0.0.0", "224.0.0.1"])
def test_blocks_private_dns(ip):
    addr = [(m.socket.AF_INET, m.socket.SOCK_STREAM, 6, "", (ip, 443))]
    with patch.object(m.socket, "getaddrinfo", return_value=addr), patch.object(m.socket, "socket") as sock:
        with pytest.raises(ValueError):
            m.PublicHTTPSConnection("offers.example").connect()
        sock.assert_not_called()

def test_mixed_dns_rejected():
    addr = [(2, 1, 6, "", (ip, 443)) for ip in ["8.8.8.8", "127.0.0.1"]]
    with patch.object(m.socket, "getaddrinfo", return_value=addr):
        with pytest.raises(ValueError):
            m.PublicHTTPSConnection("offers.example").connect()

@pytest.mark.parametrize("url", ["http://offers.example", "https://other.example", "https://u:p@offers.example", "https://offers.example:444"])
def test_bad_url_no_connection(url):
    with patch.object(m, "PublicHTTPSConnection") as conn:
        with pytest.raises(ValueError):
            m.fetch_public_html(url, 100, allowed_hosts={"offers.example"})
        conn.assert_not_called()

class Response:
    def __init__(self, status=200, body=b"<p>Free credits</p>", mime="text/html", encoding="identity"):
        self.status, self.body, self.mime, self.encoding = status, body, mime, encoding
    def getheader(self, key, default=None):
        return {"Content-Type": self.mime, "Content-Encoding": self.encoding}.get(key, default)
    def read1(self, size):
        out, self.body = self.body[:size], self.body[size:]
        return out

@pytest.mark.parametrize("status,mime,encoding,body,ok", [
    (200, "text/html", "identity", b"hello", True),
    (302, "text/html", "identity", b"", False),
    (500, "text/html", "identity", b"", False),
    (200, "application/json", "identity", b"{}", False),
    (200, "text/html", "gzip", b"abc", False),
    (200, "text/html", "identity", b"x" * 101, False),
])
def test_bounded_response(status, mime, encoding, body, ok):
    with patch.object(m, "PublicHTTPSConnection") as factory:
        conn = factory.return_value
        conn.getresponse.return_value = Response(status, body, mime, encoding)
        if ok:
            assert m.fetch_public_html("https://offers.example", 100, allowed_hosts={"offers.example"}) == "hello"
        else:
            with pytest.raises(ValueError):
                m.fetch_public_html("https://offers.example", 100, allowed_hosts={"offers.example"})
        conn.close.assert_called_once()


def test_public_connection_pins_ip_and_verifies_hostname():
    addr = [(2, 1, 6, "", ("8.8.8.8", 443))]
    with patch.object(m.socket, "getaddrinfo", return_value=addr), patch.object(m.socket, "socket") as factory:
        conn = m.PublicHTTPSConnection("offers.example", timeout=10)
        with patch.object(conn, "_context") as ctx:
            conn.connect()
            factory.return_value.connect.assert_called_once_with(("8.8.8.8", 443))
            ctx.wrap_socket.assert_called_once_with(factory.return_value, server_hostname="offers.example")
