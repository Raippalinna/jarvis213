"""Begränsad publik HTTPS-hämtning utan nycklar, cookies eller redirects."""
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urlsplit

class PublicHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        addresses = socket.getaddrinfo(self.host, 443, type=socket.SOCK_STREAM)
        if not addresses or any((not ipaddress.ip_address(a[4][0]).is_global or ipaddress.ip_address(a[4][0]).is_multicast) for a in addresses):
            raise ValueError("Privata eller reserverade nätverksadresser nekas")
        last = None
        for family, kind, proto, _, target in addresses:
            sock = socket.socket(family, kind, proto)
            try:
                sock.settimeout(self.timeout)
                sock.connect(target)
                self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
                return
            except (OSError, ssl.SSLError) as exc:
                last = exc
                sock.close()
        raise OSError("Ingen publik HTTPS-adress kunde anslutas") from last

def fetch_public_html(url, max_bytes, *, allowed_hosts, timeout=10):
    u = urlsplit(url)
    if (u.scheme != "https" or u.hostname not in allowed_hosts or u.username or
            u.password or u.port not in (None, 443) or u.fragment):
        raise ValueError("Otillåten källadress")
    if not 1 <= max_bytes <= 500_000 or not 0 < timeout <= 30:
        raise ValueError("Ogiltiga resursgränser")
    path = u.path or "/"
    if u.query:
        path += "?" + u.query
    conn = PublicHTTPSConnection(u.hostname, timeout=timeout, context=ssl.create_default_context())
    deadline = time.monotonic() + timeout
    try:
        conn.request("GET", path, headers={"User-Agent": "JarvisBenefits/0.1", "Accept": "text/html", "Accept-Encoding": "identity"})
        response = conn.getresponse()
        if response.status != 200:
            raise ValueError("HTTP-svaret nekas; inga redirects följs")
        mime = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
        if mime not in {"text/html", "text/plain"}:
            raise ValueError("Otillåten innehållstyp")
        if response.getheader("Content-Encoding", "identity").lower() != "identity":
            raise ValueError("Komprimerade svar nekas")
        parts, size = [], 0
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError("Tidsgräns för hämtning")
            part = response.read1(min(16384, max_bytes + 1 - size))
            if not part:
                break
            parts.append(part)
            size += len(part)
            if size > max_bytes:
                raise ValueError("Svarsstorleken överskrider gränsen")
        return b"".join(parts).decode("utf-8", "replace")
    finally:
        conn.close()
