# Hosting, deploy, accounts, monetization (later)

## Deploy to Cloudflare Pages — ONLY after Liran approves
Token `CLOUDFLARE_API_TOKEN` is on the box (checked read-only with `wrangler whoami`: 1 account; not used for anything else).
```bash
cd /workspace/finance-skills-directory
npm run weekly            # verify → awesome list → OG images → astro build (dist/, 105 pages)
export CLOUDFLARE_ACCOUNT_ID=<from `npx wrangler whoami`>
npx wrangler pages project create tradeskills --production-branch=main   # once
npx wrangler pages deploy dist --project-name=tradeskills --branch=main
```
→ live at https://tradeskills.pages.dev. Custom domain: buy at Cloudflare Registrar (approval), then
Pages → tradeskills → Custom domains → add `tradeskills.ai` (DNS gets set up automatically on the same account).
If the brand changes, update `src/config.ts` + `wrangler.toml` first.
Cloudflare Pages free plan: static requests/bandwidth are free; 500 builds/mo; 20k files/deploy (we use ~300).

## Weekly automation
`.github/workflows/weekly.yml` (Mondays 05:00 UTC = 07:00 Israel time) runs verify → awesome → og → build → deploy and commits `data/` + `awesome/`.
It does nothing until a GitHub repo is created and the secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` are added (needs approval).
Alternative with no GitHub: a weekly box routine running `npm run weekly && npx wrangler pages deploy dist --project-name=tradeskills`.

## Accounts needed
| Account | When | Status |
|---|---|---|
| Cloudflare (Pages + Registrar) | launch | exists, token on box |
| GitHub repo (site) + public repo `awesome-finance-ai-tools` (mirror of awesome/README.md) | launch | needs approval to create |
| Newsletter: Buttondown or beehiiv (free tier; confirm limits) → set `newsletterLive` + form action | launch | sign-up needed |
| Submissions: GitHub Issue Form in the public repo (free, public, extra backlinks) or Tally/Formspree | launch | — |
| Contact mailbox for `contactEmail` (e.g. Cloudflare Email Routing → Liran's Gmail) | launch | needed |
| Plausible/Cloudflare Web Analytics (free, no cookies) | launch | turn on in CF dashboard |
| Polar or Lemon Squeezy (merchant of record, handles VAT; KYC) | only once there's traffic | later |

## Monetization — deliberately OFF at launch
- `showAdPricing:false`, `checkoutLive:false` in `src/config.ts`. The only sign is a faint "Advertise" link in the footer (noindex page that says "sponsorships not open yet").
- Turn on later (e.g. after 10k monthly visits): sponsor slots $29/$99/$249 (prices already drafted, benchmarks: MCP Index $29/$79, Glama $49/$200, TAAFT $49, mcpservers.org $399+).
- Affiliates (apply after launch; most require a live site with traffic):
  - TradingView Partner Program: pays per new paid subscription (published range ~$10–400). Apply on tradingview.com/partner-program.
  - EODHD: 15% for the first 3 months — affiliates.eodhd.com.
  - Financial Modeling Prep: tiered affiliate program (site.financialmodelingprep.com).
  - Others (Alpaca, CoinGecko, Polygon/Massive, brokers): unknown — check each program page before applying.
  - Affiliate links must be labelled; listings stay ranked by verification, not by payment.
- Legal: "not investment advice" disclaimer incl. Israel's Investment Advice Law 5755-1995 is on every page; privacy/terms are DRAFT — get a lawyer review before charging money. Never redistribute vendor data.
