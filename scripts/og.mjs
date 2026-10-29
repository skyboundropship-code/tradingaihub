// Generates 1200x630 OG images into public/og/ (run before `astro build`; re-run weekly).
import { chromium } from "playwright-core";
import fs from "node:fs";
const tools = JSON.parse(fs.readFileSync("data/tools.json", "utf8"));
const cfg = fs.readFileSync("src/config.ts", "utf8"); const brand = cfg.match(/name: "([^"]+)"/)[1]; const domain = cfg.match(/domain: "([^"]+)"/)[1];
const lib = fs.readFileSync("src/lib/data.ts", "utf8");
const cats = [...lib.matchAll(/slug: "([^"]+)", name: "([^"]+)", short: "[^"]+", icon: "([^"]+)"/g)].map((m) => ({ slug: m[1], name: m[2], icon: m[3] }));
const comps = [...lib.matchAll(/slug: "([^"]+)", title: "([^"]+)"/g)].map((m) => ({ slug: m[1], title: m[2] }));
const verified = tools.filter((t) => t.verification.status === "verified").length;
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
  unconfirmed: (d) => ({ text: `Needs review · last checked ${d}`, color: "#b45309" }),
  unreachable: (d) => ({ text: `⚠ Unreachable · last checked ${d}`, color: "#b91c1c" }),
};
const toolBadge = (v) => (BADGE[v.status] || ((d) => ({ text: `Last checked ${d}`, color: "#475569" })))(v.checked_at);
const card = (kicker, title, sub, badge = SITE_BADGE) => `<html><body style="margin:0;width:1200px;height:630px;background:radial-gradient(circle at 85% 0%,#dbeafe 0,#ffffff 55%);border-top:12px solid #2563eb;font-family:Inter,DejaVu Sans,sans-serif;color:#0f172a;display:flex;flex-direction:column;justify-content:space-between;padding:64px;box-sizing:border-box">
<div style="font-size:30px;font-weight:800">📈 ${esc(brand)} <span style="color:${badge.color};font-size:24px;font-weight:600;margin-left:12px">${esc(badge.text)}</span></div>
<div><div style="color:#2563eb;font-size:28px;margin-bottom:14px">${esc(kicker)}</div><div style="font-size:${title.length > 60 ? 54 : 66}px;font-weight:800;line-height:1.08;letter-spacing:-1px">${esc(title)}</div></div>
<div style="display:flex;justify-content:space-between;color:#475569;font-size:26px"><span>${esc(sub)}</span><span>${esc(domain)}</span></div></body></html>`;
const jobs = [["home", card("Free directory", "AI tools for finance & trading", `${tools.length} MCP servers, skills & APIs · ${verified} verified this week`)],
  ["weekly", card("Weekly leaderboard", "State of finance AI tools", `${verified}/${tools.length} pass this week's check`)],
  ...cats.map((c) => [`category-${c.slug}`, card("Category", `${c.icon} ${c.name}`, `${tools.filter((t) => t.category === c.slug).length} tools · free · verified weekly`)]),
  ...comps.map((c) => [`compare-${c.slug}`, card("Comparison", c.title, "Pricing, status, stars & install — side by side")]),
  ...tools.map((t) => [`tool-${t.id}`, card(t.type === "mcp" ? "MCP server" : t.type === "skill" ? "Agent skill" : "API", t.name, `Status: ${t.verification.status} · checked ${t.verification.checked_at}`, toolBadge(t.verification))])];
fs.mkdirSync("public/og", { recursive: true });
const b = await chromium.launch({ executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome", args: ["--no-sandbox"] });
const p = await b.newPage({ viewport: { width: 1200, height: 630 } });
for (const [n, html] of jobs) { await p.setContent(html); await p.screenshot({ path: `public/og/${n}.png` }); }
await b.close(); console.log(jobs.length, "OG images");
