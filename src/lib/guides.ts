// Guides (English-only editorial pages) and editorial copy for comparison pages, loaded from Markdown in src/content/.
// Adding a guide = adding one file: src/content/guides/<slug>.md with the frontmatter below. Files starting with "_" are
// ignored (drafts/templates). Everything else (route, /guides/ index, OG card, sitemap, llms.txt, "Guides featuring this
// tool" on tool pages) is derived from that file.
//
// Frontmatter: title (<title>), description (meta, max 160 chars), h1, summary (cards + llms.txt), datePublished,
// dateModified (YYYY-MM-DD, the date facts were last checked), tools (tool ids from data/tools.json), compare
// (comparison slugs), tv_cta (charts | crypto | backtest | plans | none).
//
// The Markdown body is post-processed at build time so editors never hand-write affiliate markup:
//  - links to affiliate programs (TradingView, EODHD tracked paths) go through affUrl() and get rel="sponsored noopener"
//    plus the visible Partner tag that scripts/check_aff.mjs requires; untracked EODHD pages stay plain;
//  - other external links get rel="noopener" and open in a new tab;
//  - internal links must resolve to a page that exists (tool ids, categories, comparisons, guides, static pages) or the
//    build fails, so a guide can never link to a missing tool page;
//  - "## FAQ" (### question + answer paragraphs) becomes the site's FAQ markup and feeds the FAQPage JSON-LD;
//  - <!-- partner-cta --> marks where the single labelled TradingView block goes (never inside setup steps);
//  - <!-- auto-table --> (comparison editorial only) marks where the live tools.json table is rendered.
import { tools, CATEGORIES, COMPARISONS } from "./data";
import { affUrl, isAff, tvUrl } from "./aff";
import type { QA } from "./faq";

export type Guide = {
  slug: string; title: string; description: string; h1: string; summary: string;
  datePublished: string; dateModified: string; tools: string[]; compare: string[]; tv_cta: string; mod: any;
};
export type Rendered = { parts: string[]; faq: QA[] };

const iso = (v: any, where: string, key: string) => {
  // YAML turns a bare 2026-10-29 into a Date, which Astro may hand over as its ISO string: accept either, keep the day.
  let s = v instanceof Date ? v.toISOString().slice(0, 10) : String(v ?? "");
  if (/^\d{4}-\d{2}-\d{2}T00:00:00(\.000)?Z$/.test(s)) s = s.slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) throw new Error(`${where}: frontmatter ${key} must be YYYY-MM-DD, got "${s}"`);
  return s;
};
const str = (fm: any, key: string, where: string) => {
  const v = fm[key]; if (typeof v !== "string" || !v.trim()) throw new Error(`${where}: frontmatter ${key} is required`); return v.trim();
};
const TV_CTA = ["charts", "crypto", "backtest", "plans", "none"];
const toolIds = new Set(tools.map((t) => t.id));
const compSlugs = new Set(COMPARISONS.map((c) => c.slug));

const guideMods = import.meta.glob("../content/guides/*.md", { eager: true }) as Record<string, any>;
export const GUIDES: Guide[] = Object.entries(guideMods)
  .filter(([f]) => /\/[a-z0-9-]+\.md$/.test(f))
  .map(([f, mod]) => {
    const slug = f.split("/").pop()!.slice(0, -3), fm = mod.frontmatter ?? {}, where = `src/content/guides/${slug}.md`;
    const g: Guide = {
      slug, title: str(fm, "title", where), description: str(fm, "description", where), h1: str(fm, "h1", where), summary: str(fm, "summary", where),
      datePublished: iso(fm.datePublished, where, "datePublished"), dateModified: iso(fm.dateModified ?? fm.datePublished, where, "dateModified"),
      tools: fm.tools ?? [], compare: fm.compare ?? [], tv_cta: fm.tv_cta ?? "charts", mod,
    };
    if (g.description.length > 160) throw new Error(`${where}: description is ${g.description.length} chars (max 160)`);
    const badTool = g.tools.filter((id) => !toolIds.has(id)); if (badTool.length) throw new Error(`${where}: unknown tool ids ${badTool.join(", ")}`);
    const badCmp = g.compare.filter((s) => !compSlugs.has(s)); if (badCmp.length) throw new Error(`${where}: unknown comparisons ${badCmp.join(", ")}`);
    if (!TV_CTA.includes(g.tv_cta)) throw new Error(`${where}: tv_cta must be one of ${TV_CTA.join(", ")}`);
    return g;
  })
  .sort((a, b) => b.dateModified.localeCompare(a.dateModified) || a.slug.localeCompare(b.slug));
export const guidesForTool = (id: string) => GUIDES.filter((g) => g.tools.includes(id));

const compareMods = import.meta.glob("../content/compare/*.md", { eager: true }) as Record<string, any>;
export const compareEditorial = (slug: string) => {
  const mod = compareMods[`../content/compare/${slug}.md`]; if (!mod) return null;
  if (!compSlugs.has(slug)) throw new Error(`src/content/compare/${slug}.md: no comparison with that slug`);
  const fm = mod.frontmatter ?? {}, where = `src/content/compare/${slug}.md`;
  return { mod, title: str(fm, "title", where), description: str(fm, "description", where), h1: str(fm, "h1", where),
    datePublished: iso(fm.datePublished, where, "datePublished"), dateModified: iso(fm.dateModified ?? fm.datePublished, where, "dateModified") };
};

// Pages that exist in every build (English paths). Tool, category, comparison and guide pages are added from data.
const STATIC = ["/", "/tools/", "/categories/", "/compare/", "/guides/", "/about/", "/disclaimer/", "/privacy/", "/terms/", "/weekly/", "/badges/", "/verification/", "/submit/", "/accessibility/"];
const PAGES = new Set([
  ...STATIC, ...tools.map((t) => `/tools/${t.id}/`), ...CATEGORIES.map((c) => `/category/${c.slug}/`),
  ...COMPARISONS.map((c) => `/compare/${c.slug}/`), ...Object.keys(guideMods).map((f) => `/guides/${f.split("/").pop()!.slice(0, -3)}/`),
]);

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
const decode = (s: string) => s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#x27;|&#39;/g, "'").replace(/&nbsp;/g, " ").replace(/&amp;/g, "&");
const text = (html: string) => decode(html.replace(/<[^>]+>/g, "")).replace(/\s+/g, " ").trim();
const PARTNER = `<span class="partner-tag">Partner</span>`;

const CTA: Record<string, { path: string; title: string; body: string; btn: string }> = {
  charts: { path: "/chart/", title: "Chart it on TradingView", body: "Check the numbers your assistant pulls against a live chart. TradingView's Basic plan is free.", btn: "Open TradingView charts ↗" },
  crypto: { path: "/markets/cryptocurrencies/", title: "Charting crypto?", body: "TradingView charts thousands of crypto pairs across exchanges, and its Basic plan is free.", btn: "Open TradingView crypto ↗" },
  backtest: { path: "/pine-script-docs/", title: "Sanity-check a strategy visually", body: "TradingView's Pine Script editor and Strategy Tester are a quick way to eyeball an idea before you wire it into an agent. The Basic plan is free.", btn: "Open Pine Script docs ↗" },
  plans: { path: "/pricing/", title: "Compare TradingView plans", body: "The official TradingView MCP server needs Essential or higher, and trial plans don't include MCP access. Prices vary by region and promotion.", btn: "See TradingView plans ↗" },
};
/** The one labelled partner block per guide (English). check_aff accepts it because it is a partner <aside> with a Partner tag. */
export const ctaHtml = (kind: string) => {
  const c = CTA[kind]; if (!c) return "";
  return `<aside class="partner partner-guide panel" aria-label="Partner"><p><b>${esc(c.title)}</b> ${PARTNER}</p><p>${esc(c.body)}</p>`
    + `<p><a class="btn" href="${esc(tvUrl(c.path))}" target="_blank" rel="sponsored noopener">${esc(c.btn)}</a></p>`
    + `<p class="note">Partner link: we may earn a commission at no extra cost to you. It never affects listings.</p></aside>`;
};

/** Render a content module's Markdown to HTML parts (split on <!-- auto-table -->) with links, FAQ and CTA processed. */
export async function render(mod: any, where: string, cta = "none"): Promise<Rendered> {
  let html: string = await mod.compiledContent();
  html = html.replace(/^\s*<h1\b[^>]*>[\s\S]*?<\/h1>\s*/, "");
  html = html.replace(/<a href="([^"]*)"([^>]*)>([\s\S]*?)<\/a>/g, (_m, href: string, rest: string, inner: string) => {
    const raw = decode(href);
    if (/^(https?:)?\/\//.test(raw)) {
      if (/\brel=/.test(rest)) throw new Error(`${where}: write plain Markdown links, not raw <a rel>: ${raw}`);
      if (isAff(raw)) return `<a href="${esc(affUrl(raw)!)}"${rest} target="_blank" rel="sponsored noopener">${inner}</a> ${PARTNER}`;
      if (/[?&](aff_id|via)=/.test(raw)) throw new Error(`${where}: affiliate parameter on a non-affiliate link: ${raw}`);
      return `<a href="${href}"${rest} target="_blank" rel="noopener">${inner}</a>`;
    }
    if (raw.startsWith("/")) {
      const path = raw.split("#")[0].split("?")[0];
      if (!PAGES.has(path)) throw new Error(`${where}: internal link to a page that doesn't exist: ${raw}`);
    } else if (!raw.startsWith("#") && !raw.startsWith("mailto:")) throw new Error(`${where}: unsupported link ${raw}`);
    return `<a href="${href}"${rest}>${inner}</a>`;
  });
  html = html.replace(/<table>/g, `<div class="tablewrap"><table>`).replace(/<\/table>/g, "</table></div>");
  // FAQ: "## FAQ" up to the next h2 -> visible FAQ markup + the same Q&A for FAQPage JSON-LD.
  const faq: QA[] = [];
  html = html.replace(/<h2 id="faq">FAQ<\/h2>([\s\S]*?)(?=<h2\b|$)/, (_m, sec: string) => {
    const items = [...sec.matchAll(/<h3\b[^>]*>([\s\S]*?)<\/h3>([\s\S]*?)(?=<h3\b|$)/g)].map((x) => ({ q: x[1].trim(), a: x[2].trim() }));
    if (!items.length) throw new Error(`${where}: "## FAQ" has no "### question" entries`);
    for (const it of items) faq.push({ q: text(it.q), a: text(it.a) });
    return `<section class="faq" aria-labelledby="faq"><h2 class="sec" id="faq">FAQ</h2><div class="faq-list">${items.map((it) => `<div class="faq-item"><h3>${it.q}</h3>${it.a}</div>`).join("")}</div></section>\n`;
  });
  const marker = /<!--\s*partner-cta\s*-->/;
  if (cta !== "none") html = marker.test(html) ? html.replace(marker, ctaHtml(cta)) : html + ctaHtml(cta);
  else html = html.replace(marker, "");
  if (/aff_id=|via=/.test(html.replace(/<a [^>]*rel="sponsored noopener"[^>]*>/g, "").replace(/<aside class="partner[\s\S]*?<\/aside>/g, "")))
    throw new Error(`${where}: affiliate parameter outside a labelled partner link`);
  return { parts: html.split(/<!--\s*auto-table\s*-->/), faq };
}
