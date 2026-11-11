// Shared data for English-only editorial comparison pages under /compare/best-ai-tools-for-*/.
// Tool rows are resolved from data/tools.json at build time; unknown or unverified ids fail the build.
import { tools, verificationReport } from "./data";
import type { QA } from "./faq";

const byId: Record<string, any> = Object.fromEntries(tools.map((t) => [t.id, t]));

export function requireTools(ids: string[]): any[] {
  const missing = ids.filter((id) => !byId[id]);
  if (missing.length) throw new Error(`best page: unknown tool ids: ${missing.join(", ")}`);
  const notVerified = ids.filter((id) => byId[id].verification?.status !== "verified");
  if (notVerified.length) throw new Error(`best page: not verified in the latest run: ${notVerified.join(", ")}`);
  return ids.map((id) => byId[id]);
}

export function paidFrom(t: any): string {
  const v = t.pricing?.paid_from;
  if (v == null || /^(none|n\/a|unknown|—|-)$/i.test(String(v).trim())) return "—";
  return String(v);
}

export function capNoteKey(t: any): string | null {
  const caps = Array.isArray(t.capabilities) ? t.capabilities : [];
  const hasLive = caps.includes("live_trading");
  const hasFunds = caps.includes("moves_funds");
  return hasLive && hasFunds ? "tool.liveFundsNote" : hasLive ? "tool.liveTradingNote" : hasFunds ? "tool.movesFundsNote" : null;
}

export const RUN_DATE = String(verificationReport.checked_at || "").slice(0, 10);
export const RUN_TOTAL: number = verificationReport.total;
export const RUN_VERIFIED: number = verificationReport.by_status?.verified ?? 0;
export const PUBLISHED = "2026-11-11";
export const PRICING_CHECKED = "2026-11-11";

const months = ["January","February","March","April","May","June","July","August","September","October","November","December"];
export const prettyDate = (iso: string) => {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) throw new Error(`best page: bad date ${iso}`);
  return `${d} ${months[m - 1]} ${y}`;
};

export type BestPageMeta = {
  slug: string;
  title: string;
  description: string;
  h1: string;
  datePublished: string;
  dateModified: string;
  toolIds: string[];
  faq: QA[];
};

// Pricing cells on these pages use vendor wording from tools.json, re-checked against live vendor
// pricing pages on 11 November 2026. No cell wording was changed (see the PR notes).
export const STOCK: BestPageMeta = {
  slug: "best-ai-tools-for-stock-analysis",
  title: "Best AI tools for stock analysis and research (2026)",
  description: "Verified MCP servers, skills and APIs for stock analysis and SEC filings, compared from our 10 Nov 2026 check. Official vendors first. Not financial advice.",
  h1: "Best AI tools for stock analysis and research (2026)",
  datePublished: PUBLISHED,
  dateModified: PUBLISHED,
  toolIds: [
    "alpha-vantage-mcp", "fmp-mcp", "fmp-api", "finnhub-mcp", "eodhd-mcp", "massive-mcp",
    "tradingview-official-mcp", "twelve-data-api", "alpaca-market-data-api", "sec-edgar-api",
    "sec-edgar-mcp", "fmp-mcp-community", "maverick-mcp", "investor-agent", "yahoo-finance-mcp",
  ],
  faq: [
    { q: "How is “verified” defined?", a: "Verified means the listing was reachable in our weekly automated check, its homepage, docs and hosted endpoints were alive, and — for tools with a public repository — there was a commit in the last 180 days. This page uses only that status from 10 November 2026. The full run is on the verification page." },
    { q: "Are these recommendations to buy a stock?", a: "No. Nothing here is investment advice, a rating, or a prediction. These tools fetch market data or filings for your own research. Data can be delayed or wrong, and an assistant can misread a filing. Check figures against the source, and paper trade first." },
    { q: "Do official and community servers differ?", a: "Official means the data vendor publishes the tool itself. Community tools can be useful, but they depend on a maintainer and sometimes on unofficial data that can change without notice. We label each row. The same vendor data plan usually applies to an official server and a community wrapper." },
    { q: "What does the free tier actually allow?", a: "The free-tier column is the vendor’s wording for the underlying data plan, as recorded in our directory and re-checked on 11 November 2026. It is not a separate MCP allowance. A research question can trigger many calls, so a 20–25 request daily cap is enough to try a connection, not to run a daily workflow. Confirm limits on the vendor’s pricing page." },
    { q: "Why is Yahoo Finance listed with a caveat?", a: "Yahoo Finance MCP is a verified community server, but it uses unofficial Yahoo Finance endpoints. Those are not a licensed market-data feed and can change or go away without notice. Use it for experiments, not as a source of record." },
  ],
};

export const STOCK_FETCH: Record<string, string> = {
  "alpha-vantage-mcp": "Stocks, forex, crypto and indicators",
  "fmp-mcp": "Statements, quotes, indicators, news, filings (27 tools)",
  "fmp-api": "Fundamentals, ratios, prices, transcripts, 13F",
  "finnhub-mcp": "Quotes, financials, estimates, filings and more (~70 tools)",
  "eodhd-mcp": "Prices, fundamentals, news, technicals, options, macro (70+ tools)",
  "massive-mcp": "US stocks, options, forex and crypto",
  "tradingview-official-mcp": "OHLCV, screeners, technicals, fundamentals, news, alerts",
  "twelve-data-api": "Stocks, forex, crypto and ETFs",
  "alpaca-market-data-api": "US equities and options market data",
  "sec-edgar-api": "Company submissions and XBRL financial data",
  "sec-edgar-mcp": "Filings, XBRL statements and Form 3/4/5 insider data",
  "fmp-mcp-community": "Community wrapper of 250+ FMP tools",
  "maverick-mcp": "Technical analysis, screening and portfolio tools",
  "investor-agent": "Market data, sentiment and fundamentals",
  "yahoo-finance-mcp": "Quotes and history (unofficial data source)",
};

export const OPTIONS: BestPageMeta = {
  slug: "best-ai-tools-for-options-trading",
  title: "Best AI tools for options data and options trading (2026)",
  description: "Verified MCP servers, APIs and skills for options chains, Greeks and broker-connected workflows, compared from our 10 Nov 2026 check. Data tools first. Not financial advice.",
  h1: "Best AI tools for options data and options trading (2026)",
  datePublished: PUBLISHED,
  dateModified: PUBLISHED,
  // ItemList order: data table, then broker table, then the skills section tool.
  toolIds: [
    "massive-mcp", "massive-api", "alpaca-market-data-api", "eodhd-mcp", "schwab-mcp",
    "alpaca-mcp", "tasty-agent", "robinhood-trading-mcp", "webull-openapi-mcp",
    "options-trading-skills",
  ],
  faq: [
    { q: "How is “verified” defined?", a: "Verified means the listing was reachable in our weekly automated check, its homepage, docs and hosted endpoints were alive, and — for tools with a public repository — there was a commit in the last 180 days. This page uses only that status from 10 November 2026. The full run is on the verification page." },
    { q: "Should I start with paper trading or a live account?", a: "Paper trade first. Options can lose value quickly, and an assistant can mis-build a leg or send an order you did not intend. Review every order before it is submitted. Some official tools record a sandbox or a read-only default in our directory; others do not. If the table says the listing does not record a paper or sandbox mode, confirm what the vendor actually offers before you connect a funded account." },
    { q: "Do official and community servers differ?", a: "Official means the vendor publishes the tool itself. Community tools can be useful, but they depend on a maintainer and on the broker’s or data vendor’s terms. Several community servers here still require a brokerage account and, in some cases, a developer key. We label each row. A community wrapper does not make the underlying broker or data plan free." },
    { q: "Do you recommend a broker?", a: "No. Nothing on this page is a recommendation to open, fund, or trade through any brokerage. We list verified tools that can fetch options data or, separately, place orders. Choosing a broker is your decision, and it is not something these listings settle." },
    { q: "What does the free tier actually allow?", a: "The free-tier column is the vendor’s wording for the underlying data plan or access requirement, as recorded in our directory and re-checked on 11 November 2026. It is not a separate MCP allowance. Broker rows that say an account is required are not a free trading rebate. Confirm limits and fees on the vendor’s pricing page before you pay or place an order." },
  ],
};

export const OPTIONS_DATA_IDS = ["massive-mcp", "massive-api", "alpaca-market-data-api", "eodhd-mcp", "schwab-mcp"];
export const OPTIONS_BROKER_IDS = ["alpaca-mcp", "tasty-agent", "robinhood-trading-mcp", "webull-openapi-mcp"];
export const OPTIONS_SKILL_IDS = ["options-trading-skills"];

export const OPTIONS_FETCH: Record<string, string> = {
  "massive-mcp": "US stocks, options, forex and crypto",
  "massive-api": "Tick-level US stocks, options, indices, forex and crypto (REST, WebSockets, flat files)",
  "alpaca-market-data-api": "US equities and options market data",
  "eodhd-mcp": "Prices, fundamentals, news, technicals, options, macro (70+ read-only tools)",
  "schwab-mcp": "Accounts, quotes, options chains; read-only by default",
  "alpaca-mcp": "Trade stocks, ETFs, options and crypto; query positions and market data",
  "tasty-agent": "Portfolio, market data, options Greeks and order execution",
  "robinhood-trading-mcp": "Read accounts and trade stocks, options and crypto in a dedicated agent account",
  "webull-openapi-mcp": "Multi-region market data and orders for stocks, options, futures and crypto",
  "options-trading-skills": "Scanners, Greeks, spreads, PMCC screens, correlations and IBKR portfolio reports",
};

// Paper / sandbox / default: only what the listing already records. Do not invent a flag.
export const OPTIONS_PAPER: Record<string, string> = {
  "alpaca-mcp": "Not recorded in our listing; confirm with the vendor",
  "tasty-agent": "Not recorded in our listing; requires a tastytrade account",
  "robinhood-trading-mcp": "Trade approvals off by default; dedicated MCP account only; no multi-leg",
  "webull-openapi-mcp": "UAT sandbox",
};

export const EDITORIAL_COMPARES = [STOCK, OPTIONS];
