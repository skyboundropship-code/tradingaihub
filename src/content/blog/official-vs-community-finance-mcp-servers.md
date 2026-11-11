---
title: "Official vs Community MCP Servers for Finance: How to Tell Them Apart"
description: "On our Nov 2, 2026 check, 61 of 104 finance tools were official, 43 community. How each kind fails, plus six checks to tell them apart."
date: 2026-10-29
updated: 2026-11-04
tags: [mcp, verification, security]
tools: [tradingview-mcp, tradingview-official-mcp, binance-mcp, square-mcp, fmp-mcp, fmp-mcp-community, sec-edgar-mcp, schwab-mcp, tasty-agent, fred-mcp, ynab-mcp, claude-trading-skills]
---

> **Not financial advice.** These tools fetch data or place orders you tell them to. None of them predicts markets.

If you search "TradingView MCP", "Binance MCP" or "FMP MCP", you get a mix of servers published by the vendor and servers written by someone who uses the vendor's API. Both kinds can be good. But they fail in different ways, and when the server can read your brokerage account or place orders, you should know which kind you're installing.

Below is what we learned from labelling 104 finance tools (73 MCP servers, 16 APIs, 15 agent skills) as **official** or **community**, as of the 2 November 2026 check, and from re-checking all of them every week.

## The split, and what it says about reliability

As of the 2 November 2026 check, **61 of our 104 listings were official** (published by the company whose product or data they expose) and **43 were community** projects. All figures here come from our public [tools.json](/tools.json). The directory now lists 106 tools (62 official, 44 community).

As of the 2 November 2026 verification run, a listing counted as "passing" if its repo was reachable, its links worked, and (for repos) it had a commit in the last 180 days. Here's how the two groups did:

| | Listings | Passing | Stale (no commit > 1 yr) | Aging (180–365 days) | Archived | Needs review |
|---|---|---|---|---|---|---|
| Official | 61 | **54 (89%)** | 2 | 0 | 2 | 3 |
| Community | 43 | **27 (63%)** | 11 | 4 | 1 | 0 |

Two takeaways:

1. **Community servers mostly fail by going quiet.** 15 of the 16 that didn't pass are stale or aging. Nothing broke loudly. The maintainer simply moved on.
2. **"Official" is not a guarantee.** Seven official listings didn't pass. Two are archived by their own vendors (Base MCP, Ramp MCP), two are stale, and three need review. One has a repo that now redirects to a different GitHub owner, one has a hosted endpoint that returned 401 to an unauthenticated check, and one has homepage and docs that returned 403 to our checker.

The split also varies a lot by category. Every listing in payments and banking is official (10 of 10). In quant and backtesting it's 3 of 11, in research and filings 3 of 10, and in personal finance 2 of 7. If you're building on budgeting or backtesting tools, you'll mostly be choosing between community projects, so maintenance signals matter more.

## Six ways to tell official from community

### 1. Who owns the repo, not what the repo is called

Look at the GitHub owner, not the project name. Official finance servers in the directory live under organisations such as `alpacahq`, `stripe`, `paypal`, `coinbase`, `square`, `krakenfx`, `webull-inc`, `XeroAPI` and `intuit`.

The word "official" in a name proves nothing. The community Binance MCP lives under an account called `TermiX-official`. It isn't published by Binance, and it was stale on the last run (no commits for 564 days as of Nov 2, 2026).

### 2. Hosted endpoints on the vendor's own domain

More and more official finance servers are hosted rather than installed. Examples:

- `https://mcp.alphavantage.co/mcp`
- `https://mcp.finnhub.io/mcp`
- `https://mcp.eodhd.com/v2/mcp`
- `https://mcp.api.coingecko.com/mcp`
- `https://mcp.tradingview.com/mcp`
- Robinhood's `https://agent.robinhood.com/mcp/trading`

If the endpoint is on the vendor's domain and the vendor's docs link to it, that's about as clear a signal as you'll get. Community servers are almost always run locally with `npx` or `uvx`, using your own API key in an environment variable.

### 3. Does the package link back to the repo?

This is the check that catches the most surprises. When a README says `npx some-name` or `pip install some-name`, look up that name on npm or PyPI. Then confirm the registry entry's repository field points back to the same GitHub repo.

On the latest run, **10 listings** named a package whose registry entry doesn't link back. Six were community projects and four were official. Square's official MCP server is one of them: the repo is verified and active, but the npm entry for `square-mcp-server` doesn't link to it.

That doesn't mean the package is malicious. It means you can't tell from the registry alone, so install from the vendor's documented command or straight from the repo.

### 4. Repo redirects

GitHub silently redirects renamed or transferred repositories, so an old link keeps "working". That's convenient, but it also means a link can end up pointing at a different owner without anyone noticing.

On the latest run, the stored link for one large, official research platform redirected to a different organisation. We flagged it as Needs review rather than verified. If `git remote -v` or your browser's URL bar shows a different owner from the one you expected, find out why before you install.

### 5. "Not affiliated" disclaimers and naming

Good community projects say what they are. The most-starred TradingView server in the directory (5.2k stars as of Nov 2, 2026, last commit 29 October 2026) describes itself as an *unofficial community MCP, not affiliated with TradingView*. TradingView's own server is a separate, hosted product.

The two differ in practical ways:

- **Official TradingView server:** hosted, OAuth login, public beta. It isn't included in free or trial plans.
- **Community server:** self-hosted and free to run. It adds things like backtests.

Neither is "the right one". They're different products that happen to share a name.

FMP is a second example. The official hosted server exposes 27 dataset tools. A well-maintained community server wraps 250+ FMP endpoints. Both use your FMP plan and its limits.

### 6. Auth model and data source

Official hosted servers increasingly use OAuth. Finnhub, TradingView (OAuth 2.1, no API keys) and Robinhood's agent endpoint (OAuth with PKCE) all do, and EODHD accepts either an API key or OAuth. Community servers usually take a raw API key.

Also ask where the data comes from. A community server built on a vendor's official SDK (the community YNAB server is one, with an optional read-only mode) is a very different risk from one that scrapes an undocumented endpoint.

## When community is the better choice

Community doesn't mean worse. Several of the most useful finance tools have no official MCP server in the directory. (SEC and FRED do publish official APIs, but not MCP servers.)

- an SEC EDGAR MCP server (383 stars as of Nov 2, 2026)
- a Schwab MCP server
- a tastytrade agent
- a FRED server
- the most popular trading skill pack in the directory (3.5k stars as of Nov 2, 2026)

Where an official server does exist, the community version sometimes covers more endpoints (FMP) or more features (TradingView).

What matters is that you check the things that actually fail. With community projects, that's mostly **maintenance**. With official ones, it's mostly **archived repos, moved repos and access changes**.

## A two-minute checklist

Before you connect an MCP server to a brokerage, exchange or bank account:

1. Find the repo owner. Is it the vendor's organisation, or does the README say "not affiliated"?
2. Check the last commit date. Over 180 days is worth a second look. Over a year, test it carefully before relying on it.
3. Look up the npm or PyPI name and confirm it links back to that exact repo.
4. Prefer the vendor's documented install command or hosted endpoint.
5. Use read-only or paper-trading keys first, with the smallest permissions that work.
6. Re-check it later. On the 2 November 2026 run, 16 of 43 community listings and 7 of 61 official listings weren't passing.

The full per-tool results, including the failures, are public on the [verification page](/verification/). If you maintain one of these servers and something there is wrong, please let us know.
