// JSON-LD builders shared by pages. Rules: real data only (no aggregateRating/review, no invented prices), and every
// outbound URL comes from RAW data/tools.json, never from data.ts (which runs URLs through affUrl() and adds aff_id).
import raw from "../../data/tools.json";
import { SITE } from "../config";
import { untagUrl } from "./aff";
import { TYPE_LABEL } from "./data";

const rawById: Record<string, any> = Object.fromEntries((raw as any[]).map((t) => [t.id, t]));
export const ORG_ID = `${SITE.url}/#organization`;
export const WEBSITE_ID = `${SITE.url}/#website`;
export const appId = (id: string) => `${SITE.url}/tools/${id}/#app`; // stable across locales
const FREE_MODELS = new Set(["free", "freemium", "open-source"]);
const SPDX = new Set(["MIT", "MIT-0", "Apache-2.0", "AGPL-3.0", "GPL-3.0", "LGPL-3.0", "BSD-2-Clause", "BSD-3-Clause", "MPL-2.0", "ISC", "Unlicense"]);
const known = (s: any) => typeof s === "string" && s.trim() !== "" && !/^(unknown|none|n\/a)$/i.test(s.trim());
// Defensive: strip EODHD's ?via= (raw data has none) and drop anything still carrying an affiliate param.
const clean = (u: any) => { if (typeof u !== "string") return null; const x = untagUrl(u, "eodhd") ?? u; return /^https?:\/\//.test(x) && !/aff_id=|[?&]via=/i.test(x) ? x : null; };

export function softwareLd(id: string, page: { name: string; description: string; url: string; lang: string }) {
  const t = rawById[id]; if (!t) throw new Error(`softwareLd: unknown tool ${id}`);
  const v = t.verification || {}; const pkg = v.npm || v.pypi || null; const pr = t.pricing || {};
  const free = FREE_MODELS.has(pr.model);
  const offerDesc = [known(pr.free_tier) && `Free tier: ${pr.free_tier}`, known(pr.paid_from) && `Paid from ${pr.paid_from}`].filter(Boolean).join(". ");
  const sameAs = [...new Set([clean(t.repo), clean(t.homepage), clean(pkg?.url)].filter(Boolean))];
  return {
    "@context": "https://schema.org", "@type": "SoftwareApplication", "@id": appId(id), name: page.name, description: page.description,
    url: page.url, inLanguage: page.lang, applicationCategory: "FinanceApplication", applicationSubCategory: TYPE_LABEL[t.type] ?? t.type,
    operatingSystem: "Cross-platform",
    ...(SPDX.has(t.license) ? { license: `https://spdx.org/licenses/${t.license}.html` } : {}),
    ...(clean(t.repo) ? { codeRepository: t.repo } : {}),
    ...(known(pkg?.version) ? { softwareVersion: pkg.version } : {}),
    ...(free ? { isAccessibleForFree: true, offers: { "@type": "Offer", price: "0", priceCurrency: "USD", ...(offerDesc ? { description: offerDesc } : {}), ...(clean(pr.source) ? { url: pr.source } : {}) } } : {}),
    ...(sameAs.length ? { sameAs } : {}),
    ...(v.checked_at ? { dateModified: String(v.checked_at).slice(0, 10) } : {}),
  };
}

// TechArticle for guide pages. Guides are not live yet: when a guide route ships, pass this (plus a BreadcrumbList and,
// only if the page renders visible Q&As, faqLd() from ./faq) to <Base jsonld={...}>. Dates come from the guide frontmatter.
export function techArticleLd(g: { url: string; headline: string; description: string; lang: string; datePublished: string; dateModified?: string; toolIds?: string[]; image?: string }) {
  return {
    "@context": "https://schema.org", "@type": "TechArticle", headline: g.headline, description: g.description, url: g.url,
    mainEntityOfPage: g.url, inLanguage: g.lang, datePublished: g.datePublished, dateModified: g.dateModified ?? g.datePublished,
    author: { "@id": ORG_ID }, publisher: { "@id": ORG_ID }, isPartOf: { "@id": WEBSITE_ID },
    image: g.image ?? `${SITE.url}/og/home.png`,
    ...(g.toolIds?.length ? { about: g.toolIds.filter((id) => rawById[id]).map((id) => ({ "@type": "SoftwareApplication", "@id": appId(id), name: rawById[id].name })) } : {}),
  };
}
