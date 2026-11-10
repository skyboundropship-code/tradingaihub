// Public read-only API (v1) data, built at `astro build` time into static JSON under dist/api/. Pages Functions
// (functions/api/v1/[[path]].js, functions/mcp/index.js) read that dump via env.ASSETS and never touch KV.
// Public fields only: no verification internals (checks, issues, http codes), no repo_keep / *_note / source_url, and no
// affiliate internals (no partner ids, config or param names as fields). Links per tool:
//   url          the tool's page on tradingaihub.com
//   website_url  the vendor link exactly as the site renders it (affUrl from src/lib/aff.ts): tagged when it is an affiliate link
//   vendor_url   the same link, always plain
//   affiliate    true when website_url is a tagged affiliate link; disclosure is a short English notice then, otherwise null
// Every other URL field (homepage, docs, repo, pricing.source, ...) stays plain. The build checks this contract (contract()).
import raw from "../../data/tools.json";
import { AFFILIATES, SITE } from "../config";
import { affUrl, isAff, untagUrl } from "./aff";
import { tools as siteTools, CATEGORIES, STATUS, TYPE_LABEL, starsOf, lastCommit, isCollection, pkgOf } from "./data";

export const API_VERSION = "1.0.0";
export const MCP_URL = `${SITE.url}/mcp`;
export const DOCS_URL = `${SITE.url}/developers/`;
export const DISCLOSURE = `This link is an affiliate link; TradingAIHub may earn a commission at no extra cost to you. It never affects listings. See ${SITE.url}/disclaimer/`;
/** Data licence (CC BY 4.0 for the data, MIT (API and MCP server code), scoped in LICENSE-CODE). Same values as functions/_lib/api.js DATA_LICENSE. */
export const DATA_LICENSE = { license: "CC BY 4.0", license_url: "https://creativecommons.org/licenses/by/4.0/", attribution: "TradingAIHub, https://tradingaihub.com" };
export const RATE_LIMITS = { api: 120, mcp: 60, windowSec: 60 };

const plain = (u: any): string | null => {
  if (typeof u !== "string" || !/^https?:\/\//.test(u)) return null;
  let s: string | undefined = u;
  for (const k of Object.keys(AFFILIATES) as (keyof typeof AFFILIATES)[]) s = untagUrl(s, k);
  return s ?? null;
};
const known = (x: any) => (typeof x === "string" && x.trim() !== "" && !/^(unknown|none|n\/a)$/i.test(x.trim()) ? x : null);
/** Package ecosystem -> language. The data has no language field; it is derived from the published package (documented). */
const languagesOf = (v: any) => [...(v?.npm ? ["javascript"] : []), ...(v?.pypi ? ["python"] : [])];
const pkg = (p: any) => (p ? { name: p.name, version: p.version ?? null, url: plain(p.url) } : null);

/** The vendor link the tool page shows first (homepage, else docs, else repo): tagged as on the site, and plain. */
function links(t: any) {
  const vendor = plain(t.homepage) ?? plain(t.docs) ?? plain(t.repo);
  const website = vendor ? affUrl(vendor) ?? vendor : null;
  const affiliate = !!vendor && isAff(vendor) && website !== vendor;
  return { website_url: website, vendor_url: vendor, affiliate, disclosure: affiliate ? DISCLOSURE : null };
}

export function publicTool(t: any) {
  const v = t.verification || {};
  const cat = CATEGORIES.find((c) => c.slug === t.category);
  return {
    slug: t.id,
    name: t.name,
    type: t.type,
    type_label: TYPE_LABEL[t.type] ?? t.type,
    category: t.category,
    category_name: cat?.name ?? null,
    description: t.description,
    official: !!t.official,
    url: `${SITE.url}/tools/${t.id}/`,
    ...links(t),
    homepage: plain(t.homepage),
    docs: plain(t.docs),
    repo: plain(t.repo),
    remote_mcp_url: plain(t.remote_mcp_url),
    license: known(t.license),
    pricing: t.pricing ? { model: t.pricing.model ?? null, free_tier: known(t.pricing.free_tier), paid_from: known(t.pricing.paid_from), details: known(t.pricing.details), source: plain(t.pricing.source), checked: t.pricing.checked ?? null } : null,
    languages: pkgOf(t) ? languagesOf(v) : [],
    packages: { npm: pkgOf(t) ? pkg(v.npm) : null, pypi: pkgOf(t) ? pkg(v.pypi) : null },
    install: t.install_from_source ? { from_source: true, note: "The published package is currently unmaintained, so don't install it from the registry. Clone the repository, follow its README to run it locally, then register the start command as a stdio MCP server in your client." } : null,
    capabilities: Array.isArray(t.capabilities) ? t.capabilities : [],
    deprecated: !!t.deprecated,
    status: v.status,
    status_label: STATUS[v.status]?.label ?? v.status,
    verified: v.status === "verified",
    checked_at: v.checked_at ?? null,
    github: v.github ? { stars: starsOf(t), last_commit: lastCommit(t), archived: !!v.github.archived, collection: isCollection(t) } : null,
  };
}

export const publicTools = (raw as any[]).map(publicTool);

export const publicCategories = CATEGORIES.map((c) => ({
  slug: c.slug, name: c.name, short: c.short, icon: c.icon, description: c.blurb,
  url: `${SITE.url}/category/${c.slug}/`,
  count: publicTools.filter((t) => t.category === c.slug).length,
}));

const latestCheck = publicTools.map((t) => t.checked_at || "").sort().at(-1) || null;
const meta = { api_version: API_VERSION, source: SITE.url, docs: DOCS_URL, terms: `${SITE.url}/terms/`, ...DATA_LICENSE, notice: "Information directory only. Not investment advice.", data_checked_at: latestCheck };

// Affiliate contract, checked at build time (the build fails on any violation):
//  - website_url equals the href the site renders for that tool (data.ts homepage / docs / repo, all via affUrl)
//  - affiliate (and a disclosure) appear exactly when website_url carries an affiliate tag
//  - vendor_url and every other field carry no affiliate param and no _go= redirect param
export const AFF_RE = new RegExp(`[?&](${[...Object.values(AFFILIATES).map((a) => a.param), "_go"].join("|")})=`, "i");
const siteHref = new Map(siteTools.map((t: any) => [t.id, t.homepage || t.docs || t.repo || null]));
export function contract(tool: any) {
  const fail = (m: string) => { throw new Error(`publicApi: ${tool.slug}: ${m}`); };
  const site = siteHref.get(tool.slug) ?? null;
  if (tool.website_url !== site) fail(`website_url ${tool.website_url} != site href ${site}`);
  const tagged = !!tool.website_url && AFF_RE.test(tool.website_url);
  if (tool.affiliate !== tagged) fail("affiliate flag does not match the tagged link");
  if (tagged ? tool.disclosure !== DISCLOSURE : tool.disclosure !== null) fail("disclosure must be set exactly for affiliate links");
  const { website_url, ...rest } = tool;
  if (AFF_RE.test(JSON.stringify(rest))) fail("an affiliate param reached a field other than website_url");
  return tool;
}
publicTools.forEach(contract);
const guard = (o: any) => {
  const s = JSON.stringify(o);
  if (/"(partner|partners|aff_id|affiliate_id)"\s*:/.test(s)) throw new Error("publicApi: affiliate internals in the dump");
  return s;
};
export const toolsDumpJson = () => guard({ ...meta, count: publicTools.length, tools: publicTools.map(contract) });
export const categoriesJson = () => { const s = guard({ ...meta, count: publicCategories.length, categories: publicCategories }); if (AFF_RE.test(s)) throw new Error("publicApi: affiliate param in categories"); return s; };

export const FILTERS = {
  type: Object.keys(TYPE_LABEL),
  category: CATEGORIES.map((c) => c.slug),
  status: Object.keys(STATUS),
  language: ["javascript", "python"],
};
