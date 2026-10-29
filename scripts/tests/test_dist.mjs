import fs from "node:fs"; import path from "node:path";
// Post-build checks of the built site (JSON-LD vs visible content, robots, sitemaps, llms.txt).
// usage: node scripts/tests/test_dist.mjs [distDir=dist] [--data=data/tools.json]    (npm run test:dist)
// Checks: FAQPage == visible FAQ, ItemLists, RTL, llms.txt/llms-full.txt, robots groups, single sitemap index -> 13
// locale sitemaps (no orphan sitemap-N.xml, no duplicates, every URL a built page), one Organization+WebSite graph per
// page, SoftwareApplication == raw tools.json, BreadcrumbList == visible .crumbs (same length, names, hrefs).
const args = process.argv.slice(2); const V2 = true;
const D = args.find(a => !a.startsWith("--")) || "dist";
const dataArg = args.find(a => a.startsWith("--data="))?.slice(7) || path.join(D, "..", "data", "tools.json");
const tools = JSON.parse(fs.readFileSync(dataArg, "utf8")); const T = Array.isArray(tools)?tools:tools.tools;
const N = T.length;
let fail = 0; const ok = (c, m) => { if (!c) { fail++; console.log("FAIL", m); } };
const LANGS = ["en","he","es","pt","de","fr","ja","ko","zh","hi","tr","ar","ru"];
const CATS = ["market-data","trading-brokers","crypto","accounting","payments-banking","personal-finance","research-filings","quant-backtesting","macro"];
const dec = (s) => s.replace(/<[^>]+>/g,"").replace(/&#(\d+);/g,(_,n)=>String.fromCodePoint(+n)).replace(/&#x([0-9a-f]+);/gi,(_,n)=>String.fromCodePoint(parseInt(n,16))).replace(/&quot;/g,'"').replace(/&#39;|&apos;/g,"'").replace(/&lt;/g,"<").replace(/&gt;/g,">").replace(/&amp;/g,"&").replace(/\s+/g," ").trim();
const types = {};
function page(rel, kind, lang) {
  const html = fs.readFileSync(path.join(D, rel, "index.html"), "utf8");
  const blocks = [...html.matchAll(/<script type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/g)].map(m => JSON.parse(m[1])).flatMap(b => b["@graph"] ?? [b]);
  const ts = blocks.map(b => b["@type"]); types[kind] ??= new Set(); types[kind].add(ts.join("+"));
  ok(new Set(ts).size === ts.length, `${rel} duplicate types ${ts}`);
  const faq = blocks.find(b => b["@type"] === "FAQPage"); ok(faq, `${rel} no FAQPage`); if (!faq) return;
  ok(faq.inLanguage === lang, `${rel} inLanguage`);
  const sec = html.match(/<section class="faq"[\s\S]*?<\/section>/)?.[0]; ok(sec, `${rel} no visible faq`);
  const qs = [...sec.matchAll(/<h3[^>]*>([\s\S]*?)<\/h3>\s*<p[^>]*>([\s\S]*?)<\/p>/g)].map(m => [dec(m[1]), dec(m[2])]);
  ok(qs.length === faq.mainEntity.length, `${rel} count ${qs.length} vs ${faq.mainEntity.length}`);
  const n = kind === "home" ? [4,6] : [2,4]; ok(qs.length >= n[0] && qs.length <= n[1], `${rel} faq size ${qs.length}`);
  faq.mainEntity.forEach((q, i) => { ok(q.name === qs[i]?.[0], `${rel} Q${i} ${q.name} !== ${qs[i]?.[0]}`); ok(q.acceptedAnswer.text === qs[i]?.[1], `${rel} A${i}\n ${q.acceptedAnswer.text}\n ${qs[i]?.[1]}`); ok(!/[{}\u2068\u2069]/.test(q.name + q.acceptedAnswer.text), `${rel} leftover placeholder/isolate`); });
  const il = blocks.find(b => b["@type"] === "ItemList") || blocks.find(b => b["@type"] === "CollectionPage")?.mainEntity;
  ok(il && il.itemListElement.every((x, i) => x.position === i + 1 && x.url && x.name), `${rel} ItemList`);
  if (kind === "category") { const slug = rel.split("/").at(-1); ok(il.itemListElement.length === T.filter(x => x.category === slug).length, `${rel} itemlist count`); }
  if (/^(he|ar)/.test(rel)) ok(/<html[^>]*dir="rtl"/.test(html), `${rel} rtl`);
  return faq;
}
let pages = 0;
for (const l of LANGS) { const pre = l === "en" ? "" : l + "/"; page(pre || ".", "home", l); pages++; for (const c of CATS) { page(`${pre}category/${c}`, "category", l); pages++; } }
// llms
const full = fs.readFileSync(path.join(D, "llms-full.txt"), "utf8"); const lines = full.split("\n").filter(s => /^- \[.*\]\(https:\/\/tradingaihub\.com\/tools\//.test(s));
const ids = lines.map(s => s.match(/\/tools\/([^/]+)\//)[1]);
ok(lines.length === N && new Set(ids).size === N && T.every(t => ids.includes(t.id)), `llms-full tools ${lines.length}`);
ok((full.match(/^### /gm) || []).length === 9, "llms-full categories");
for (const id of ids) ok(fs.existsSync(path.join(D, "tools", id, "index.html")), `tool page missing ${id}`);
const lt = fs.readFileSync(path.join(D, "llms.txt"), "utf8"); ok(/^# TradingAIHub\n\n> /.test(lt) && lt.includes("/llms-full.txt") && lt.includes("13 languages"), "llms.txt format");
for (const u of lt.matchAll(/\]\((https:\/\/tradingaihub\.com\/[^)]*)\)/g)) { const p = u[1].replace("https://tradingaihub.com/", ""); ok(fs.existsSync(path.join(D, p)) || fs.existsSync(path.join(D, p, "index.html")), `llms.txt dead link ${u[1]}`); }
// robots
const rb = fs.readFileSync(path.join(D, "robots.txt"), "utf8");
const BOTS = V2 ? ["*","GPTBot","OAI-SearchBot","ChatGPT-User","ClaudeBot","Claude-SearchBot","Claude-User","PerplexityBot","Perplexity-User","Google-Extended","Applebot-Extended","Bingbot"] : ["*","GPTBot","OAI-SearchBot","ClaudeBot","PerplexityBot","Google-Extended"];
for (const b of BOTS) ok(rb.includes(`User-agent: ${b}\nAllow: /`), `robots ${b}`);
ok((rb.match(/^User-agent:/gm) || []).length === BOTS.length, "robots group count");
ok(!/Disallow/.test(rb), "robots disallow"); const sm = rb.match(/^Sitemap: .*/gm);
if (V2) ok(sm.length === 1 && sm[0] === "Sitemap: https://tradingaihub.com/sitemap-index.xml", "robots single sitemap index");
else { ok(sm.length === 13 && new Set(sm).size === 13, "robots sitemaps"); for (const s of sm) ok(fs.existsSync(path.join(D, s.split("/").at(-1))), `sitemap missing ${s}`); }
// locale sitemaps: the only sitemaps (the numbered @astrojs/sitemap files are removed by locale_sitemaps.mjs)
const locs = (f) => [...fs.readFileSync(path.join(D, f), "utf8").matchAll(/<loc>([^<]+)<\/loc>/g)].map(m => m[1]);
const sl = new Set(LANGS.flatMap(l => locs(`sitemap-${l}.xml`)));
const orphans = fs.readdirSync(D).filter(f => /^sitemap-\d+\.xml$/.test(f)); ok(orphans.length === 0, `orphan sitemaps ${orphans}`);
const unbuilt = [...sl].filter(u => { const p = u.replace("https://tradingaihub.com/", ""); return !fs.existsSync(path.join(D, p, "index.html")); });
ok(unbuilt.length === 0, `sitemap URLs without a built page ${unbuilt.slice(0, 5)}`);
const lm = [...fs.readFileSync(path.join(D, "sitemap-index.xml"), "utf8").matchAll(/<lastmod>([^<]+)<\/lastmod>/g)].map(m => m[1]);
const newest = T.map(t => String(t.verification?.checked_at ?? "").slice(0, 10)).filter(Boolean).sort().at(-1);
ok(lm.length === 0 || lm.every(d => d === newest), `sitemap-index lastmod ${[...new Set(lm)]} != newest checked_at ${newest}`);
if (V2) {
  const idx = locs("sitemap-index.xml"); ok(idx.length === 13 && LANGS.every(l => idx.includes(`https://tradingaihub.com/sitemap-${l}.xml`)) && !idx.some(u => u.endsWith("sitemap-0.xml")), "sitemap-index lists exactly the 13 locale sitemaps");
  ok(fs.readFileSync(path.join(D, "sitemap.xml"), "utf8") === fs.readFileSync(path.join(D, "sitemap-index.xml"), "utf8"), "sitemap.xml == sitemap-index.xml");
  const all = LANGS.flatMap(l => locs(`sitemap-${l}.xml`)); ok(all.length === new Set(all).size, `duplicate URLs across locale sitemaps ${all.length - new Set(all).size}`);
  for (const u of idx) ok(fs.existsSync(path.join(D, u.split("/").at(-1))), `index child missing ${u}`);
}
console.log(`locale sitemaps: ${sl.size} unique URLs, ${orphans.length} orphan sitemap files, index lastmod ${[...new Set(lm)].join(",") || "none"}`);
if (V2) v2checks();
console.log("pages checked", pages, "schema types:", Object.fromEntries(Object.entries(types).map(([k, v]) => [k, [...v]])));
console.log(fail ? `FAILURES: ${fail}` : "ALL OK"); process.exit(fail ? 1 : 0);

function v2checks() {
  const raw = Object.fromEntries(T.map(t => [t.id, t]));
  const walk = (d) => fs.readdirSync(d, { withFileTypes: true }).flatMap(e => e.isDirectory() ? walk(path.join(d, e.name)) : e.name.endsWith(".html") ? [path.join(d, e.name)] : []);
  const files = walk(D); let graphRef = null, nLd = 0, nTool = 0, nCrumb = 0;
  const crumbsOf = (html) => { const c = html.match(/<div class="crumbs">([\s\S]*?)<\/div>/)?.[1]; return c ? c.split(" / ").map(x => dec(x)) : null; };
  const hrefsOf = (html) => [...(html.match(/<div class="crumbs">([\s\S]*?)<\/div>/)?.[1] ?? "").matchAll(/href="([^"]+)"/g)].map(m => m[1]);
  for (const f of files) {
    const html = fs.readFileSync(f, "utf8"); const rel = path.relative(D, f);
    let blocks; try { blocks = [...html.matchAll(/<script type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/g)].map(m => JSON.parse(m[1])); } catch (e) { ok(false, `${rel} JSON-LD parse ${e}`); continue; }
    if (!blocks.length) continue; nLd++;
    const txt = JSON.stringify(blocks);
    ok(!/aff_id|aggregateRating|"review"|SearchAction/.test(txt), `${rel} forbidden JSON-LD content`);
    const graphs = blocks.filter(b => b["@graph"]); ok(graphs.length === 1, `${rel} sitewide graph count ${graphs.length}`);
    const g = JSON.stringify(graphs[0]); graphRef ??= g; ok(g === graphRef, `${rel} sitewide graph differs`);
    const nodes = blocks.flatMap(b => b["@graph"] ?? [b]); const ts = nodes.map(n => n["@type"]);
    ok(new Set(ts).size === ts.length, `${rel} duplicate types ${ts}`);
    ok(ts.filter(x => x === "Organization").length === 1 && ts.filter(x => x === "WebSite").length === 1, `${rel} org/website`);
    const lang = html.match(/<html lang="([^"]+)"/)[1]; const pre = lang === "en" ? "" : `/${lang}`;
    const bc = nodes.find(n => n["@type"] === "BreadcrumbList");
    if (bc) { nCrumb++; const vis = crumbsOf(html); const h = hrefsOf(html); const el = bc.itemListElement;
      ok(el.every((x, i) => x.position === i + 1 && /^https:\/\/tradingaihub\.com\//.test(x.item)), `${rel} breadcrumb positions/items`);
      ok(vis && vis.length >= 2 && vis.length === el.length && el.every((x, i) => x.name === vis[i]), `${rel} breadcrumb names ${el.map(x => x.name)} vs ${vis}`);
      ok(dec(html.match(/<h1[^>]*>([\s\S]*?)<\/h1>/)[1]).endsWith(el.at(-1).name), `${rel} last crumb != h1`);
      ok(h.every((u, i) => el[i].item === "https://tradingaihub.com" + u), `${rel} breadcrumb urls`);
      const canon = html.match(/<link rel="canonical" href="([^"]+)"/)?.[1]; ok(el.at(-1).item === canon, `${rel} last crumb != canonical`);
    }
    const app = nodes.find(n => n["@type"] === "SoftwareApplication");
    if (app) { nTool++; const id = rel.split(path.sep).at(-2); const t = raw[id]; const v = t.verification; const pkg = v.npm || v.pypi;
      const canon = html.match(/<link rel="canonical" href="([^"]+)"/)[1];
      ok(app.url === canon && app.inLanguage === lang && app["@id"] === `https://tradingaihub.com/tools/${id}/#app`, `${rel} app url/lang/id`);
      ok(app.name === dec(html.match(/<h1[^>]*>([\s\S]*?)<\/h1>/)[1]), `${rel} app name vs h1`);
      ok(html.includes(">" + app.description.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;") + "<") || dec(html).includes(app.description), `${rel} app description not visible`);
      ok((app.codeRepository ?? null) === (t.repo ?? null), `${rel} codeRepository`);
      ok(JSON.stringify(app.sameAs ?? []) === JSON.stringify([...new Set([t.repo, t.homepage, pkg?.url].filter(Boolean))]), `${rel} sameAs raw ${app.sameAs}`);
      ok((app.softwareVersion ?? null) === (pkg?.version ?? null), `${rel} softwareVersion`);
      const free = ["free", "freemium", "open-source"].includes(t.pricing?.model);
      ok(free ? app.offers?.price === "0" && app.offers.priceCurrency === "USD" && app.isAccessibleForFree === true && (app.offers.url ?? null) === (t.pricing.source ?? null) : !app.offers && !("isAccessibleForFree" in app), `${rel} offers/free ${t.pricing?.model}`);
      ok(/^(MIT|MIT-0|Apache-2\.0|AGPL-3\.0)$/.test(t.license) ? app.license === `https://spdx.org/licenses/${t.license}.html` : !("license" in app), `${rel} license ${t.license}`);
      ok(app.applicationSubCategory === { mcp: "MCP server", skill: "Agent skill", api: "API" }[t.type], `${rel} subcategory`);
    }
  }
  ok(nTool === N * 13, `tool pages with SoftwareApplication ${nTool}`);
  const png = fs.readFileSync(path.join(D, "logo-512.png")); ok(png.readUInt32BE(16) === 512 && png.readUInt32BE(20) === 512 && png.toString("ascii", 1, 4) === "PNG", "logo-512.png is a 512x512 PNG");
  const org = JSON.parse(graphRef)["@graph"].find(n => n["@type"] === "Organization"); ok(org.logo.url === "https://tradingaihub.com/logo-512.png", "org logo url");
  const full = fs.readFileSync(path.join(D, "llms-full.txt"), "utf8"), lt = fs.readFileSync(path.join(D, "llms.txt"), "utf8");
  ok(!/aff_id/.test(full + lt), "llms aff_id");
  for (const t of T) { if (t.repo) ok(full.includes(`Repo: ${t.repo}`), `llms-full repo ${t.id}`); if (t.homepage) ok(full.includes(`Homepage: ${t.homepage}`), `llms-full homepage ${t.id}`); }
  ok((full.match(/· License: /g) || []).length === N, "llms-full license lines");
  console.log(`v2: ${files.length} html files, ${nLd} with JSON-LD (all parse, one identical Organization+WebSite graph each), ${nTool} SoftwareApplication pages, ${nCrumb} BreadcrumbLists checked against visible crumbs`);
}
