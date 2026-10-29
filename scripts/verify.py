#!/usr/bin/env python3
"""Weekly verifier for the directory.
Reads data/seed.json (curated entries) and writes data/tools.json (seed + verification)
and data/verification-report.{json,md}.
Checks per entry: repo reachable (+renames/archived), last commit date, stars, license,
package published on npm/PyPI (+latest version), homepage and docs links alive.
Uses the GitHub REST API when GITHUB_TOKEN is set; otherwise scrapes public HTML/Atom
(no auth, avoids the 60 req/h anonymous API limit).
Run:  python3 scripts/verify.py        (weekly via cron / GitHub Actions)
      python3 scripts/verify.py --dry-run [--only=id1,id2]   (verify, write nothing, print status changes;
      set VERIFY_DRY_JSON=/path.json to save the would-be tools.json for review)"""
from urllib.parse import urlsplit
import json, os, re, sys, shutil, subprocess, threading, time, datetime as dt, tomllib
from concurrent.futures import ThreadPoolExecutor
import requests, urllib3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "FinanceAgentDirectoryBot/0.1 (weekly link check)"}
TOKEN = os.environ.get("GITHUB_TOKEN")
NOW = dt.datetime.now(dt.timezone.utc)
S = requests.Session(); S.headers.update(UA)

GET_DEADLINE = 25.0  # seconds, hard total for one homepage/docs/GitHub GET (DNS, connect, TLS, headers, body)

def _bounded(fn, deadline):
    """Run fn() in a daemon worker and wait at most `deadline` seconds of wall-clock time.
    -> (finished, value_or_exception). A worker that is still stuck (e.g. a server trickling one header line every few
    seconds, which keeps resetting the per-read socket timeout) is abandoned; being a daemon it cannot keep the run alive."""
    box = {}
    def run():
        try: box["v"] = fn()
        except BaseException as e: box["v"] = e
    th = threading.Thread(target=run, daemon=True); th.start(); th.join(max(deadline, 0))
    return ("v" in box), box.get("v")

def get(url, **kw):
    done, r = _bounded(lambda: S.get(url, timeout=20, allow_redirects=True, **kw), GET_DEADLINE)
    if not done: return Timeout(f"no complete answer within {GET_DEADLINE:g}s")
    if isinstance(r, requests.RequestException): return r
    if isinstance(r, Exception): return requests.RequestException(f"{type(r).__name__}: {r}")
    return r

# --- HTTP status classification -------------------------------------------------------------
# ok     2xx/3xx (redirects followed)                         -> counts as a live link
# dead   404, 410                                             -> link failure (tool gets "warning")
# gated  401, 403, 405, 406, 407, 429, 451: the server answered but refused us (auth wall, bot block,
#        wrong method, rate limit). Neither a pass nor dead: the tool gets "unconfirmed" instead of
#        "verified" and is NOT counted as verified.
# fail   any other 4xx                                        -> link failure
# error  5xx, timeouts, DNS/TLS/connection errors             -> link failure
DEAD = frozenset({404, 410})
GATED = frozenset({401, 403, 405, 406, 407, 429, 451})
FAILURES = ("dead", "fail", "error")
BROWSER = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "en"}

def classify(status):
    """HTTP status (int) or exception name (str) -> ok | dead | gated | fail | error."""
    if not isinstance(status, int): return "error"
    if status < 400: return "ok"
    if status in DEAD: return "dead"
    if status in GATED: return "gated"
    return "fail" if status < 500 else "error"

def link(url, status, result, **extra):
    return {"url": url, "ok": result == "ok", "status": status, "result": result, **extra}

def _challenge(r):
    """Cloudflare (or similar) bot challenge served with a 2xx/403: never proof the page is live."""
    return (r.headers.get("cf-mitigated") or "").lower() == "challenge"

def alive(url):
    """GET a homepage/docs URL. We never trust HEAD (many servers answer HEAD with 403/405), and a bot-blocked
    403/429 gets one retry with browser headers; if that is still refused, or the "pass" is a bot-challenge page
    (cf-mitigated: challenge), the link stays "gated"."""
    if not url: return None
    r = get(url)
    if isinstance(r, Exception): return link(url, type(r).__name__, "error")
    if _challenge(r): return link(url, r.status_code, "gated", why="bot challenge page (cf-mitigated)")
    res = classify(r.status_code)
    if r.status_code in (403, 429):
        r2 = get(url, headers=BROWSER)
        if not isinstance(r2, Exception) and classify(r2.status_code) == "ok":
            if _challenge(r2):
                return link(url, r.status_code, "gated", why="browser-header retry got a bot challenge page (cf-mitigated)")
            return link(url, r2.status_code, "ok", first_status=r.status_code, retry="browser-headers")
    return link(url, r.status_code, res)

MCP_INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "tradingaihub-verify", "version": "0.2"}}}

# --- Bounded HTTP for MCP endpoints and their metadata -------------------------------------------------------
# A server may keep an SSE stream open forever (the spec only says it SHOULD close it), or trickle its headers one
# line at a time (each line resets the per-read socket timeout). Every MCP-side request therefore runs in a daemon
# worker that is joined with a hard wall-clock DEADLINE covering DNS, connect, TLS, headers and body, then abandoned;
# and mcp_probe() gives ONE endpoint a single DEADLINE budget shared by all its requests (POST, GET fallback, metadata
# fetch and its retry). Bodies are read up to MAX_BODY bytes. One endpoint can never hang or crash the weekly run: the
# worst case is that this one tool becomes Needs review (and, if it was verified, one recheck: <= 2 x DEADLINE).
DEADLINE = 8.0           # seconds, hard total per endpoint (all of its requests together)
TIMEOUT = (5, DEADLINE)  # requests' connect / per-read timeouts (the worker join enforces the total)
MAX_BODY = 64 * 1024

class Timeout(Exception):
    """The request hit DEADLINE (an SSE stream that stays open without a JSON-RPC response, a header trickle ...)."""

class UnsafeURL(Exception):
    """A URL we refuse to fetch: parsers could disagree about its host (backslash, @/userinfo, control chars ...)."""

def _norm_host(h):
    h = (h or "").strip("[]").lower().rstrip(".")
    try: h.encode("ascii")
    except UnicodeEncodeError:
        try: h = h.encode("idna").decode("ascii")
        except UnicodeError: return ""
    return h

_DEFAULT_PORT = {"https": 443, "http": 80}

def url_problem(u):
    """None if `u` is a plain http(s) URL whose host every parser agrees on; else the reason we refuse it.
    `https://evil.test\\@mcp.example.com/` is read by urlsplit as host mcp.example.com but fetched by
    requests/urllib3 from evil.test, so backslashes, '@' (userinfo) and their %-encodings are rejected anywhere,
    and the host/port must be identical in urlsplit, urllib3.parse_url and the URL requests would actually send."""
    if not isinstance(u, str) or not u: return "empty URL"
    if "\\" in u or "@" in u or re.search(r"%(5c|40)", u, re.I): return "URL contains a backslash or '@' (userinfo is not allowed)"
    if any(ord(c) <= 0x20 or ord(c) == 0x7f for c in u): return "URL contains whitespace or control characters"
    try:
        p = urlsplit(u); port = p.port
    except ValueError: return "not a valid URL"
    if p.scheme.lower() not in _DEFAULT_PORT or not p.hostname: return "not an http(s) URL with a host"
    if p.username is not None or p.password is not None: return "URL contains userinfo"
    want = (p.scheme.lower(), _norm_host(p.hostname), port or _DEFAULT_PORT[p.scheme.lower()])
    try:
        for other in (u, requests.Request("GET", u).prepare().url):
            q = urllib3.util.parse_url(other)
            if q.auth: return "URL contains userinfo"
            if ((q.scheme or "").lower(), _norm_host(q.host), q.port or _DEFAULT_PORT.get((q.scheme or "").lower())) != want:
                return "URL parsers disagree about the host"
    except Exception: return "not a valid URL"
    return None

def _target(u):
    """(scheme, host, port) as urllib3 will connect to it (urllib3 parses the prepared URL with parse_url)."""
    q = urllib3.util.parse_url(u); sc = (q.scheme or "").lower()
    return (sc, _norm_host(q.host), q.port or _DEFAULT_PORT.get(sc))

def _validated(u):
    """(scheme, host, port) from the urlsplit components that our host checks were made on."""
    p = urlsplit(u); sc = p.scheme.lower()
    return (sc, _norm_host(p.hostname), p.port or _DEFAULT_PORT.get(sc))

def _req(method, url, until=None, deadline=None, max_body=MAX_BODY, **kw):
    """-> (response | exception, body bytes). Hard wall-clock `deadline` (default DEADLINE) for the whole request.
    The URL must pass url_problem(), and the prepared request (exactly what urllib3 connects to) must target the same
    scheme/host/port. Redirects are not followed unless asked. Body is read only for 2xx, chunk by chunk, until
    `until(r, body)` is true, EOF, max_body bytes, or the deadline. Never raises."""
    deadline = DEADLINE if deadline is None else deadline
    if deadline <= 0: return Timeout(f"no complete answer within {DEADLINE:g}s"), b""
    bad = url_problem(url)
    if bad: return UnsafeURL(bad), b""
    allow = kw.pop("allow_redirects", False)
    try:
        prep = S.prepare_request(requests.Request(method, url, **kw))
        if _target(prep.url) != _validated(url): return UnsafeURL("prepared request targets another host"), b""
    except Exception as e: return e, b""
    t0, box, stop = time.monotonic(), {"body": b""}, threading.Event()
    def work():
        r = S.send(prep, timeout=(min(TIMEOUT[0], deadline), deadline + 1), stream=True, allow_redirects=allow)
        box["r"] = r
        try:
            if 200 <= r.status_code < 300:
                rd = (lambda n: r.raw.read1(n, decode_content=True)) if hasattr(r.raw, "read1") else (lambda n: r.raw.read(n, decode_content=True))
                body = b""
                while len(body) < max_body:
                    if stop.is_set() or time.monotonic() - t0 > deadline: raise Timeout(f"no complete answer within {deadline:g}s")
                    chunk = rd(min(4096, max_body - len(body)))
                    if not chunk: break
                    body += chunk; box["body"] = body
                    if until and until(r, body): break
        finally:
            r.close()
        return r
    done, r = _bounded(work, deadline)
    body = box["body"]
    if not done:
        stop.set()
        def _close(x):
            try: x.close()
            except Exception: pass
        # Close from yet another daemon thread: Response.close() can block on the stuck reader's lock. This unblocks a
        # worker stuck reading the body; a worker stuck in the header phase is simply abandoned (daemon).
        if box.get("r") is not None: threading.Thread(target=_close, args=(box["r"],), daemon=True).start()
        r = box.get("r")
        if r is not None and until and until(r, body): return r, body
        return Timeout(f"no complete answer within {deadline:g}s"), body
    return r, body

def jsonrpc_response(body, ctype=""):
    """The JSON-RPC 2.0 response to our initialize (id 1), from a JSON body or an SSE `data:` line; else None."""
    def ok(j): return j if isinstance(j, dict) and j.get("jsonrpc") == "2.0" and j.get("id") == 1 and ("result" in j or "error" in j) else None
    text = body.decode("utf-8", "replace")
    if "text/event-stream" in ctype:
        for line in text.splitlines():
            if line.startswith("data:"):
                try: j = ok(json.loads(line[5:].strip()))
                except ValueError: j = None
                if j: return j
        return None
    if "json" in ctype:
        try: return ok(json.loads(text))
        except ValueError: return None
    return None

# --- MCP OAuth evidence (QA rule for 401s, PR #18) ---------------------------------------------
# Only a 401 can count as verified (a 403 is always Needs review), and only if ALL of these hold:
#  (a) WWW-Authenticate is a Bearer challenge with an https resource_metadata URL whose host is EXACTLY the
#      endpoint's host (case-insensitive), or a host listed for that endpoint host in VENDOR_AUTH_HOSTS.
#      No registrable-domain / public-suffix logic: sibling subdomains do not count.
#  (b) that URL answers 200 (redirects are NOT followed) with a valid JSON object;
#  (c) its "resource" is a valid URL with the endpoint's origin (scheme, host, port) and its path is a segment
#      prefix of the endpoint's path (e.g. resource https://x.com or https://x.com/mcp for endpoint https://x.com/mcp);
#  (d) it lists at least one non-empty authorization_servers entry.
# Anything weaker (bare 401, missing/foreign/unloadable metadata, bad or mismatched resource, no auth servers) -> gated.
# A metadata fetch that errors or answers 5xx is retried once before it counts against the tool.
#
# VENDOR_AUTH_HOSTS: exact endpoint host -> exact extra hosts allowed to serve its metadata. Ships EMPTY (all
# current tools serve metadata on the endpoint host). Every entry needs a comment linking the vendor's docs.
VENDOR_AUTH_HOSTS: dict[str, frozenset] = {}

def _host(u):
    return (urlsplit(u).hostname or "").lower().rstrip(".")

def _origin(u):
    """(scheme, host, port); raises ValueError on an invalid URL/port."""
    p = urlsplit(u)
    port = p.port or {"https": 443, "http": 80}.get(p.scheme)
    if not p.hostname: raise ValueError("no host")
    return (p.scheme.lower(), p.hostname.lower().rstrip("."), port)

def _path_prefix(resource_path, endpoint_path):
    rp, ep = resource_path.rstrip("/"), endpoint_path.rstrip("/")
    return ep == rp or ep.startswith(rp + "/")

class _Meta:
    def __init__(self, status, body): self.status_code, self._b = status, body
    def json(self): return json.loads(self._b.decode("utf-8"))

def fetch_metadata(u, end=None):
    """GET protected-resource metadata: redirects NOT followed, bounded size and time, one retry on error/5xx while
    the endpoint's budget (`end`, a time.monotonic() value; default now + DEADLINE) has time left."""
    end = time.monotonic() + DEADLINE if end is None else end
    for attempt in (1, 2):
        r, body = _req("GET", u, deadline=end - time.monotonic(), allow_redirects=False, headers={"Accept": "application/json"})
        if not isinstance(r, Exception) and r.status_code < 500: return _Meta(r.status_code, body)
        if isinstance(r, UnsafeURL): break
    if isinstance(r, Exception): raise r if isinstance(r, requests.RequestException) else requests.RequestException(str(r) or type(r).__name__)
    return _Meta(r.status_code, body)

def oauth_evidence(endpoint, www_auth, fetch=None, end=None):
    """QA's strict 401 rule. Returns (True, metadata_url) or (False, reason). Never raises."""
    fetch = fetch or (lambda u: fetch_metadata(u, end=end))
    wa = (www_auth or "").strip()
    if not wa.lower().startswith("bearer"): return False, "no Bearer challenge"
    m = re.search(r'resource_metadata="?([^",\s]+)', wa)
    if not m: return False, "no resource_metadata in WWW-Authenticate"
    md_url = m.group(1)
    bad = url_problem(md_url)
    if bad: return False, f"resource_metadata refused: {bad}"
    try: mp = urlsplit(md_url); md_host = (mp.hostname or "").lower().rstrip("."); mp.port
    except ValueError: return False, "resource_metadata is not a valid URL"
    if mp.scheme != "https" or not md_host: return False, "resource_metadata is not an https URL"
    ep_host = _host(endpoint)
    if md_host != ep_host and md_host not in VENDOR_AUTH_HOSTS.get(ep_host, frozenset()):
        return False, f"resource_metadata on {md_host}, not the endpoint host {ep_host} or an allowlisted vendor auth host"  # (a)
    try: r = fetch(md_url)
    except Exception as e: return False, f"metadata fetch failed ({type(e).__name__})"
    if r.status_code != 200: return False, f"metadata answered {r.status_code}"                          # (b)
    try: j = r.json()
    except ValueError: return False, "metadata is not valid JSON"                                        # (b)
    if not isinstance(j, dict): return False, "metadata is not a JSON object"                            # (b)
    res = j.get("resource")
    if not isinstance(res, str) or not res: return False, "metadata has no resource"                     # (c)
    bad = url_problem(res)
    if bad: return False, f"metadata resource {res[:120]!r} refused: {bad}"                              # (c)
    try: same = _origin(res) == _origin(endpoint) and _path_prefix(urlsplit(res).path, urlsplit(endpoint).path)
    except ValueError: return False, f"metadata resource {res[:120]!r} is not a valid URL"                # (c)
    if not same: return False, f"metadata resource {res[:120]} does not match endpoint origin/path"      # (c)
    au = j.get("authorization_servers")
    if not isinstance(au, list) or not any(isinstance(x, str) and x.strip() for x in au):
        return False, "metadata lists no authorization_servers"                                          # (d)
    return True, md_url

def mcp_probe(url):
    """Remote MCP endpoint: POST a JSON-RPC `initialize` (what a real client sends), not a bare GET.
    ok     2xx with a real JSON-RPC response to initialize (application/json or an SSE data: event), or a 401 that
           passes oauth_evidence() (QA's strict rule). A 2xx HTML page / challenge page is NOT ok.
    gated  any other 401, every 403 (even with good metadata), a 2xx without a JSON-RPC answer, a stream that
           stays open past DEADLINE, a legacy-SSE GET that does not answer text/event-stream.
    other  POST refused with 405/other 4xx -> retry with GET (legacy SSE transport), then classify() as usual."""
    hdr = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    def ct(resp): return (resp.headers.get("Content-Type") or "").lower()
    def done(resp, body): return jsonrpc_response(body, ct(resp)) is not None
    def left(): return end - time.monotonic()
    bad = url_problem(url)
    if bad: return link(url, "UnsafeURL", "gated", method="POST", why=f"endpoint URL refused: {bad}")
    end = time.monotonic() + DEADLINE  # one budget for every request this endpoint needs
    try:
        r, body = _req("POST", url, json=MCP_INIT, headers=hdr, until=done, deadline=left())
    except Exception as e:  # belt and braces: _req never raises
        r, body = e, b""
    if isinstance(r, Timeout): return link(url, "Timeout", "gated", method="POST", why=str(r))
    if isinstance(r, UnsafeURL): return link(url, "UnsafeURL", "gated", method="POST", why=str(r))
    if isinstance(r, Exception): return link(url, type(r).__name__, "error", method="POST")
    if r.status_code < 300:
        if done(r, body) and not _challenge(r): return link(url, r.status_code, "ok", method="POST", evidence="mcp-initialize")
        why = "bot challenge page (cf-mitigated)" if _challenge(r) else f"{r.status_code} {ct(r) or 'no content-type'} without a JSON-RPC initialize response"
        return link(url, r.status_code, "gated", method="POST", why=why)
    if 300 <= r.status_code < 400:
        return link(url, r.status_code, "gated", method="POST", why=f"redirects to {r.headers.get('Location') or '?'} (not followed)")
    if r.status_code == 401:
        ok, info = oauth_evidence(url, r.headers.get("WWW-Authenticate"), end=end)
        if ok: return link(url, r.status_code, "ok", method="POST", evidence="mcp-oauth", resource_metadata=info)
        return link(url, r.status_code, "gated", method="POST", why=info)
    if r.status_code == 403:
        return link(url, 403, "gated", method="POST", why="403 is never verified (policy: only a 401 with valid OAuth metadata counts)")
    if r.status_code in DEAD or r.status_code == 429 or r.status_code >= 500:
        return link(url, r.status_code, classify(r.status_code), method="POST")
    def sse_ok(resp, b): return b"event:" in b or b"data:" in b
    g, gb = _req("GET", url, headers={"Accept": "text/event-stream"}, until=sse_ok, deadline=left())
    if isinstance(g, Timeout): return link(url, "Timeout", "gated", method="GET", post_status=r.status_code, why=str(g))
    if isinstance(g, Exception): return link(url, type(g).__name__, "error", method="GET", post_status=r.status_code)
    if 300 <= g.status_code < 400:
        return link(url, g.status_code, "gated", method="GET", post_status=r.status_code,
                    why=f"redirects to {g.headers.get('Location') or '?'} (not followed)")
    if g.status_code < 300:
        gct = (g.headers.get("Content-Type") or "").lower()
        if "text/event-stream" in gct and sse_ok(g, gb) and not _challenge(g):
            return link(url, g.status_code, "ok", method="GET", post_status=r.status_code, evidence="sse-get")
        return link(url, g.status_code, "gated", method="GET", post_status=r.status_code,
                    why=f"GET {g.status_code} {gct or 'no content-type'} is not an MCP SSE stream")
    return link(url, g.status_code, classify(g.status_code), method="GET", post_status=r.status_code)

LABEL = {"homepage alive": "homepage", "docs alive": "docs", "remote MCP endpoint responds": "MCP endpoint"}
NOTE = {"dead": "{s}: not found (dead link)", "fail": "{s}: client error", "error": "{s}: server/connection error",
        "gated": "{s}: answered but refused our checker (sign-in required, bot block or rate limit)",
        "timeout": "timed out: no complete answer in time", "refused": "{s}: not checked, the URL was refused"}

LIC = [("Apache-2.0", r"Apache License"), ("MIT", r"\bMIT License|Permission is hereby granted, free of charge"),
       ("AGPL-3.0", r"GNU AFFERO GENERAL PUBLIC"), ("LGPL", r"GNU LESSER GENERAL PUBLIC"), ("GPL-3.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 3"),
       ("GPL-2.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 2"), ("BSD-3-Clause", r"Redistribution and use in source and binary forms"),
       ("MPL-2.0", r"Mozilla Public License"), ("Unlicense", r"This is free and unencumbered"), ("ISC", r"\bISC License")]

def api(path):
    """GitHub REST GET: GITHUB_TOKEN if set, else the logged-in `gh` CLI if available, else None."""
    if TOKEN:
        r = get(f"https://api.github.com/{path}", headers={"Authorization": f"Bearer {TOKEN}"})
        return r.json() if not isinstance(r, Exception) and r.status_code == 200 else None
    if shutil.which("gh"):
        try:
            p = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=30)
            return json.loads(p.stdout) if p.returncode == 0 else None
        except Exception: return None
    return None

def parse_repo(url):
    """https://github.com/o/r[/tree/<branch>/<sub/path>] -> (owner, repo, branch|None, subpath|None)."""
    m = re.match(r"https://github.com/([^/]+)/([^/#?]+)(?:/tree/([^/]+)/([^#?]+?))?/?$", url)
    return m.group(1), m.group(2), m.group(3), m.group(4)

def raw(owner, repo, path):
    r = get(f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{path}")
    return r.text if not isinstance(r, Exception) and r.status_code == 200 else None

def gh_info(repo_url, collection=False):
    owner, name, branch, sub = parse_repo(repo_url)
    orig_owner = owner
    out = {"reachable": False}
    j = api(f"repos/{owner}/{name}")
    if j:
        lic = (j.get("license") or {}).get("spdx_id")
        out.update(reachable=True, final_url=j["html_url"], stars=j["stargazers_count"], archived=j["archived"],
                   license=None if lic in (None, "NOASSERTION", "OTHER") else lic, last_commit=j["pushed_at"])
        owner, name = j["owner"]["login"], j["name"]
    if not out["reachable"]:
        r = get(f"https://github.com/{owner}/{name}")
        if isinstance(r, Exception) or r.status_code != 200:
            out["status"] = getattr(r, "status_code", type(r).__name__); return out, owner, name
        html = r.text
        fm = re.match(r"https://github.com/([^/]+)/([^/#?]+)", r.url)
        if fm: owner, name = fm.group(1), fm.group(2)
        out.update(reachable=True, final_url=f"https://github.com/{owner}/{name}")
        sm = re.search(r'"stargazerCount":(\d+)', html) or re.search(r'id="repo-stars-counter-star"[^>]*title="([\d,]+)"', html)
        out["stars"] = int(sm.group(1).replace(",", "")) if sm else None
        out["archived"] = "This repository has been archived" in html
        a = get(f"https://github.com/{owner}/{name}/commits.atom")
        if not isinstance(a, Exception) and a.status_code == 200:
            um = re.search(r"<entry>.*?<updated>([^<]+)</updated>", a.text, re.S)
            out["last_commit"] = um.group(1) if um else None
        lm = re.search(r'"spdxId":"([^"]+)"', html)
        out["license"] = lm.group(1) if lm and lm.group(1) not in ("NOASSERTION", "OTHER") else None
    if out.get("final_url"):
        fo = re.match(r"https://github.com/([^/]+)/", out["final_url"] + "/").group(1)
        if fo.lower() != orig_owner.lower():
            # Repo moved to a different owner/org (e.g. OpenBB-finance -> openbq-org). Never auto-follow into stored links.
            out["cross_org_redirect"] = out["final_url"]
    if collection or sub:
        # Shared list / monorepo: the repo's stars belong to the whole collection, never to one entry.
        out["collection"] = True; out["collection_stars"] = out.get("stars"); out["stars"] = None
        if sub:
            out["subpath"] = sub
            c = api(f"repos/{owner}/{name}/commits?path={sub}&per_page=1")
            if c: out["last_commit"] = c[0]["commit"]["committer"]["date"]
            out["subpath_exists"] = api(f"repos/{owner}/{name}/contents/{sub}") is not None
    if not out.get("license"):
        for fn in ("LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "license"):
            t = raw(owner, name, fn)
            if t:
                out["license"] = next((k for k, p in LIC if re.search(p, t, re.I)), "Other (see repo)"); break
    return out, owner, name

def detect_packages(owner, name):
    pk = {}
    pj = raw(owner, name, "package.json")
    if pj:
        try:
            j = json.loads(pj)
            if j.get("name") and not j.get("private"): pk["npm_candidate"] = j["name"]
        except Exception: pass
    pp = raw(owner, name, "pyproject.toml")
    if pp:
        try:
            n = tomllib.loads(pp).get("project", {}).get("name")
            if n: pk["pypi_candidate"] = n
        except Exception: pass
    return pk

def links_back(blob, owner, name):
    return f"{owner}/{name}".lower() in json.dumps(blob).lower()

def npm(name):
    r = get(f"https://registry.npmjs.org/{name.replace('/', '%2F')}")
    if isinstance(r, Exception) or r.status_code != 200: return None
    j = r.json(); v = j.get("dist-tags", {}).get("latest")
    lb = json.dumps([j.get("repository"), j.get("homepage"), j.get("bugs")]).lower()
    return {"_raw_links_back": None, "_lb": lb, "name": name, "version": v, "published": j.get("time", {}).get(v), "url": f"https://www.npmjs.com/package/{name}"}

def pypi(name):
    r = get(f"https://pypi.org/pypi/{name}/json")
    if isinstance(r, Exception) or r.status_code != 200: return None
    j = r.json(); v = j["info"]["version"]; files = j.get("releases", {}).get(v) or [{}]
    lb = json.dumps([j["info"].get("project_urls"), j["info"].get("home_page"), j["info"].get("download_url")]).lower()
    return {"_raw_links_back": None, "_lb": lb, "name": j["info"]["name"], "version": v, "published": files[0].get("upload_time_iso_8601"), "url": f"https://pypi.org/project/{j['info']['name']}/"}

def age_days(ts):
    if not ts: return None
    return (NOW - dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))).days

def verify(t):
    v = {"checked_at": NOW.strftime("%Y-%m-%d"), "checks": [], "issues": []}
    if t.get("repo"):
        g, owner, name = gh_info(t["repo"], collection=t.get("repo_is_collection", False))
        v["github"] = g
        v["checks"].append({"check": "repo reachable", "ok": g["reachable"]})
        if g["reachable"]:
            pk = detect_packages(owner, name)
            if t["type"] == "skill":
                v["claude_marketplace"] = raw(owner, name, ".claude-plugin/marketplace.json") is not None
                v["root_skill_md"] = raw(owner, name, (g["subpath"] + "/" if g.get("subpath") else "") + "SKILL.md") is not None
            for kind, fn in (("npm", npm), ("pypi", pypi)):
                cand = pk.get(f"{kind}_candidate")
                if not cand: continue
                res = fn(cand)
                if res:
                    res.pop("_raw_links_back"); res["links_back"] = f"{owner}/{name}".lower() in res.pop("_lb")
                if res and res["links_back"]:
                    v[kind] = res
                elif res:
                    v["issues"].append(f"{kind} name '{cand}' exists on the registry but does not link to this repo (not counted)")
            v["checks"].append({"check": "package published", "ok": bool(v.get("npm") or v.get("pypi")),
                                "note": "no npm/PyPI package detected at repo root" if not (v.get("npm") or v.get("pypi")) else None})
    for key in ("homepage", "docs"):
        if t.get(key) and t.get(key) != t.get("repo"):
            a = alive(t[key]); v[key] = a
            v["checks"].append({"check": f"{key} alive", "ok": a["ok"], "result": a["result"],
                                "note": _note(a)})
    if t.get("remote_mcp_url"):
        a = mcp_probe(t["remote_mcp_url"]); v["remote_mcp"] = a
        v["checks"].append({"check": "remote MCP endpoint responds", "ok": a["ok"], "result": a["result"],
                            "note": _note(a)})
    g = v.get("github")
    if g and g.get("cross_org_redirect"):
        v["issues"].append(f"Repository redirects to another owner ({g['cross_org_redirect']}); stored link not updated")
    v["status"] = status_of(v)
    return v

def recheck_demotions(todo, fresh, current, fn=None):
    """One retry before a tool drops from verified (e.g. to Needs review): a transient network error must not
    demote it. The second result is final and is marked `rechecked`."""
    fn = fn or safe_verify
    again = [t for t in todo if (current.get(t["id"]) or {}).get("verification", {}).get("status") == "verified"
             and fresh[t["id"]]["status"] != "verified"]
    if again:
        with ThreadPoolExecutor(8) as ex: retry = dict(zip([t["id"] for t in again], ex.map(fn, again)))
        for i, v in retry.items(): v["rechecked"] = True; fresh[i] = v
    return [t["id"] for t in again]

TOOL_DEADLINE = 150.0  # last-resort hard cap for one tool's whole verify() (GitHub, packages, links, endpoint)

def safe_verify(t):
    """verify() that can never abort or hang the run: an unexpected error, or a verify() still running after
    TOOL_DEADLINE seconds, makes only this tool Needs review."""
    done, v = _bounded(lambda: verify(t), TOOL_DEADLINE)
    if done and not isinstance(v, BaseException): return v
    why = f"checker error ({type(v).__name__})" if done else f"checker timed out after {TOOL_DEADLINE:g}s"
    return {"checked_at": NOW.strftime("%Y-%m-%d"), "checks": [], "status": "unconfirmed", "issues": [f"Could not confirm: {why}"]}

def _note(a):
    if a["ok"]: return None
    key = {"Timeout": "timeout", "UnsafeURL": "refused"}.get(a["status"], a["result"]) if a["result"] == "gated" else a["result"]
    return NOTE[key].format(s=a["status"]) + (f" [{a['why']}]" if a.get("why") else "")

def _why(c):
    return f"{LABEL.get(c['check'], c['check'])} {c.get('note') or 'failed'}"

def status_of(v):
    """unreachable > archived > warning (a link is dead/failed) > stale/aging > unconfirmed > verified.
    "unconfirmed" (Needs review) replaces "verified" when any link was gated (401/403/405/429, no JSON-RPC answer,
    timeout ...) or the repo redirects to another owner. Only "verified" counts toward the verified totals."""
    g = v.get("github")
    if g and not g["reachable"]: v["issues"].append("Repository not reachable"); return "unreachable"
    if g and g.get("archived"): v["issues"].append("Repository is archived"); return "archived"
    links = [c for c in v["checks"] if c["check"] not in ("package published", "repo reachable")]
    days = age_days(g.get("last_commit")) if g else None
    v["last_commit_days"] = days
    failed = [c for c in links if c.get("result", "ok" if c["ok"] else "error") in FAILURES]
    gated = [c for c in links if c.get("result") == "gated"]
    if failed:
        v["issues"].append("A homepage/docs/endpoint link failed: " + "; ".join(_why(c) for c in failed)); return "warning"
    if gated:
        v["issues"].append("Could not confirm: " + "; ".join(_why(c) for c in gated))
    cross = bool(g and g.get("cross_org_redirect"))  # moved to another owner: the stored link is unconfirmed
    if days is None: status = "verified" if not g else "warning"
    elif days <= 180: status = "verified"
    elif days <= 365: status = "aging"; v["issues"].append(f"No commits for {days} days")
    else: status = "stale"; v["issues"].append(f"No commits for {days} days")
    return "unconfirmed" if status == "verified" and (gated or cross) else status

def repo_key(t):
    o, n, _, _ = parse_repo(t["repo"]); return f"{o}/{n}".lower()

def parse_args(args, known_ids):
    """`--dry-run` plus `--only=...`; returns (only, dry_run)."""
    dry = "--dry-run" in args
    return parse_only([a for a in args if a != "--dry-run"], known_ids), dry

def parse_only(args, known_ids):
    """Parse `--only=a,b` or `--only a,b`. Any other argument, an empty list or an unknown id exits with an error,
    so a mistyped flag can never silently fall back to a full run."""
    only, i = None, 0
    while i < len(args):
        a = args[i]
        if a.startswith("--only="):
            val = a.split("=", 1)[1]
        elif a == "--only":
            if i + 1 >= len(args) or args[i + 1].startswith("-"):
                sys.exit("verify.py: --only needs a comma-separated list of ids, e.g. --only=openbb,fred-api")
            i += 1
            val = args[i]
        else:
            sys.exit(f"verify.py: unknown argument {a!r} (usage: verify.py [--dry-run] [--only=id1,id2])")
        ids = [x.strip() for x in val.split(",") if x.strip()]
        if not ids:
            sys.exit("verify.py: --only needs at least one id")
        unknown = [x for x in ids if x not in known_ids]
        if unknown:
            sys.exit(f"verify.py: unknown id(s) for --only: {', '.join(unknown)}")
        only = (only or []) + ids
        i += 1
    return only


def main():
    seed = json.load(open(os.path.join(ROOT, "data/seed.json")))
    # A repo shared by several entries is a collection/monorepo: none of them gets its stars.
    from collections import Counter
    shared = Counter(repo_key(t) for t in seed if t.get("repo"))
    for t in seed:
        if t.get("repo") and (shared[repo_key(t)] > 1 or parse_repo(t["repo"])[1].lower().startswith("awesome-")):
            t["repo_is_collection"] = True
    # --only id1,id2: re-verify just those entries, keep the rest from the current data/tools.json
    only, dry = parse_args(sys.argv[1:], {t["id"] for t in seed})
    tp = os.path.join(ROOT, "data/tools.json")
    current = {x["id"]: x for x in json.load(open(tp))} if os.path.exists(tp) else {}
    prev = current if only else {}
    todo = [t for t in seed if not only or t["id"] in only or t["id"] not in prev]
    with ThreadPoolExecutor(8) as ex: fresh = dict(zip([t["id"] for t in todo], ex.map(safe_verify, todo)))
    recheck_demotions(todo, fresh, current)
    tools = []
    for t in seed:
        if t["id"] not in fresh:
            tools.append(prev[t["id"]]); continue
        v = fresh[t["id"]]
        t = dict(t); t["verification"] = v
        g = v.get("github") or {}
        t["license"] = g.get("license") or ("Proprietary / ToS" if t["type"] == "api" or not t.get("repo") else "unknown")
        # keep subfolder URLs (collections) and pinned slugs; otherwise follow GitHub renames
        if g.get("final_url") and not g.get("collection") and not t.get("repo_keep") and not g.get("cross_org_redirect"): t["repo"] = g["final_url"]
        tools.append(t)
    if dry:
        dry_report(tools, current); return
    json.dump(tools, open(tp, "w"), indent=2)
    c = Counter(t["verification"]["status"] for t in tools)
    rep = {"checked_at": NOW.isoformat(), "total": len(tools), "by_status": dict(c),
           "with_package": sum(1 for t in tools if t["verification"].get("npm") or t["verification"].get("pypi")),
           "issues": [{"id": t["id"], "status": t["verification"]["status"], "issues": t["verification"]["issues"]} for t in tools if t["verification"]["issues"]]}
    json.dump(rep, open(os.path.join(ROOT, "data/verification-report.json"), "w"), indent=2)
    lines = [f"# Verification report — {NOW:%Y-%m-%d %H:%M} UTC", "", f"Total entries: {len(tools)}", ""]
    lines += [f"- {k}: {n}" for k, n in c.most_common()]
    lines += ["", f"Entries with a published npm/PyPI package: {rep['with_package']}", "", "| id | status | stars | last commit | license | package | issues |", "|---|---|---|---|---|---|---|"]
    for t in tools:
        v = t["verification"]; g = v.get("github") or {}; p = v.get("npm") or v.get("pypi")
        lines.append(f"| {t['id']} | {v['status']} | {g.get('stars','')} | {(g.get('last_commit') or '')[:10]} | {t['license']} | {(p['name']+'@'+p['version']) if p else ''} | {'; '.join(v['issues'])} |")
    open(os.path.join(ROOT, "data/verification-report.md"), "w").write("\n".join(lines) + "\n")
    write_history(tools)
    print(json.dumps({k: rep[k] for k in ("total", "by_status", "with_package")}))

LINK_KEYS = (("homepage", "homepage"), ("docs", "docs"), ("remote_mcp", "MCP endpoint"))

def link_ok(l):
    return l.get("result", "ok" if l.get("ok") else "error")

def diff_rows(tools, current):
    """Rows for every tool whose status changes vs data/tools.json, with the links behind the change."""
    rows = []
    for t in tools:
        old = (current.get(t["id"]) or {}).get("verification", {})
        new = t["verification"]
        if old.get("status") == new["status"]: continue
        why = [f"{lbl} {new[k]['url']} -> {new[k]['status']} ({link_ok(new[k])})" for k, lbl in LINK_KEYS
               if new.get(k) and link_ok(new[k]) != "ok"]
        rows.append({"id": t["id"], "name": t["name"], "old": old.get("status", "(new)"), "new": new["status"], "why": why or new["issues"]})
    return rows

def dry_report(tools, current):
    """--dry-run: verify everything, write nothing; print status changes vs the current data/tools.json."""
    from collections import Counter
    rows = diff_rows(tools, current)
    print(f"# verify.py --dry-run ({NOW:%Y-%m-%d %H:%M} UTC): nothing written", file=sys.stderr)
    print("| tool | old | new | why |\n|---|---|---|---|")
    for r in rows: print(f"| {r['name']} (`{r['id']}`) | {r['old']} | {r['new']} | {'<br>'.join(r['why'])} |")
    old_c = Counter(x["verification"]["status"] for x in current.values()); new_c = Counter(t["verification"]["status"] for t in tools)
    print(json.dumps({"changed": len(rows), "old_by_status": dict(old_c), "new_by_status": dict(new_c),
                      "verified_old": old_c.get("verified", 0), "verified_new": new_c.get("verified", 0)}), file=sys.stderr)
    out = os.environ.get("VERIFY_DRY_JSON")
    if out: json.dump(tools, open(out, "w"), indent=2)

def write_history(tools):
    """Snapshot this run and diff it against the previous snapshot -> data/changelog.json (feeds /weekly and /rss.xml)."""
    hd = os.path.join(ROOT, "data/history"); os.makedirs(hd, exist_ok=True)
    today = NOW.strftime("%Y-%m-%d")
    snap = {t["id"]: {"name": t["name"], "status": t["verification"]["status"], "stars": None if t.get("repo_is_collection") else (t["verification"].get("github") or {}).get("stars"),
                      "version": ((t["verification"].get("npm") or t["verification"].get("pypi")) or {}).get("version")} for t in tools}
    prev_files = sorted(f for f in os.listdir(hd) if f.endswith(".json") and f[:-5] < today)
    prev = json.load(open(os.path.join(hd, prev_files[-1]))) if prev_files else None
    json.dump(snap, open(os.path.join(hd, f"{today}.json"), "w"), indent=1)
    ch = []
    if prev is None:
        ch.append({"kind": "launch", "text": f"First verification run: {len(snap)} tools checked."})
    else:
        for i, s in snap.items():
            p = prev.get(i)
            if not p: ch.append({"kind": "new", "id": i, "text": f"New: {s['name']} added."}); continue
            if p["status"] != s["status"]: ch.append({"kind": "status", "id": i, "text": f"{s['name']}: {p['status']} → {s['status']}"})
            if p.get("version") and s.get("version") and p["version"] != s["version"]: ch.append({"kind": "release", "id": i, "text": f"{s['name']} released {s['version']} (was {p['version']})"})
            if p.get("stars") and s.get("stars") and s["stars"] - p["stars"] >= 25: ch.append({"kind": "stars", "id": i, "text": f"{s['name']} gained {s['stars'] - p['stars']} stars"})
        for i in set(prev) - set(snap): ch.append({"kind": "removed", "id": i, "text": f"Removed: {prev[i]['name']}"})
    cp = os.path.join(ROOT, "data/changelog.json")
    log = json.load(open(cp)) if os.path.exists(cp) else []
    log = [e for e in log if e["date"] != today]
    log.insert(0, {"date": today, "counts": dict(__import__("collections").Counter(s["status"] for s in snap.values())), "changes": ch})
    json.dump(log, open(cp, "w"), indent=2)

if __name__ == "__main__": main()
