#!/usr/bin/env python3
"""Weekly verifier for the directory.
Reads data/seed.json (curated entries) and writes data/tools.json (seed + verification)
and data/verification-report.{json,md}.
Checks per entry: repo reachable (+renames/archived), last commit date, stars, license,
package published on npm/PyPI (+latest version), homepage and docs links alive.
Uses the GitHub REST API when GITHUB_TOKEN is set; otherwise scrapes public HTML/Atom
(no auth, avoids the 60 req/h anonymous API limit).
Run:  python3 scripts/verify.py        (weekly via cron / GitHub Actions)"""
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

def alive(url):
    if not url: return None
    r = get(url)
    if isinstance(r, Exception): return {"url": url, "ok": False, "status": type(r).__name__}
    # 401/403/429 = reachable but gated / bot-blocked: count as reachable
    return {"url": url, "ok": r.status_code < 400 or r.status_code in (401, 403, 429), "status": r.status_code}

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
            a = alive(t[key]); v[key] = a; v["checks"].append({"check": f"{key} alive", "ok": a["ok"]})
    if t.get("remote_mcp_url"):
        a = alive(t["remote_mcp_url"])  # MCP endpoints answer 401/405/406 without auth: any HTTP answer = reachable
        a["ok"] = not isinstance(a.get("status"), str) and a["status"] < 500
        v["remote_mcp"] = a; v["checks"].append({"check": "remote MCP endpoint responds", "ok": a["ok"]})
    # status
    g = v.get("github")
    if g and not g["reachable"]: status = "unreachable"; v["issues"].append("Repository not reachable")
    elif g and g.get("archived"): status = "archived"; v["issues"].append("Repository is archived")
    else:
        days = age_days(g.get("last_commit")) if g else None
        links_ok = all(c["ok"] for c in v["checks"] if c["check"] != "package published")
        if not links_ok: status = "warning"; v["issues"].append("A homepage/docs/endpoint link failed")
        elif days is None: status = "verified" if not g else "warning"
        elif days <= 180: status = "verified"
        elif days <= 365: status = "aging"; v["issues"].append(f"No commits for {days} days")
        else: status = "stale"; v["issues"].append(f"No commits for {days} days")
        v["last_commit_days"] = days
    v["status"] = status
    return v

def repo_key(t):
    o, n, _, _ = parse_repo(t["repo"]); return f"{o}/{n}".lower()

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
            sys.exit(f"verify.py: unknown argument {a!r} (usage: verify.py [--only=id1,id2])")
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
    only = parse_only(sys.argv[1:], {t["id"] for t in seed})
    prev = {x["id"]: x for x in json.load(open(os.path.join(ROOT, "data/tools.json")))} if only else {}
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
        if g.get("final_url") and not g.get("collection") and not t.get("repo_keep"): t["repo"] = g["final_url"]
        tools.append(t)
    json.dump(tools, open(os.path.join(ROOT, "data/tools.json"), "w"), indent=2)
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
