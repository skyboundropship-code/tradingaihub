# Outbound click tracking

- Endpoint: `POST /api/click` (functions/api/click.js), fired by `navigator.sendBeacon` from src/layouts/Base.astro.
  Links are never rewritten or redirected: the browser follows the original href, affiliate tags intact. No open-redirect surface.
- Storage: Workers Analytics Engine, binding `CLICKS` (dataset `tah_clicks`, preview `tah_clicks_preview`). Zero KV reads/writes,
  so clicks never consume the account-wide KV free-tier write limit (1,000/day) the newsletter needs.
- Dimensions (blobs): 1 tool, 2 affiliate id (tradingview, eodhd, polar, … ; `-` for plain links), 3 kind, 4 target host,
  5 locale, 6 page path (locale prefix removed), 7 referrer host (`(direct)` if none), 8 is_bot (`0`/`1`), 9 source (`human`/`bot`/`qa`).
  No IP, user agent, cookie or other personal data is stored.
- Bot / own traffic is written with is_bot=1 and excluded by reports:
  - UA matching the bot regex (crawlers, headless, curl, wget, python, puppeteer/playwright/selenium, …), missing UA, Cloudflare verified bots;
  - **QA: our QA and test scripts must send the header `x-tah-qa: 1`** on every request to /api/click (and may send it site-wide).
- Report: `npm run clicks [-- --env preview] [--json]` — per-affiliate, per-tool and total human clicks for 1/7/30 days via the
  AE SQL API. Needs `CLOUDFLARE_API_TOKEN` with **Account Analytics: Read** (+ `CLOUDFLARE_ACCOUNT_ID`, optional if the token sees one account).
  The token is never printed; if it lacks the permission the report says so.
