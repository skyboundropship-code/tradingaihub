import { SITE } from "../config";
// Everything is allowed for every crawler. AI search/assistant crawlers and AI-use control tokens get explicit groups so their
// operators see an unambiguous opt-in. A crawler obeys only the most specific group that matches it, so every named group
// repeats the full rule set: if a Disallow is ever added under "*", add it to every named group too.
const AI_BOTS = [
  "GPTBot", "OAI-SearchBot", "ChatGPT-User", // OpenAI: training, ChatGPT search index, user-initiated fetches
  "ClaudeBot", "Claude-SearchBot", "Claude-User", // Anthropic: training, search index, user-initiated fetches
  "PerplexityBot", "Perplexity-User", // Perplexity: search index, user-initiated fetches
  "Google-Extended", "Applebot-Extended", // control tokens (not crawlers) for Gemini / Apple Intelligence use of fetched content
  "Bingbot", // Bing index, which also feeds Copilot and ChatGPT search
];
export function GET() {
  // One entry point: sitemap-index.xml lists the 13 per-locale sitemaps (hreflang alternates); see scripts/locale_sitemaps.mjs.
  const groups = ["*", ...AI_BOTS].map((ua) => `User-agent: ${ua}\nAllow: /`).join("\n\n");
  return new Response(`${groups}\n\nSitemap: ${SITE.url}/sitemap-index.xml\n`, { headers: { "content-type": "text/plain; charset=utf-8" } });
}
