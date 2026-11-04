import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";
import { SITE } from "./src/config.ts";
const CODES = ["en", "he", "es", "pt", "de", "fr", "ja", "ko", "zh", "hi", "tr", "ar", "ru"];
export default defineConfig({
  site: SITE.url, trailingSlash: "ignore", build: { format: "directory" },
  // Guide Markdown (src/content/) renders code blocks as plain <pre><code> styled by global.css: no inline Shiki colours.
  markdown: { syntaxHighlight: false },
  integrations: [sitemap({
    filter: (p) => !/\/advertise\/$/.test(p),
    i18n: { defaultLocale: "en", locales: Object.fromEntries(CODES.map((c) => [c, c === "zh" ? "zh-CN" : c])) },
  })],
});
