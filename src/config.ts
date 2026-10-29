// ===== Single place to swap the brand. Change these and rebuild. =====
export const SITE = {
  name: "TradingAIHub",                 // brand — domain purchased by Liran at Cloudflare Registrar 2026-10-29
  domain: "tradingaihub.com",            // owned (Cloudflare Registrar)
  url: "https://tradingaihub.com",       // used for canonical URLs + sitemap
  tagline: "Verified AI tools for finance & trading",
  description:
    "A weekly-verified directory of MCP servers, agent skills and APIs for market data, trading, crypto, accounting and financial research — with pricing, free tiers and copy-paste install snippets for Claude, Cursor, ChatGPT, Grok and Gemini.",
  contactEmail: "hello@tradingaihub.com", // Cloudflare Email Routing → Liran
  showAdPricing: false,               // launch = 100% free feel: hide paid tiers until traffic exists
  newsletterLive: true,                // form POSTs to functions/api/subscribe.js (needs KV binding NEWSLETTER)
  githubAwesomeRepo: "https://github.com/skyboundropship-code/awesome-finance-ai-tools",
  checkoutLive: false,                 // featured-listing checkout is NOT live
  checkoutUrl: "#checkout-not-live",   // replace with Polar / Lemon Squeezy link after approval
};

// Affiliate programs. Links are always labelled and use rel="sponsored noopener".
export const AFFILIATES = {
  tradingview: { id: "1173592", param: "aff_id", hosts: ["tradingview.com"], home: "https://www.tradingview.com/" },
};
