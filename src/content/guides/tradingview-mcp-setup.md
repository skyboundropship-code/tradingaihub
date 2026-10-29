---
title: "TradingView MCP Setup: Official vs Community Servers"
description: "Connect TradingView to Claude, ChatGPT or Cursor: the official MCP server vs community options, plan requirements, setup steps and limits."
h1: "TradingView MCP setup: official vs community servers (2026)"
summary: "The official TradingView MCP server vs community servers, plan requirements, and step-by-step setup for Claude, ChatGPT and Cursor."
datePublished: 2026-10-29
dateModified: 2026-10-29
tools: [tradingview-official-mcp, tradingview-mcp, pineify-mcp]
compare: [best-stock-market-mcp-servers, broker-trading-mcp-servers, crypto-mcp-servers]
tv_cta: plans
---

There are now two very different things people mean by "TradingView MCP":

1. **TradingView's official MCP server.** It's a hosted server at `https://mcp.tradingview.com/mcp`. You log in with your TradingView account, and it's in public beta for paid plans.
2. **Community MCP servers.** These are open-source projects that are *not* made by TradingView. Some fetch market data on their own. Others take control of the TradingView Desktop app on your computer.

This guide explains how they differ and helps you pick one. It then walks through connecting the official server to **Claude, ChatGPT and Cursor**, step by step. Every setup step and limit below comes from vendor docs and GitHub READMEs, checked on 29 October 2026.

> **Not financial advice.** MCP servers give an AI assistant access to data and tools. They don't make its answers correct. Nothing here is a recommendation to buy or sell anything. If an assistant can act on an account, test with paper trading first. AI output can be wrong, and market data can be delayed.

## Official vs community TradingView MCP at a glance

| What | Official TradingView MCP | atilaahmettaner/tradingview-mcp | tradesdontlie/tradingview-mcp |
|---|---|---|---|
| Made by | TradingView | Independent (not affiliated with TradingView) | Independent (not affiliated with TradingView) |
| How it works | Hosted server, streamable HTTP | Self-hosted Python server (a paid hosted version, TradingMCP, also exists) | Controls your local TradingView Desktop app via Chrome DevTools Protocol |
| Login / keys | OAuth 2.1 with your TradingView account, no API keys | No TradingView account needed | Needs TradingView Desktop and a valid TradingView subscription |
| Plan needed | Essential or higher. Trial plans don't include MCP access | Free (MIT) to self-host | Your existing TradingView subscription |
| Clients | Claude, Claude Code, ChatGPT/Codex, Cursor, Grok, Perplexity and other MCP clients | Claude Desktop and other stdio MCP clients | Claude Code (per its README) |
| Main caveat | Public beta: limited tool list, delayed market data, possible daily request limits | Uses third-party market data, not your TradingView account | Relies on undocumented internal TradingView APIs that "can change or break without notice" |

The directory tracks the community server here: [TradingView MCP (community)](/tools/tradingview-mcp/). The official server has its own listing too: [TradingView MCP (official)](/tools/tradingview-official-mcp/).

## Option 1: The official TradingView MCP server

TradingView announced the server on its blog on **16 September 2026** as a **public beta for paid plans**. Through it, an assistant can pull quotes and price history, run the Screener, look up fundamentals, news, filings and calendars, and manage your watchlists and alerts.

### What you need

- **A TradingView account on Essential or higher.** TradingView's docs say MCP is "included in Essential and above; trial plans don't include MCP access." Plan prices vary by region and promotion, so check the current price on TradingView's pricing page.
- **An MCP client** that supports streamable HTTP with OAuth 2.1, such as Claude, Claude Code, ChatGPT/Codex, Cursor, Grok or Perplexity.
- **The server URL:** `https://mcp.tradingview.com/mcp`. Every client uses the same URL.

No API keys are involved. You approve access by logging in to TradingView in your browser.

### Connect Claude (web, desktop and mobile)

According to TradingView, a connector added once in Claude works on claude.ai, the desktop app and the mobile app.

1. Open **Claude → Settings → Connectors**.
2. Click **Add custom connector**.
3. Paste `https://mcp.tradingview.com/mcp` and click **Add**.
4. Authorize with your TradingView account.

### Connect Claude Code

1. In your terminal, run:
   ```bash
   claude mcp add --transport http mcp-tradingview https://mcp.tradingview.com/mcp
   ```
2. Inside Claude Code, run `/mcp` and authorize with your TradingView account in the browser.

### Connect ChatGPT (and the Codex desktop app)

These menu names come straight from TradingView's docs. ChatGPT's settings menus change often, so the labels may have moved by the time you read this.

1. Open **ChatGPT → Settings → Plugins → Add → MCPs → Add → Add MCP Server**.
2. Set **Type** to **Streamable HTTP**.
3. Paste `https://mcp.tradingview.com/mcp` as the URL and click **Save**.
4. Open **Plugins → MCPs** and click **Authenticate** on the new server.
5. Log in with your paid TradingView account if asked, then allow access to the tools.

**Codex in the terminal:**

```bash
codex mcp add tradingview --url https://mcp.tradingview.com/mcp
```

Authorize in the browser, then start a new Codex task and ask it to use TradingView.

### Connect Cursor

1. Open **Cursor → Customize → MCPs** and click **New MCP Server**.
2. Choose **User** to use the server in all projects, or pick a workspace to use it in one project only. Cursor opens `mcp.json`.
3. Add the server and save the file:
   ```json
   {
     "mcpServers": {
       "tradingview": {
         "type": "http",
         "url": "https://mcp.tradingview.com/mcp"
       }
     }
   }
   ```
4. Click **Authenticate** next to the server in the MCP list. Log in with your paid TradingView account and allow access to the tools.

### Other MCP clients

TradingView says any client that supports MCP over streamable HTTP with OAuth 2.1 will work. It also has step-by-step instructions for **Grok** and **Perplexity**. The generic JSON config is the same `"type": "http"` block shown in the Cursor section.

### Check that it works

Start a new chat and try a read-only prompt first, for example:

- "List my TradingView watchlists."
- "Get the last 30 daily bars for NASDAQ:AAPL from TradingView and summarise the range."

TradingView's docs also suggest asking your assistant to list the available TradingView tools, because the beta toolset changes over time.

### What the official server can and can't do (beta)

TradingView's tool reference, read on 29 Oct 2026, lists the following.

**Read tools:**
- Watchlists: `list_watchlists`, `get_watchlist`, `get_active_watchlist`.
- Prices and indicators: OHLCV history (`get_ohlcv`, max 5,000 bars per call) and an indicator snapshot (`get_technicals_rating`).
- Symbols and screening: symbol search, screener columns and `run_screener`.
- Fundamentals: `get_financials` and `get_financial_history`.
- Documents and calendars: filings and transcripts (`get_documents`, `get_document_view`), earnings and economic calendars, economic data series, and news.
- Alerts: alert lists and the alert fire log.

**Write tools:**
- Watchlists: create, update and delete watchlists, and add or remove symbols.
- Alerts: create and update alerts.

**Limits to know about:**
- **Rate limit:** about 100 tool calls per minute per user. During the beta, TradingView "may limit the number of requests per day".
- **Delayed data:** the launch post says "market data is delayed" during the beta, and the tool list is limited.
- **Price alerts only:** alerts are simple price-condition alerts. The docs say multi-condition and indicator-based alerts "are NOT supported yet". Webhook alerts can't be created or edited through MCP, because TradingView requires two-factor verification for webhooks. One sample prompt in the launch post asks for an RSI-based alert, but the tool reference rules that out for now.
- **No trading tools:** the published tool list has no order placement, broker or position tools.

## Option 2: Community TradingView MCP servers

### atilaahmettaner/tradingview-mcp: market analysis without a TradingView login

[TradingView MCP (community)](/tools/tradingview-mcp/) is an MIT-licensed Python server. Its README describes screeners, multi-timeframe technical analysis, backtests and sentiment across crypto, stocks, forex and futures. The README says it is "not affiliated with, endorsed by, or associated with TradingView Inc." It also says it "does not log into, scrape, or automate a TradingView session". Data comes server-side from public endpoints, so it needs no TradingView account.

**Install (from the README):**

```bash
pip install tradingview-mcp-server
```

**Claude Desktop config (`claude_desktop_config.json`):**

```json
{
  "mcpServers": {
    "tradingview": {
      "command": "uvx",
      "args": ["--from", "tradingview-mcp-server", "tradingview-mcp"]
    }
  }
}
```

Notes from the README:
- On macOS, give the full path to `uvx` (for example `/Users/YOUR_USERNAME/.local/bin/uvx`). GUI apps may not have `~/.local/bin` on their PATH.
- Python 3.14 isn't supported yet. Pin 3.13 with `"args": ["--python", "3.13", "--from", "tradingview-mcp-server", "tradingview-mcp"]`.
- The only official sources are the GitHub repo, the PyPI package `tradingview-mcp-server` and the project's hosted service. The README warns about **impersonating npm packages**: there is no official npm package.

The maintainer also sells a hosted version called TradingMCP. We haven't tested it and have no relationship with it.

### tradesdontlie/tradingview-mcp: control TradingView Desktop from Claude Code

This project connects Claude Code to **the TradingView Desktop app running on your machine** through the Chrome DevTools Protocol. It's used for chart analysis, Pine Script development and workflow automation. Its README states:

- It's not affiliated with TradingView, and it **requires a valid TradingView subscription**.
- You start TradingView Desktop with a debug port enabled (`--remote-debugging-port=9222`). Setup is `git clone` and then `npm install`.
- It "accesses undocumented internal TradingView APIs via the Electron debug interface" that "can change or break without notice", so the README suggests pinning your TradingView Desktop version.

There's also a widely forked variant, **LewisWJackson/tradingview-mcp-jackson** (a GitHub fork of the project above). Treat forks as separate code and review them before you run them. Opening a debug port gives local software deep control over the app.

## Which TradingView MCP should you use?

- **You already pay for TradingView (Essential or higher) and want your own watchlists, alerts, screener and fundamentals in chat:** use the **official server**. It's the only option that works with your TradingView account through a supported OAuth login.
- **You want free, self-hosted technical analysis and screening without a TradingView account:** consider the **atilaahmettaner** server. Its data comes from third parties, not from your TradingView account.
- **You want an AI to work inside your TradingView Desktop charts or on Pine Script:** the **tradesdontlie** project does that, but it relies on undocumented internals that can break. For Pine Script, also see [Pineify MCP](/tools/pineify-mcp/).
- **You want to place trades:** none of these places broker orders. Use a broker MCP and start with paper trading. See our [Alpaca MCP setup guide](/guides/alpaca-mcp-setup/) and the [broker & trading MCP comparison](/compare/broker-trading-mcp-servers/).

For more market data inside your assistant, see [the best MCP servers for stock market data](/compare/best-stock-market-mcp-servers/). For crypto-focused servers, see the [crypto MCP comparison](/compare/crypto-mcp-servers/).

<!-- partner-cta -->

## Safety checklist

- **Read before write.** Try read-only prompts first. The official server's write tools can delete watchlists and change alerts, so check what the assistant plans to do before you approve it.
- **Only install from official sources.** Copycat packages exist (see the npm warning above).
- **Don't trust AI numbers blindly.** Check figures against the chart before acting on them, especially while beta data is delayed.
- **Test any trading idea on paper first.** Neither the indicators nor the AI's summaries are signals.

## FAQ

### Does TradingView have an official MCP server?
Yes. TradingView runs an official MCP server at `https://mcp.tradingview.com/mcp`. It launched as a public beta on 16 September 2026. You log in with your TradingView account through OAuth 2.1, and no API keys are needed.

### Which TradingView plan do I need for MCP?
Essential or higher. TradingView's docs say trial plans don't include MCP access. The free Basic plan isn't listed as eligible.

### Can I use the TradingView MCP with ChatGPT?
Yes. TradingView documents a setup for ChatGPT and the Codex desktop app (add an MCP server with type "Streamable HTTP", then authenticate). For the Codex CLI, the command is `codex mcp add tradingview --url https://mcp.tradingview.com/mcp`.

### How do I add TradingView MCP to Cursor?
Go to Cursor → Customize → MCPs → New MCP Server. Add a `tradingview` entry with `"type": "http"` and the server URL to `mcp.json`, then click Authenticate and log in with your paid TradingView account.

### Can the TradingView MCP place trades?
No. The official tool list covers data, screening, fundamentals, news, filings, calendars, watchlists and price alerts. It has no order or position tools. To trade through an AI client, you'd need a broker MCP such as [Alpaca's](/tools/alpaca-mcp/), and you should start in paper trading mode.

### Is the community "tradingview-mcp" made by TradingView?
No. Both atilaahmettaner/tradingview-mcp and tradesdontlie/tradingview-mcp say in their READMEs that they aren't affiliated with TradingView.

### Is TradingView MCP data real-time?
Not during the beta. TradingView's launch post says market data is delayed and the tool list is limited for now.

### Can it create indicator or webhook alerts?
Not yet. The official docs say only simple price-condition alerts are supported. Webhook alerts can't be created or edited through MCP.

## Partner disclosure

TradingView links marked **Partner** on this page are affiliate links. TradingAIHub may earn a commission if you subscribe, at no extra cost to you. The commission doesn't affect which servers we list or how we describe them. See [how we verify listings](/about/#how-we-verify) and our [disclaimer](/disclaimer/).

## Sources (fetched 29 Oct 2026)

- TradingView MCP docs (server URL, plan requirement, client setup steps, tool reference, rate limit): https://www.tradingview.com/mcp/docs
- TradingView blog, "Bring TradingView to Claude with the new MCP Server: public beta available for paid plans" (16 Sep 2026; beta scope, delayed data, daily request limits): https://www.tradingview.com/blog/en/tradingview-mcp-server-public-beta-60864/
- TradingView pricing page (plan names: Basic, Essential, Plus, Premium, Ultimate): https://www.tradingview.com/pricing/
- atilaahmettaner/tradingview-mcp README (install, config, non-affiliation, npm impersonation warning, Python 3.14 note): https://github.com/atilaahmettaner/tradingview-mcp
- PyPI package `tradingview-mcp-server`: https://pypi.org/project/tradingview-mcp-server/
- tradesdontlie/tradingview-mcp README (CDP on port 9222, subscription requirement, undocumented-API warning): https://github.com/tradesdontlie/tradingview-mcp
- LewisWJackson/tradingview-mcp-jackson (fork of tradesdontlie/tradingview-mcp, per GitHub API): https://github.com/LewisWJackson/tradingview-mcp-jackson
