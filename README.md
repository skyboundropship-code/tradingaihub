# TradingAIHub — verified AI tools for finance & trading

[![MCP Registry](https://img.shields.io/badge/MCP_Registry-com.tradingaihub%2Fdirectory-555)](https://registry.modelcontextprotocol.io/v0/servers?search=tradingaihub)
[![Public API](https://img.shields.io/badge/API-public%20%7C%20no%20key-15803d)](https://tradingaihub.com/developers/)
[![Data: CC BY 4.0](https://img.shields.io/badge/data-CC%20BY%204.0-lightgrey)](https://creativecommons.org/licenses/by/4.0/)
[![Code: MIT](https://img.shields.io/badge/code-MIT-blue)](https://github.com/tradingaihub/tradingaihub/blob/main/LICENSE-CODE)
[![GitHub stars](https://img.shields.io/github/stars/tradingaihub/tradingaihub?style=social)](https://github.com/tradingaihub/tradingaihub)

**Live site: https://tradingaihub.com** — a free directory of 104 MCP servers, agent skills and APIs for market data, trading, crypto, accounting and financial research, available in 13 languages.

Every tool is re-checked weekly by a script: the repo is reachable, recent commits, stars, whether its npm/PyPI package links back to the repo, and whether hosted endpoints respond. Broken or archived tools are marked, not quietly kept. How it works: [verification methodology](https://tradingaihub.com/verification/).

- ⭐ The open list: [tradingaihub/awesome-finance-ai-tools](https://github.com/tradingaihub/awesome-finance-ai-tools)
- Full data dump: [tradingaihub.com/tools.json](https://tradingaihub.com/tools.json) · [/api/v1/tools.json](https://tradingaihub.com/api/v1/tools.json) · [llms.txt](https://tradingaihub.com/llms.txt)
- Free public API and MCP server (no key): [docs](https://tradingaihub.com/developers/) · [REST](https://tradingaihub.com/api/v1/tools) · [OpenAPI](https://tradingaihub.com/api/openapi.json) · [MCP](https://tradingaihub.com/developers/) · official registry `com.tradingaihub/directory`

## Use it from your AI agent

The same weekly-checked directory is available as a remote MCP server (Streamable HTTP, no sign-in) and as a read-only JSON API. Data is CC BY 4.0 (credit "TradingAIHub, https://tradingaihub.com"); the API and MCP server code is MIT, see [LICENSE-CODE](LICENSE-CODE).

**Cursor** — add to `.cursor/mcp.json` or `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "tradingaihub": {
      "url": "https://tradingaihub.com/mcp"
    }
  }
}
```

**Claude Code:**

```bash
claude mcp add --transport http tradingaihub https://tradingaihub.com/mcp
```

**Claude (desktop or web):** Settings → Connectors → Add custom connector, paste `https://tradingaihub.com/mcp`, auth empty.

**VS Code / GitHub Copilot** — add to `.vscode/mcp.json`:

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

**REST, no key:**

```bash
curl -s "https://tradingaihub.com/api/v1/search?q=options+data&limit=5"
curl -s "https://tradingaihub.com/api/v1/tools?category=market-data&type=mcp&verified=true"
```

The MCP tools are `search_tools`, `get_tool` and `list_categories` (all read-only). Rate limits are about 120 requests/min for the API and 60/min for MCP, per IP per edge. Not investment advice. Full snippets, including ChatGPT: https://tradingaihub.com/developers/

## Submit a tool
Use the [submit form](https://tradingaihub.com/submit/) or open an issue / PR on the [awesome list](https://github.com/tradingaihub/awesome-finance-ai-tools). Tools must be finance-relevant, have a public repo or official docs, and be actively maintained. Listing is free; paid placements, if any, are clearly labelled as sponsored and never affect verification.

## Development
Static [Astro](https://astro.build) site + weekly verifier. Brand settings live in `src/config.ts`.

- `npm run verify` – verify all tools (data/seed.json → data/tools.json, reports, history, changelog)
- `npm run weekly` – verify → awesome list → OG images → build
- `npm run build` – build `dist/` with affiliate-link and OG checks
- `npm run test:functions` / `npm run test:aff` / `npm run test:verify` – tests
- `npm run preview` – http://localhost:4321

Docs: `docs/HOSTING.md`, `docs/DOMAINS.md`, `docs/LAUNCH-PLAN.md`.

## Brand

Logo 6 "Verified t" (lowercase wordmark `tradingaihub`; green #15803d on light, #22c55e on dark). Optimized SVGs and the 1600x400 lockup PNG live in `public/brand/`; favicons, `apple-touch-icon.png`, `icon-192/512.png` and `logo-512.png` (JSON-LD Organization logo) are in `public/`. The header/footer use `src/components/BrandLogo.astro`, which follows the site theme.

## Contact
hello@tradingaihub.com — the TradingAIHub team.

Not investment advice.
