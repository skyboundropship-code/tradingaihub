// ===== Single place to swap the brand. Change these and rebuild. =====
export const SITE = {
  name: "TradingAIHub",                 // brand — domain purchased by the TradingAIHub team at Cloudflare Registrar 2026-10-29
  domain: "tradingaihub.com",            // owned (Cloudflare Registrar)
  url: "https://tradingaihub.com",       // used for canonical URLs + sitemap
  tagline: "Verified AI tools for finance & trading",
  description:
    "A weekly-verified directory of MCP servers, agent skills and APIs for market data, trading, crypto, accounting and financial research — with pricing, free tiers and copy-paste install snippets for Claude, Cursor, ChatGPT, Grok and Gemini.",
  contactEmail: "hello@tradingaihub.com", // Cloudflare Email Routing → TradingAIHub team inbox
  showAdPricing: false,               // launch = 100% free feel: hide paid tiers until traffic exists
  newsletterLive: true,                // form POSTs to functions/api/subscribe.js (needs KV binding NEWSLETTER)
  githubAwesomeRepo: "https://github.com/skyboundropship-code/awesome-finance-ai-tools",
  checkoutLive: false,                 // featured-listing checkout is NOT live
  checkoutUrl: "#checkout-not-live",   // replace with Polar / Lemon Squeezy link after approval
};

// Affiliate programs. Links are always labelled and use rel="sponsored noopener".
export const AFFILIATES = {
  tradingview: { id: "1173592", param: "aff_id", hosts: ["tradingview.com"], home: "https://www.tradingview.com/" },
  // exact: only eodhd.com / www.eodhd.com are tagged; API and MCP hosts (api., mcp.) never are.
  // paths: exact pathname match; read by check_aff.mjs. Includes pages proven (curl) to load
  // cdn.promotekit.com/promotekit.js (/, /pricing, /lp/eodhd-mcp-server) plus the two docs paths
  // EODHD asked to tag: /financial-apis/ and the official MCP docs page.
  eodhd: { id: "tradingaihub", param: "via", hosts: ["eodhd.com", "www.eodhd.com"], exact: true, paths: ["/", "/pricing", "/lp/eodhd-mcp-server", "/financial-apis/", "/financial-apis/mcp-server-for-financial-data-by-eodhd"], home: "https://eodhd.com/" },
};
