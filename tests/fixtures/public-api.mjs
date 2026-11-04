// Small fixture for tests/public-api.test.mjs + tests/mcp.test.mjs: a fake env.ASSETS serving the two API dumps
// (same shape as dist/api/v1/*.json built from src/lib/publicApi.ts). No network.
const tool = (o) => ({ type_label: "MCP server", category_name: "Market data APIs & MCPs", official: false, homepage: null, docs: null, repo: null, remote_mcp_url: null,
  license: "MIT", pricing: null, languages: [], packages: { npm: null, pypi: null }, status: "verified", status_label: "Verified", verified: true,
  checked_at: "2026-11-02", github: null, url: `https://tradingaihub.com/tools/${o.slug}/`, ...o });
export const TOOLS = [
  tool({ slug: "alpha-vantage-mcp", name: "Alpha Vantage MCP", type: "mcp", category: "market-data", description: "Official MCP server exposing Alpha Vantage stocks, forex, crypto and indicators.", official: true, remote_mcp_url: "https://mcp.alphavantage.co/mcp", github: { stars: 500, last_commit: "2026-10-01", archived: false, collection: false } }),
  tool({ slug: "yfinance-mcp", name: "Yahoo Finance MCP", type: "mcp", category: "market-data", description: "Stock prices and fundamentals from Yahoo Finance.", languages: ["python"], packages: { npm: null, pypi: { name: "yfinance-mcp", version: "1.0", url: "https://pypi.org/project/yfinance-mcp/" } }, status: "aging", status_label: "Aging", verified: false, github: { stars: 900, last_commit: "2026-01-01", archived: false, collection: false } }),
  tool({ slug: "ccxt-mcp", name: "CCXT MCP", type: "mcp", category: "crypto", category_name: "Crypto & DeFi", description: "Crypto exchange trading through CCXT.", languages: ["javascript"], packages: { npm: { name: "ccxt-mcp", version: "2.0", url: "https://www.npmjs.com/package/ccxt-mcp" }, pypi: null } }),
  tool({ slug: "sec-edgar-api", name: "SEC EDGAR API", type: "api", type_label: "API", category: "research-filings", category_name: "Research & filings", description: "Company filings from the SEC.", official: true, license: null }),
];
export const CATS = { count: 3, categories: [
  { slug: "market-data", name: "Market data APIs & MCPs", short: "Market data", icon: "📈", description: "Prices.", url: "https://tradingaihub.com/category/market-data/", count: 2 },
  { slug: "crypto", name: "Crypto & DeFi", short: "Crypto", icon: "🪙", description: "Crypto.", url: "https://tradingaihub.com/category/crypto/", count: 1 },
  { slug: "research-filings", name: "Research & filings", short: "Research", icon: "📄", description: "Filings.", url: "https://tradingaihub.com/category/research-filings/", count: 1 },
] };
export const DUMP = { api_version: "1.0.0", source: "https://tradingaihub.com", count: TOOLS.length, tools: TOOLS };
export const OPENAPI = { openapi: "3.1.0", info: { title: "TradingAIHub public API", version: "1.0.0" }, paths: {} };

export function makeAssets({ fail = false } = {}) {
  const calls = [];
  return { calls, async fetch(req) {
    const p = new URL(req.url ?? req).pathname; calls.push(p);
    if (fail) return new Response("err", { status: 500 });
    const body = { "/api/v1/tools.json": DUMP, "/api/v1/categories.json": CATS, "/api/openapi.json": OPENAPI }[p];
    return body ? new Response(JSON.stringify(body), { headers: { "content-type": "application/json" } }) : new Response("not found", { status: 404 });
  } };
}
let ipN = 0;
export const freshIp = () => `10.0.${(++ipN >> 8) & 255}.${ipN & 255}`;
