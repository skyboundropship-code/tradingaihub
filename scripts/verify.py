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
import json, os, re, sys, shutil, subprocess, datetime as dt, tomllib
from concurrent.futures import ThreadPoolExecutor
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "FinanceAgentDirectoryBot/0.1 (weekly link check)"}
TOKEN = os.environ.get("GITHUB_TOKEN")
NOW = dt.datetime.now(dt.timezone.utc)
S = requests.Session(); S.headers.update(UA)

def get(url, **kw):
    try:
        return S.get(url, timeout=20, allow_redirects=True, **kw)
    except requests.RequestException as e:
        return e

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

def alive(url):
    """GET a homepage/docs URL. We never trust HEAD (many servers answer HEAD with 403/405), and a bot-blocked
    403/429 gets one retry with browser headers; if that is still refused the link stays "gated"."""
    if not url: return None
    r = get(url)
    if isinstance(r, Exception): return link(url, type(r).__name__, "error")
    res = classify(r.status_code)
    if r.status_code in (403, 429):
        r2 = get(url, headers=BROWSER)
        if not isinstance(r2, Exception) and classify(r2.status_code) == "ok":
            return link(url, r2.status_code, "ok", first_status=r.status_code, retry="browser-headers")
    return link(url, r.status_code, res)

MCP_INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "tradingaihub-verify", "version": "0.2"}}}

def _req(method, url, **kw):
    try:
        r = S.request(method, url, timeout=20, allow_redirects=True, stream=True, **kw)
        body = r.raw.read(4096, decode_content=True) if r.status_code < 300 else b""
        r.close(); return r, body
    except requests.RequestException as e:
        return e, b""

# --- MCP OAuth evidence (QA rule for 401s, PR #18) ---------------------------------------------
# A 401/403 from a remote MCP endpoint counts as verified ONLY if ALL of these hold:
#  (a) WWW-Authenticate is a Bearer challenge with a resource_metadata URL (https) whose host is on the same
#      registrable domain as the endpoint, or on a vendor auth domain listed in VENDOR_AUTH_DOMAINS;
#  (b) that URL answers 200 (redirects are NOT followed) with a valid JSON object;
#  (c) its "resource" has the endpoint's origin (scheme, host, port) and its path is a segment prefix of the
#      endpoint's path (e.g. resource https://x.com or https://x.com/mcp for endpoint https://x.com/mcp);
#  (d) it lists at least one non-empty authorization_servers entry.
# Anything weaker (bare 401, missing/foreign/unloadable metadata, mismatched resource, no auth servers) -> gated.
#
# VENDOR_AUTH_DOMAINS: endpoint registrable domain -> extra registrable domains allowed to host its metadata.
# Keep it empty or minimal; every entry needs a reason (link to the vendor's docs) next to it.
VENDOR_AUTH_DOMAINS: dict[str, frozenset] = {}
# Multi-label public suffixes we may meet (registrable domain = suffix + one label). Not the full Public Suffix
# List: an unknown multi-label suffix makes the check STRICTER (falls back to the last two labels), never looser.
MULTI_SUFFIXES = frozenset({"co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "net.au", "org.au", "co.nz", "co.jp", "ne.jp",
                            "or.jp", "co.kr", "co.in", "net.in", "org.in", "com.br", "com.cn", "com.hk", "com.sg", "com.tr",
                            "com.mx", "co.za", "co.il", "com.tw", "github.io", "pages.dev", "workers.dev", "vercel.app",
                            "netlify.app", "herokuapp.com", "onrender.com", "fly.dev", "azurewebsites.net", "cloudfront.net"})

def registrable_domain(host):
    h = (host or "").lower().rstrip(".")
    if not h or re.fullmatch(r"[\d.]+|\[.*\]", h): return h  # IP literal: exact match only
    parts = h.split(".")
    n = 3 if len(parts) >= 3 and ".".join(parts[-2:]) in MULTI_SUFFIXES else 2
    return ".".join(parts[-n:])

def _origin(u):
    p = urlsplit(u)
    port = p.port or {"https": 443, "http": 80}.get(p.scheme)
    return (p.scheme.lower(), (p.hostname or "").lower(), port)

def _path_prefix(resource_path, endpoint_path):
    rp, ep = resource_path.rstrip("/"), endpoint_path.rstrip("/")
    return ep == rp or ep.startswith(rp + "/")

def oauth_evidence(endpoint, www_auth, fetch=None):
    """QA's strict 401 rule. Returns (True, metadata_url) or (False, reason)."""
    fetch = fetch or (lambda u: S.get(u, timeout=20, allow_redirects=False, headers={"Accept": "application/json"}))
    wa = (www_auth or "").strip()
    if not wa.lower().startswith("bearer"): return False, "no Bearer challenge"
    m = re.search(r'resource_metadata="?([^",\s]+)', wa)
    if not m: return False, "no resource_metadata in WWW-Authenticate"
    md_url = m.group(1); mp = urlsplit(md_url)
    if mp.scheme != "https" or not mp.hostname: return False, "resource_metadata is not an https URL"
    ep_dom = registrable_domain(urlsplit(endpoint).hostname)
    md_dom = registrable_domain(mp.hostname)
    if md_dom != ep_dom and md_dom not in VENDOR_AUTH_DOMAINS.get(ep_dom, frozenset()):
        return False, f"resource_metadata on {md_dom}, not {ep_dom} or an allowlisted vendor auth domain"   # (a)
    try: r = fetch(md_url)
    except requests.RequestException as e: return False, f"metadata fetch failed ({type(e).__name__})"
    if r.status_code != 200: return False, f"metadata answered {r.status_code}"                          # (b)
    try: j = r.json()
    except ValueError: return False, "metadata is not valid JSON"                                        # (b)
    if not isinstance(j, dict): return False, "metadata is not a JSON object"                            # (b)
    res = j.get("resource")
    if not isinstance(res, str) or not res: return False, "metadata has no resource"                     # (c)
    if _origin(res) != _origin(endpoint) or not _path_prefix(urlsplit(res).path, urlsplit(endpoint).path):
        return False, f"metadata resource {res} does not match endpoint origin/path"                     # (c)
    au = j.get("authorization_servers")
    if not isinstance(au, list) or not any(isinstance(x, str) and x.strip() for x in au):
        return False, "metadata lists no authorization_servers"                                          # (d)
    return True, md_url

def mcp_probe(url):
    """Remote MCP endpoint: POST a JSON-RPC `initialize` (what a real client sends), not a bare GET.
    ok     2xx answer (JSON-RPC result or SSE stream), or a 401/403 that passes oauth_evidence() (QA's strict rule).
    gated  any other 401/403, including a bare 401.
    other  POST refused with 405/other 4xx -> retry with GET (legacy SSE transport), then classify() as usual."""
    hdr = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    r, body = _req("POST", url, json=MCP_INIT, headers=hdr)
    if isinstance(r, Exception): return link(url, type(r).__name__, "error", method="POST")
    if r.status_code < 300:
        return link(url, r.status_code, "ok", method="POST", evidence="mcp-initialize" if b"jsonrpc" in body else "2xx")
    if r.status_code in (401, 403):
        ok, info = oauth_evidence(url, r.headers.get("WWW-Authenticate"))
        if ok: return link(url, r.status_code, "ok", method="POST", evidence="mcp-oauth", resource_metadata=info)
        return link(url, r.status_code, "gated", method="POST", why=info)
    if r.status_code in DEAD or r.status_code in (401, 403, 429) or r.status_code >= 500:
        return link(url, r.status_code, classify(r.status_code), method="POST")
    g, _ = _req("GET", url, headers={"Accept": "text/event-stream"})
    if isinstance(g, Exception): return link(url, type(g).__name__, "error", method="GET", post_status=r.status_code)
    return link(url, g.status_code, classify(g.status_code), method="GET", post_status=r.status_code,
                **({"evidence": "sse-get"} if g.status_code < 300 else {}))

LABEL = {"homepage alive": "homepage", "docs alive": "docs", "remote MCP endpoint responds": "MCP endpoint"}
NOTE = {"dead": "{s}: not found (dead link)", "fail": "{s}: client error", "error": "{s}: server/connection error",
        "gated": "{s}: answered but refused our checker (sign-in required, bot block or rate limit)"}

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
                                "note": NOTE[a["result"]].format(s=a["status"]) if not a["ok"] else None})
    if t.get("remote_mcp_url"):
        a = mcp_probe(t["remote_mcp_url"]); v["remote_mcp"] = a
        v["checks"].append({"check": "remote MCP endpoint responds", "ok": a["ok"], "result": a["result"],
                            "note": (NOTE[a["result"]].format(s=a["status"]) + (f" [{a['why']}]" if a.get("why") else "")) if not a["ok"] else None})
    g = v.get("github")
    if g and g.get("cross_org_redirect"):
        v["issues"].append(f"Repository redirects to another owner ({g['cross_org_redirect']}); stored link not updated")
    v["status"] = status_of(v)
    return v

def _why(c):
    return f"{LABEL.get(c['check'], c['check'])} {c.get('note') or 'failed'}"

def status_of(v):
    """unreachable > archived > warning (a link is dead/failed) > stale/aging > unconfirmed (a link was gated) > verified.
    Only "verified" counts toward the verified totals; "unconfirmed" replaces it when any link answered 401/403/405/429...."""
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
    if days is None: status = "verified" if not g else "warning"
    elif days <= 180: status = "verified"
    elif days <= 365: status = "aging"; v["issues"].append(f"No commits for {days} days")
    else: status = "stale"; v["issues"].append(f"No commits for {days} days")
    return "unconfirmed" if status == "verified" and gated else status
    v["status"] = status
    return v

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
    with ThreadPoolExecutor(8) as ex: fresh = dict(zip([t["id"] for t in todo], ex.map(verify, todo)))
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
