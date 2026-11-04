# TradingAIHub (placeholder brand) — verified AI tools for finance & trading
Static Astro site + weekly verifier. Brand/domain in `src/config.ts`.
- `npm run verify` – verify 75 tools (data/seed.json → data/tools.json, reports, history, changelog)
- `npm run weekly` – verify → awesome list → OG images → build
- `npm run weekly:publish` – weekly + deploy + IndexNow ping (`npm run indexnow` alone re-submits all sitemap URLs)
- `npm run preview` – http://localhost:4321 · `npm run screenshots`
- Docs: docs/HOSTING.md (deploy steps, accounts, monetization later), docs/DOMAINS.md, docs/LAUNCH-PLAN.md
Nothing here is deployed or published. Not investment advice.

## Brand

Logo 6 "Verified t" (lowercase wordmark `tradingaihub`; green #15803d on light, #22c55e on dark). Optimized SVGs and the 1600x400 lockup PNG live in `public/brand/`; favicons, `apple-touch-icon.png`, `icon-192/512.png` and `logo-512.png` (JSON-LD Organization logo) are in `public/`. The header/footer use `src/components/BrandLogo.astro`, which follows the site theme.
