import { SITE } from "../config";
import { CODES } from "../i18n";
// Everything is allowed for every crawler. AI search/assistant crawlers get explicit groups so their operators
// see an unambiguous opt-in (a named group replaces "*" for that bot, so each one repeats Allow: /).
const AI_BOTS = ["GPTBot", "OAI-SearchBot", "ClaudeBot", "PerplexityBot", "Google-Extended"];
export function GET() {
  // One sitemap set only: the per-locale sitemaps (with hreflang alternates). sitemap-index.xml (-> sitemap-0.xml)
  // repeats the same URLs, so it is not listed here (it still exists for Search Console).
  const maps = [...new Set(CODES.map((c) => `${SITE.url}/sitemap-${c}.xml`))];
  const groups = [["*", ...AI_BOTS].map((ua) => `User-agent: ${ua}\nAllow: /`).join("\n\n")];
  return new Response(`${groups.join("\n\n")}\n\n${maps.map((m) => `Sitemap: ${m}`).join("\n")}\n`, { headers: { "content-type": "text/plain; charset=utf-8" } });
}
