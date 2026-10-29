// Generates 1200x630 OG images into public/og/ from live repo data (data/tools.json, src/lib/data.ts).
// Runs automatically as the first step of `npm run build`, so counts on the cards can never go stale.
// Fonts are bundled in scripts/og-fonts/ (Inter + a Noto Color Emoji subset, SIL OFL 1.1) and inlined as data: URLs,
// so rendering needs no network and does not depend on system fonts. Unchanged cards are skipped via a content-hash cache.
import { chromium } from "playwright-core";
import fs from "node:fs";
import crypto from "node:crypto";
const t0 = Date.now();
const tools = JSON.parse(fs.readFileSync("data/tools.json", "utf8"));
const cfg = fs.readFileSync("src/config.ts", "utf8"); const brand = cfg.match(/name: "([^"]+)"/)[1]; const domain = cfg.match(/domain: "([^"]+)"/)[1];
const lib = fs.readFileSync("src/lib/data.ts", "utf8");
const cats = [...lib.matchAll(/slug: "([^"]+)", name: "([^"]+)", short: "[^"]+", icon: "([^"]+)"/g)].map((m) => ({ slug: m[1], name: m[2], icon: m[3] }));
const comps = [...lib.matchAll(/slug: "([^"]+)", title: "([^"]+)"/g)].map((m) => ({ slug: m[1], title: m[2] }));
const verified = tools.filter((t) => t.verification.status === "verified").length;
// "This week" is only claimed when the latest verification run is within 7 days of the build date (OG_DATE=YYYY-MM-DD overrides
// for testing). Otherwise the cards name the date of the last check instead — never an invented or stale "this week" number.
const today = process.env.OG_DATE || new Date().toISOString().slice(0, 10);
const weekAgo = new Date(Date.parse(today) - 7 * 864e5).toISOString().slice(0, 10);
const latestCheck = tools.map((t) => t.verification.checked_at).filter(Boolean).sort().at(-1) || "";
const fresh = latestCheck >= weekAgo;
const verifiedThisWeek = tools.filter((t) => t.verification.status === "verified" && (t.verification.checked_at || "") >= weekAgo).length;
const homeSub = fresh ? `${tools.length} MCP servers, skills & APIs · ${verifiedThisWeek} verified this week` : `${tools.length} MCP servers, skills & APIs · ${verified} verified (checked ${latestCheck})`;
const weeklySub = fresh ? `${verifiedThisWeek}/${tools.length} pass this week's check` : `${verified}/${tools.length} passed the ${latestCheck} check`;
const font = (f) => fs.readFileSync(new URL(`./og-fonts/${f}`, import.meta.url)).toString("base64");
const FONTS = `<style>@font-face{font-family:Inter;font-weight:100 900;src:url(data:font/ttf;base64,${font("Inter-subset.ttf")}) format("truetype")}@font-face{font-family:"Noto Color Emoji";src:url(data:font/ttf;base64,${font("NotoColorEmoji-subset.ttf")}) format("truetype")}</style>`;
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
// Header badge. Site-level cards keep "✓ verified weekly"; tool cards reflect that tool's own verification status
// (only status "verified" gets the checkmark — see BADGE below).
const SITE_BADGE = { text: "✓ verified weekly", color: "#15803d" };
const BADGE = {
  verified: () => SITE_BADGE,
  aging: (d) => ({ text: `Aging · last checked ${d}`, color: "#b45309" }),
  stale: (d) => ({ text: `⚠ Stale · last checked ${d}`, color: "#b45309" }),
  archived: () => ({ text: "Archived by owner", color: "#b91c1c" }),
  warning: (d) => ({ text: `⚠ Check links · last checked ${d}`, color: "#b45309" }),
  unreachable: (d) => ({ text: `⚠ Unreachable · last checked ${d}`, color: "#b91c1c" }),
};
const toolBadge = (v) => (BADGE[v.status] || ((d) => ({ text: `Last checked ${d}`, color: "#475569" })))(v.checked_at);
const card = (kicker, title, sub, badge = SITE_BADGE) => `<html><head>${FONTS}</head><body style="margin:0;width:1200px;height:630px;background:radial-gradient(circle at 85% 0%,#dbeafe 0,#ffffff 55%);border-top:12px solid #2563eb;font-family:Inter,'Noto Color Emoji',DejaVu Sans,sans-serif;font-optical-sizing:none;color:#0f172a;display:flex;flex-direction:column;justify-content:space-between;padding:64px;box-sizing:border-box">
<div style="font-size:30px;font-weight:800">📈 ${esc(brand)} <span style="color:${badge.color};font-size:24px;font-weight:600;margin-left:12px">${esc(badge.text)}</span></div>
<div><div style="color:#2563eb;font-size:28px;margin-bottom:14px">${esc(kicker)}</div><div style="font-size:${title.length > 60 ? 54 : 66}px;font-weight:800;line-height:1.08;letter-spacing:-1px">${esc(title)}</div></div>
<div style="display:flex;justify-content:space-between;color:#475569;font-size:26px"><span>${esc(sub)}</span><span>${esc(domain)}</span></div></body></html>`;
const jobs = [["home", card("Free directory", "AI tools for finance & trading", homeSub)],
  ["weekly", card("Weekly leaderboard", "State of finance AI tools", weeklySub)],
  ...cats.map((c) => [`category-${c.slug}`, card("Category", `${c.icon} ${c.name}`, `${tools.filter((t) => t.category === c.slug).length} tools · free · verified weekly`)]),
  ...comps.map((c) => [`compare-${c.slug}`, card("Comparison", c.title, "Pricing, status, stars & install — side by side")]),
  ...tools.map((t) => [`tool-${t.id}`, card(t.type === "mcp" ? "MCP server" : t.type === "skill" ? "Agent skill" : "API", t.name, `Status: ${t.verification.status} · checked ${t.verification.checked_at}`, toolBadge(t.verification))])];
fs.mkdirSync("public/og", { recursive: true });
// Content-hash cache (local only, not committed): skip cards whose HTML is unchanged and whose PNG still exists.
const cacheFile = "node_modules/.cache/og-hashes.json";
let cache = {}; try { cache = JSON.parse(fs.readFileSync(cacheFile, "utf8")); } catch {}
const hash = (h) => crypto.createHash("sha256").update(h).digest("hex");
const pngHash = (n) => (fs.existsSync(`public/og/${n}.png`) ? hash(fs.readFileSync(`public/og/${n}.png`)) : "");
const todo = process.env.OG_FORCE ? jobs : jobs.filter(([n, html]) => cache[n]?.html !== hash(html) || cache[n]?.png !== pngHash(n));
if (todo.length) {
  const b = await chromium.launch({ executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome", args: ["--no-sandbox"] });
  const p = await b.newPage({ viewport: { width: 1200, height: 630 } });
  for (const [n, html] of todo) {
    await p.setContent(html); await p.evaluate(() => document.fonts.ready);
    await p.screenshot({ path: `public/og/${n}.png` }); cache[n] = { html: hash(html), png: pngHash(n) };
  }
  await b.close();
  fs.mkdirSync("node_modules/.cache", { recursive: true }); fs.writeFileSync(cacheFile, JSON.stringify(cache));
}
console.log(`OG images: ${todo.length} rendered, ${jobs.length - todo.length} unchanged (${jobs.length} total) in ${((Date.now() - t0) / 1000).toFixed(1)}s · home: "${homeSub}"`);
