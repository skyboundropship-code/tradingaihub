#!/usr/bin/env python3
"""Generates awesome/README.md — a GitHub awesome-list mirror of the directory (backlink + discovery loop).
Placeholder brand/URL are read from src/config.ts so a rename stays in one place."""
import json, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cfg = open(os.path.join(ROOT, "src/config.ts")).read()
brand = re.search(r'name: "([^"]+)"', cfg).group(1); url = re.search(r'url: "([^"]+)"', cfg).group(1)
lib = open(os.path.join(ROOT, "src/lib/data.ts")).read()
cats = re.findall(r'slug: "([^"]+)", name: "([^"]+)", short: "[^"]+", icon: "([^"]+)"', lib)
tools = json.load(open(os.path.join(ROOT, "data/tools.json")))
def stars_of(t):  # None for shared lists/monorepos: their stars belong to the collection, not one entry
    g = t["verification"].get("github") or {}
    return None if (t.get("repo_is_collection") or g.get("collection")) else g.get("stars")
ok = {"verified": "✅", "aging": "🟡", "warning": "🟡", "stale": "🔴", "archived": "🗄️", "unreachable": "❌"}
date = tools[0]["verification"]["checked_at"]
L = [f"# Awesome Finance & Trading AI Tools [![Awesome](https://awesome.re/badge.svg)](https://awesome.re)", "",
     f"> A curated, **automatically re-verified** list of MCP servers, agent skills and APIs for finance and trading. Mirror of [{brand}]({url}) — status checked weekly (last: {date}).", "",
     "Legend: ✅ verified · 🟡 aging (6–12 months without commits) · 🔴 stale (12+ months) · 🗄️ archived. ⭐ = GitHub stars. Not investment advice.", "", "## Contents", ""]
L += [f"- [{n}](#{re.sub(r'[^a-z0-9 -]', '', n.lower()).strip().replace(' ', '-')})" for s, n, i in cats]
for s, n, i in cats:
    items = sorted([t for t in tools if t["category"] == s], key=lambda t: -(stars_of(t) or 0))
    if not items: continue
    L += ["", f"## {n}", ""]
    for t in items:
        g = t["verification"].get("github") or {}; link = t.get("repo") or t.get("homepage")
        stars = f" ⭐ {stars_of(t):,}" if stars_of(t) is not None else ""
        off = " *(official)*" if t.get("official") else ""
        L.append(f"- {ok.get(t['verification']['status'], '')} [{t['name']}]({link}){off} — {t['description']}{stars} · [details]({url}/tools/{t['id']}/)")
L += ["", "## Contributing", "", f"Submit a tool for free at {url}/submit/ or open a PR. Entries are re-checked weekly; stale ones are flagged, not silently kept.", "",
      "## License", "", "[![CC0](https://licensebuttons.net/p/zero/1.0/88x31.png)](https://creativecommons.org/publicdomain/zero/1.0/) — list text is CC0. Tool names and trademarks belong to their owners.", ""]
os.makedirs(os.path.join(ROOT, "awesome"), exist_ok=True)
open(os.path.join(ROOT, "awesome/README.md"), "w").write("\n".join(L))
print("awesome/README.md:", sum(1 for l in L if l.startswith("- ") and "](http" in l), "entries")
