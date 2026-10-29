"""Unit tests for scripts/verify.py status classification (no network).
Run: python3 -m unittest discover -s tests -p 'test_verify.py'"""
import importlib.util, os, sys, unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# VERIFY_PY lets scripts/tests/mutate_verify.py run this suite against a mutated copy without touching the repo.
spec = importlib.util.spec_from_file_location("verify", os.environ.get("VERIFY_PY") or os.path.join(ROOT, "scripts", "verify.py"))
V = importlib.util.module_from_spec(spec); spec.loader.exec_module(V)


def _read(path):
    with open(path) as f: return f.read()


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

    def test_g1_browser_retry_cloudflare_challenge_gated(self):
        def fake(url, **kw): return R(200, {"cf-mitigated": "challenge"}) if kw.get("headers") else R(403)
        with mock.patch.object(V, "get", side_effect=fake):
            a = V.alive("https://x/")
        self.assertEqual((a["result"], a["ok"]), ("gated", False))

    def test_first_get_cloudflare_challenge_gated(self):
        with mock.patch.object(V, "get", return_value=R(200, {"cf-mitigated": "challenge"})):
            self.assertEqual(V.alive("https://x/")["result"], "gated")

    def test_403_still_refused_is_gated_not_pass(self):
        with mock.patch.object(V, "get", return_value=R(403)):
            a = V.alive("https://x/"); self.assertEqual((a["result"], a["ok"]), ("gated", False))

    def test_401_no_retry_gated(self):
        with mock.patch.object(V, "get", return_value=R(401)) as g:
            self.assertEqual(V.alive("https://x/")["result"], "gated"); self.assertEqual(g.call_count, 1)

    def test_exception_is_error(self):
        with mock.patch.object(V, "get", return_value=V.requests.ConnectionError("boom")):
            a = V.alive("https://x/"); self.assertEqual((a["result"], a["status"]), ("error", "ConnectionError"))


JSON = {"Content-Type": "application/json"}
SSE = {"Content-Type": "text/event-stream"}
def hdr(md="https://mcp.example.com/.well-known/oauth-protected-resource/v2/mcp"):
    return f'Bearer realm="x", resource_metadata="{md}", scope="read"'


class McpProbe(unittest.TestCase):
    def probe(self, post, get=None, meta=None):
        seq = [post] + ([get] if get else [])
        fm = mock.Mock(return_value=meta or R(404))
        with mock.patch.object(V, "_req", side_effect=seq) as rq, mock.patch.object(V, "fetch_metadata", fm):
            out = V.mcp_probe("https://mcp.example.com/mcp")
        return out, rq

    def test_initialize_200_ok(self):
        a, _ = self.probe((R(200, JSON), b'{"jsonrpc":"2.0","id":1,"result":{}}'))
        self.assertEqual((a["result"], a["evidence"]), ("ok", "mcp-initialize"))

    def test_initialize_sse_ok(self):
        a, _ = self.probe((R(200, SSE), b'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{}}\n\n'))
        self.assertEqual((a["result"], a["evidence"]), ("ok", "mcp-initialize"))

    def test_jsonrpc_error_response_still_alive(self):
        a, _ = self.probe((R(200, JSON), b'{"jsonrpc":"2.0","id":1,"error":{"code":-32600,"message":"x"}}'))
        self.assertEqual(a["result"], "ok")

    # gaming cases (QA G1-G3 and friends)
    def test_g2_post_200_html_gated(self):
        a, _ = self.probe((R(200, {"Content-Type": "text/html"}), b'<html>"jsonrpc"</html>'))
        self.assertEqual(a["result"], "gated"); self.assertIn("JSON-RPC", a["why"])

    def test_post_200_json_without_jsonrpc_gated(self):
        for body in (b'{"ok":true}', b'{"jsonrpc":"2.0","id":2,"result":{}}', b'{"jsonrpc":"1.0","id":1,"result":{}}', b"not json"):
            with self.subTest(body=body):
                a, _ = self.probe((R(200, JSON), body)); self.assertEqual(a["result"], "gated")

    def test_post_200_cloudflare_challenge_gated(self):
        a, _ = self.probe((R(200, {**JSON, "cf-mitigated": "challenge"}), b'{"jsonrpc":"2.0","id":1,"result":{}}'))
        self.assertEqual(a["result"], "gated")

    def test_g3_post_405_get_html_gated(self):
        a, _ = self.probe((R(405), b""), get=(R(200, {"Content-Type": "text/html"}), b"<html>event: data:</html>"))
        self.assertEqual((a["result"], a["method"]), ("gated", "GET"))

    def test_post_405_get_sse_without_events_gated(self):
        a, _ = self.probe((R(405), b""), get=(R(200, SSE), b""))
        self.assertEqual(a["result"], "gated")

    def test_open_stream_timeout_is_gated_not_crash(self):
        a, _ = self.probe((V.Timeout("no complete answer within 8s"), b": ping\n"))
        self.assertEqual((a["result"], a["status"]), ("gated", "Timeout"))

    def test_403_with_good_metadata_is_never_verified(self):
        h = {"WWW-Authenticate": hdr("https://mcp.example.com/.well-known/oauth-protected-resource/mcp")}
        meta = R(200, json_body={"resource": "https://mcp.example.com/mcp", "authorization_servers": ["https://a"]})
        a, _ = self.probe((R(403, h), b""), meta=meta)
        self.assertEqual(a["result"], "gated"); self.assertIn("403", a["why"])
        a, _ = self.probe((R(401, h), b""), meta=meta)  # same evidence on a 401 passes
        self.assertEqual(a["result"], "ok")

    def test_404_dead_paypal_case(self):
        a, rq = self.probe((R(404), b""))
        self.assertEqual((a["result"], a["status"]), ("dead", 404)); self.assertEqual(rq.call_count, 1)

    def test_401_with_strict_oauth_metadata_ok(self):
        h = {"WWW-Authenticate": 'Bearer resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource/mcp"'}
        meta = R(200, json_body={"resource": "https://mcp.example.com/mcp", "authorization_servers": ["https://auth.example.com"]})
        a, _ = self.probe((R(401, h), b""), meta=meta)
        self.assertEqual((a["result"], a["evidence"]), ("ok", "mcp-oauth"))

    def test_401_weak_metadata_gated_with_reason(self):
        h = {"WWW-Authenticate": 'Bearer resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource"'}
        a, _ = self.probe((R(401, h), b""), meta=R(200, json_body={"resource": "https://mcp.example.com/mcp"}))
        self.assertEqual(a["result"], "gated"); self.assertIn("authorization_servers", a["why"])

    def test_401_plain_bearer_gated(self):
        a, _ = self.probe((R(401, {"WWW-Authenticate": 'Bearer error="invalid_token"'}), b""))
        self.assertEqual(a["result"], "gated")

    def test_post_405_falls_back_to_get(self):
        a, rq = self.probe((R(405), b""), get=(R(200, SSE), b"event: endpoint\ndata: /messages\n\n"))
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

    def test_jsonrpc_reply_needs_result_or_error(self):
        for body, ct in ((b'{"jsonrpc":"2.0","id":1}', "application/json"), (b'data: {"jsonrpc":"2.0","id":1}\n\n', "text/event-stream"),
                         (b'{"jsonrpc":"2.0","id":1,"method":"x"}', "application/json")):
            with self.subTest(body=body):
                self.assertIsNone(V.jsonrpc_response(body, ct))
                a, _ = self.probe((R(200, {"Content-Type": ct}), body)); self.assertEqual(a["result"], "gated")
        self.assertIsNotNone(V.jsonrpc_response(b'{"jsonrpc":"2.0","id":1,"result":{}}', "application/json"))

    def test_post_redirect_not_followed(self):
        for code in (301, 302, 307, 308):
            with self.subTest(code=code):
                a, rq = self.probe((R(code, {"Location": "https://elsewhere.example/mcp"}), b""))
                self.assertEqual(a["result"], "gated"); self.assertIn("not followed", a["why"]); self.assertEqual(rq.call_count, 1)
                self.assertFalse(rq.call_args.kwargs.get("allow_redirects", False))

    def test_get_fallback_redirect_not_followed(self):
        a, rq = self.probe((R(405), b""), get=(R(302, {"Location": "https://elsewhere.example/sse"}), b""))
        self.assertEqual((a["result"], a["method"]), ("gated", "GET")); self.assertIn("not followed", a["why"])

    def test_one_budget_for_the_whole_endpoint(self):
        h = {"WWW-Authenticate": hdr("https://mcp.example.com/.well-known/oauth-protected-resource/mcp")}
        fm = mock.Mock(return_value=R(200, json_body={"resource": "https://mcp.example.com/mcp", "authorization_servers": ["https://a"]}))
        with mock.patch.object(V, "_req", return_value=(R(401, h), b"")) as rq, mock.patch.object(V, "fetch_metadata", fm):
            t = V.time.monotonic(); a = V.mcp_probe("https://mcp.example.com/mcp")
        self.assertEqual(a["result"], "ok")
        self.assertLessEqual(rq.call_args.kwargs["deadline"], V.DEADLINE)
        end = fm.call_args.kwargs["end"]; self.assertLessEqual(end, t + V.DEADLINE + 0.01); self.assertGreater(end, t)

    def test_unsafe_endpoint_never_requested(self):
        for u in ("https://evil.test\\@mcp.example.com/mcp", "https://evil.test%5C@mcp.example.com/mcp", "https://u@mcp.example.com/mcp"):
            with self.subTest(u=u), mock.patch.object(V, "_req") as rq:
                a = V.mcp_probe(u)
                self.assertEqual((a["result"], a["status"]), ("gated", "UnsafeURL")); rq.assert_not_called()


class TimeoutNote(unittest.TestCase):
    def test_timeout_note_says_timed_out(self):
        n = V._note(V.link("https://x/mcp", "Timeout", "gated", why="no complete answer within 8s"))
        self.assertIn("timed out", n); self.assertNotIn("refused our checker", n); self.assertIn("8s", n)
        self.assertIn("refused our checker", V._note(V.link("https://x/mcp", 401, "gated", why="no Bearer challenge")))


class MetadataRetry(unittest.TestCase):
    U = "https://mcp.example.com/.well-known/oauth-protected-resource"
    def fm(self, *seq):
        with mock.patch.object(V, "_req", side_effect=list(seq)) as rq:
            try: out = V.fetch_metadata(self.U)
            except Exception as e: out = e
        return out, rq.call_count

    def test_retry_once_after_error_or_5xx(self):
        for first in ((V.requests.ConnectionError("blip"), b""), (R(503), b""), (V.Timeout("t"), b"")):
            with self.subTest(first=first[0]):
                out, n = self.fm(first, (R(200), b'{"resource":"x"}'))
                self.assertEqual((out.status_code, n), (200, 2)); self.assertEqual(out.json()["resource"], "x")

    def test_only_one_retry(self):
        out, n = self.fm((R(503), b""), (R(502), b""), (R(200), b"{}"))
        self.assertEqual((out.status_code, n), (502, 2))
        out, n = self.fm((V.requests.ConnectionError("a"), b""), (V.requests.ConnectionError("b"), b""))
        self.assertIsInstance(out, V.requests.RequestException); self.assertEqual(n, 2)

    def test_no_retry_on_4xx(self):
        out, n = self.fm((R(404), b""), (R(200), b"{}"))
        self.assertEqual((out.status_code, n), (404, 1))

    def test_no_retry_when_budget_is_spent(self):
        with mock.patch.object(V.S, "send") as send:
            with self.assertRaises(Exception): V.fetch_metadata(self.U, end=V.time.monotonic() - 1)
            send.assert_not_called()


class UrlSafety(unittest.TestCase):
    """QA round 2 blocker 1: `https://evil.test\\@mcp.example.com/` is host mcp.example.com to urlsplit but is fetched
    from evil.test by requests/urllib3. Backslash, '@'/userinfo and their %-encodings are refused everywhere."""
    BAD = ("https://evil.test\\@mcp.example.com/.well-known/oauth-protected-resource",
           "https://evil.test%5C@mcp.example.com/.well-known/oauth-protected-resource",
           "https://evil.test%5c@mcp.example.com/.well-known/oauth-protected-resource",
           "https://evil.test%5C%40mcp.example.com/.well-known/oauth-protected-resource",
           "https://evil.test\\%40mcp.example.com/.well-known/oauth-protected-resource",
           "https://evil.test%40mcp.example.com/.well-known/oauth-protected-resource",
           "https://evil.test\\mcp.example.com/.well-known/oauth-protected-resource",
           "https://mcp.example.com\\.evil.test/.well-known/oauth-protected-resource",
           "https://mcp.example.com@evil.test/.well-known/oauth-protected-resource",
           "https://user:pw@mcp.example.com/.well-known/oauth-protected-resource",
           "https://@mcp.example.com/.well-known/oauth-protected-resource",
           "https://mcp.example.com/a\\b", "https://mcp.example.com/%5C", "https://mcp.example.com/x y",
           "https://mcp.example.com/\tx", "https://mcp.example.com\n.evil.test/", "ftp://mcp.example.com/x",
           "https://mcp.example.com:abc/x", "https:///x", "",
           # "@" anywhere is refused, not just in the authority (some parsers split on the last "@", some on the first)
           "https://mcp.example.com/x@evil.test", "https://mcp.example.com/x?u=a@evil.test", "https://mcp.example.com/#@evil.test")
    GOOD = ("https://mcp.example.com/.well-known/oauth-protected-resource/v2/mcp", "https://MCP.Example.com:443/x",
            "https://mcp.example.com./x", "http://127.0.0.1:8080/mcp", "https://mcp.example.com/v2/mcp?x=1#y")

    def test_url_problem(self):
        for u in self.BAD:
            with self.subTest(bad=u): self.assertIsNotNone(V.url_problem(u))
        for u in self.GOOD:
            with self.subTest(good=u): self.assertIsNone(V.url_problem(u))

    def test_parsers_really_disagree_on_backslash(self):
        u = "https://evil.test\\@mcp.example.com/x"
        self.assertEqual(V._validated(u)[1], "mcp.example.com")
        self.assertEqual(V._target(V.requests.Request("GET", u).prepare().url)[1], "evil.test")

    def test_metadata_url_refused_before_any_fetch(self):
        for md in self.BAD[:11]:
            with self.subTest(md=md):
                fetch = mock.Mock(return_value=R(200, json_body=GOOD))
                ok, why = V.oauth_evidence(EP, hdr(md), fetch=fetch)
                self.assertFalse(ok); fetch.assert_not_called()

    def test_resource_with_backslash_refused(self):
        for res in ("https://evil.test\\@mcp.example.com/v2/mcp", "https://evil.test%5C@mcp.example.com/v2/mcp",
                    "https://x@mcp.example.com/v2/mcp", "https://mcp.example.com/v2/mcp\\"):
            with self.subTest(res=res):
                ok, why = V.oauth_evidence(EP, hdr(), fetch=lambda u: R(200, json_body={**GOOD, "resource": res}))
                self.assertFalse(ok); self.assertIn("refused", why)

    def test_req_never_connects_to_unsafe_url(self):
        with mock.patch.object(V.S, "send") as send:
            for u in self.BAD:
                with self.subTest(u=u):
                    r, _ = V._req("GET", u); self.assertIsInstance(r, Exception)
            send.assert_not_called()

    def test_req_checks_prepared_target_too(self):
        # second layer: even if url_problem() missed a trick, the prepared request must target the validated host
        with mock.patch.object(V, "url_problem", return_value=None), mock.patch.object(V.S, "send") as send:
            r, _ = V._req("GET", "https://evil.test\\@mcp.example.com/x")
        self.assertIsInstance(r, V.UnsafeURL); send.assert_not_called()

    def test_fetch_metadata_live_shape_refused(self):
        with mock.patch.object(V.S, "send") as send:
            with self.assertRaises(Exception): V.fetch_metadata("https://example.org\\@mcp.example.com/.well-known/oauth-protected-resource")
            send.assert_not_called()


EP = "https://mcp.example.com/v2/mcp"
GOOD = {"resource": EP, "authorization_servers": ["https://auth.example.com"]}


class OauthEvidenceStrict(unittest.TestCase):
    """QA rule (PR #18): a 401 is verified only if (a) metadata URL on the EXACT endpoint host (or allowlisted host),
    (b) valid JSON, (c) resource matches endpoint origin + path prefix, (d) >=1 authorization_servers."""
    def ev(self, www=None, body=GOOD, status=200, endpoint=EP, raise_=None):
        def fetch(u):
            if raise_: raise raise_
            return R(status, json_body=body)
        return V.oauth_evidence(endpoint, hdr() if www is None else www, fetch=fetch)

    def test_all_conditions_pass(self):
        self.assertEqual(self.ev(), (True, "https://mcp.example.com/.well-known/oauth-protected-resource/v2/mcp"))

    def test_unquoted_metadata_and_host_case(self):
        self.assertTrue(self.ev(www="Bearer resource_metadata=https://MCP.Example.com/.well-known/oauth-protected-resource")[0])
        self.assertTrue(self.ev(www="bearer resource_metadata=https://mcp.example.com/.well-known/oauth-protected-resource")[0])

    # (a)
    def test_a_bare_401_or_no_bearer(self):
        self.assertFalse(self.ev(www="")[0]); self.assertFalse(self.ev(www='Basic realm="x"')[0])
        self.assertFalse(self.ev(www='Bearer error="invalid_token"')[0])

    def test_a_bearer_required_even_with_good_metadata(self):
        for scheme in ("Basic", "Digest", "DPoP", "Negotiate", ""):
            with self.subTest(scheme=scheme):
                www = f'{scheme} resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource/v2/mcp"'.strip()
                ok, why = self.ev(www=www); self.assertFalse(ok); self.assertIn("Bearer", why)

    def test_a_sibling_subdomain_rejected(self):
        for h in ("auth.example.com", "example.com", "www.example.com", "a.mcp.example.com"):
            with self.subTest(h=h):
                ok, why = self.ev(www=hdr(f"https://{h}/.well-known/oauth-protected-resource"))
                self.assertFalse(ok); self.assertIn("endpoint host", why)

    def test_a_shared_hosting_and_cctld_pairs_rejected(self):
        # QA's PSL list: a last-two-labels rule would merge these tenants. Exact host never does.
        pairs = [("a.appspot.com", "evil.appspot.com"), ("a.blogspot.com", "evil.blogspot.com"),
                 ("a.s3.amazonaws.com", "evil.s3.amazonaws.com"), ("a.web.app", "evil.web.app"),
                 ("a.firebaseapp.com", "evil.firebaseapp.com"), ("a.r2.dev", "evil.r2.dev"), ("a.deno.dev", "evil.deno.dev"),
                 ("mcp.example.com.ar", "evil.com.ar"), ("mcp.example.co.at", "evil.co.at"),
                 ("a.example.co.uk", "evil.co.uk"), ("alice.github.io", "bob.github.io")]
        for ep, md in pairs:
            with self.subTest(ep=ep, md=md):
                e = f"https://{ep}/mcp"
                self.assertFalse(self.ev(endpoint=e, www=hdr(f"https://{md}/.well-known/oauth-protected-resource"),
                                         body={"resource": e, "authorization_servers": ["https://a"]})[0])
                self.assertTrue(self.ev(endpoint=e, www=hdr(f"https://{ep}/.well-known/oauth-protected-resource"),
                                        body={"resource": e, "authorization_servers": ["https://a"]})[0])

    def test_a_foreign_and_lookalike_hosts(self):
        for md in ("https://evil.example.net/x", "https://mcp.example.com.evil.io/x", "https://mcp.example.com@evil.io/x"):
            with self.subTest(md=md): self.assertFalse(self.ev(www=hdr(md))[0])

    def test_a_http_metadata(self):
        self.assertFalse(self.ev(www=hdr("http://mcp.example.com/.well-known/oauth-protected-resource"))[0])

    def test_a_bad_metadata_url_port(self):
        ok, why = self.ev(www=hdr("https://mcp.example.com:abc/.well-known/oauth-protected-resource"))
        self.assertFalse(ok)

    def test_a_allowlist(self):
        md = hdr("https://login.vendorauth.com/.well-known/oauth-protected-resource")
        self.assertFalse(self.ev(www=md)[0])
        with mock.patch.dict(V.VENDOR_AUTH_HOSTS, {"mcp.example.com": frozenset({"login.vendorauth.com"})}):
            self.assertTrue(self.ev(www=md)[0])
            self.assertFalse(self.ev(www=hdr("https://other.vendorauth.com/x"))[0])

    def test_a_allowlist_ships_empty_and_no_psl_logic(self):
        self.assertEqual(V.VENDOR_AUTH_HOSTS, {})
        for gone in ("registrable_domain", "MULTI_SUFFIXES", "VENDOR_AUTH_DOMAINS"):
            self.assertFalse(hasattr(V, gone), gone)

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
    def test_c_invalid_resource_url_no_crash(self):
        for res in ("https://mcp.example.com:abc/v2/mcp", "https://mcp.example.com:99999/v2/mcp", "https://[::1/v2/mcp", "not a url", "https:///v2/mcp"):
            with self.subTest(res=res):
                ok, why = self.ev(body={**GOOD, "resource": res}); self.assertFalse(ok)

    def test_b_fetch_any_exception_no_crash(self):
        self.assertFalse(self.ev(raise_=ValueError("x"))[0])

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


class CrossOrg(unittest.TestCase):
    """OpenBB-finance/OpenBB -> openbq-org/OpenBB: Needs review, never verified, with the note; link not rewritten."""
    G = {"reachable": True, "final_url": "https://github.com/openbq-org/OpenBB", "archived": False, "stars": 1,
         "license": "AGPL-3.0", "last_commit": "2026-10-20T00:00:00Z", "cross_org_redirect": "https://github.com/openbq-org/OpenBB"}

    def run_verify(self, g):
        t = {"id": "openbb", "type": "api", "repo": "https://github.com/OpenBB-finance/OpenBB"}
        with mock.patch.object(V, "gh_info", return_value=(dict(g), "openbq-org", "OpenBB")), \
             mock.patch.object(V, "detect_packages", return_value={}), mock.patch.object(V, "age_days", return_value=8):
            return V.verify(t)

    def test_cross_org_is_needs_review_with_note(self):
        v = self.run_verify(self.G)
        self.assertEqual(v["status"], "unconfirmed")
        self.assertTrue(any("redirects to another owner" in i and "openbq-org" in i for i in v["issues"]), v["issues"])

    def test_same_owner_stays_verified(self):
        g = {k: x for k, x in self.G.items() if k != "cross_org_redirect"}; g["final_url"] = "https://github.com/OpenBB-finance/OpenBB"
        v = self.run_verify(g)
        self.assertEqual((v["status"], v["issues"]), ("verified", []))

    def test_status_of_cross_org(self):
        with mock.patch.object(V, "age_days", return_value=5):
            self.assertEqual(V.status_of(ver([], cross_org_redirect="https://github.com/x/y")), "unconfirmed")
        with mock.patch.object(V, "age_days", return_value=300):
            self.assertEqual(V.status_of(ver([], cross_org_redirect="https://github.com/x/y")), "aging")

    def test_main_does_not_rewrite_repo(self):
        src = _read(os.path.join(ROOT, "scripts/verify.py"))
        self.assertIn('not g.get("cross_org_redirect"): t["repo"] = g["final_url"]', src)


class RunNeverDies(unittest.TestCase):
    def test_safe_verify_turns_crash_into_needs_review(self):
        with mock.patch.object(V, "verify", side_effect=ValueError("Port could not be cast to integer value as 'abc'")):
            v = V.safe_verify({"id": "x"})
        self.assertEqual(v["status"], "unconfirmed"); self.assertIn("ValueError", v["issues"][0])

    def test_recheck_once_before_demotion(self):
        todo = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        current = {i: {"verification": {"status": s}} for i, s in (("a", "verified"), ("b", "verified"), ("c", "unconfirmed"))}
        fresh = {"a": {"status": "unconfirmed"}, "b": {"status": "verified"}, "c": {"status": "unconfirmed"}}
        fn = mock.Mock(return_value={"status": "verified"})
        again = V.recheck_demotions(todo, fresh, current, fn=fn)
        self.assertEqual(again, ["a"]); fn.assert_called_once_with({"id": "a"})
        self.assertEqual(fresh["a"], {"status": "verified", "rechecked": True})

    def test_safe_verify_hard_cap(self):
        with mock.patch.object(V, "TOOL_DEADLINE", 0.3), mock.patch.object(V, "verify", side_effect=lambda t: time.sleep(3)):
            t = time.monotonic(); v = V.safe_verify({"id": "x"})
        self.assertLess(time.monotonic() - t, 1.5)
        self.assertEqual(v["status"], "unconfirmed"); self.assertIn("timed out", v["issues"][0])

    def test_recheck_keeps_second_result(self):
        fresh = {"a": {"status": "warning"}}
        V.recheck_demotions([{"id": "a"}], fresh, {"a": {"verification": {"status": "verified"}}}, fn=lambda t: {"status": "unconfirmed"})
        self.assertEqual(fresh["a"]["status"], "unconfirmed")


import http.server, threading, time

class _H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def _chunk(self, b): self.wfile.write(b"%x\r\n%s\r\n" % (len(b), b)); self.wfile.flush()
    def _sse(self, first=None, ping=False):
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.send_header("Transfer-Encoding", "chunked"); self.end_headers()
        try:
            if first: self._chunk(first)
            for _ in range(40):
                if ping: self._chunk(b": ping\n")
                time.sleep(0.1)
        except OSError: pass
    def _send(self, code, body=b"", ctype="application/json", **h):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        for k, x in h.items(): self.send_header(k, x)
        self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        self.rfile.read(int(self.headers.get("content-length", 0)))
        if self.path == "/hold": self._sse(b'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{}}\n\n')
        elif self.path == "/drip": self._sse(ping=True)
        elif self.path == "/silent": self._sse()
        elif self.path == "/html": self._send(200, b"<html>jsonrpc</html>", "text/html")
        elif self.path == "/slowhdr": self._slowhdr()
        elif self.path == "/big": self._send(200, b"x" * (200 * 1024), "application/octet-stream")
        elif self.path == "/redir": self._send(307, b"", Location="/hold")
        else: self._send(404)
    def _slowhdr(self):
        # QA blocker 2: one header line every 0.3s (< the 1s per-read timeout), for ~15s
        try:
            self.wfile.write(b"HTTP/1.1 200 OK\r\n"); self.wfile.flush()
            for i in range(50):
                time.sleep(0.3); self.wfile.write(b"X-Slow-%d: 1\r\n" % i); self.wfile.flush()
        except OSError: pass
    def do_GET(self):
        if self.path == "/slowhdr": return self._slowhdr()
        if self.path == "/md-redirect": self._send(302, b"", Location="/md-good")
        elif self.path == "/md-good": self._send(200, b'{"resource":"x","authorization_servers":["a"]}')
        else: self._send(404)


class _Srv(http.server.ThreadingHTTPServer):
    def handle_error(self, request, client_address): pass  # clients hang up on purpose (deadline); keep test output clean


class LiveServer(unittest.TestCase):
    """Real sockets on 127.0.0.1: open SSE streams, the read deadline, and redirect handling of the metadata fetch."""
    @classmethod
    def setUpClass(cls):
        cls.srv = _Srv(("127.0.0.1", 0), _H); cls.srv.daemon_threads = True
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        cls.p = [mock.patch.object(V, "DEADLINE", 1.0), mock.patch.object(V, "TIMEOUT", (1, 1.0))]
        for p in cls.p: p.start()
    @classmethod
    def tearDownClass(cls):
        for p in cls.p: p.stop()
        cls.srv.shutdown(); cls.srv.server_close()

    def test_open_sse_stream_with_answer_passes_fast(self):
        t = time.monotonic(); a = V.mcp_probe(self.base + "/hold")
        self.assertEqual((a["result"], a["evidence"]), ("ok", "mcp-initialize")); self.assertLess(time.monotonic() - t, 0.9)

    def test_open_sse_stream_keepalive_only_times_out_gated(self):
        for path in ("/drip", "/silent"):
            with self.subTest(path=path):
                t = time.monotonic(); a = V.mcp_probe(self.base + path)
                self.assertEqual((a["result"], a["status"]), ("gated", "Timeout")); self.assertLess(time.monotonic() - t, 3)

    def test_post_200_html_gated(self):
        self.assertEqual(V.mcp_probe(self.base + "/html")["result"], "gated")

    def test_req_caps_body(self):
        r, body = V._req("POST", self.base + "/drip", max_body=20, json={})
        self.assertNotIsInstance(r, Exception)  # stopped at the byte cap, long before the deadline
        self.assertLessEqual(len(body), 20)

    def test_metadata_fetch_does_not_follow_redirects(self):
        self.assertEqual(V.fetch_metadata(self.base + "/md-redirect").status_code, 302)
        self.assertEqual(V.fetch_metadata(self.base + "/md-good").json()["resource"], "x")

    def test_slow_header_trickle_is_bounded(self):
        t = time.monotonic(); a = V.mcp_probe(self.base + "/slowhdr")
        self.assertEqual((a["result"], a["status"]), ("gated", "Timeout")); self.assertLess(time.monotonic() - t, 2.0)
        self.assertIn("timed out", V._note(a))

    def test_slow_header_trickle_bounded_for_plain_get(self):
        with mock.patch.object(V, "GET_DEADLINE", 1.0):
            t = time.monotonic(); r = V.get(self.base + "/slowhdr")
        self.assertIsInstance(r, Exception); self.assertLess(time.monotonic() - t, 2.0)
        self.assertEqual(V.alive(self.base + "/html")["result"], "dead")  # GET /html -> 404 here; plain path still works

    def test_body_cap_64k(self):
        r, body = V._req("POST", self.base + "/big", json={})
        self.assertEqual(r.status_code, 200); self.assertEqual(len(body), V.MAX_BODY); self.assertEqual(V.MAX_BODY, 64 * 1024)

    def test_post_redirect_not_followed_live(self):
        a = V.mcp_probe(self.base + "/redir")
        self.assertEqual((a["result"], a["status"]), ("gated", 307)); self.assertIn("not followed", a["why"])

    def test_bad_port_endpoint_is_error_not_crash(self):
        a = V.mcp_probe("http://127.0.0.1:abc/mcp")
        self.assertFalse(a["ok"])


import contextlib, io, json, tempfile

class MainRun(unittest.TestCase):
    """main() end to end (dry run, temp data dir): the recheck is wired in, the run is bounded, links are kept."""
    def run_main(self, seed, current, extra=()):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "data"))
            for name, obj in (("seed.json", seed), ("tools.json", current)):
                with open(os.path.join(d, "data", name), "w") as f: json.dump(obj, f)
            out_json = os.path.join(d, "dry.json")
            with mock.patch.object(V, "ROOT", d), mock.patch.object(V.sys, "argv", ["verify.py", "--dry-run"]), \
                 mock.patch.dict(os.environ, {"VERIFY_DRY_JSON": out_json}), contextlib.ExitStack() as st, \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                for p in extra: st.enter_context(p)
                t = time.monotonic(); V.main(); el = time.monotonic() - t
            with open(out_json) as f: return {x["id"]: x for x in json.load(f)}, el

    def test_main_rechecks_demotions(self):
        seed = [{"id": "a", "name": "A", "type": "mcp", "remote_mcp_url": "https://a.example/mcp"}]
        cur = [{**seed[0], "verification": {"status": "verified"}}]
        res = iter([V.link("u", "ConnectionError", "error"), V.link("u", 200, "ok", evidence="mcp-initialize")])
        calls = []
        def probe(u): calls.append(u); return next(res)
        out, _ = self.run_main(seed, cur, [mock.patch.object(V, "mcp_probe", side_effect=probe)])
        self.assertEqual(len(calls), 2)
        self.assertEqual(out["a"]["verification"]["status"], "verified"); self.assertTrue(out["a"]["verification"].get("rechecked"))

    def test_main_cross_org_link_never_rewritten(self):
        g = dict(CrossOrg.G)
        seed = [{"id": "openbb", "name": "OpenBB", "type": "api", "repo": "https://github.com/OpenBB-finance/OpenBB"},
                {"id": "ren", "name": "Ren", "type": "api", "repo": "https://github.com/Same/old"}]
        def gh(url, collection=False):
            if "OpenBB" in url: return dict(g), "openbq-org", "OpenBB"
            return {"reachable": True, "final_url": "https://github.com/Same/new", "archived": False, "last_commit": "x"}, "Same", "new"
        out, _ = self.run_main(seed, [], [mock.patch.object(V, "gh_info", side_effect=gh), mock.patch.object(V, "detect_packages", return_value={}),
                                          mock.patch.object(V, "age_days", return_value=5)])
        self.assertEqual(out["openbb"]["repo"], "https://github.com/OpenBB-finance/OpenBB")
        self.assertEqual(out["openbb"]["verification"]["status"], "unconfirmed")
        self.assertEqual(out["ren"]["repo"], "https://github.com/Same/new")  # same-owner rename is still followed

    def test_whole_run_bounded_with_header_trickle_and_recheck(self):
        srv = _Srv(("127.0.0.1", 0), _H); srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        try:
            seed = [{"id": f"s{i}", "name": f"S{i}", "type": "mcp", "remote_mcp_url": base + p}
                    for i, p in enumerate(("/slowhdr", "/slowhdr", "/drip", "/silent", "/hold"))]
            cur = [{**t, "verification": {"status": "verified"}} for t in seed]
            out, el = self.run_main(seed, cur, [mock.patch.object(V, "DEADLINE", 1.0), mock.patch.object(V, "TIMEOUT", (1, 1.0))])
        finally:
            srv.shutdown(); srv.server_close()
        self.assertLess(el, 2 * 1.0 + 1.5)  # first pass + one recheck, each <= DEADLINE, plus margin
        for i in range(4):
            v = out[f"s{i}"]["verification"]
            self.assertEqual(v["status"], "unconfirmed"); self.assertTrue(v.get("rechecked")); self.assertEqual(v["remote_mcp"]["status"], "Timeout")
        self.assertEqual(out["s4"]["verification"]["status"], "verified"); self.assertNotIn("rechecked", out["s4"]["verification"])


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
        data_ts = _read(os.path.join(ROOT, "src/lib/data.ts"))
        og = _read(os.path.join(ROOT, "scripts/og.mjs"))
        aw = _read(os.path.join(ROOT, "scripts/awesome.py"))
        cat = _read(os.path.join(ROOT, "src/pages/[...lang]/category/[slug].astro"))
        for s in self.STATUSES:
            with self.subTest(status=s):
                self.assertRegex(data_ts, rf"\b{s}: \{{ label"); self.assertRegex(og, rf"\b{s}: \(")
                self.assertIn(f'"{s}":', aw); self.assertRegex(cat, rf"\b{s}: \d")
        for f in glob.glob(os.path.join(ROOT, "src/i18n/*.json")):
            with open(f) as fh: st = json.load(fh)["status"]
            with self.subTest(locale=os.path.basename(f)): self.assertTrue(self.STATUSES <= set(st))


if __name__ == "__main__": unittest.main()
