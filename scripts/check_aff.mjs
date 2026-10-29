// Fails the build if:
//  - any TradingView link in dist/ lacks the affiliate ID or rel="sponsored noopener";
//  - a required partner CTA is missing (home page of every locale, every category page, tool pages in charting/market-data/crypto/quant categories);
//  - a partner CTA is not labelled or its TradingView link is not sponsored/affiliate-tagged.
//  - any EODHD link to eodhd.com / www.eodhd.com (also protocol-relative or with a trailing dot) in dist/ lacks exactly one
//    via=tradingaihub or rel="sponsored noopener"; any other *.eodhd.com link (api., mcp.) carries via=;
//  - any affiliate link (TradingView or EODHD) has no visible "Partner" tag: either inside a partner <aside> or a
//    <span class="partner-tag"> right after the link;
//  - any Partner tag's text differs from the page locale's partner.label.
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
// EODHD affiliate (via=tradingaihub): every outbound eodhd.com link must be tagged and sponsored.
const EODHD_VIA = "tradingaihub"; let eok = 0, ebad = 0;
for (const f of walk("dist").filter((f) => f.endsWith(".html"))) {
  const html = fs.readFileSync(f, "utf8");
  for (const m of html.matchAll(/<a\b[^>]*href="((?:https?:)?\/\/(?:[\w-]+\.)*eodhd\.com\.?(?=[\/:?#"])[^"]*)"[^>]*>/gi)) {
    let u = null; try { u = new URL(m[1].replace(/&amp;/g, "&"), "https://x/"); } catch {}
    const host = u ? u.hostname.toLowerCase().replace(/\.$/, "") : "", via = u ? u.searchParams.getAll("via") : [];
    const vendor = host === "eodhd.com" || host === "www.eodhd.com";
    const good = vendor ? via.length === 1 && via[0] === EODHD_VIA && /rel="sponsored noopener"/.test(m[0]) : u && via.length === 0;
    if (good) eok++; else { ebad++; console.error(vendor ? "BAD EODHD link" : "BAD EODHD API/MCP link (must not be tagged)", f, m[0]); }
  }
}
console.log(`EODHD links: ${eok} ok, ${ebad} bad`);
// Every affiliate anchor needs a visible "Partner" tag: in a partner <aside> (CTA) or a partner-tag span right after </a>.
let lok = 0, lbad = 0;
for (const f of walk("dist").filter((f) => f.endsWith(".html"))) {
  const html = fs.readFileSync(f, "utf8");
  for (const m of html.matchAll(/<a\b[^>]*href="((?:https?:)?\/\/[^"]+)"[^>]*>[\s\S]*?<\/a>/g)) {
    let u = null; try { u = new URL(m[1].replace(/&amp;/g, "&"), "https://x/"); } catch { continue; }
    const host = u.hostname.toLowerCase().replace(/\.$/, "");
    const aff = ((host === "tradingview.com" || host.endsWith(".tradingview.com")) && u.searchParams.get("aff_id") === ID) || ((host === "eodhd.com" || host === "www.eodhd.com") && u.searchParams.has("via"));
    if (!aff) continue;
    const before = html.slice(0, m.index), open = before.lastIndexOf("<aside"), close = before.lastIndexOf("</aside>");
    const asideTag = open > close ? before.slice(open, before.indexOf(">", open) + 1) : "";
    const asideEnd = open > close ? html.indexOf("</aside>", m.index) : -1;
    const inPartnerAside = /class="partner\b/.test(asideTag) && html.slice(open, asideEnd).includes('class="partner-tag"');
    const tagAfter = /^\s*<span class="partner-tag"[^>]*>[^<]+<\/span>/.test(html.slice(m.index + m[0].length, m.index + m[0].length + 400));
    if (inPartnerAside || tagAfter) lok++; else { lbad++; console.error("UNLABELLED affiliate link", f, m[0].slice(0, 200)); }
  }
}
console.log(`Affiliate labels: ${lok} ok, ${lbad} missing`);
// Every Partner tag's text must be exactly the page locale's partner.label (empty or other words like "Featured" fail).
const LABEL = Object.fromEntries(CODES.map((c) => [c, JSON.parse(fs.readFileSync(`src/i18n/${c}.json`, "utf8")).partner.label]));
let tok = 0, tbad = 0;
for (const f of walk("dist").filter((f) => f.endsWith(".html"))) {
  const seg = path.relative("dist", f).split(path.sep)[0], lang = CODES.includes(seg) ? seg : "en";
  for (const m of fs.readFileSync(f, "utf8").matchAll(/<span class="partner-tag"[^>]*>([\s\S]*?)<\/span>/g)) {
    if (m[1].trim() === LABEL[lang]) tok++; else { tbad++; console.error(`WRONG Partner tag text (want "${LABEL[lang]}")`, f, JSON.stringify(m[1])); }
  }
}
console.log(`Partner tag text: ${tok} ok, ${tbad} wrong`);
console.log(`TradingView links: ${ok} ok, ${bad} bad; partner CTAs verified: ${ctas}`); process.exit(bad || ebad || lbad || tbad ? 1 : 0);
