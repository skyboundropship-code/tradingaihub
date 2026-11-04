// Public read-only API (v1) data, built at `astro build` time into static JSON under dist/api/. Pages Functions
// (functions/api/v1/[[path]].js, functions/mcp/index.js) read that dump via env.ASSETS and never touch KV.
// Public fields only: no verification internals (checks, issues, http codes), no repo_keep / *_note / source_url, and no
// affiliate internals. Outbound vendor URLs are the RAW data/tools.json values (plain, exactly as llms.txt / llms-full.txt
// publish them): data.ts runs URLs through affUrl() for the site's own links, and those tags never enter this dump.
// As a guard, every URL is also passed through untagUrl() for each program, and the build fails if a tag slips through.
import raw from "../../data/tools.json";
import { AFFILIATES, SITE } from "../config";
import { untagUrl } from "./aff";
import { CATEGORIES, STATUS, TYPE_LABEL, starsOf, lastCommit, isCollection } from "./data";

export const API_VERSION = "1.0.0";
export const MCP_URL = `${SITE.url}/mcp`;
export const DOCS_URL = `${SITE.url}/developers/`;
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
    homepage: plain(t.homepage),
    docs: plain(t.docs),
    repo: plain(t.repo),
    remote_mcp_url: plain(t.remote_mcp_url),
    license: known(t.license),
    pricing: t.pricing ? { model: t.pricing.model ?? null, free_tier: known(t.pricing.free_tier), paid_from: known(t.pricing.paid_from), details: known(t.pricing.details), source: plain(t.pricing.source), checked: t.pricing.checked ?? null } : null,
    languages: languagesOf(v),
    packages: { npm: pkg(v.npm), pypi: pkg(v.pypi) },
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
const meta = { api_version: API_VERSION, source: SITE.url, docs: DOCS_URL, terms: `${SITE.url}/terms/`, notice: "Information directory only. Not investment advice.", data_checked_at: latestCheck };

// Affiliate guard: no affiliate param of any program, and no _go= redirect param, may appear anywhere in the dump.
const AFF_RE = new RegExp(`[?&](${[...Object.values(AFFILIATES).map((a) => a.param), "_go"].join("|")})=`, "i");
function guard(o: any) {
  const s = JSON.stringify(o);
  if (AFF_RE.test(s)) throw new Error("publicApi: an affiliate parameter reached the public API dump");
  return s;
}
export const toolsDumpJson = () => guard({ ...meta, count: publicTools.length, tools: publicTools });
export const categoriesJson = () => guard({ ...meta, count: publicCategories.length, categories: publicCategories });

export const FILTERS = {
  type: Object.keys(TYPE_LABEL),
  category: CATEGORIES.map((c) => c.slug),
  status: Object.keys(STATUS),
  language: ["javascript", "python"],
};
