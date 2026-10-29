// Fails the build if:
//  - any TradingView link in dist/ lacks the affiliate ID or rel="sponsored noopener";
//  - a required partner CTA is missing (home page of every locale, every category page, tool pages in charting/market-data/crypto/quant categories);
//  - a partner CTA is not labelled or its TradingView link is not sponsored/affiliate-tagged.
//  - any EODHD link to a tracked path (AFFILIATES.eodhd.paths) on eodhd.com / www.eodhd.com (also protocol-relative or with
//    a trailing dot) lacks exactly one via=tradingaihub or rel="sponsored noopener"; any untracked EODHD path has via=,
//    rel sponsored or a Partner tag; any other *.eodhd.com link (api., mcp.) carries via=;
//  - any affiliate link (TradingView or EODHD) has no visible "Partner" tag: either inside a partner <aside> or a
//    <span class="partner-tag"> right after the link;
//  - any Partner tag is hidden, its text differs from the page locale's partner.label, or it sits on a non-affiliate link.
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
// EODHD affiliate (via=tradingaihub): links to tracked paths (AFFILIATES.eodhd.paths in src/config.ts: pages proven to load
// promotekit.js) must carry exactly one via=tradingaihub and rel="sponsored noopener"; every other EODHD link must be plain
// (no via, no rel sponsored, no Partner tag), and api./mcp. links are never tagged.
const EODHD_VIA = "tradingaihub"; let eok = 0, ebad = 0, etag = 0, eplain = 0;
const EODHD_PATHS = (() => {
  const m = fs.readFileSync("src/config.ts", "utf8").match(/\beodhd:\s*\{[^}]*\bpaths:\s*(\[[^\]]*\])/);
  if (!m) { console.error("check_aff: AFFILIATES.eodhd.paths not found in src/config.ts"); process.exit(1); }
  return JSON.parse(m[1]);
})();
const TAG_RE = /<span\b[^>]*\bclass="[^"]*\bpartner-tag\b[^"]*"[^>]*>([\s\S]*?)<\/span>/g;
const parse = (href) => { try { return new URL(href.replace(/&amp;/g, "&"), "https://x/"); } catch { return null; } };
const normHost = (u) => u.hostname.toLowerCase().replace(/\.$/, "");
const isEodhdVendor = (u) => ["eodhd.com", "www.eodhd.com"].includes(normHost(u));
// An affiliate link as the site defines it: TradingView with our aff_id, or an EODHD tracked path with via.
const isAffHref = (href) => {
  const u = /^(?:https?:)?\/\//.test(href) ? parse(href) : null; if (!u) return false; const h = normHost(u);
  return ((h === "tradingview.com" || h.endsWith(".tradingview.com")) && u.searchParams.get("aff_id") === ID)
    || (isEodhdVendor(u) && EODHD_PATHS.includes(u.pathname) && u.searchParams.has("via"));
};
for (const f of walk("dist").filter((f) => f.endsWith(".html"))) {
  const html = fs.readFileSync(f, "utf8");
  for (const m of html.matchAll(/<a\b[^>]*href="((?:https?:)?\/\/(?:[\w-]+\.)*eodhd\.com\.?(?=[\/:?#"])[^"]*)"[^>]*>/gi)) {
    const u = parse(m[1]), via = u ? u.searchParams.getAll("via") : [], vendor = !!u && isEodhdVendor(u);
    const trackedPath = vendor && EODHD_PATHS.includes(u.pathname);
    const close = html.indexOf("</a>", m.index);
    const tagAfter = close >= 0 && /^<\/a>\s*<span\b[^>]*\bpartner-tag\b/.test(html.slice(close, close + 300));
    const good = trackedPath ? via.length === 1 && via[0] === EODHD_VIA && /rel="sponsored noopener"/.test(m[0])
      : !!u && via.length === 0 && !/\bsponsored\b/.test(m[0]) && !tagAfter;
    if (good) { eok++; if (trackedPath) etag++; else eplain++; }
    else { ebad++; console.error(trackedPath ? "BAD EODHD link (tracked path needs exactly one via=tradingaihub + rel sponsored)" : vendor ? "BAD EODHD link (untracked path must be plain: no via, no sponsored, no Partner tag)" : "BAD EODHD API/MCP link (must not be tagged)", f, m[0]); }
  }
}
console.log(`EODHD links: ${eok} ok (${etag} tagged on ${EODHD_PATHS.join(", ")}; ${eplain} plain), ${ebad} bad`);
// Every affiliate anchor needs a visible "Partner" tag: in a partner <aside> (CTA) or a partner-tag span right after </a>.
let lok = 0, lbad = 0;
for (const f of walk("dist").filter((f) => f.endsWith(".html"))) {
  const html = fs.readFileSync(f, "utf8");
  for (const m of html.matchAll(/<a\b[^>]*href="((?:https?:)?\/\/[^"]+)"[^>]*>[\s\S]*?<\/a>/g)) {
    if (!isAffHref(m[1])) continue;
    const before = html.slice(0, m.index), open = before.lastIndexOf("<aside"), close = before.lastIndexOf("</aside>");
    const asideTag = open > close ? before.slice(open, before.indexOf(">", open) + 1) : "";
    const asideEnd = open > close ? html.indexOf("</aside>", m.index) : -1;
    const inPartnerAside = /class="partner\b/.test(asideTag) && /\bpartner-tag\b/.test(html.slice(open, asideEnd));
    const tagAfter = /^\s*<span\b[^>]*\bpartner-tag\b[^>]*>\s*\S[^<]*<\/span>/.test(html.slice(m.index + m[0].length, m.index + m[0].length + 400));
    if (inPartnerAside || tagAfter) lok++; else { lbad++; console.error("UNLABELLED affiliate link", f, m[0].slice(0, 200)); }
  }
}
console.log(`Affiliate labels: ${lok} ok, ${lbad} missing`);
// Every Partner tag must be visible, read exactly the page locale's partner.label (empty, whitespace-only or other words like
// "Featured" fail), and belong to an affiliate link: right after one, or in a partner <aside> that contains one.
const LABEL = Object.fromEntries(CODES.map((c) => [c, JSON.parse(fs.readFileSync(`src/i18n/${c}.json`, "utf8")).partner.label]));
const HIDDEN = /\shidden(?=[\s>=])|aria-hidden="true"|\bsr-only\b|\bvisually-hidden\b|display\s*:\s*none|visibility\s*:\s*hidden/i;
let tok = 0, tbad = 0, orphan = 0;
for (const f of walk("dist").filter((f) => f.endsWith(".html"))) {
  const seg = path.relative("dist", f).split(path.sep)[0], lang = CODES.includes(seg) ? seg : "en";
  const html = fs.readFileSync(f, "utf8");
  for (const m of html.matchAll(TAG_RE)) {
    const openTag = m[0].slice(0, m[0].indexOf(">") + 1);
    if (m[1].trim() !== LABEL[lang] || HIDDEN.test(openTag)) { tbad++; console.error(`WRONG Partner tag (want visible "${LABEL[lang]}")`, f, JSON.stringify(m[0])); continue; }
    tok++;
    const before = html.slice(0, m.index); let attached = false;
    if (/<\/a>\s*$/.test(before)) { const a = before.slice(before.lastIndexOf("<a ")).match(/href="([^"]*)"/); attached = !!a && isAffHref(a[1]); }
    else {
      const open = before.lastIndexOf("<aside"), close = before.lastIndexOf("</aside>");
      if (open > close && /class="partner\b/.test(before.slice(open, before.indexOf(">", open) + 1))) {
        const body = html.slice(open, html.indexOf("</aside>", m.index));
        attached = [...body.matchAll(/<a\b[^>]*href="([^"]+)"/g)].some((x) => isAffHref(x[1]));
      }
    }
    if (!attached) { orphan++; console.error("ORPHAN Partner tag (not on an affiliate link)", f, before.slice(-160).replace(/\s+/g, " ")); }
  }
}
console.log(`Partner tag text: ${tok} ok, ${tbad} wrong; ${orphan} on non-affiliate links`);
console.log(`TradingView links: ${ok} ok, ${bad} bad; partner CTAs verified: ${ctas}`); process.exit(bad || ebad || lbad || tbad || orphan ? 1 : 0);
