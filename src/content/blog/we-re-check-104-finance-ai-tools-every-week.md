---
title: "We Re-check 100+ Finance MCP Servers, Skills and APIs Every Week: Here's What Breaks"
description: "A weekly GitHub Action verifies every tool in a finance AI directory. 84 of 104 passed on Oct 29, 2026. The rules, the code and the surprises."
date: 2026-10-29
tags: [verification, mcp, security]
tools: [financial-datasets-mcp]
---
*Disclosure: We build and run [TradingAIHub](/), the directory whose data this post is based on. We checked every number against the Oct 29, 2026 verification run. Nothing here is investment advice.*

The number of MCP servers and agent skills for finance has grown fast. You can now point Claude, Cursor or ChatGPT at a server and pull quotes, read 10-Ks, reconcile a ledger or place a paper trade. The trouble is the long tail. Many repos get a burst of stars in their launch week and then go quiet. Others have names that sound official but have nothing to do with the vendor.

We wanted a list that removes the dead ones on its own. So every entry in the directory goes through a script once a week, and the results are published. This post explains how that check works and what it found this week.

## The numbers (run of Oct 29, 2026)

The directory has **104 tools**: 73 MCP servers, 15 agent skills and 16 APIs, across 9 categories.

| Status | Count | Rule |
|---|---|---|
| ✅ Verified | 84 | last commit ≤ 180 days, links alive |
| 🟡 Aging | 4 | 181–365 days since last commit |
| 🔴 Stale | 13 | more than 365 days |
| 📦 Archived | 3 | GitHub archived flag |

So 20 of 104 (19%) don't currently pass. That number is lower than you might expect, because the list is curated first and verified second. It still matters, though, because the failures aren't the obscure ones:

- **Financial Datasets MCP** has 2.3k stars and an official badge, but no commit since June 2025 (510 days). Stale.
- **MetaTrader 5 MCP** has 843 stars and has been quiet for 214 days. Aging.
- **Base MCP** (Coinbase's Base, official, 351 stars) and **Ramp MCP** (official) are both archived.
- **Crypto** is the roughest category: only 8 of 16 pass (5 stale, 2 aging, 1 archived). Macro is the opposite, at 8 of 8.

Official vs community is the other split worth watching. Of the 61 tools published by the vendor, 57 pass (93%). Of the 43 community projects, 27 pass (63%). Community tools aren't worse. Plenty of the best ones are community-built, like Maverick MCP (714★), investor-agent (348★) and the unofficial TradingView MCP (5.2k★). They just go quiet more often, and you should know that before you depend on one.

## How the check works

The verifier is a single Python file (`scripts/verify.py`) run by a GitHub Action every Monday at 05:00 UTC. The pipeline is `verify → regenerate awesome-list → regenerate OG images → build → deploy`. For each entry it does five things.

### 1. Is the repo still there, and is it archived?

It calls the GitHub API, follows renames, and records `archived`, stars, license and the last commit date. An unreachable repo is flagged as `unreachable`. An archived one is `archived`, whatever its stars.

### 2. How long since the last commit?

```python
days = age_days(g.get("last_commit")) if g else None
links_ok = all(c["ok"] for c in v["checks"] if c["check"] != "package published")
if not links_ok: status = "warning"
elif days is None: status = "verified" if not g else "warning"
elif days <= 180: status = "verified"
elif days <= 365: status = "aging"
else: status = "stale"
```

180 days is lenient on purpose. Some finance servers are thin, stable wrappers around a REST API that don't need monthly commits. "Aging" is a yellow flag, not a verdict. Whether 180 should be tighter, given how fast the MCP spec moves, is an open question.

### 3. Does the published package really belong to this repo?

This one surprised us most. If a repo has a `package.json` or `pyproject.toml`, the script looks up that name on npm or PyPI. It only counts the package if the registry entry points back to the same `owner/repo`:

```python
res["links_back"] = f"{owner}/{name}".lower() in res.pop("_lb")
if res and res["links_back"]:
    v[kind] = res
elif res:
    v["issues"].append(f"{kind} name '{cand}' exists on the registry "
                       "but does not link to this repo (not counted)")
```

`_lb` is the JSON of the registry's `repository`, `homepage` and `bugs` fields (npm), or `project_urls` and `home_page` (PyPI). In this week's run, **10 of 104 entries** had a package name that exists on the registry but belongs to someone else. Examples are `mcp-server` on PyPI, which Financial Datasets' repo declares, and `binance-mcp` and `bitcoin-mcp` on npm. If your install instructions say `npx <name>` or `pip install <name>`, this is the difference between running the author's code and running a stranger's. 28 entries have a package that does link back.

### 4. Are the homepage, docs and hosted endpoint alive?

Homepages and docs must return a status below 400. 401, 403 and 429 also count as alive, because many vendor sites block bots. Hosted MCP endpoints need different handling: without auth, most answer `401` or `405`. So any HTTP response below 500 counts as reachable:

```python
a = alive(t["remote_mcp_url"])  # MCP endpoints answer 401/405/406 without auth
a["ok"] = not isinstance(a.get("status"), str) and a["status"] < 500
```

15 tools now ship an official hosted MCP endpoint, including Alpha Vantage, Finnhub, EODHD, CoinGecko, Stripe, PayPal, Square, Mercury, Interactive Brokers and Robinhood. This week 10 of them returned 401, 3 returned 405, and the other two returned 400 and 404. This check is admittedly coarse. It proves something is listening, not that the MCP handshake works. A real `initialize` call is next on the list.

### 5. Official or community?

This label is curated rather than computed. "Official" means the vendor publishes it (its GitHub org, its docs, its domain). Everything else is community, and community tools that use a brand name get an explicit "not affiliated" note.

## What's verified in the busiest categories

**Market data:** Maverick MCP (714★), Massive MCP (official, 398★), investor-agent (348★), Alpha Vantage MCP (official, hosted, 223★), FMP MCP (150★). Finnhub, EODHD and FMP also run official hosted endpoints.

**Brokers:** Alpaca MCP (official, 1.0k★), Kraken CLI with a built-in MCP server (official, 783★), tasty-agent for tastytrade (88★) and Schwab MCP (66★, read-only by default). Interactive Brokers and Robinhood have hosted MCPs. If you connect any of them, use paper trading first.

**Research & quant:** OpenBB (74.9k★), SEC EDGAR MCP (380★), Claude Trading Skills (3.4k★) and QuantConnect's official MCP (79★).

## What we'd do differently

- **Stars are a terrible proxy for maintenance.** The stale list includes Financial Datasets MCP (2.3k★), the aging list includes MetaTrader 5 MCP (843★), and Base MCP (351★) is archived.
- **Publish the rules, not just the badges.** The full table, with each tool's last commit and issues, is public at [/verification/](/verification/). The raw data is at [/tools.json](/tools.json), so you can disagree with a status and see exactly why it was assigned.
- **Verification is a floor, not an endorsement.** A recent commit doesn't mean a server is safe to give your brokerage credentials to. Read the code, scope the API keys, and keep trading tools read-only or in paper mode until you trust them.

If you maintain a finance MCP server or skill that's missing, or you think a status is wrong, we'd like to hear it in the comments. We're also curious where you'd set the staleness threshold.

---

*Informational only. Not investment, financial or trading advice. Star counts and statuses are from the Oct 29, 2026 run and change weekly.*
