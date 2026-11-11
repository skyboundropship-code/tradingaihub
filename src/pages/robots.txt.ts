import { SITE } from "../config";
// Everything is allowed for every crawler. AI search/assistant crawlers and AI-use control tokens get explicit groups so their
// operators see an unambiguous opt-in. A crawler obeys only the most specific group that matches it, so every named group
// repeats the full rule set: if a Disallow is ever added under "*", add it to every named group too.
// Names checked against official operator docs where they exist, otherwise the maintained list at
// https://github.com/ai-robots-txt/ai.robots.txt (fetched 2026-11-10). No xAI/Grok token is included:
// xAI has not published a crawler user-agent.
const AI_BOTS = [
  "GPTBot", "OAI-SearchBot", "ChatGPT-User", // OpenAI: training, ChatGPT search index, user-initiated fetches
  "ClaudeBot", "Claude-SearchBot", "Claude-User", // Anthropic: training, search index, user-initiated fetches
  "anthropic-ai", "Claude-Web", // legacy Anthropic tokens still listed by ai-robots-txt
  "PerplexityBot", "Perplexity-User", // Perplexity: search index, user-initiated fetches
  "Google-Extended", "Applebot-Extended", // control tokens (not crawlers) for Gemini / Apple Intelligence use of fetched content
  "Applebot", // Apple search crawler (distinct from the Applebot-Extended control token)
  "GoogleOther", "Google-CloudVertexBot", // Google other fetchers / Vertex AI grounding
  "Bingbot", // Bing index, which also feeds Copilot and ChatGPT search
  "Meta-ExternalAgent", "Meta-ExternalFetcher", "FacebookBot", // Meta AI + Facebook crawler
  "Amazonbot", "DuckAssistBot", // Amazon crawler / DuckDuckGo assistant
  "MistralAI-User", "cohere-ai", "cohere-training-data-crawler",
  "YouBot", "PhindBot", "Kagibot", "CCBot", // You.com, Phind, Kagi search (official UA at kagi.com/bot), Common Crawl
  "Diffbot", "Timpibot", "iaskspider", "AI2Bot", "PetalBot",
];
export function GET() {
  // One entry point: sitemap-index.xml lists the 13 per-locale sitemaps (hreflang alternates); see scripts/locale_sitemaps.mjs.
  const groups = ["*", ...AI_BOTS].map((ua) => `User-agent: ${ua}\nAllow: /`).join("\n\n");
  return new Response(
    `# Machine-readable site index: ${SITE.url}/llms.txt\n\n${groups}\n\nSitemap: ${SITE.url}/sitemap-index.xml\n`,
    { headers: { "content-type": "text/plain; charset=utf-8" } },
  );
}
