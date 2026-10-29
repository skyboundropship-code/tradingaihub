import { chromium } from "playwright-core";
const base = process.env.BASE || "http://localhost:4321";
const pages = [["home","/"],["tools","/tools/"],["category-market-data","/category/market-data/"],["tool-alpaca-mcp","/tools/alpaca-mcp/"],["tool-coingecko-mcp","/tools/coingecko-mcp/"],["compare-api-pricing","/compare/market-data-api-pricing/"],["compare-broker-mcps","/compare/broker-trading-mcp-servers/"],["advertise-footer-only","/advertise/"],["weekly-leaderboard","/weekly/"],["badges","/badges/"],["submit","/submit/"],["about","/about/"],["disclaimer","/disclaimer/"],["verification","/verification/"]];
const b = await chromium.launch({ executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome", args: ["--no-sandbox"] });
const p = await b.newPage({ viewport: { width: 1366, height: 900 } });
for (const [n, u] of pages) { await p.goto(base + u, { waitUntil: "networkidle" }); await p.screenshot({ path: `screenshots/${n}.png`, fullPage: true }); }
const m = await b.newPage({ viewport: { width: 390, height: 844 }, isMobile: true });
await m.goto(base + "/"); await m.screenshot({ path: "screenshots/home-mobile.png", fullPage: false });
await b.close(); console.log("done");
