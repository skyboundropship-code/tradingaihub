// Fails the build if:
//  - any TradingView link in dist/ lacks the affiliate ID or rel="sponsored noopener";
//  - a required partner CTA is missing (home page of every locale, every category page, tool pages in charting/market-data/crypto/quant categories);
//  - a partner CTA is not labelled or its TradingView link is not sponsored/affiliate-tagged.
import fs from "node:fs"; import path from "node:path";
const ID = "1173592"; let bad = 0, ok = 0, ctas = 0;
const CODES = ["en", "he", "es", "pt", "de", "fr", "ja", "ko", "zh", "hi", "tr", "ar", "ru"];
const PARTNER_CATS = ["market-data", "trading-brokers", "crypto", "quant-backtesting", "research-filings", "macro"];
const tools = JSON.parse(fs.readFileSync("data/tools.json", "utf8"));
const walk = (d) => fs.readdirSync(d, { withFileTypes: true }).flatMap((e) => e.isDirectory() ? walk(path.join(d, e.name)) : [path.join(d, e.name)]);
for (const f of walk("dist").filter((f) => f.endsWith(".html"))) {
  const html = fs.readFileSync(f, "utf8");
  for (const m of html.matchAll(/<a\b[^>]*href="(https?:\/\/(?:[\w-]+\.)*tradingview\.com[^"]*)"[^>]*>/g)) {
    if (m[1].includes("aff_id=" + ID) && /rel="sponsored noopener"/.test(m[0])) ok++; else { bad++; console.error("BAD link", f, m[0]); }
  }
}
const need = (file, variant) => {
  if (!fs.existsSync(file)) { bad++; console.error("MISSING page", file); return; }
  const html = fs.readFileSync(file, "utf8");
  const m = html.match(new RegExp(`<aside class="partner partner-${variant}"[\\s\\S]*?</aside>`));
  if (!m) { bad++; console.error(`MISSING ${variant} partner CTA`, file); return; }
  if (!/class="partner-tag"/.test(m[0]) || !/rel="sponsored noopener"/.test(m[0]) || !m[0].includes("aff_id=" + ID)) { bad++; console.error("BAD partner CTA", file); return; }
  ctas++;
};
for (const c of CODES) {
  const pre = c === "en" ? "dist" : `dist/${c}`;
  need(`${pre}/index.html`, "hero");
  for (const d of fs.readdirSync(`${pre}/category`)) need(`${pre}/category/${d}/index.html`, "tool");
  for (const t of tools.filter((t) => PARTNER_CATS.includes(t.category))) need(`${pre}/tools/${t.id}/index.html`, "tool");
}
console.log(`TradingView links: ${ok} ok, ${bad} bad; partner CTAs verified: ${ctas}`); process.exit(bad ? 1 : 0);
