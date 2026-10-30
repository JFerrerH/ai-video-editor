"""Network guard for the `site` capture: every request the page makes is checked and fetched here.

    g = Guard()
    g.check("https://example.com/")          # → Target, or GuardError naming the reason
    r = g.fetch("https://example.com/")      # → Response (redirects followed and re-checked)

Rules: http/https only, ports 80/443, no credentials in the URL; the host is resolved and refused
if ANY address is loopback, private, link-local (incl. 169.254.169.254), CGNAT, multicast, reserved,
unspecified or IPv6 ULA (IPv4 embedded in IPv6 is unwrapped first). The connection goes to the
address that was checked (TLS still verifies the requested name), so a resolver that answers
differently the second time (DNS rebinding) can't redirect it. Redirects are followed here, at most
5 hops, each hop checked again. Bodies count against a shared budget (8 MB per response, 20 MB
total) and a deadline (30 s); past either, fetches raise Budget and the capture keeps what it has.
"""

from __future__ import annotations

import ipaddress
import socket
import time
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urljoin, urlsplit

import certifi
import urllib3

SCHEMES = {"http": 80, "https": 443}
MAX_REDIRECTS = 5
PER_RESPONSE = 8 * 1024 * 1024
TOTAL_BYTES = 20 * 1024 * 1024
DEADLINE = 30.0
FORWARD_HEADERS = ("user-agent", "accept", "accept-language", "referer")
DROP_RESPONSE_HEADERS = {"content-encoding", "content-length", "transfer-encoding", "connection",
                         "set-cookie", "strict-transport-security", "alt-svc"}

EXTRA_REFUSED = [ipaddress.ip_network(n) for n in
                 ("100.64.0.0/10", "fc00::/7", "fe80::/10", "169.254.0.0/16", "0.0.0.0/8", "64:ff9b:1::/48")]
NAT64 = ipaddress.ip_network("64:ff9b::/96")


class GuardError(Exception):
    """The URL or one of its addresses is refused (a policy decision, not a network failure)."""


class FetchError(Exception):
    """Allowed, but the fetch didn't complete (unreachable, reset, budget spent)."""


class Budget(FetchError):
    """The capture's byte or time budget is spent."""


def refused_reason(addr: str) -> str | None:
    """Why this address is refused, or None if it is a public address."""
    try:
        ip = ipaddress.ip_address(addr.split("%", 1)[0])
    except ValueError:
        return f"not an IP address: {addr}"
    inner = []
    if isinstance(ip, ipaddress.IPv6Address):  # IPv4 inside IPv6 reaches the IPv4 host: check that too
        inner += [x for x in (ip.ipv4_mapped, ip.sixtofour, *(ip.teredo or ())) if x]
        if ip in NAT64:
            inner.append(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF))
    for x in (ip, *inner):
        for flag, name in (("is_loopback", "loopback"), ("is_link_local", "link-local"),
                           ("is_multicast", "multicast"), ("is_unspecified", "unspecified"),
                           ("is_private", "private"), ("is_reserved", "reserved")):
            if getattr(x, flag):
                return f"{name} address {x}"
        if any(x in n for n in EXTRA_REFUSED if n.version == x.version):
            return f"private address {x}"
        if not x.is_global:
            return f"non-public address {x}"
    return None


def system_resolver(host: str, port: int) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise FetchError(f"can't resolve {host}: {e.strerror or e}") from None
    return list(dict.fromkeys(i[4][0] for i in infos))


@dataclass
class Target:
    url: str
    scheme: str
    host: str
    port: int
    ip: str


@dataclass
class Response:
    url: str  # the final URL after redirects
    status: int
    headers: dict[str, str]
    body: bytes

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "").split(";")[0].strip().lower()


@dataclass
class Guard:
    resolver: Callable[[str, int], list[str]] = system_resolver
    total_bytes: int = TOTAL_BYTES
    per_response: int = PER_RESPONSE
    deadline: float = DEADLINE
    # tests only: checked address → where the socket really connects (a local listener)
    dial: dict[str, tuple[str, int]] = field(default_factory=dict)
    fetched: int = 0
    blocked: int = 0
    truncated: bool = False
    connections: list[str] = field(default_factory=list)
    cache: dict[str, Response] = field(default_factory=dict)
    started: float = field(default_factory=time.monotonic)

    def remaining(self) -> float:
        return self.deadline - (time.monotonic() - self.started)

    def check(self, url: str) -> Target:
        """Parse and resolve `url`; GuardError unless every address is public."""
        try:
            u = urlsplit(url)
            port = u.port
        except ValueError as e:
            raise GuardError(f"invalid URL: {e}") from None
        scheme = u.scheme.lower()
        if scheme not in SCHEMES:
            raise GuardError(f"scheme {scheme or '(none)'!r} is not allowed (http or https only)")
        if u.username is not None or u.password is not None:
            raise GuardError("credentials in the URL are not allowed")
        host = (u.hostname or "").rstrip(".")
        if not host:
            raise GuardError("the URL has no host")
        port = port or SCHEMES[scheme]
        if port not in (80, 443):
            raise GuardError(f"port {port} is not allowed (80 or 443 only)")
        try:
            ipaddress.ip_address(host)
            addrs = [host]
        except ValueError:
            addrs = self.resolver(host, port)
        if not addrs:
            raise GuardError(f"{host} has no address")
        for a in addrs:  # one bad address refuses the host: the browser could have picked it
            if why := refused_reason(a):
                raise GuardError(f"{host} resolves to a {why}")
        return Target(url, scheme, host, port, addrs[0])

    def _get(self, t: Target, headers: dict[str, str]) -> Response:
        left = self.remaining()
        if left <= 0 or self.fetched >= self.total_bytes:
            self.truncated = True
            raise Budget("capture budget spent")
        ip, port = self.dial.get(t.ip, (t.ip, t.port))
        self.connections.append(t.ip)
        timeout = urllib3.Timeout(connect=min(5.0, left), read=left)
        if t.scheme == "https" and t.ip not in self.dial:
            pool = urllib3.HTTPSConnectionPool(ip, port, timeout=timeout, retries=False, maxsize=1,
                                               server_hostname=t.host, assert_hostname=t.host,
                                               cert_reqs="CERT_REQUIRED", ca_certs=certifi.where())
        else:
            pool = urllib3.HTTPConnectionPool(ip, port, timeout=timeout, retries=False, maxsize=1)
        u = urlsplit(t.url)
        path = (u.path or "/") + (f"?{u.query}" if u.query else "")
        host_header = t.host if t.port == SCHEMES[t.scheme] else f"{t.host}:{t.port}"
        try:
            r = pool.urlopen("GET", path, headers={**headers, "Host": host_header}, redirect=False,
                             preload_content=False, assert_same_host=False)
            body = bytearray()
            while True:  # never past either limit: read at most what is left, plus 1 byte to see if more is coming
                left = min(self.per_response - len(body), self.total_bytes - self.fetched)
                chunk = r.read(min(64 * 1024, left + 1), decode_content=True)
                if not chunk:
                    break
                if len(chunk) > left or self.remaining() <= 0:
                    self.truncated = True
                    r.release_conn()
                    raise Budget("capture budget spent")
                body += chunk
                self.fetched += len(chunk)
            hdrs = {k.lower(): v for k, v in r.headers.items()}
            return Response(t.url, r.status, hdrs, bytes(body))
        except urllib3.exceptions.HTTPError as e:
            raise FetchError(f"can't fetch {t.host}: {type(e).__name__}") from None
        finally:
            pool.close()

    def fetch(self, url: str, headers: dict[str, str] | None = None) -> Response:
        """GET `url`, following up to 5 redirects, each re-checked; cached by requested URL."""
        if url in self.cache:
            return self.cache[url]
        sent = {k: v for k, v in (headers or {}).items() if k.lower() in FORWARD_HEADERS}
        cur = url
        for hop in range(MAX_REDIRECTS + 1):
            t = self.check(cur) if hop == 0 else self._check_redirect(cur)
            r = self._get(t, sent)
            loc = r.headers.get("location")
            if r.status in (301, 302, 303, 307, 308) and loc:
                cur = urljoin(cur, loc)
                continue
            r = Response(cur, r.status, r.headers, r.body)
            self.cache[url] = self.cache[cur] = r
            return r
        raise GuardError(f"more than {MAX_REDIRECTS} redirects")

    def _check_redirect(self, url: str) -> Target:
        try:
            return self.check(url)
        except GuardError as e:
            raise GuardError(f"redirect to {url} refused: {e}") from None

    @staticmethod
    def fulfil_headers(r: Response) -> dict[str, str]:
        """Response headers safe to hand back to the browser (body already decoded)."""
        return {k: v for k, v in r.headers.items() if k not in DROP_RESPONSE_HEADERS}
