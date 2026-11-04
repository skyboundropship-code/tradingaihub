# TradingAIHub — verified AI tools for finance & trading

**Live site: https://tradingaihub.com** — a free directory of 104 MCP servers, agent skills and APIs for market data, trading, crypto, accounting and financial research, available in 13 languages.

Every tool is re-checked weekly by a script: the repo is reachable, recent commits, stars, whether its npm/PyPI package links back to the repo, and whether hosted endpoints respond. Broken or archived tools are marked, not quietly kept. How it works: [verification methodology](https://tradingaihub.com/verification/).

- ⭐ The open list: [skyboundropship-code/awesome-finance-ai-tools](https://github.com/skyboundropship-code/awesome-finance-ai-tools)
- Full data dump: [tradingaihub.com/tools.json](https://tradingaihub.com/tools.json) · [llms.txt](https://tradingaihub.com/llms.txt)
- Free public API and MCP server: coming soon

## Submit a tool
Use the [submit form](https://tradingaihub.com/submit/) or open an issue / PR on the [awesome list](https://github.com/skyboundropship-code/awesome-finance-ai-tools). Tools must be finance-relevant, have a public repo or official docs, and be actively maintained. Listing is free; paid placements, if any, are clearly labelled as sponsored and never affect verification.

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
