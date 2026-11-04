import { tools } from "../lib/data";
import { untagUrl } from "../lib/aff";
// Public data export: EODHD and TrendSpider vendor URLs are exported plain (no via=/_go=); the site's own links carry the affiliate param.
const plain = (u?: string) => untagUrl(untagUrl(u, "eodhd"), "trendspider");
export const GET = () => new Response(JSON.stringify(tools.map(({ id, name, type, category, description, repo, homepage, pricing, license, verification }) => ({ id, name, type, category, description, repo, homepage: plain(homepage), pricing: pricing ? { ...pricing, source: plain(pricing.source) } : pricing, license, status: verification.status, checked_at: verification.checked_at }))), { headers: { "content-type": "application/json" } });
