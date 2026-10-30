"""site_guard.py: refused URLs and addresses, pinned connections, redirects and the budget.

    uv run python -m unittest tools.tests.test_site_guard      (or: uv run --with pytest pytest tools/tests/test_site_guard.py)

No real network: names resolve through a stub, and public-looking addresses are dialled to local
listeners (`Guard.dial`), so a listener standing in for a private address can prove it was never hit.
"""

import http.server
import sys
import threading
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import site_guard as G  # noqa: E402

PUBLIC = "93.184.215.14"
PUBLIC2 = "93.184.215.15"
PRIVATE = "10.0.0.5"


class Listener:
    """A local HTTP server answering from `routes` {path: (status, headers, body)}; counts hits."""

    def __init__(self, routes: dict | None = None):
        self.routes = routes or {}
        self.hits: list[str] = []
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                outer.hits.append(self.path)
                status, headers, body = outer.routes.get(self.path, (404, {}, b"nope"))
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


def stub(table: dict):
    """Resolver from {host: [addresses]} (a list of lists answers in turn, for rebinding)."""
    calls: dict[str, int] = {}

    def resolve(host, port):
        v = table.get(host)
        if v is None:
            raise G.FetchError(f"can't resolve {host}")
        if v and isinstance(v[0], list):
            i = calls.get(host, 0)
            calls[host] = i + 1
            return v[min(i, len(v) - 1)]
        return v

    return resolve


class Addresses(unittest.TestCase):
    def test_refused_ranges(self):
        for a in ("127.0.0.1", "10.1.2.3", "172.16.0.1", "192.168.1.1", "169.254.169.254", "100.64.0.1",
                  "0.0.0.0", "224.0.0.1", "240.0.0.1", "255.255.255.255", "::1", "::", "fc00::1", "fd12::1",
                  "fe80::1", "ff02::1", "::ffff:127.0.0.1", "::ffff:169.254.169.254", "64:ff9b::a00:5",
                  "2002:a00:5::1", "192.0.2.1", "198.18.0.1"):
            with self.subTest(a=a):
                self.assertIsNotNone(G.refused_reason(a))

    def test_public_ok(self):
        for a in (PUBLIC, "8.8.8.8", "2606:4700:4700::1111", "::ffff:8.8.8.8"):
            with self.subTest(a=a):
                self.assertIsNone(G.refused_reason(a))

    def test_metadata_named_link_local(self):
        with self.assertRaisesRegex(G.GuardError, "link-local"):
            G.Guard().check("http://169.254.169.254/latest/meta-data/")


class Urls(unittest.TestCase):
    def setUp(self):
        self.g = G.Guard(resolver=stub({"example.com": [PUBLIC], "mixed.example": [PUBLIC, PRIVATE],
                                        "loop.example": ["127.0.0.1"]}))

    def test_schemes(self):
        for url in ("file:///etc/passwd", "data:text/html,hi", "ftp://example.com/", "javascript:alert(1)",
                    "gopher://example.com/"):
            with self.subTest(url=url), self.assertRaisesRegex(G.GuardError, "scheme"):
                self.g.check(url)

    def test_credentials(self):
        with self.assertRaisesRegex(G.GuardError, "credentials"):
            self.g.check("http://user:pw@example.com/")

    def test_ports(self):
        with self.assertRaisesRegex(G.GuardError, "port 8080"):
            self.g.check("http://example.com:8080/")
        self.assertEqual(self.g.check("https://example.com:443/").port, 443)

    def test_one_private_address_refuses_the_host(self):
        with self.assertRaisesRegex(G.GuardError, "private"):
            self.g.check("http://mixed.example/")

    def test_name_resolving_to_loopback(self):
        with self.assertRaisesRegex(G.GuardError, "loopback"):
            self.g.check("http://loop.example/")

    def test_ip_literals(self):
        with self.assertRaisesRegex(G.GuardError, "private"):
            self.g.check("http://10.0.0.5/")
        with self.assertRaisesRegex(G.GuardError, "loopback"):
            self.g.check("http://[::ffff:127.0.0.1]/")
        self.assertEqual(self.g.check(f"http://{PUBLIC}/").ip, PUBLIC)


class Fetching(unittest.TestCase):
    def setUp(self):
        self.site = Listener()
        self.private = Listener({"/": (200, {}, b"secret")})
        self.addCleanup(self.site.close)
        self.addCleanup(self.private.close)

    def guard(self, table, **kw) -> G.Guard:
        return G.Guard(resolver=stub(table), dial={PUBLIC: ("127.0.0.1", self.site.port),
                                                   PUBLIC2: ("127.0.0.1", self.site.port),
                                                   PRIVATE: ("127.0.0.1", self.private.port)}, **kw)

    def test_fetch_and_cache(self):
        self.site.routes["/a"] = (200, {"Content-Type": "text/html; charset=utf-8"}, b"<h1>hi</h1>")
        g = self.guard({"example.com": [PUBLIC]})
        r = g.fetch("http://example.com/a")
        self.assertEqual((r.status, r.body, r.content_type), (200, b"<h1>hi</h1>", "text/html"))
        g.fetch("http://example.com/a")
        self.assertEqual(self.site.hits, ["/a"])

    def test_rebinding_connects_only_to_checked_address(self):
        self.site.routes["/"] = (200, {}, b"public")
        g = self.guard({"rebind.example": [[PUBLIC], [PRIVATE]]})
        r = g.fetch("http://rebind.example/")
        self.assertEqual(r.body, b"public")
        self.assertEqual(g.connections, [PUBLIC])
        self.assertEqual(self.private.hits, [])

    def test_redirect_to_private_address(self):
        self.site.routes["/"] = (302, {"Location": "http://10.0.0.5/"}, b"")
        g = self.guard({"example.com": [PUBLIC]})
        with self.assertRaisesRegex(G.GuardError, "redirect to http://10.0.0.5/ refused"):
            g.fetch("http://example.com/")
        self.assertEqual(self.private.hits, [])

    def test_redirect_to_name_resolving_private(self):
        self.site.routes["/"] = (301, {"Location": "http://inside.example/x"}, b"")
        g = self.guard({"example.com": [PUBLIC], "inside.example": [PRIVATE]})
        with self.assertRaisesRegex(G.GuardError, "refused"):
            g.fetch("http://example.com/")
        self.assertEqual(self.private.hits, [])

    def test_redirects_followed_and_capped(self):
        self.site.routes["/0"] = (302, {"Location": "/1"}, b"")
        self.site.routes["/1"] = (302, {"Location": "http://other.example/2"}, b"")
        self.site.routes["/2"] = (200, {}, b"end")
        g = self.guard({"example.com": [PUBLIC], "other.example": [PUBLIC2]})
        r = g.fetch("http://example.com/0")
        self.assertEqual((r.url, r.body), ("http://other.example/2", b"end"))
        for i in range(7):
            self.site.routes[f"/loop{i}"] = (302, {"Location": f"/loop{i + 1}"}, b"")
        with self.assertRaisesRegex(G.GuardError, "more than 5 redirects"):
            g.fetch("http://example.com/loop0")

    def test_budget(self):
        self.site.routes["/big"] = (200, {}, b"x" * 300_000)
        g = self.guard({"example.com": [PUBLIC]}, per_response=100_000)
        with self.assertRaises(G.Budget):
            g.fetch("http://example.com/big")
        self.assertTrue(g.truncated)
        g = self.guard({"example.com": [PUBLIC]}, total_bytes=500_000)
        for i in range(2):
            self.site.routes[f"/p{i}"] = (200, {}, b"x" * 300_000)
        g.fetch("http://example.com/p0")
        with self.assertRaises(G.Budget):
            g.fetch("http://example.com/p1")
        self.assertLessEqual(g.fetched, 500_000)
        g = self.guard({"example.com": [PUBLIC]}, deadline=0)
        with self.assertRaises(G.Budget):
            g.fetch("http://example.com/p0")


if __name__ == "__main__":
    unittest.main()
