---
title: "A Free API and MCP Server for Finding Finance AI Tools"
description: "Query 104 weekly-checked finance MCP servers, agent skills and APIs over REST or MCP: no key, no sign-up. Endpoints, client setup and limits."
date: 2026-11-10
tags: [api, mcp, developers]
---
> **Disclosure:** We publish [TradingAIHub](/), an independent directory of AI tools for finance and trading. This post is about its free public API and MCP server. There are no affiliate or partner links in this post. (Two vendors *inside the API data*, TradingView and EODHD, have affiliate-tagged `website_url` values, across three tool records. The API labels those records `affiliate: true` with a `disclosure` string, and every record also has a plain `vendor_url`. More on that below.)
>
> **Not investment advice.** This is a directory of tools: names, links, pricing and maintenance status. It does not give quotes, signals or recommendations.

When you ask an AI assistant "is there an MCP server for options data?", it tends to answer from memory. That memory can be months old, and it can't tell you whether a repo was archived last week or whether a free tier has been cut back.

TradingAIHub tracks 104 finance-related AI tools: 73 MCP servers, 16 APIs and 15 agent skills, in 9 categories. Each one is re-checked weekly. As of the 9 November 2026 check, 81 were marked verified. The same data is now available two ways:

- a **read-only REST API** (JSON, no key, CORS enabled)
- a **remote MCP server** you can add to Claude, Cursor, VS Code or ChatGPT, so your assistant looks things up instead of guessing

Both are free and need no sign-up. The MCP server is listed in the [official MCP Registry](https://registry.modelcontextprotocol.io/v0/servers?search=tradingaihub) as `com.tradingaihub/directory` v1.0.0. The data is licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) (credit "TradingAIHub, https://tradingaihub.com"); the API and MCP server code is MIT. Here is how to use them, and what their limits are.

## What's in the data

Each tool record includes:

- `slug`, `name`, `type` (`mcp`, `api` or `skill`) and `category`
- `official`: whether the tool is published by the vendor itself or by the community
- `status` and `verified`, plus `checked_at`, the date of the last check
- `pricing`: model, free tier, the lowest paid plan, the source URL and the date it was checked
- `license`, `repo`, `docs`, `homepage`, `remote_mcp_url`, and npm/PyPI package names where they exist
- `url`: the TradingAIHub page. `vendor_url`: the vendor's own link, always plain. `website_url`: the same link, except that it's affiliate-tagged for two vendors, currently TradingView and EODHD (`affiliate: true` with a `disclosure` string). As of this writing that covers three records: TradingView's official MCP, the EODHD API and the official EODHD MCP.

The categories are market data, trading & brokers, crypto, accounting, payments & banking, personal finance, research & filings, quant & backtesting, and macro.

Every list or search response also carries `license`, `license_url` and `attribution`. The index at `/api/v1` adds `code_license`: `MIT (API and MCP server code)`.

## REST API quickstart

Base URL: `https://tradingaihub.com`. Every endpoint is a `GET`; there's no key and no sign-up.

| Endpoint | What it returns |
|---|---|
| `/api/v1` | Index: endpoint list, licences and rate-limit info |
| `/api/v1/tools` | Paged list. Filters: `category`, `type`, `language`, `status`, `verified`, `official`. Paging: `limit` (1–100, default 50) and `offset`. |
| `/api/v1/tools/{slug}` | One tool |
| `/api/v1/search?q=` | Keyword search (`q` 1–100 chars). Optional `category`, `type`, `limit` (1–50, default 10). |
| `/api/v1/categories` | All 9 categories with tool counts |
| `/api/v1/tools.json` | Full dump in one file |
| `/api/openapi.json` | OpenAPI 3.1 spec |

### curl

Verified, market-data MCP servers:

```bash
curl -s "https://tradingaihub.com/api/v1/tools?category=market-data&type=mcp&verified=true"
```

Lists come back with `total`, `count`, `limit`, `offset` and a ready-made `next` URL for the following page.

One tool:

```bash
curl -s "https://tradingaihub.com/api/v1/tools/alpha-vantage-mcp"
```

Search:

```bash
curl -s "https://tradingaihub.com/api/v1/search?q=options+data&limit=5"
```

A trimmed record from that search (as returned on 10 November 2026):

```json
{
  "slug": "alpaca-market-data-api",
  "name": "Alpaca Market Data API",
  "type": "api",
  "category": "market-data",
  "official": true,
  "vendor_url": "https://alpaca.markets/data",
  "affiliate": false,
  "license": "Proprietary / ToS",
  "pricing": {
    "model": "freemium",
    "free_tier": "Basic: real-time IEX, 200 calls/min",
    "paid_from": "$99/mo",
    "source": "https://docs.alpaca.markets/us/docs/about-market-data-api",
    "checked": "2026-10-29"
  },
  "status": "verified",
  "checked_at": "2026-11-09"
}
```

Pricing changes, so each price carries the `source` it was read from and the date it was `checked`. Check the vendor's page before you rely on a number.

### JavaScript (browser or Node 18+)

CORS is open (`Access-Control-Allow-Origin: *`), so this also works from a static page:

```js
const res = await fetch(
  "https://tradingaihub.com/api/v1/search?q=crypto+exchange&limit=5"
);
const { tools } = await res.json();
for (const t of tools) {
  console.log(t.name, t.type, t.status, t.vendor_url);
}
```

### Python

```python
import requests

r = requests.get(
    "https://tradingaihub.com/api/v1/tools",
    params={"category": "trading-brokers", "verified": "true"},
    timeout=10,
)
r.raise_for_status()
for t in r.json()["tools"]:
    print(t["name"], t["type"], t["pricing"]["model"])
```

### Errors

Errors are JSON with a stable `code`:

```json
{"error":{"status":404,"code":"not_found","message":"No tool with slug \"nope\". List slugs at /api/v1/tools."}}
```

The codes are `invalid_parameter` (400), `not_found` (404), `method_not_allowed` (405) and `rate_limited` (429).

## MCP server quickstart

The endpoint is `https://tradingaihub.com/mcp`. It uses Streamable HTTP, is stateless, answers `POST` only and needs no auth. It is registered in the official MCP Registry as `com.tradingaihub/directory` v1.0.0. Clients that support discovery can also find it through its server card at `/mcp/server-card`.

It exposes three read-only tools:

- `search_tools(query, category?, limit?)`: keyword search (limit 1–25, default 10)
- `get_tool(slug)`: the full record for one tool
- `list_categories()`: the categories with their counts

All three are marked `readOnlyHint: true`. The server can't place orders, and it never touches your accounts. It supports MCP protocol versions `2026-07-28`, `2025-11-25`, `2025-06-18` and `2025-03-26`.

### Claude (desktop or web)

**Settings → Connectors → Add custom connector**, name it TradingAIHub, paste `https://tradingaihub.com/mcp`, and leave auth empty.

If you'd rather use the config file (`claude_desktop_config.json`), bridge it with `mcp-remote`:

```json
{
  "mcpServers": {
    "tradingaihub": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://tradingaihub.com/mcp"]
    }
  }
}
```

### Cursor

Put this in `.cursor/mcp.json` for one project, or `~/.cursor/mcp.json` for all of them:

```json
{
  "mcpServers": {
    "tradingaihub": {
      "url": "https://tradingaihub.com/mcp"
    }
  }
}
```

### Claude Code

```bash
claude mcp add --transport http tradingaihub https://tradingaihub.com/mcp
```

### VS Code (GitHub Copilot)

Put this in `.vscode/mcp.json`:

```json
{
  "servers": {
    "tradingaihub": {
      "type": "http",
      "url": "https://tradingaihub.com/mcp"
    }
  }
}
```

### ChatGPT

ChatGPT → Settings → Apps & Connectors → Advanced settings → turn on developer mode, then Create: name TradingAIHub, MCP server URL `https://tradingaihub.com/mcp`, authentication: none.

### Raw JSON-RPC (handy for debugging)

```bash
curl -s https://tradingaihub.com/mcp \
  -H "content-type: application/json" \
  -H "accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search_tools","arguments":{"query":"stock prices","limit":3}}}'
```

Once it's connected, ask things like *"Find a verified MCP server for SEC filings and tell me its free tier"* or *"Which crypto exchange MCP servers are official?"*. The assistant calls `search_tools` and then `get_tool`, and answers from the current record rather than from its training data.

## Limits

- **Rate limits.** About 120 requests per minute for the REST API and 60 per minute for MCP, per IP. Limits are counted per Cloudflare edge instance, so treat them as a ceiling rather than a quota. Every response carries `RateLimit-Limit`, `RateLimit-Remaining` and `RateLimit-Reset` headers. If you go over, you get a `429` with `Retry-After`.
- **Caching.** REST responses are cached for 5 minutes in the browser (`max-age=300`) and up to an hour at the edge (`s-maxage=3600`). The data itself changes about once a week, so polling every few seconds gains you nothing. If you want everything, take one copy of `/api/v1/tools.json`.
- **Coverage.** 104 tools is a curated list, not the whole ecosystem. If a tool you use is missing, or a record is wrong, email [hello@tradingaihub.com](mailto:hello@tradingaihub.com) and we'll fix it.
- **Read-only.** There are no write endpoints and nothing to authenticate. That also means no user-specific data.

## Why we built it this way

Most of what goes wrong with finance AI tools isn't about the AI. It's stale information: an MCP server whose repo was archived, a "free tier" that's now paid, or a community fork presented as the official one. Putting the weekly-checked data behind a plain API and an MCP endpoint lets your own code, or your assistant, check those things itself.

The docs, with copy-paste snippets for every client, are at [tradingaihub.com/developers](/developers/).
