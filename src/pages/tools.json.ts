import { tools } from "../lib/data";
import { untagUrl } from "../lib/aff";
import { provExport } from "../lib/provenance";
// Public data export: EODHD vendor URLs are exported plain (no via=); the site's own links carry the affiliate param.
// provenance is the public shape only (state, registry, package, package_url, declared_repo); no maintainer names.
const plain = (u?: string) => untagUrl(u, "eodhd");
export const GET = () => new Response(JSON.stringify(tools.map(({ id, name, type, category, description, repo, homepage, pricing, license, verification }) => ({ id, name, type, category, description, repo, homepage: plain(homepage), pricing: pricing ? { ...pricing, source: plain(pricing.source) } : pricing, license, status: verification.status, checked_at: verification.checked_at, provenance: provExport(id) }))), { headers: { "content-type": "application/json" } });
