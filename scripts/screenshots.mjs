import { chromium } from "playwright-core";
const base = process.env.BASE || "http://localhost:4321";
// [name, path, theme]
const pages = [["home-light","/","light"],["home-dark","/","dark"],["he-home-light","/he/","light"],["ar-home-dark","/ar/","dark"],["tools","/tools/","light"],["category-market-data","/category/market-data/","light"],["tool-alpaca-mcp","/tools/alpaca-mcp/","light"],["tool-alpaca-mcp-dark","/tools/alpaca-mcp/","dark"],["compare-api-pricing","/compare/market-data-api-pricing/","light"],["weekly-leaderboard","/weekly/","light"],["about","/about/","light"]];
const b = await chromium.launch({ executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome", args: ["--no-sandbox"] });
for (const [n, u, theme] of pages) {
  const ctx = await b.newContext({ viewport: { width: 1366, height: 900 }, locale: "en-US" });
  await ctx.addInitScript((th) => { try { localStorage.setItem("theme", th); localStorage.setItem("langAuto", "1"); } catch {} }, theme);
  const p = await ctx.newPage(); await p.goto(base + u, { waitUntil: "networkidle" }); await p.screenshot({ path: `screenshots/${n}.png`, fullPage: true }); await ctx.close();
}
const m = await b.newPage({ viewport: { width: 390, height: 844 }, isMobile: true });
await m.goto(base + "/"); await m.screenshot({ path: "screenshots/home-mobile.png", fullPage: false });
await b.close(); console.log("done");
