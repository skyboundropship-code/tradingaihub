---
title: "Best MCP Servers for Stock Market Data (2026)"
description: "Official and community MCP servers for stock prices, fundamentals and news in Claude, ChatGPT and Cursor, compared by data source, free tier and setup."
h1: "Best MCP servers for stock market data (2026)"
datePublished: 2026-10-29
dateModified: 2026-10-29
---

An MCP server lets an AI client like Claude, ChatGPT or Cursor fetch real market data instead of guessing from training data. In practice, the useful question isn't which server has the most tools. It's **where the data comes from, what the free tier allows, and whether the server is still maintained.**

This page compares the stock-data MCP servers we track. **Official vendor servers** come first, then **community servers**. Pricing and setup facts were checked against vendor pricing pages, docs and GitHub on 29 October 2026. Each [listing](/tools/) also shows live GitHub status.

> **Not financial advice.** These tools return data. They don't give recommendations, and nothing here suggests buying or selling any security. Market data can be delayed or wrong, and AI assistants can misread it. If you connect a broker, paper trade first.

## Quick picks

- **Easiest hosted setup with a free tier:** [Alpha Vantage MCP](/tools/alpha-vantage-mcp/). It's the official server, with a remote URL and OAuth. The free tier allows 25 requests per day.
- **Deep US market data from an established vendor:** [Massive MCP](/tools/massive-mcp/). This is the official server from Massive, formerly Polygon.io. Its free tier is end-of-day data at 5 calls per minute.
- **Fundamentals-heavy research:** Financial Modeling Prep, via its [official hosted MCP](/tools/fmp-mcp/) or the [community FMP MCP](/tools/fmp-mcp-community/) (250+ tools). FMP's free tier allows 250 calls per day.
- **Global end-of-day data and fundamentals:** [EODHD's official hosted MCP](/tools/eodhd-mcp/). Its free tier allows 20 calls per day. See also the [EODHD API listing](/tools/eodhd-api/).
- **No API key, for experimenting:** [Yahoo Finance MCP](/tools/yahoo-finance-mcp/) or [Maverick MCP](/tools/maverick-mcp/). Both use unofficial Yahoo Finance data, so keep the caveats below in mind.
- **Already a paying TradingView user:** [TradingView's official MCP server](/tools/tradingview-official-mcp/). See our [TradingView MCP setup guide](/guides/tradingview-mcp-setup/).
- **You also want to trade (on paper first):** [Alpaca MCP](/tools/alpaca-mcp/). Read the [Alpaca MCP setup guide](/guides/alpaca-mcp-setup/).

## Comparison table

| Server | Maker | Data source | Connection | Free tier (vendor) | Paid from | Status (29 Oct 2026) |
|---|---|---|---|---|---|---|
| [Alpha Vantage MCP](/tools/alpha-vantage-mcp/) | Alpha Vantage (official) | Alpha Vantage API | Remote `https://mcp.alphavantage.co/mcp` (OAuth) or local `uvx marketdata-mcp-server` | 25 requests/day | $49.99/mo (75 req/min) | Maintained, MIT |
| [Massive MCP](/tools/massive-mcp/) | Massive (official) | Massive (ex-Polygon.io) API | Local, `uv tool install` + stdio; streamable HTTP option | Basic: end-of-day, 5 calls/min | Starter $29/mo (15-min delayed) | Maintained, MIT |
| [FMP official MCP](/tools/fmp-mcp/) | Financial Modeling Prep | FMP API | Hosted `https://financialmodelingprep.com/mcp?apikey=…` | Basic: 250 calls/day, end-of-day | Starter $29/mo ($19/mo billed annually) | Vendor-hosted |
| [FMP MCP (community)](/tools/fmp-mcp-community/) | Community (imbenrabi) | FMP API (your key) | `npx financial-modeling-prep-mcp-server` | Same FMP plans | Same FMP plans | Maintained, Apache-2.0 |
| [EODHD MCP](/tools/eodhd-mcp/) | EODHD (official) | EODHD API | Hosted v1 (API key in URL) or v2 `https://mcp.eodhd.com/v2/mcp` (OAuth 2.1) | 20 calls/day | $19.99/mo (EOD) | Vendor-hosted |
| [TradingView MCP (official)](/tools/tradingview-official-mcp/) | TradingView | Your TradingView account | Hosted `https://mcp.tradingview.com/mcp` (OAuth 2.1) | None (trial plans excluded) | Essential plan or higher | Public beta, delayed data |
| [Alpaca MCP](/tools/alpaca-mcp/) | Alpaca (official) | Alpaca Market Data + Trading API | Local `uvx alpaca-mcp-server` | Basic: real-time IEX only, 200 calls/min | Algo Trader Plus $99/mo | Maintained, MIT |
| [Yahoo Finance MCP](/tools/yahoo-finance-mcp/) | Community (maxscheijen) | Yahoo Finance (unofficial) | Local `uvx mcp-yahoo-finance` | No key needed | n/a | Maintained, MIT |
| [Maverick MCP](/tools/maverick-mcp/) | Community (wshobson) | Yahoo Finance via `yfinance` | Local (uv) | No key for core tools | n/a | Maintained, MIT |
| [investor-agent](/tools/investor-agent/) | Community (ferdousbhai) | Mixed public sources | Hosted `https://investor.ferdousbhai.com/mcp` (no auth) or build from source | No key needed | n/a | Maintained, MIT |
| [Financial Datasets MCP](/tools/financial-datasets-mcp/) | Financial Datasets | Financial Datasets API | Local (uv) | Not verified | Not verified | **Stale** (last commit Jun 2025) |
| [Stock Market MCP (Finnhub)](/tools/finnhub-mcp-community/) | Community (sverze) | Finnhub API | Local (uv) | Finnhub: 60 calls/min | Varies by plan | **Stale** (last commit May 2025) |

"Maintained" means the repo had commits in October 2026 when we checked. "Vendor-hosted" means the data vendor runs the server and documents it, so we check it against the vendor's docs rather than repo activity. Free-tier limits belong to the underlying **data API**, not the MCP server. Many vendors restrict their individual plans to personal or non-professional use, so check the license before using data commercially.

## Official vendor MCP servers

### Alpha Vantage MCP

This is the official server from Alpha Vantage. It exposes Alpha Vantage API functions directly as MCP tools.

- **Setup:** the recommended option is the remote server at `https://mcp.alphavantage.co/mcp`. When you connect, an authorization page asks for your API key. A key-in-URL variant also exists, but Alpha Vantage marks it as deprecated. For local use, run `uvx marketdata-mcp-server YOUR_API_KEY`.
- **Clients:** the README says it's listed in Claude's Connectors directory and ChatGPT's app directory. It also documents setup for Claude Code, Cursor, VS Code and others.
- **Pricing:** free up to 25 API requests per day. Premium plans run from $49.99/month (75 requests/min) to $249.99/month (1,200 requests/min). Alpha Vantage says real-time and 15-minute-delayed US data for personal use need a separate data entitlement.
- **Best for:** trying an MCP market data workflow quickly. Expect to hit the daily cap fast in agent loops.

### Massive MCP (formerly Polygon.io)

This is the official server from Massive. Instead of one tool per endpoint, it gives the model three composable tools: **search**, **call** and **query**. Results can go into an in-memory SQLite database for further analysis.

- **Setup:** needs Python 3.12+ and uv. The README now recommends `uv tool install` over `uvx`, because cold-start downloads can exceed Claude's 30-second connection timeout. Then register it with `claude mcp add massive -e MASSIVE_API_KEY=your_api_key_here -- mcp_massive`. A streamable HTTP mode is also available.
- **Pricing:** the Basic plan is free, with end-of-day data at 5 API calls per minute. Starter is $29/month with 15-minute delayed intraday data. Advanced is $199/month with real-time data. Individual plans are for personal, non-professional use.
- **Best for:** US equities research and building analysis pipelines with an agent.

### Financial Modeling Prep (official hosted MCP and community server)

FMP documents an [official hosted MCP endpoint](/tools/fmp-mcp/) (`https://financialmodelingprep.com/mcp?apikey=FMP_API_KEY`) in its developer docs. Separately, the community [FMP MCP server](/tools/fmp-mcp-community/) by imbenrabi exposes **250+ tools across 24 categories**. It has dynamic, static and all-tools modes to keep the tool count manageable (`npx financial-modeling-prep-mcp-server --fmp-token=YOUR_FMP_API_KEY`).

- **Pricing:** Basic is free with 250 calls per day, end-of-day data. Starter is $29/month ($19/month billed annually), and Premium is $69/month ($49/month annually). The pricing page also lists monthly bandwidth caps per plan.
- **Best for:** financial statements, ratios, estimates and filings-style research.

### EODHD MCP

EODHD runs an [official hosted MCP server](/tools/eodhd-mcp/). According to its docs, the server has **72 read-only tools** and comes in two versions. **v1** passes the API key in the URL (`https://mcp.eodhd.com/v1/mcp?apikey=…`). **v2** uses OAuth 2.1 (`https://mcp.eodhd.com/v2/mcp`) for clients with native OAuth, such as Claude Desktop. EODHD also publishes [EODHD Claude Skills](/tools/eodhd-claude-skills/).

- **Pricing:** after registration you get 20 free API calls per day, and some data types aren't included in the free package. Paid plans start at $19.99/month (EOD Historical) and go up to $99.99/month (All-In-One).
- **Best for:** global end-of-day coverage and fundamentals at a low entry price.

### TradingView MCP (official, public beta)

[TradingView's own server](/tools/tradingview-official-mcp/) works through your TradingView account. Its tools cover OHLCV bars, the Screener, fundamentals, filings, transcripts, calendars, news, watchlists and simple price alerts. It requires **Essential or higher**, and trial plans are excluded. During the beta, TradingView says market data is delayed and daily requests may be limited. It doesn't place trades. Full setup steps for Claude, ChatGPT and Cursor are in our [TradingView MCP setup guide](/guides/tradingview-mcp-setup/).

### Alpaca MCP

[Alpaca's official server](/tools/alpaca-mcp/) is mainly a **trading** server, but its `stock-data`, `options-data`, `crypto-data` and `news` toolsets make it a solid data source too. You can turn on only those toolsets with `ALPACA_TOOLSETS`. The free Basic data plan gives real-time equities from IEX only. Algo Trader Plus ($99/month) covers all US exchanges plus OPRA options. Start with paper keys: see the [Alpaca MCP setup guide](/guides/alpaca-mcp-setup/).

## Community MCP servers

### Yahoo Finance MCP

[maxscheijen/mcp-yahoo-finance](/tools/yahoo-finance-mcp/) returns prices, company data, financial reports, news, analyst ratings, earnings dates, dividends and options data from Yahoo Finance. Run it with `uvx mcp-yahoo-finance`. You don't need an API key. However, Yahoo doesn't offer an official public API for this, so these servers depend on **unofficial endpoints** that can change, and your use has to comply with Yahoo's terms.

### Maverick MCP

[Maverick MCP](/tools/maverick-mcp/) uses Yahoo Finance data through `yfinance`, with no API key needed for its core tools. According to its README, release v1.2.1 has **38 core tools**, plus 12 optional backtesting tools and 3 optional research tools. Daily history supports US symbols and a set of exchange suffixes (.L, .T, .TO, .AX, .HK, .DE). Requires Python 3.12+ and uv.

### investor-agent

[investor-agent](/tools/investor-agent/) is aimed at long-term investors. Its tools cover stock info, historical prices, options, market movers, an earnings calendar, CNN's Fear & Greed index and technical indicators. A **hosted instance** runs at `https://investor.ferdousbhai.com/mcp` with no authentication. The README warns there's **no npm package** under that name, so don't run `npx investor-agent`.

### Regional servers

- [KOSPI/KOSDAQ MCP](/tools/kospi-kosdaq-mcp/) covers Korean equities.
- [HK Finance MCP](/tools/hk-finance-mcp/) covers Hong Kong financial data.

### Stale servers (use with care)

- [Financial Datasets MCP](/tools/financial-datasets-mcp/) is popular on GitHub, but it had no commits after June 2025 when we checked. It requires a Financial Datasets API key, and we haven't verified current plan pricing.
- [Stock Market MCP (Finnhub)](/tools/finnhub-mcp-community/) is a small community server using the Finnhub API, with its last commit in May 2025. Finnhub's free tier is listed at 60 calls per minute. Finnhub's API docs also say Finnhub now offers its own MCP server for ChatGPT, Claude and Gemini Enterprise ([Finnhub MCP (official)](/tools/finnhub-mcp/)), so check that before you rely on this community server.

## How to choose

1. **Start with the data, not the server.** If you already pay for a vendor, use that vendor's official MCP. Compare the underlying plans in our [market data API pricing comparison](/compare/market-data-api-pricing/).
2. **Check the free tier against how agents behave.** An agent can make dozens of calls for a single question. A 20 or 25 calls-per-day cap is fine for testing, but not for daily use.
3. **Prefer hosted OAuth servers over keys in config files.** Alpha Vantage, EODHD v2 and TradingView support OAuth. That way you don't paste API keys into JSON configs or URLs.
4. **Check maintenance status.** Our listings show each repo's last commit and license, and we mark inactive servers as stale.
5. **Use official package sources only.** Several READMEs warn about lookalike packages.

Browse everything in the [market data category](/category/market-data/), or see the related comparisons for [SEC filings & research tools](/compare/sec-filings-research-tools/), [crypto MCP servers](/compare/crypto-mcp-servers/) and [broker & trading MCP servers](/compare/broker-trading-mcp-servers/).

<!-- auto-table -->

## FAQ

### What is the best MCP server for stock market data?
It depends on your data source. Alpha Vantage MCP is the quickest official hosted option with a free tier (25 requests/day). Massive suits deep US market data. FMP and EODHD are strong on fundamentals and global end-of-day data. TradingView's official MCP suits people who already pay for TradingView Essential or higher.

### Is there a free stock market MCP server?
Yes, within limits. Alpha Vantage (25 requests/day), FMP (250 calls/day), EODHD (20 calls/day) and Massive (end-of-day, 5 calls/min) all have free API tiers that work with their MCP servers. Yahoo Finance-based community servers need no key but use unofficial data.

### Is there an official Yahoo Finance MCP server?
Not that we've found. Yahoo Finance MCP servers like mcp-yahoo-finance and Maverick MCP are community projects that use unofficial Yahoo Finance data.

### Which stock data MCP servers work with ChatGPT?
ChatGPT needs a remote MCP server. Hosted options include Alpha Vantage (listed in ChatGPT's app directory, per its README), FMP's hosted endpoint, EODHD v1 (which EODHD recommends for ChatGPT), TradingView's official server and the hosted investor-agent instance.

### Do MCP servers give real-time stock prices?
Some do, depending on your plan. Free tiers are often end-of-day or limited. Alpaca's free plan is real-time from IEX only, and Massive's real-time data starts at its Advanced plan. TradingView's MCP data is delayed during its beta.

### Can these MCP servers place trades?
The data servers on this page don't. Alpaca MCP can, so set it up with paper trading keys first and see the [broker & trading comparison](/compare/broker-trading-mcp-servers/).

## Partner disclosure

TradingView and EODHD pricing links marked **Partner** on this page are affiliate links. TradingAIHub may earn a commission at no extra cost to you, and it doesn't affect rankings or listings. See [how we verify](/about/#how-we-verify) and the [disclaimer](/disclaimer/).

## Sources (fetched 29 Oct 2026)

- Alpha Vantage MCP README (remote/OAuth, deprecated key-in-URL, `uvx marketdata-mcp-server`, Claude/ChatGPT directory listings): https://github.com/alphavantage/alpha_vantage_mcp
- Alpha Vantage Premium (25 requests/day free; $49.99–$249.99/mo tiers; data entitlement note): https://www.alphavantage.co/premium/
- Massive MCP README (search/call/query tools, Python 3.12+, `uv tool install`, `claude mcp add`, 30-second timeout note): https://github.com/massive-com/mcp_massive
- Massive stocks pricing (Basic free EOD 5 calls/min; Starter $29; Advanced $199; individual use): https://massive.com/stocks
- FMP pricing plans (Basic 250 calls/day; Starter $29 / $19 annual; Premium $69 / $49 annual; bandwidth caps): https://site.financialmodelingprep.com/pricing-plans
- FMP MCP server docs (hosted endpoint): https://site.financialmodelingprep.com/developer/docs/mcp-server
- Community FMP MCP README (250+ tools, 24 categories, modes, npx command): https://github.com/imbenrabi/Financial-Modeling-Prep-MCP-Server
- EODHD MCP server docs (72 read-only tools; v1 and v2 URLs and auth): https://eodhd.com/financial-apis/mcp-server-for-financial-data-by-eodhd
- EODHD pricing (20 free calls/day; $19.99–$99.99/mo): https://eodhd.com/pricing
- TradingView MCP docs and launch post: https://www.tradingview.com/mcp/docs · https://www.tradingview.com/blog/en/tradingview-mcp-server-public-beta-60864/
- Alpaca Trading API MCP docs and Market Data plans: https://docs.alpaca.markets/us/docs/trading-api-mcp · https://docs.alpaca.markets/us/docs/about-market-data-api
- mcp-yahoo-finance README: https://github.com/maxscheijen/mcp-yahoo-finance
- Maverick MCP README (yfinance, v1.2.1 tool counts, suffixes, Python 3.12+): https://github.com/wshobson/maverick-mcp
- investor-agent README (hosted URL, tools, npm warning): https://github.com/ferdousbhai/investor-agent
- Financial Datasets MCP repo: https://github.com/financial-datasets/mcp-server
- sverze/stock-market-mcp-server (Finnhub): https://github.com/sverze/stock-market-mcp-server
- Finnhub API docs (official Finnhub MCP server note; 30 calls/second cap on top of plan limits): https://finnhub.io/docs/api
- Finnhub free-tier figure (60 calls/min): TradingAIHub tools.json pricing record (source https://www.finnhub.io/pricing-fundamental-data), checked 2026-10-29. Not re-fetched for this draft.
- Repo activity (last commit, license, archived flag): GitHub REST API, 29 Oct 2026
