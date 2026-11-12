// JSON-LD builders shared by pages. Rules: real data only (no aggregateRating/review, no invented prices), and every
// outbound URL comes from RAW data/tools.json, never from data.ts (which runs URLs through affUrl() and adds aff_id).
import raw from "../../data/tools.json";
import { SITE } from "../config";
import { untagUrl } from "./aff";
import { TYPE_LABEL, pkgOf, verificationReport } from "./data";

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
  const v = t.verification || {}; const pkg = pkgOf(t); const pr = t.pricing || {};
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

export function articleLd(a: { url: string; headline: string; description: string; lang: string; datePublished: string; dateModified?: string; toolIds?: string[]; image?: string }) {
  return {
    "@context": "https://schema.org", "@type": "Article", headline: a.headline, description: a.description, url: a.url,
    mainEntityOfPage: a.url, inLanguage: a.lang, datePublished: a.datePublished, dateModified: a.dateModified ?? a.datePublished,
    author: { "@type": "Organization", name: "TradingAIHub Editorial", "@id": ORG_ID }, publisher: { "@id": ORG_ID }, isPartOf: { "@id": WEBSITE_ID },
    image: a.image ?? `${SITE.url}/og/home.png`,
    ...(a.toolIds?.length ? { about: a.toolIds.filter((id) => rawById[id]).map((id) => ({ "@type": "SoftwareApplication", "@id": appId(id), name: rawById[id].name })) } : {}),
  };
}

export function breadcrumbLd(items: { name: string; url: string }[]) {
  return { "@context": "https://schema.org", "@type": "BreadcrumbList", itemListElement: items.map((x, i) => ({ "@type": "ListItem", position: i + 1, name: x.name, item: x.url })) };
}

// Dataset for the weekly verification run. @id is per-run (date in the fragment) so one dataset is shared by
// /verification/ and /weekly/ (and their locale pages). Counts and the date come from verification-report.json.
export function datasetLd(page: { url: string; lang: string }) {
  const date = String(verificationReport.checked_at || "").slice(0, 10);
  const total = verificationReport.total;
  const verified = verificationReport.by_status?.verified ?? 0;
  return {
    "@context": "https://schema.org", "@type": "Dataset",
    "@id": `${SITE.url}/verification/#dataset-${date}`,
    name: `TradingAIHub weekly verification run, ${date}`,
    description: `Results of the weekly automated verification of every listed finance and trading AI tool: repository reachability, recent commits, package provenance, and whether homepage, docs and hosted MCP endpoints respond. Pricing is copied from each vendor's own pricing page. This run covers ${total} tools, ${verified} verified.`,
    url: page.url, inLanguage: page.lang,
    creator: { "@id": ORG_ID }, publisher: { "@id": ORG_ID }, isPartOf: { "@id": WEBSITE_ID },
    license: "https://creativecommons.org/licenses/by/4.0/",
    copyrightNotice: "TradingAIHub, https://tradingaihub.com",
    datePublished: date, dateModified: date, temporalCoverage: date,
    keywords: ["MCP", "finance", "trading", "verification", "AI tools"],
    variableMeasured: [
      "verification status", "repository reachability", "latest commit recency",
      "package provenance", "homepage and docs HTTP status",
    ],
    distribution: [
      { "@type": "DataDownload", encodingFormat: "application/json", contentUrl: `${SITE.url}/api/v1/tools.json` },
      { "@type": "DataDownload", encodingFormat: "application/json", contentUrl: `${SITE.url}/tools.json` },
    ],
  };
}

// Dataset for /audit/ (data licence: CC BY 4.0, attribution "TradingAIHub, https://tradingaihub.com").
// Separate from datasetLd() on /verification/ and /weekly/, which describes the weekly verification run.
export function auditDatasetLd(d: { name: string; description: string; url: string; lang: string; dateModified: string }) {
  return {
    "@context": "https://schema.org", "@type": "Dataset", name: d.name, description: d.description, url: d.url, inLanguage: d.lang,
    license: "https://creativecommons.org/licenses/by/4.0/", creator: { "@id": ORG_ID }, publisher: { "@id": ORG_ID },
    isAccessibleForFree: true, dateModified: d.dateModified, isPartOf: { "@id": WEBSITE_ID },
    variableMeasured: ["state", "registry", "package", "declared_repo"].map((n) => ({ "@type": "PropertyValue", name: n })),
    distribution: [
      { "@type": "DataDownload", encodingFormat: "application/json", contentUrl: `${SITE.url}/tools.json` },
      { "@type": "DataDownload", encodingFormat: "application/json", contentUrl: `${SITE.url}/api/v1/tools.json` },
    ],
  };
}
