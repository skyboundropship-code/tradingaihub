// Writes one sitemap per locale (dist/sitemap-<lang>.xml) with hreflang alternates, from the built HTML files.
import { readdirSync, readFileSync, statSync, unlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";
const SITE = "https://tradingaihub.com";
const CODES = ["en", "he", "es", "pt", "de", "fr", "ja", "ko", "zh", "hi", "tr", "ar", "ru"];
const dist = "dist";
const walk = (d) => readdirSync(d).flatMap((f) => { const p = join(d, f); return statSync(p).isDirectory() ? walk(p) : [p]; });
const pages = walk(dist).filter((f) => f.endsWith("/index.html")).map((f) => "/" + f.slice(dist.length + 1).replace(/index\.html$/, ""))
  .filter((p) => !p.startsWith("/advertise/") && !/^\/[a-z]{2}\/advertise\//.test(p));
const base = new Set(pages.filter((p) => { const m = p.match(/^\/([a-z]{2})\//); return !(m && CODES.includes(m[1])); }));
const pathFor = (c, b) => (c === "en" ? b : `/${c}${b}`);
const all = new Set();
for (const c of CODES) {
  for (const b of base) all.add(`${SITE}${pathFor(c, b)}`);
  const urls = [...base].sort().map((b) => `<url><loc>${SITE}${pathFor(c, b)}</loc>${CODES.map((a) => `<xhtml:link rel="alternate" hreflang="${a}" href="${SITE}${pathFor(a, b)}"/>`).join("")}<xhtml:link rel="alternate" hreflang="x-default" href="${SITE}${b}"/></url>`);
  writeFileSync(join(dist, `sitemap-${c}.xml`), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n${urls.join("\n")}\n</urlset>\n`);
}
console.log(`locale sitemaps: ${CODES.length} × ${base.size} URLs`);
// sitemap-index.xml (and sitemap.xml, a copy) point at the 13 locale sitemaps, so robots.txt needs one Sitemap line.
// @astrojs/sitemap's numbered sitemap-N.xml files are not in the index (they would submit every URL twice), so they are
// deleted here, but only after checking that every URL they list is in a locale sitemap (the build fails otherwise).
for (const f of readdirSync(dist).filter((f) => /^sitemap-\d+\.xml$/.test(f))) {
  const locs = [...readFileSync(join(dist, f), "utf8").matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
  const lost = locs.filter((u) => !all.has(u));
  if (lost.length) { console.error(`${f}: ${lost.length} URLs missing from the locale sitemaps, e.g. ${lost.slice(0, 3).join(" ")}`); process.exit(1); }
  unlinkSync(join(dist, f));
  console.log(`${f} removed: all ${locs.length} URLs are in the locale sitemaps (${all.size} total)`);
}
// <lastmod> = the newest verification date in data/tools.json (content date), not the build date, so it only moves
// when the data does. Omitted if no date is available.
let lastmod = "";
try {
  const dates = JSON.parse(readFileSync("data/tools.json", "utf8")).map((t) => String(t?.verification?.checked_at ?? "").slice(0, 10)).filter((d) => /^\d{4}-\d{2}-\d{2}$/.test(d));
  lastmod = dates.sort().at(-1) ?? "";
} catch {}
const lm = lastmod ? `<lastmod>${lastmod}</lastmod>` : "";
const index = `<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${CODES.map((c) => `<sitemap><loc>${SITE}/sitemap-${c}.xml</loc>${lm}</sitemap>`).join("\n")}\n</sitemapindex>\n`;
writeFileSync(join(dist, "sitemap-index.xml"), index);
writeFileSync(join(dist, "sitemap.xml"), index);
console.log(`sitemap-index.xml + sitemap.xml -> ${CODES.length} locale sitemaps (${all.size} URLs, lastmod ${lastmod || "omitted"})`);
