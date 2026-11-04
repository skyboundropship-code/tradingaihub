// Blog (English-only articles), loaded from Markdown in src/content/blog/<slug>.md. Adding a post = adding one file; the
// route, /blog/ index, tag pages, RSS (/blog/rss.xml), OG card, sitemap and llms.txt entry are all derived from it.
// See CONTRIBUTING-BLOG.md for the authoring steps.
//
// Frontmatter (validated here; the build fails on a bad value):
//   title        string, required (h1, <title>, RSS, cards)
//   description  string, required, max 160 chars (meta description, RSS description, cards; aim for ~155)
//   date         YYYY-MM-DD, required (datePublished)
//   updated      YYYY-MM-DD, optional (dateModified; defaults to date)
//   tags         string[], optional (lowercase words/hyphens; each gets /blog/tag/<tag>/)
//   draft        boolean, optional. true = not built at all in production: no page, not in the index, tags, RSS,
//                sitemap or llms.txt. Set BLOG_DRAFTS=1 at build time (preview deploys only) to render drafts as noindex
//                pages, listed on /blog/ with a "Draft" badge; they still stay out of RSS, sitemaps and llms.txt.
//   ogImage      optional path under public/ (e.g. /og/custom.png). Default: the generated card /og/blog-<slug>.png.
//   tools        optional tool ids (data/tools.json) for the "Tools mentioned" block
//   guides       optional guide slugs (src/content/guides/) for "Related guides"
// The byline is fixed: "TradingAIHub Editorial" (BYLINE). Authors don't set it.
//
// The Markdown body is post-processed at build time (same rules as the guides) so authors never hand-write affiliate markup:
//  - links to affiliate programs (src/config.ts AFFILIATES, via affUrl/isAff) get the tagged URL, rel="sponsored noopener" and
//    the visible Partner tag that scripts/check_aff.mjs requires, plus one affiliate note at the end of the post;
//  - other external links get rel="noopener" and open in a new tab; a raw affiliate parameter on a non-affiliate link fails;
//  - internal links must resolve to a page that exists, or the build fails.
import { tools, CATEGORIES, COMPARISONS } from "./data";
import { affUrl, isAff } from "./aff";
import { SITE } from "../config";

export const BYLINE = "TradingAIHub Editorial";
export const PER_PAGE = 20;
export const SHOW_DRAFTS = /^(1|true|yes)$/i.test(String(process.env.BLOG_DRAFTS ?? ""));

export type Post = {
  slug: string; title: string; description: string; date: string; updated: string; tags: string[]; draft: boolean;
  ogImage: string; tools: string[]; guides: string[]; mod: any;
};

const iso = (v: any, where: string, key: string) => {
  let s = v instanceof Date ? v.toISOString().slice(0, 10) : String(v ?? "");
  if (/^\d{4}-\d{2}-\d{2}T00:00:00(\.000)?Z$/.test(s)) s = s.slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s) || isNaN(Date.parse(`${s}T00:00:00Z`))) throw new Error(`${where}: frontmatter ${key} must be YYYY-MM-DD, got "${s}"`);
  return s;
};
const str = (fm: any, key: string, where: string) => {
  const v = fm[key]; if (typeof v !== "string" || !v.trim()) throw new Error(`${where}: frontmatter ${key} is required`); return v.trim();
};
const KNOWN = new Set(["title", "description", "date", "updated", "tags", "draft", "ogImage", "tools", "guides"]);
const toolIds = new Set(tools.map((t) => t.id));
const guideMods = import.meta.glob("../content/guides/*.md", { eager: true }) as Record<string, any>;
const guideSlugs = new Set(Object.keys(guideMods).map((f) => f.split("/").pop()!.slice(0, -3)));
export const guideTitle = (slug: string) => { const fm = guideMods[`../content/guides/${slug}.md`]?.frontmatter ?? {}; return String(fm.h1 ?? fm.title ?? slug); };

const mods = import.meta.glob("../content/blog/*.md", { eager: true }) as Record<string, any>;
/** Every post, drafts included, newest first. Use POSTS (what this build publishes) in pages. */
export const ALL_POSTS: Post[] = Object.entries(mods)
  .filter(([f]) => /\/[a-z0-9-]+\.md$/.test(f))
  .map(([f, mod]) => {
    const slug = f.split("/").pop()!.slice(0, -3), fm = mod.frontmatter ?? {}, where = `src/content/blog/${slug}.md`;
    const unknown = Object.keys(fm).filter((k) => !KNOWN.has(k)); if (unknown.length) throw new Error(`${where}: unknown frontmatter ${unknown.join(", ")} (author/byline is fixed)`);
    const tags = fm.tags ?? []; if (!Array.isArray(tags) || tags.some((t: any) => typeof t !== "string" || !/^[a-z0-9]+(-[a-z0-9]+)*$/.test(t))) throw new Error(`${where}: tags must be lowercase-hyphenated strings`);
    if (fm.draft != null && typeof fm.draft !== "boolean") throw new Error(`${where}: draft must be true or false`);
    const og = fm.ogImage == null ? `/og/blog-${slug}.png` : String(fm.ogImage);
    if (!/^\/[\w./-]+\.(png|jpe?g|webp)$/.test(og)) throw new Error(`${where}: ogImage must be a site path like /og/name.png`);
    const p: Post = {
      slug, title: str(fm, "title", where), description: str(fm, "description", where), date: iso(fm.date, where, "date"),
      updated: iso(fm.updated ?? fm.date, where, "updated"), tags: [...new Set(tags as string[])], draft: fm.draft === true, ogImage: og,
      tools: fm.tools ?? [], guides: fm.guides ?? [], mod,
    };
    if (p.description.length > 160) throw new Error(`${where}: description is ${p.description.length} chars (max 160)`);
    if (p.updated < p.date) throw new Error(`${where}: updated is before date`);
    const badTool = p.tools.filter((id) => !toolIds.has(id)); if (badTool.length) throw new Error(`${where}: unknown tool ids ${badTool.join(", ")}`);
    const badGuide = p.guides.filter((g) => !guideSlugs.has(g)); if (badGuide.length) throw new Error(`${where}: unknown guides ${badGuide.join(", ")}`);
    return p;
  })
  .sort((a, b) => b.date.localeCompare(a.date) || b.updated.localeCompare(a.updated) || a.slug.localeCompare(b.slug));
/** Posts this build renders as pages (drafts only with BLOG_DRAFTS=1). */
export const POSTS = ALL_POSTS.filter((p) => !p.draft || SHOW_DRAFTS);
/** Posts that are public: index-able, in RSS, sitemaps and llms.txt. Never drafts. */
export const PUBLISHED = ALL_POSTS.filter((p) => !p.draft);
export const TAGS = [...new Set(POSTS.flatMap((p) => p.tags))].sort();
export const pageCount = Math.max(1, Math.ceil(POSTS.length / PER_PAGE));
export const fmtDate = (d: string) => new Date(`${d}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
export const postUrl = (p: Post) => `${SITE.url}/blog/${p.slug}/`;

const STATIC = ["/", "/tools/", "/categories/", "/compare/", "/blog/", "/about/", "/disclaimer/", "/privacy/", "/terms/", "/weekly/", "/badges/", "/verification/", "/submit/", "/accessibility/", "/advertise/"];
const PAGES = new Set([
  ...STATIC, ...tools.map((t) => `/tools/${t.id}/`), ...CATEGORIES.map((c) => `/category/${c.slug}/`), ...COMPARISONS.map((c) => `/compare/${c.slug}/`),
  ...[...guideSlugs].map((g) => `/guides/${g}/`), ...(guideSlugs.size ? ["/guides/"] : []), ...PUBLISHED.map((p) => `/blog/${p.slug}/`),
]);

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
const decode = (s: string) => s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#x27;|&#39;/g, "'").replace(/&nbsp;/g, " ").replace(/&amp;/g, "&");
const PARTNER = `<span class="partner-tag">Partner</span>`;
export const AFF_NOTE = `<p class="note aff-note">Partner links are labelled: we may earn a commission at no extra cost to you. It never affects listings or verification status.</p>`;

/** Render a post's Markdown to HTML with link rules applied; returns html, toc (h2/h3) and whether it has partner links. */
export async function render(p: Post) {
  const where = `src/content/blog/${p.slug}.md`;
  let html: string = await p.mod.compiledContent();
  html = html.replace(/^\s*<h1\b[^>]*>[\s\S]*?<\/h1>\s*/, "");
  if (/<h1\b/.test(html)) throw new Error(`${where}: use ## for sections; the title is the only h1`);
  let partner = false;
  html = html.replace(/<a href="([^"]*)"([^>]*)>([\s\S]*?)<\/a>/g, (_m, href: string, rest: string, inner: string) => {
    const raw = decode(href);
    if (/^(https?:)?\/\//.test(raw)) {
      if (/^http:/.test(raw)) throw new Error(`${where}: use https links: ${raw}`);
      if (/\brel=/.test(rest)) throw new Error(`${where}: write plain Markdown links, not raw <a rel>: ${raw}`);
      if (isAff(raw)) { partner = true; return `<a href="${esc(affUrl(raw)!)}"${rest} target="_blank" rel="sponsored noopener">${inner}</a> ${PARTNER}`; }
      if (/[?&](aff_id|via|_go|ref)=/.test(raw)) throw new Error(`${where}: affiliate-looking parameter on a non-affiliate link: ${raw}`);
      return `<a href="${href}"${rest} target="_blank" rel="noopener">${inner}</a>`;
    }
    if (raw.startsWith("/")) {
      const path = raw.split("#")[0].split("?")[0];
      if (!PAGES.has(path)) throw new Error(`${where}: internal link to a page that doesn't exist: ${raw}`);
    } else if (!raw.startsWith("#") && !raw.startsWith("mailto:")) throw new Error(`${where}: unsupported link ${raw}`);
    return `<a href="${href}"${rest}>${inner}</a>`;
  });
  if (/<a\b(?![^>]*href=")/.test(html)) throw new Error(`${where}: raw <a> without href`);
  html = html.replace(/<table>/g, `<div class="tablewrap"><table>`).replace(/<\/table>/g, "</table></div>");
  const toc = (p.mod.getHeadings?.() ?? []).filter((h: any) => h.depth === 2 || h.depth === 3).map((h: any) => ({ depth: h.depth, slug: h.slug, text: h.text }));
  const words = decode(html.replace(/<[^>]+>/g, " ")).split(/\s+/).filter(Boolean).length;
  return { html, toc, partner, words, minutes: Math.max(1, Math.round(words / 220)) };
}

/** BlogPosting JSON-LD. URLs are internal or the OG image, so no affiliate parameter can reach it. */
export function blogPostingLd(p: Post) {
  const url = postUrl(p);
  return {
    "@context": "https://schema.org", "@type": "BlogPosting", headline: p.title, description: p.description, url, mainEntityOfPage: { "@type": "WebPage", "@id": url },
    inLanguage: "en", datePublished: p.date, dateModified: p.updated,
    author: { "@type": "Organization", name: BYLINE, url: `${SITE.url}/about/` },
    publisher: { "@id": `${SITE.url}/#organization` }, isPartOf: { "@type": "Blog", "@id": `${SITE.url}/blog/#blog`, name: `${SITE.name} Blog` },
    image: new URL(p.ogImage, SITE.url).href, ...(p.tags.length ? { keywords: p.tags.join(", ") } : {}),
  };
}
export const crumbsLd = (items: [string, string][]) => ({ "@context": "https://schema.org", "@type": "BreadcrumbList",
  itemListElement: items.map(([name, path], i) => ({ "@type": "ListItem", position: i + 1, name, item: `${SITE.url}${path}` })) });
