import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";
import { SITE } from "./src/config.ts";
import fs from "node:fs";
// Blog drafts (draft: true) and tag pages that only list drafts never go in the sitemap, even in a BLOG_DRAFTS=1 preview build.
const fmOf = (f) => fs.readFileSync(`src/content/blog/${f}`, "utf8").match(/^---\r?\n([\s\S]*?)\r?\n---/)?.[1] ?? "";
const BLOG = fs.existsSync("src/content/blog") ? fs.readdirSync("src/content/blog").filter((f) => /^[a-z0-9-]+\.md$/.test(f)).map((f) => { const fm = fmOf(f);
  return { slug: f.slice(0, -3), draft: /^draft:\s*true\s*$/m.test(fm), tags: (fm.match(/^tags:\s*\[(.*)\]\s*$/m)?.[1] ?? "").split(",").map((t) => t.trim().replace(/^["']|["']$/g, "")).filter(Boolean) }; }) : [];
const DRAFTS = BLOG.filter((p) => p.draft).map((p) => p.slug);
const LIVE_TAGS = new Set(BLOG.filter((p) => !p.draft).flatMap((p) => p.tags));
const CODES = ["en", "he", "es", "pt", "de", "fr", "ja", "ko", "zh", "hi", "tr", "ar", "ru"];
export default defineConfig({
  site: SITE.url, trailingSlash: "ignore", build: { format: "directory" },
  // Guide and blog Markdown (src/content/) renders code blocks as plain <pre><code> styled by global.css: no inline Shiki colours.
  markdown: { syntaxHighlight: false },
  integrations: [sitemap({
    filter: (p) => !/\/advertise\/$/.test(p) && !DRAFTS.some((d) => p.endsWith(`/blog/${d}/`)) && !(/\/blog\/tag\/([^/]+)\/$/.test(p) && !LIVE_TAGS.has(p.match(/\/blog\/tag\/([^/]+)\/$/)[1])),
    i18n: { defaultLocale: "en", locales: Object.fromEntries(CODES.map((c) => [c, c === "zh" ? "zh-CN" : c])) },
  })],
});
