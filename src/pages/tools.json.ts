import { tools, plainUrl as plain } from "../lib/data";
// Public data export: vendor URLs are exported plain (no TradingView aff_id, no EODHD via=); the site's own links carry
// the affiliate param.
export const GET = () => new Response(JSON.stringify(tools.map(({ id, name, type, category, description, repo, homepage, pricing, license, verification }) => ({ id, name, type, category, description, repo, homepage: plain(homepage), pricing: pricing ? { ...pricing, source: plain(pricing.source) } : pricing, license, status: verification.status, checked_at: verification.checked_at }))), { headers: { "content-type": "application/json" } });
