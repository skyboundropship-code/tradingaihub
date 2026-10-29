import { SITE } from "../config";
import { changelog } from "../lib/data";
const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
export function GET() {
  const items = changelog.map((w) => `<item><title>${esc(`State of finance AI tools — ${w.date}`)}</title><link>${SITE.url}/weekly/</link><guid isPermaLink="false">weekly-${w.date}</guid><pubDate>${new Date(w.date).toUTCString()}</pubDate><description>${esc(w.changes.map((c: any) => c.text).join(" • "))}</description></item>`).join("");
  return new Response(`<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>${esc(SITE.name)} weekly</title><link>${SITE.url}</link><description>${esc(SITE.tagline)}</description>${items}</channel></rss>`, { headers: { "content-type": "application/rss+xml" } });
}
