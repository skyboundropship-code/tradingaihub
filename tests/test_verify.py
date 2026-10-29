"""Unit tests for scripts/verify.py status classification (no network).
Run: python3 -m unittest discover -s tests -p 'test_verify.py'"""
import importlib.util, os, sys, unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("verify", os.path.join(ROOT, "scripts", "verify.py"))
V = importlib.util.module_from_spec(spec); spec.loader.exec_module(V)


class R:
    """Minimal stand-in for a requests.Response."""
    def __init__(self, status, headers=None, json_body=None):
        self.status_code, self.headers, self._j = status, headers or {}, json_body
    def json(self):
        if self._j is None: raise ValueError("no json")
        return self._j


class Classify(unittest.TestCase):
    def test_table(self):
        cases = {200: "ok", 204: "ok", 301: "ok", 308: "ok", 404: "dead", 410: "dead",
                 401: "gated", 403: "gated", 405: "gated", 406: "gated", 407: "gated", 429: "gated", 451: "gated",
                 400: "fail", 402: "fail", 409: "fail", 418: "fail", 422: "fail",
                 500: "error", 502: "error", 503: "error", "ConnectTimeout": "error", "SSLError": "error", None: "error"}
        for code, want in cases.items():
            with self.subTest(code=code): self.assertEqual(V.classify(code), want)

    def test_link_ok_only_for_ok(self):
        for res in ("dead", "gated", "fail", "error"): self.assertFalse(V.link("u", 1, res)["ok"])
        self.assertTrue(V.link("u", 200, "ok")["ok"])


class Alive(unittest.TestCase):
    def test_404_is_dead(self):
        with mock.patch.object(V, "get", return_value=R(404)):
            a = V.alive("https://x/"); self.assertEqual((a["result"], a["ok"], a["status"]), ("dead", False, 404))

    def test_403_retries_with_browser_headers_and_passes(self):
        calls = []
        def fake(url, **kw): calls.append(kw); return R(200) if kw.get("headers") else R(403)
        with mock.patch.object(V, "get", side_effect=fake):
            a = V.alive("https://x/")
        self.assertEqual((a["result"], a["status"], a["first_status"], a["retry"]), ("ok", 200, 403, "browser-headers"))
        self.assertEqual(len(calls), 2)

    def test_403_still_refused_is_gated_not_pass(self):
        with mock.patch.object(V, "get", return_value=R(403)):
            a = V.alive("https://x/"); self.assertEqual((a["result"], a["ok"]), ("gated", False))

    def test_401_no_retry_gated(self):
        with mock.patch.object(V, "get", return_value=R(401)) as g:
            self.assertEqual(V.alive("https://x/")["result"], "gated"); self.assertEqual(g.call_count, 1)

    def test_exception_is_error(self):
        with mock.patch.object(V, "get", return_value=V.requests.ConnectionError("boom")):
            a = V.alive("https://x/"); self.assertEqual((a["result"], a["status"]), ("error", "ConnectionError"))


class McpProbe(unittest.TestCase):
    def probe(self, post, get=None, meta=None):
        seq = [post] + ([get] if get else [])
        with mock.patch.object(V, "_req", side_effect=seq) as rq, mock.patch.object(V, "get", return_value=meta or R(404)):
            out = V.mcp_probe("https://mcp.example.com/mcp")
        return out, rq

    def test_initialize_200_ok(self):
        a, _ = self.probe((R(200), b'{"jsonrpc":"2.0","result":{}}'))
        self.assertEqual((a["result"], a["evidence"]), ("ok", "mcp-initialize"))

    def test_404_dead_paypal_case(self):
        a, rq = self.probe((R(404), b""))
        self.assertEqual((a["result"], a["status"]), ("dead", 404)); self.assertEqual(rq.call_count, 1)

    def test_401_with_strict_oauth_metadata_ok(self):
        h = {"WWW-Authenticate": 'Bearer resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource/mcp"'}
        meta = R(200, json_body={"resource": "https://mcp.example.com/mcp", "authorization_servers": ["https://auth.example.com"]})
        with mock.patch.object(V.S, "get", return_value=meta):
            a, _ = self.probe((R(401, h), b""))
        self.assertEqual((a["result"], a["evidence"]), ("ok", "mcp-oauth"))

    def test_401_weak_metadata_gated_with_reason(self):
        h = {"WWW-Authenticate": 'Bearer resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource"'}
        with mock.patch.object(V.S, "get", return_value=R(200, json_body={"resource": "https://mcp.example.com/mcp"})):
            a, _ = self.probe((R(401, h), b""))
        self.assertEqual(a["result"], "gated"); self.assertIn("authorization_servers", a["why"])

    def test_401_plain_bearer_gated(self):
        a, _ = self.probe((R(401, {"WWW-Authenticate": 'Bearer error="invalid_token"'}), b""))
        self.assertEqual(a["result"], "gated")

    def test_post_405_falls_back_to_get(self):
        a, rq = self.probe((R(405), b""), get=(R(200), b"event: endpoint"))
        self.assertEqual((a["result"], a["method"], a["post_status"]), ("ok", "GET", 405)); self.assertEqual(rq.call_count, 2)

    def test_post_405_get_405_gated(self):
        a, _ = self.probe((R(405), b""), get=(R(405), b""))
        self.assertEqual(a["result"], "gated")

    def test_post_400_get_404_dead(self):
        a, _ = self.probe((R(400), b""), get=(R(404), b""))
        self.assertEqual(a["result"], "dead")

    def test_5xx_error(self):
        a, _ = self.probe((R(503), b""))
        self.assertEqual(a["result"], "error")


EP = "https://mcp.example.com/v2/mcp"
GOOD = {"resource": EP, "authorization_servers": ["https://auth.example.com"]}
def hdr(md="https://mcp.example.com/.well-known/oauth-protected-resource/v2/mcp"):
    return f'Bearer realm="x", resource_metadata="{md}", scope="read"'


class OauthEvidenceStrict(unittest.TestCase):
    """QA rule (PR #18): a 401 is verified only if (a) same-registrable-domain/allowlisted metadata URL,
    (b) valid JSON, (c) resource matches endpoint origin + path prefix, (d) >=1 authorization_servers."""
    def ev(self, www=None, body=GOOD, status=200, endpoint=EP, raise_=None):
        def fetch(u):
            if raise_: raise raise_
            return R(status, json_body=body)
        return V.oauth_evidence(endpoint, hdr() if www is None else www, fetch=fetch)

    def test_all_conditions_pass(self):
        self.assertEqual(self.ev(), (True, "https://mcp.example.com/.well-known/oauth-protected-resource/v2/mcp"))

    def test_unquoted_metadata_and_sibling_subdomain_pass(self):
        self.assertTrue(self.ev(www="Bearer resource_metadata=https://auth.example.com/.well-known/oauth-protected-resource")[0])

    # (a)
    def test_a_bare_401_or_no_bearer(self):
        self.assertFalse(self.ev(www="")[0]); self.assertFalse(self.ev(www='Basic realm="x"')[0])
        self.assertFalse(self.ev(www='Bearer error="invalid_token"')[0])

    def test_a_foreign_domain(self):
        ok, why = self.ev(www=hdr("https://evil.example.net/.well-known/oauth-protected-resource"))
        self.assertFalse(ok); self.assertIn("allowlisted", why)

    def test_a_lookalike_suffix_domain(self):
        self.assertFalse(self.ev(www=hdr("https://mcp.example.com.evil.io/.well-known/oauth-protected-resource"))[0])

    def test_a_http_metadata(self):
        self.assertFalse(self.ev(www=hdr("http://mcp.example.com/.well-known/oauth-protected-resource"))[0])

    def test_a_allowlist(self):
        md = hdr("https://login.vendorauth.com/.well-known/oauth-protected-resource")
        self.assertFalse(self.ev(www=md)[0])
        with mock.patch.dict(V.VENDOR_AUTH_DOMAINS, {"example.com": frozenset({"vendorauth.com"})}):
            self.assertTrue(self.ev(www=md)[0])

    def test_a_allowlist_ships_minimal(self):
        self.assertLessEqual(len(V.VENDOR_AUTH_DOMAINS), 3)

    def test_registrable_domain(self):
        self.assertEqual(V.registrable_domain("mcp.api.coingecko.com"), "coingecko.com")
        self.assertEqual(V.registrable_domain("a.b.example.co.uk"), "example.co.uk")
        self.assertEqual(V.registrable_domain("foo.github.io"), "foo.github.io")
        self.assertNotEqual(V.registrable_domain("a.github.io"), V.registrable_domain("b.github.io"))

    # (b)
    def test_b_non_200(self):
        for st in (301, 302, 404, 500):
            with self.subTest(st=st): self.assertFalse(self.ev(status=st)[0])

    def test_b_invalid_json_or_not_object(self):
        self.assertFalse(self.ev(body=None)[0]); self.assertFalse(self.ev(body=["x"])[0])

    def test_b_fetch_exception(self):
        self.assertFalse(self.ev(raise_=V.requests.ConnectTimeout())[0])

    # (c)
    def test_c_missing_resource(self):
        self.assertFalse(self.ev(body={"authorization_servers": ["https://a"]})[0])

    def test_c_other_host_scheme_port(self):
        for res in ("https://other.example.com/v2/mcp", "http://mcp.example.com/v2/mcp", "https://mcp.example.com:8443/v2/mcp"):
            with self.subTest(res=res): self.assertFalse(self.ev(body={**GOOD, "resource": res})[0])

    def test_c_path_must_be_segment_prefix(self):
        for res, want in (("https://mcp.example.com", True), ("https://mcp.example.com/", True), ("https://mcp.example.com/v2", True),
                          ("https://mcp.example.com/v2/mcp/", True), ("https://mcp.example.com/v2/mc", False),
                          ("https://mcp.example.com/v1/mcp", False), ("https://mcp.example.com/v2/mcp/extra", False)):
            with self.subTest(res=res): self.assertEqual(self.ev(body={**GOOD, "resource": res})[0], want)

    def test_c_default_port_equivalent(self):
        self.assertTrue(self.ev(body={**GOOD, "resource": "https://MCP.example.com:443/v2/mcp"})[0])

    # (d)
    def test_d_authorization_servers(self):
        for au in (None, [], [""], ["  "], "https://auth.example.com", [1]):
            body = {"resource": EP} if au is None else {"resource": EP, "authorization_servers": au}
            with self.subTest(au=au): self.assertFalse(self.ev(body=body)[0])


def ver(links, days=10, github=True, **g):
    v = {"checks": [], "issues": []}
    if github: v["github"] = {"reachable": True, "last_commit": "x", **g}
    for name, res in links:
        v["checks"].append({"check": name, "ok": res == "ok", "result": res, "note": None if res == "ok" else V.NOTE[res].format(s=0)})
    return v


class StatusOf(unittest.TestCase):
    def setUp(self):
        self.p = mock.patch.object(V, "age_days", side_effect=lambda ts: self.days); self.p.start(); self.days = 10
    def tearDown(self): self.p.stop()

    def test_all_ok_verified(self):
        self.assertEqual(V.status_of(ver([("homepage alive", "ok"), ("remote MCP endpoint responds", "ok")])), "verified")

    def test_dead_is_warning(self):
        self.assertEqual(V.status_of(ver([("remote MCP endpoint responds", "dead")])), "warning")

    def test_gated_is_unconfirmed_not_verified(self):
        v = ver([("homepage alive", "ok"), ("remote MCP endpoint responds", "gated")])
        self.assertEqual(V.status_of(v), "unconfirmed"); self.assertTrue(any("Could not confirm" in i for i in v["issues"]))

    def test_dead_beats_gated(self):
        self.assertEqual(V.status_of(ver([("homepage alive", "gated"), ("docs alive", "dead")])), "warning")

    def test_age_beats_gated(self):
        self.days = 400; self.assertEqual(V.status_of(ver([("homepage alive", "gated")])), "stale")
        self.days = 200; self.assertEqual(V.status_of(ver([("homepage alive", "gated")])), "aging")

    def test_no_repo_gated(self):
        self.days = None; self.assertEqual(V.status_of(ver([("homepage alive", "gated")], github=False)), "unconfirmed")
        self.assertEqual(V.status_of(ver([("homepage alive", "ok")], github=False)), "verified")

    def test_package_check_ignored(self):
        v = ver([("homepage alive", "ok")]); v["checks"].append({"check": "package published", "ok": False})
        self.assertEqual(V.status_of(v), "verified")

    def test_legacy_check_without_result_failure(self):
        v = ver([]); v["checks"].append({"check": "homepage alive", "ok": False})
        self.assertEqual(V.status_of(v), "warning")

    def test_unreachable_and_archived(self):
        self.assertEqual(V.status_of({"checks": [], "issues": [], "github": {"reachable": False}}), "unreachable")
        self.assertEqual(V.status_of(ver([], archived=True)), "archived")


class Args(unittest.TestCase):
    def test_dry_run_and_only(self):
        self.assertEqual(V.parse_args(["--dry-run", "--only=a"], {"a"}), (["a"], True))
        self.assertEqual(V.parse_args(["--only", "a"], {"a"}), (["a"], False))
        self.assertEqual(V.parse_args([], {"a"}), (None, False))
        with self.assertRaises(SystemExit): V.parse_args(["--dryrun"], {"a"})


class SiteKnowsEveryStatus(unittest.TestCase):
    """Every status verify.py can emit must exist in the site's STATUS map, every locale, the OG badges and awesome.py."""
    STATUSES = {"verified", "unconfirmed", "aging", "stale", "archived", "warning", "unreachable"}
    def test_registered(self):
        import json, glob, re
        data_ts = open(os.path.join(ROOT, "src/lib/data.ts")).read()
        og = open(os.path.join(ROOT, "scripts/og.mjs")).read()
        aw = open(os.path.join(ROOT, "scripts/awesome.py")).read()
        cat = open(os.path.join(ROOT, "src/pages/[...lang]/category/[slug].astro")).read()
        for s in self.STATUSES:
            with self.subTest(status=s):
                self.assertRegex(data_ts, rf"\b{s}: \{{ label"); self.assertRegex(og, rf"\b{s}: \(")
                self.assertIn(f'"{s}":', aw); self.assertRegex(cat, rf"\b{s}: \d")
        for f in glob.glob(os.path.join(ROOT, "src/i18n/*.json")):
            with open(f) as fh: st = json.load(fh)["status"]
            with self.subTest(locale=os.path.basename(f)): self.assertTrue(self.STATUSES <= set(st))


if __name__ == "__main__": unittest.main()
