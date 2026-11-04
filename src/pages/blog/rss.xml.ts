// /blog/rss.xml: published posts only (never drafts, even with BLOG_DRAFTS=1), newest first, full description + link.
import { SITE } from "../../config";
import { PUBLISHED, BYLINE, postUrl } from "../../lib/blog";
const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
export function GET() {
  const items = PUBLISHED.map((p) => `<item><title>${esc(p.title)}</title><link>${postUrl(p)}</link><guid isPermaLink="true">${postUrl(p)}</guid><pubDate>${new Date(`${p.date}T00:00:00Z`).toUTCString()}</pubDate><dc:creator>${esc(BYLINE)}</dc:creator>${p.tags.map((t) => `<category>${esc(t)}</category>`).join("")}<description>${esc(p.description)}</description></item>`).join("");
  const last = PUBLISHED.length ? `<lastBuildDate>${new Date(`${PUBLISHED.map((p) => p.updated).sort().at(-1)}T00:00:00Z`).toUTCString()}</lastBuildDate>` : "";
  return new Response(`<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><title>${esc(SITE.name)} Blog</title><link>${SITE.url}/blog/</link><atom:link href="${SITE.url}/blog/rss.xml" rel="self" type="application/rss+xml"/><description>Articles from ${esc(BYLINE)} on AI tools for finance and trading.</description><language>en</language>${last}${items}</channel></rss>`, { headers: { "content-type": "application/rss+xml" } });
}
