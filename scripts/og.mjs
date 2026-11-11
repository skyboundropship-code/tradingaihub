// Generates 1200x630 OG images into public/og/ from live repo data (data/tools.json, src/lib/data.ts).
// Runs automatically as the first step of `npm run build`, so counts on the cards can never go stale.
// Fonts are bundled in scripts/og-fonts/ (Inter + a Noto Color Emoji subset, SIL OFL 1.1) and inlined as data: URLs,
// so rendering needs no network and does not depend on system fonts. Unchanged cards are skipped via a content-hash cache.
import { chromium } from "playwright-core";
import fs from "node:fs";
import crypto from "node:crypto";
import { execFileSync } from "node:child_process";
const t0 = Date.now();
const tools = JSON.parse(fs.readFileSync("data/tools.json", "utf8"));
const cfg = fs.readFileSync("src/config.ts", "utf8"); const brand = cfg.match(/name: "([^"]+)"/)[1]; const domain = cfg.match(/domain: "([^"]+)"/)[1];
const lib = fs.readFileSync("src/lib/data.ts", "utf8");
const cats = [...lib.matchAll(/slug: "([^"]+)", name: "([^"]+)", short: "[^"]+", icon: "([^"]+)"/g)].map((m) => ({ slug: m[1], name: m[2], icon: m[3] }));
const comps = [...lib.matchAll(/slug: "([^"]+)", title: "([^"]+)"/g)].map((m) => ({ slug: m[1], title: m[2] }));
// Friendly status names ("Needs review", not "unconfirmed"), taken from the site's STATUS map in src/lib/data.ts.
const STATUS_LABEL = Object.fromEntries([...lib.matchAll(/^\s+(\w+): \{ label: "([^"]+)"/gm)].map((m) => [m[1], m[2]]));
const statusLabel = (s) => (s === "unconfirmed" ? "Link check pending" : STATUS_LABEL[s] || s);
const verified = tools.filter((t) => t.verification.status === "verified").length;
// "This week" = the check is less than 7 days old (age < 7 days, i.e. checked_at > build date − 7 days), using UTC dates.
// It is only claimed when the latest verification run is that fresh; otherwise the cards name the date of the last check,
// drop the "verified weekly" claims, and never show an invented or stale "this week" number.
// Dates must be strict ISO YYYY-MM-DD (real calendar dates); anything else counts as "no date". OG_DATE=YYYY-MM-DD overrides today (testing).
const DAY = 864e5;
const isoDay = (d) => (typeof d === "string" && /^\d{4}-\d{2}-\d{2}$/.test(d) && !isNaN(Date.parse(`${d}T00:00:00Z`)) && new Date(`${d}T00:00:00Z`).toISOString().slice(0, 10) === d ? d : "");
const isoOrThrow = (d) => { if (isoDay(d)) return d; throw new Error(`OG_DATE must be a valid YYYY-MM-DD date, got "${d}"`); };
const today = process.env.OG_DATE ? isoOrThrow(process.env.OG_DATE) : new Date().toISOString().slice(0, 10);
const ageDays = (d) => (Date.parse(`${today}T00:00:00Z`) - Date.parse(`${d}T00:00:00Z`)) / DAY;
const checkedAt = (t) => isoDay(t.verification?.checked_at);
const thisWeek = (d) => !!d && ageDays(d) < 7;
const latestCheck = tools.map(checkedAt).filter(Boolean).sort().at(-1) || "";
const fresh = thisWeek(latestCheck);
const verifiedThisWeek = tools.filter((t) => t.verification.status === "verified" && thisWeek(checkedAt(t))).length;
const homeSub = fresh ? `${tools.length} MCP servers, skills & APIs · ${verifiedThisWeek} verified this week`
  : latestCheck ? `${tools.length} MCP servers, skills & APIs · ${verified} verified (checked ${latestCheck})` : `${tools.length} MCP servers, skills & APIs`;
const weeklySub = fresh ? `${verifiedThisWeek}/${tools.length} pass this week's check`
  : latestCheck ? `${verified}/${tools.length} passed the ${latestCheck} check` : `${verified}/${tools.length} passed the latest check`;
const font = (f) => fs.readFileSync(new URL(`./og-fonts/${f}`, import.meta.url)).toString("base64");
const FONTS = `<style>@font-face{font-family:Inter;font-weight:100 900;src:url(data:font/ttf;base64,${font("Inter-subset.ttf")}) format("truetype")}@font-face{font-family:"Noto Color Emoji";src:url(data:font/ttf;base64,${font("NotoColorEmoji-subset.ttf")}) format("truetype")}</style>`;
// Brand lockup (logo 6 "Verified t", light art from public/brand/logo-lockup.svg); the accessible/brand name stays TradingAIHub.
const LOGO = `<svg viewBox="270 104 1068 190" width="253" height="45" role="img" aria-label="TradingAIHub"><g transform="translate(266.346 112)scale(1.76)"><path fill="none" stroke="#0f172a" stroke-linecap="round" stroke-linejoin="round" stroke-width="15" d="M42 8v52c0 20 16 26 30 14l20-20"/><path fill="none" stroke="#0f172a" stroke-linecap="round" stroke-width="15" d="M16 32h48"/><circle cx="86" cy="22" r="8" fill="#15803d"/></g><path fill="#0f172a" d="M539.608 254.164q-5.908 0-10.908-2.197t-8.03-7.273-3.03-13.408V160.23l18.03-9.697v75.905q0 6.363 1.817 9.772 1.818 3.409 6.97 3.409 1.515 0 3.484-.379t4.242-.985v13.787q-3.181 1.061-6.287 1.591t-6.288.53m-35.907-62.27v-13.787h48.482v13.787ZM563.85 252.8v-74.693h18.029v20.15l-3.03.455q.606-6.515 4.166-11.514 3.56-5 8.712-7.803 5.15-2.803 10.302-2.803 3.788 0 7.12.985 3.334.985 6.97 3.106l-8.636 16.06q-1.666-.91-4.242-1.667t-5.151-.757q-3.03 0-5.985 1.136-2.954 1.136-5.302 3.56-2.349 2.424-3.56 6.212-.758 2.121-1.137 5.454t-.379 9.545V252.8Zm107.569 0-1.364-11.969v-35.15q0-6.969-4.242-10.453-4.242-3.485-11.817-3.485-5.909 0-11.894 2.348-5.984 2.349-10.832 6.894l-9.394-11.97q7.576-6.666 15.757-9.544t17.878-2.879q15.302 0 23.786 7.727t8.485 21.362V252.8Zm-22.877 1.364q-8.182 0-14.62-3.03-6.44-3.03-10.076-8.56t-3.636-12.803q0-6.363 2.651-10.908 2.652-4.546 6.894-7.121 3.787-2.273 8.484-3.182t10-.909h23.332v13.181h-20.757q-2.575 0-5.075.455-2.5.454-4.47 1.818-1.515 1.212-2.348 2.878t-.833 3.94q0 4.545 3.484 7.196t9.394 2.651q5.302 0 9.62-2.272 4.318-2.273 6.894-6.363 2.575-4.091 2.575-9.242l5.152 9.242q-1.97 7.878-5.91 13.03-3.938 5.15-9.241 7.574-5.303 2.425-11.514 2.425m83.177 0q-10 0-17.196-5.076t-11.136-13.863-3.94-19.847q0-12.272 4.319-20.908 4.318-8.636 11.666-13.257 7.348-4.62 16.287-4.62 6.211 0 11.514 2.575t9.015 7.5 5.075 12.347l-3.788-.454V147.2h17.727v105.6h-17.727v-20.453l4.394-1.515q-1.818 8.484-5.833 13.635t-9.317 7.424-11.06 2.273m4.545-16.363q5.757 0 10-2.803 4.241-2.803 6.514-7.878t2.273-11.742q0-6.818-2.273-11.818t-6.515-7.802-10-2.803q-5.605 0-9.923 2.727t-6.666 7.803q-2.349 5.075-2.349 11.893t2.349 11.893q2.348 5.076 6.666 7.803t9.924 2.727M787.17 252.8v-74.693h17.878V252.8Zm-.606-86.662V147.2h19.241v18.938Zm34.392 86.662v-74.693h17.878v16.666l-3.03.606q1.97-6.666 5.757-10.757t8.863-6.06 10.53-1.97q12.575 0 19.695 7.197 7.121 7.196 7.121 20.377V252.8h-17.878v-41.967q0-9.697-3.484-14.242t-10.757-4.545q-5.606 0-9.318 2.576t-5.606 8.03-1.893 14.09V252.8Zm113.478 32.422q-16.666 0-26.21-5.984-9.545-5.985-9.545-16.287 0-.91.075-2.197.076-1.288.38-2.5l20.604-13.03 4.697 4.849-9.697 11.969q-.151.454-.151.757v.758q0 4.394 5.454 6.818t14.393 2.424q7.424 0 11.666-1.97t4.242-5.908q0-2.122-1.212-3.41-1.212-1.287-3.787-2.12t-6.515-1.516-9.394-1.287q-6.817-.91-13.484-2.955t-10.984-5.984-4.318-10.606q0-5.757 4.015-10.605t10.53-8.03l8.939 6.97q-4.242.757-6.288 2.954-2.045 2.197-2.045 5.075 0 2.576 1.97 4.09 1.97 1.516 5.605 2.273t8.788 1.516q7.726.909 14.241 2.12 6.515 1.213 11.439 3.41t7.575 5.984 2.652 9.848q0 10.908-8.788 16.741t-24.847 5.833m-1.666-53.784q-9.242 0-16.212-3.485t-10.908-9.62-3.94-14.015q0-8.333 4.167-14.545t11.136-9.696 15.15-3.485 15.151 3.485 11.212 9.848 4.242 14.999q0 8.03-3.788 14.014-3.787 5.985-10.53 9.242-6.741 3.258-15.68 3.258m-.303-14.09q6.211 0 9.393-3.864t3.182-9.318q0-5.757-3.41-9.317-3.408-3.56-9.165-3.56-5.91 0-9.394 3.56t-3.484 9.166 3.257 9.47q3.257 3.862 9.62 3.862m25.301-23.787-12.878-8.333 16.969-13.787 9.09 11.06Z"/><path fill="#15803d" d="m1026.399 252.8-1.364-11.969v-35.15q0-6.969-4.242-10.453-4.242-3.485-11.818-3.485-5.908 0-11.893 2.348-5.984 2.349-10.833 6.894l-9.393-11.97q7.575-6.666 15.757-9.544t17.877-2.879q15.303 0 23.787 7.727t8.484 21.362V252.8Zm-22.878 1.364q-8.181 0-14.62-3.03-6.44-3.03-10.075-8.56-3.637-5.53-3.637-12.803 0-6.363 2.652-10.908 2.651-4.546 6.893-7.121 3.788-2.273 8.485-3.182t10-.909h23.331v13.181h-20.756q-2.576 0-5.076.455-2.5.454-4.47 1.818-1.514 1.212-2.348 2.878t-.833 3.94q0 4.545 3.485 7.196t9.393 2.651q5.303 0 9.62-2.272 4.319-2.273 6.894-6.363 2.576-4.091 2.576-9.242l5.151 9.242q-1.97 7.878-5.908 13.03-3.94 5.15-9.242 7.574-5.303 2.425-11.515 2.425m54.239-1.364v-74.693h17.878V252.8Zm-.606-86.662V147.2h19.242v18.938Z"/><path fill="#0f172a" d="M1091.546 252.8V147.2h17.878v47.573l-3.03.606q1.97-6.666 5.833-10.757t8.863-6.06 10.454-1.97q12.575 0 19.696 7.197 7.12 7.196 7.12 20.377V252.8h-17.877v-41.967q0-9.697-3.485-14.242t-10.757-4.545q-8.332 0-12.575 5.909t-4.242 18.786V252.8Zm108.328 1.364q-8.94 0-15-3.56t-9.09-10.152q-3.03-6.59-3.03-15.68v-46.665h17.878v42.12q0 5.453 1.287 9.62 1.288 4.166 4.47 6.515t8.787 2.348q6.515 0 10.075-3.636t5-10.303 1.44-15.756v-30.908h17.877V252.8h-17.878v-16.211l2.728 1.363q-3.334 8.485-9.924 12.348t-14.62 3.864m95.449 0q-5.758 0-11.06-2.273t-9.242-7.424-5.909-13.635l4.394 1.515V252.8h-17.727V147.2h17.727v51.36l-3.788.607q1.364-7.424 5.075-12.424t9.09-7.575q5.38-2.576 11.44-2.576 8.938 0 16.287 4.621t11.666 13.257 4.317 20.908q0 11.06-3.939 19.847t-11.135 13.863-17.196 5.076m-4.546-16.363q5.758 0 10-2.727t6.59-7.803 2.349-11.893-2.349-11.893-6.59-7.803-10-2.727-9.999 2.803-6.515 7.802-2.272 11.818q0 6.666 2.272 11.742 2.273 5.075 6.515 7.878t10 2.803"/></svg>`;
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
// Header badge. Site-level cards show "✓ verified weekly" only while the data is fresh (hidden otherwise); tool cards reflect
// that tool's own verification status (only status "verified" gets the checkmark — see BADGE below).
const SITE_BADGE = fresh ? { text: "✓ verified weekly", color: "#15803d" } : { text: "", color: "#15803d" };
const lc = (d) => (d ? ` · last checked ${d}` : "");
const BADGE = {
  verified: (d) => (fresh ? SITE_BADGE : { text: `✓ Verified${lc(d)}`, color: "#15803d" }),
  aging: (d) => ({ text: `Aging${lc(d)}`, color: "#b45309" }),
  stale: (d) => ({ text: `⚠ Stale${lc(d)}`, color: "#b45309" }),
  archived: () => ({ text: "Archived by owner", color: "#b91c1c" }),
  warning: (d) => ({ text: `⚠ Check links${lc(d)}`, color: "#b45309" }),
  unconfirmed: (d) => ({ text: `Link check pending${lc(d)}`, color: "#4b5a70" }),
  unreachable: (d) => ({ text: `⚠ Unreachable${lc(d)}`, color: "#b91c1c" }),
};
const toolBadge = (t) => (BADGE[t.verification.status] || ((d) => ({ text: d ? `Last checked ${d}` : "Not checked yet", color: "#475569" })))(checkedAt(t));
const card = (kicker, title, sub, badge = SITE_BADGE) => `<html><head>${FONTS}</head><body style="margin:0;width:1200px;height:630px;background:radial-gradient(circle at 85% 0%,#dbeafe 0,#ffffff 55%);border-top:12px solid #2563eb;font-family:Inter,'Noto Color Emoji',DejaVu Sans,sans-serif;font-optical-sizing:none;color:#0f172a;display:flex;flex-direction:column;justify-content:space-between;padding:64px;box-sizing:border-box">
<div style="font-size:30px;font-weight:800;display:flex;align-items:center">${LOGO} ${badge.text ? `<span style="color:${badge.color};font-size:24px;font-weight:600;margin-left:12px">${esc(badge.text)}</span>` : ""}</div>
<div><div style="color:#2563eb;font-size:28px;margin-bottom:14px">${esc(kicker)}</div><div style="font-size:${title.length > 60 ? 54 : 66}px;font-weight:800;line-height:1.08;letter-spacing:-1px">${esc(title)}</div></div>
<div style="display:flex;justify-content:space-between;color:#475569;font-size:26px"><span>${esc(sub)}</span><span>${esc(domain)}</span></div></body></html>`;
const jobs = [["home", card("Free directory", "AI tools for finance & trading", homeSub)],
  ["weekly", card("Weekly leaderboard", "State of finance AI tools", weeklySub)],
  ...cats.map((c) => [`category-${c.slug}`, card("Category", `${c.icon} ${c.name}`, `${tools.filter((t) => t.category === c.slug).length} tools · free${fresh ? " · verified weekly" : ""}`)]),
  ...comps.map((c) => [`compare-${c.slug}`, card("Comparison", c.title, "Pricing, status, stars & install — side by side")]),
  ["compare-best-ai-tools-for-stock-analysis", card("Comparison", "Best AI tools for stock analysis and research (2026)", "Verified MCP servers, skills and APIs — official vendors first")],
  ["compare-best-ai-tools-for-options-trading", card("Comparison", "Best AI tools for options data and options trading (2026)", "Options data first, then broker-connected tools")],
  ...tools.map((t) => [`tool-${t.id}`, card(t.type === "mcp" ? "MCP server" : t.type === "skill" ? "Agent skill" : "API", t.name, `Status: ${statusLabel(t.verification.status)}${checkedAt(t) ? ` · checked ${checkedAt(t)}` : ""}`, toolBadge(t))])];
fs.mkdirSync("public/og", { recursive: true });
// Render-side inputs. Bump RENDER_VERSION for any render change the key below can't see.
const RENDER_VERSION = 2;
const VIEWPORT = { width: 1200, height: 630 };
const SHOT = { type: "png", fullPage: false };
const CHROME = process.env.CHROME_PATH || "/usr/bin/google-chrome";
let chromeVersion = "unknown"; try { chromeVersion = execFileSync(CHROME, ["--version"], { encoding: "utf8" }).trim(); } catch {}
let pwVersion = "unknown"; try { pwVersion = JSON.parse(fs.readFileSync("node_modules/playwright-core/package.json", "utf8")).version; } catch {}
const RENDER_KEY = crypto.createHash("sha256").update(JSON.stringify({ RENDER_VERSION, VIEWPORT, SHOT, chromeVersion, pwVersion, src: fs.readFileSync(new URL(import.meta.url), "utf8") })).digest("hex");
// Content-hash cache (local only, not committed): a card is skipped only if its HTML, the render key (og.mjs source, viewport,
// screenshot options, Chrome + Playwright versions, RENDER_VERSION) and the PNG on disk all match the last render.
const cacheFile = "node_modules/.cache/og-hashes.json";
let cache = {}; try { cache = JSON.parse(fs.readFileSync(cacheFile, "utf8")); } catch {}
const hash = (h) => crypto.createHash("sha256").update(h).digest("hex");
const pngHash = (n) => (fs.existsSync(`public/og/${n}.png`) ? hash(fs.readFileSync(`public/og/${n}.png`)) : "");
const force = /^(1|true|yes)$/i.test(process.env.OG_FORCE || "");
const key = (html) => hash(RENDER_KEY + html);
const todo = force ? jobs : jobs.filter(([n, html]) => cache[n]?.html !== key(html) || cache[n]?.png !== pngHash(n));
if (todo.length) {
  const b = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
  const p = await b.newPage({ viewport: VIEWPORT });
  for (const [n, html] of todo) {
    await p.setContent(html); await p.evaluate(() => document.fonts.ready);
    await p.screenshot({ ...SHOT, path: `public/og/${n}.png` }); cache[n] = { html: key(html), png: pngHash(n) };
  }
  await b.close();
  fs.mkdirSync("node_modules/.cache", { recursive: true }); fs.writeFileSync(cacheFile, JSON.stringify(cache));
}
console.log(`OG images: ${todo.length} rendered, ${jobs.length - todo.length} unchanged (${jobs.length} total) in ${((Date.now() - t0) / 1000).toFixed(1)}s${force ? " (forced)" : ""} · home: "${homeSub}"`);
