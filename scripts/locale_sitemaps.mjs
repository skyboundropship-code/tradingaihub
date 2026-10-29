// Writes one sitemap per locale (dist/sitemap-<lang>.xml) with hreflang alternates, from the built HTML files.
import { existsSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";
const SITE = "https://tradingaihub.com";
const CODES = ["en", "he", "es", "pt", "de", "fr", "ja", "ko", "zh", "hi", "tr", "ar", "ru"];
const dist = "dist";
const walk = (d) => readdirSync(d).flatMap((f) => { const p = join(d, f); return statSync(p).isDirectory() ? walk(p) : [p]; });
const pages = walk(dist).filter((f) => f.endsWith("/index.html")).map((f) => "/" + f.slice(dist.length + 1).replace(/index\.html$/, ""))
  .filter((p) => !p.startsWith("/advertise/") && !/^\/[a-z]{2}\/advertise\//.test(p));
const base = new Set(pages.filter((p) => { const m = p.match(/^\/([a-z]{2})\//); return !(m && CODES.includes(m[1])); }));
const pathFor = (c, b) => (c === "en" ? b : `/${c}${b}`);
// A URL (and an hreflang alternate) is listed only for the locales where the page was actually built, so English-only
// pages (guides) appear once, in sitemap-en.xml, with no alternates pointing at translations that don't exist.
const built = (c, b) => existsSync(join(dist, pathFor(c, b).slice(1), "index.html"));
// <lastmod> only where the page states it (article:modified_time on guides and editorial pages), never a build date.
const lastmodOf = (c, b) => readFileSync(join(dist, pathFor(c, b).slice(1), "index.html"), "utf8").match(/<meta property="article:modified_time" content="(\d{4}-\d{2}-\d{2})"/)?.[1];
const counts = [];
for (const c of CODES) {
  const urls = [...base].sort().filter((b) => built(c, b)).map((b) => {
    const langs = CODES.filter((a) => built(a, b)), lm = lastmodOf(c, b);
    const alt = langs.length > 1 ? `${langs.map((a) => `<xhtml:link rel="alternate" hreflang="${a}" href="${SITE}${pathFor(a, b)}"/>`).join("")}<xhtml:link rel="alternate" hreflang="x-default" href="${SITE}${b}"/>` : "";
    return `<url><loc>${SITE}${pathFor(c, b)}</loc>${lm ? `<lastmod>${lm}</lastmod>` : ""}${alt}</url>`;
  });
  counts.push(`${c} ${urls.length}`);
  writeFileSync(join(dist, `sitemap-${c}.xml`), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n${urls.join("\n")}\n</urlset>\n`);
}
console.log(`locale sitemaps: ${CODES.length} files, ${base.size} English paths (${counts.join(", ")})`);
// sitemap-index.xml (and the sitemap.xml copy made in `build`) point at the 13 locale sitemaps, so robots.txt needs one
// Sitemap line. sitemap-0.xml (@astrojs/sitemap) leaves the index: every URL in it is already in each locale sitemap, so
// listing both would submit every URL twice. The file stays in dist for anything that fetched it directly.
const lastmod = new Date().toISOString().slice(0, 10);
const index = `<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${CODES.map((c) => `<sitemap><loc>${SITE}/sitemap-${c}.xml</loc><lastmod>${lastmod}</lastmod></sitemap>`).join("\n")}\n</sitemapindex>\n`;
writeFileSync(join(dist, "sitemap-index.xml"), index);
writeFileSync(join(dist, "sitemap.xml"), index);
console.log(`sitemap-index.xml + sitemap.xml -> ${CODES.length} locale sitemaps`);
