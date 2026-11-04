---
title: "Alpaca MCP Server Setup: Paper Trading First (2026)"
description: "Set up Alpaca's official MCP server in Claude, Cursor or VS Code with paper-trading keys, read-only toolsets and a safe path before any live trading."
h1: "Alpaca MCP server setup: paper trading first"
summary: "Set up Alpaca's official MCP server with paper-trading keys and read-only toolsets in Claude, Cursor or VS Code before enabling any trading."
datePublished: 2026-10-29
dateModified: 2026-10-29
tools: [alpaca-mcp, alpaca-market-data-api]
compare: [broker-trading-mcp-servers, best-stock-market-mcp-servers]
tv_cta: charts
---

Alpaca's official MCP server, [`alpacahq/alpaca-mcp-server`](/tools/alpaca-mcp/), connects an AI assistant to Alpaca's Trading API and Market Data API. That covers stocks, ETFs, options and crypto. It runs locally on your machine and works with Claude Desktop, Claude Code, Cursor, VS Code, PyCharm, Gemini CLI and other MCP clients.

The server can **place real orders**, so this guide sets it up the safe way. You use paper-trading keys, start with a read-only toolset, and only then decide whether to enable trading. Every command and setting below comes from Alpaca's docs and the GitHub README, checked on 29 October 2026.

> **Not financial advice. Paper trade first.** Alpaca's own disclosure says insights from the MCP server and connected AI agents "are for educational and informational purposes only and should not be taken as investment advice." AI assistants misread instructions, use stale data and make arithmetic mistakes. Keep the server on paper trading until you've reviewed how it behaves, and check every order before you confirm it.

## What you need

From Alpaca's prerequisites:

- **Python 3.10+**
- **uv**, which gives you the `uvx` command. See the [uv install guide](https://docs.astral.sh/uv/getting-started/installation/).
- **Alpaca API keys.** Alpaca says "a free paper trading account is enough to start."
- **An MCP client**, such as Claude Desktop, Claude Code, Cursor, VS Code or PyCharm.

**About V2:** the current server is a full rewrite built with FastMCP and OpenAPI. Alpaca says "none of the V1 tools exist in V2". If you followed an older tutorial that used `init` commands or `.env` files, start fresh: remove the old config, restart your client and open a new chat.

## Step 1: Create paper-trading API keys

1. Sign in to the [Alpaca paper trading dashboard](https://app.alpaca.markets/paper/dashboard/overview). If you don't have an account yet, create a free paper trading account.
2. Generate an **API key and secret** for the **paper** account.
3. Keep them somewhere safe. You'll paste them into your MCP client's config file, and **never into the chat itself**. Alpaca's docs say: "Never paste API keys into chat."

## Step 2: Add the server to your MCP client

You don't run any `init` command and there's no `.env` file. The credentials live in one place: the `env` block of your client config. Restart the client after you edit it.

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, or `%APPDATA%\Claude\claude_desktop_config.json` on Windows:

```json
{
  "mcpServers": {
    "alpaca": {
      "command": "uvx",
      "args": ["alpaca-mcp-server"],
      "env": {
        "ALPACA_API_KEY": "your_alpaca_api_key",
        "ALPACA_SECRET_KEY": "your_alpaca_secret_key"
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add alpaca --scope user --transport stdio uvx alpaca-mcp-server \
  --env ALPACA_API_KEY=your_alpaca_api_key \
  --env ALPACA_SECRET_KEY=your_alpaca_secret_key
```

Then run `/mcp` in Claude Code to confirm the server is connected.

### Cursor

Add the same block to `~/.cursor/mcp.json`. The README also links a one-click install from the Cursor Directory.

```json
{
  "mcpServers": {
    "alpaca": {
      "command": "uvx",
      "args": ["alpaca-mcp-server"],
      "env": {
        "ALPACA_API_KEY": "your_alpaca_api_key",
        "ALPACA_SECRET_KEY": "your_alpaca_secret_key"
      }
    }
  }
}
```

### VS Code

Create `.vscode/mcp.json` in your project root. VS Code uses a `servers` key instead of `mcpServers`:

```json
{
  "servers": {
    "alpaca": {
      "type": "stdio",
      "command": "uvx",
      "args": ["alpaca-mcp-server"],
      "env": {
        "ALPACA_API_KEY": "your_alpaca_api_key",
        "ALPACA_SECRET_KEY": "your_alpaca_secret_key"
      }
    }
  }
}
```

### Docker (optional)

```bash
git clone https://github.com/alpacahq/alpaca-mcp-server.git
cd alpaca-mcp-server
docker build -t mcp/alpaca:latest .
```

Then point your client at `docker run --rm -i -e ALPACA_API_KEY=... -e ALPACA_SECRET_KEY=... -e ALPACA_PAPER_TRADE=true mcp/alpaca:latest`. The README has the full JSON.

### What about ChatGPT and Claude mobile?

Alpaca's README says both **need a remote MCP server**. This package "does not configure remote MCP authentication, so do not expose it directly to the public internet with your Alpaca API keys." Use a desktop client with the local setup above.

## Step 3: Start read-only with toolset filtering

By default the server turns on every tool, including order placement and `close_all_positions`. For your first sessions, use the `ALPACA_TOOLSETS` variable to leave out the `trading` toolset. Here is Alpaca's own read-only market-data example:

```json
"env": {
  "ALPACA_API_KEY": "your_alpaca_api_key",
  "ALPACA_SECRET_KEY": "your_alpaca_secret_key",
  "ALPACA_TOOLSETS": "account,stock-data,crypto-data,options-data,news"
}
```

These are the available toolsets, per Alpaca's docs and README:

| Toolset | What it covers |
|---|---|
| `account` | Account info, config, portfolio history, activities |
| `trading` | Orders, positions, exercising options (**can change your account**) |
| `watchlists` | Create, read, update and delete watchlists |
| `assets` | Asset lookup, option contracts, calendar, clock |
| `stock-data` | Stock bars, quotes, trades, snapshots, screeners |
| `crypto-data` | Crypto bars, quotes, trades, snapshots, order books |
| `options-data` | Option bars, quotes, trades, snapshots, chain |
| `corporate-actions` | Corporate action announcements |
| `news` | News for stocks and crypto |
| `fixed-income-data` | Fixed income (bond/treasury) quotes |
| `locates` | Short-sale locates (README only; not available in paper trading) |

Fewer toolsets also help if your MCP client limits how many tools it can load.

## Step 4: Verify the connection

Restart your client and ask:

> "What is my Alpaca account balance and buying power?"

If you get account details back, it's working. Alpaca's docs use this same check. Next, try a few read-only prompts:

- "Show me AAPL's daily price bars for the last week."
- "What are the market open and close times today?"
- "What's the latest quote for BTC/USD?"

**About data:** Alpaca's free **Basic** market-data plan gives real-time equities data from the **IEX exchange only**, with 200 historical API calls per minute. **Algo Trader Plus** costs $99/month and covers all US stock exchanges plus the OPRA options feed. Alpaca notes that some real-time data in the MCP server may need Algo Trader Plus. Compare data vendors in our [market data API pricing comparison](/compare/market-data-api-pricing/), or read the [Alpaca Market Data API listing](/tools/alpaca-market-data-api/).

## Step 5: Enable trading on paper

Once you're comfortable with what the assistant does, add `trading` to `ALPACA_TOOLSETS`, or remove the variable to enable everything. **Keep your paper keys in place.** `ALPACA_PAPER_TRADE` defaults to `true`, so orders go to your paper account.

Good habits while you paper trade:

- **Ask for a dry run first.** For example: "Before placing anything, tell me exactly which order you would send: symbol, side, quantity, type and limit price."
- **Review every tool call.** Alpaca warns that "orders execute directly against Alpaca's Trading API. Review AI-suggested orders before confirming." Don't set your client to auto-approve tool calls for this server.
- **Watch the dangerous tools.** `cancel_all_orders` and `close_all_positions` do exactly what their names say.
- **Mind rate limits.** Alpaca applies per-account API rate limits, so looping prompts can hit them.

## Going live (only if you decide to)

Alpaca's docs say: "Switch to live trading only when you set `ALPACA_PAPER_TRADE=false` with live API keys." That takes two deliberate changes:

```json
"env": {
  "ALPACA_API_KEY": "your_live_api_key",
  "ALPACA_SECRET_KEY": "your_live_secret_key",
  "ALPACA_PAPER_TRADE": "false"
}
```

Before you do, ask yourself whether a human needs to approve every order, and keep `ALPACA_TOOLSETS` as narrow as your workflow allows. Live trading with an AI client can lose real money. Whether to do it is your decision, and nothing on this page recommends it.

## Troubleshooting

- **`uvx` not found:** install uv, then restart your terminal (and your MCP client) so `uv`/`uvx` are on your PATH.
- **Credentials missing:** set `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` in the client's `env` block.
- **The assistant uses old tool names:** that's left over from V1. Restart the client, start a new chat and update any custom rules that mention V1 tools. To stay on V1, pin it with `"args": ["alpaca-mcp-server==1.x.x", "serve"]`.

<!-- partner-cta -->

## Related

- [Alpaca MCP Server listing](/tools/alpaca-mcp/), with live GitHub status and license
- [Broker & trading MCP servers compared](/compare/broker-trading-mcp-servers/), including [IBKR MCP](/tools/ibkr-mcp/), [tasty-agent](/tools/tasty-agent/) and [MetaTrader MCP](/tools/metatrader-mcp/)
- [Trading & brokers category](/category/trading-brokers/)
- [TradingView MCP setup guide](/guides/tradingview-mcp-setup/), for charts and screening data (not order execution)
- [Best MCP servers for stock market data](/compare/best-stock-market-mcp-servers/)
- [Claude Trading Skills](/tools/claude-trading-skills/), with skills for analysis workflows

## FAQ

### Is the Alpaca MCP server official?
Yes. It's published by Alpaca at github.com/alpacahq/alpaca-mcp-server under the MIT license, and Alpaca documents it on docs.alpaca.markets.

### Is the Alpaca MCP server free?
The server is open source, and a paper trading account is free. Alpaca's Basic market-data plan is free (real-time equities from IEX only). Algo Trader Plus costs $99/month for full US exchange coverage and OPRA options data.

### Does Alpaca MCP default to paper trading?
Yes. `ALPACA_PAPER_TRADE` defaults to `true`. Live trading needs live API keys **and** `ALPACA_PAPER_TRADE` set to `false`.

### Can I make the Alpaca MCP read-only?
Yes. Set `ALPACA_TOOLSETS` to a list that leaves out `trading`, for example `account,stock-data,crypto-data,options-data,news`.

### Does it work with ChatGPT?
Not with this local package directly. Alpaca's README says ChatGPT and Claude mobile need a remote MCP server, and warns against exposing this server to the public internet with your API keys.

### What install command does the Alpaca MCP use?
It runs with `uvx alpaca-mcp-server`, configured in your MCP client. For Claude Code, run `claude mcp add alpaca --scope user --transport stdio uvx alpaca-mcp-server` with your keys passed via `--env`.

### Which Python version do I need?
Python 3.10 or newer, plus uv for the `uvx` command.

## Partner disclosure

TradingView links marked **Partner** on this page are affiliate links. TradingAIHub may earn a commission if you subscribe, at no extra cost to you. Alpaca links are not affiliate links. See [how we verify listings](/about/#how-we-verify) and our [disclaimer](/disclaimer/).

## Sources (fetched 29 Oct 2026)

- Alpaca docs, Trading API MCP (prerequisites, setup per client, env vars, toolsets, verify prompt, considerations, disclosure): https://docs.alpaca.markets/us/docs/trading-api-mcp
- alpacahq/alpaca-mcp-server README (V2 rewrite notes, ChatGPT/Claude Mobile remote caveat, VS Code `servers` key, Docker, `locates`/`fixed-income-data` toolsets, troubleshooting): https://github.com/alpacahq/alpaca-mcp-server
- PyPI `alpaca-mcp-server` (latest v2.4.0, uploaded 12 Oct 2026, per PyPI JSON API): https://pypi.org/project/alpaca-mcp-server/
- Alpaca docs, About Market Data API (Basic vs Algo Trader Plus, $99/month, IEX, 200 vs 10,000 calls/min): https://docs.alpaca.markets/us/docs/about-market-data-api
- uv installation guide: https://docs.astral.sh/uv/getting-started/installation/
