#!/usr/bin/env node
// Touch test for badge explanations (src/components/XpTip.astro + the [data-xp-toggle] script in src/layouts/Base.astro).
// BASE=https://<preview>.tradingaihub.pages.dev node scripts/touch_badges.mjs   (npm run test:touch)
// Playwright (playwright-core + system Chrome), 375x667, hasTouch + isMobile, real touchscreen.tap, locales en/he/ar.
// Checks: every badge type on cards opens its explanation without navigating; a tap on the card body still navigates;
// every explained badge on tool pages opens (aria-expanded=true); a tap outside closes; the Partner pill in the
// TradingView banner opens its explanation, and a tap on the banner body opens the partner link (stretched link).
// Network: /api/click and tradingview.com are aborted (no beacons, no partner hits). Exit code 1 on any failure.
const PW = process.env.PW_CORE || "/workspace/qa/visual-2026-11-11/node_modules/playwright-core/index.mjs";
const { chromium } = await import(PW);
const BASE = (process.env.BASE || "https://tradingaihub.com").replace(/\/$/, "");
const LOCALES = (process.env.LOCALES || "en,he,ar").split(",");
const CARD_KEYS = ["type", "official", "status", "scan", "secnote", "pricing", "stars"];
const fails = []; let passes = 0;
const ok = (cond, msg) => { if (cond) passes++; else { fails.push(msg); console.log("FAIL", msg); } };
const pre = (l) => (l === "en" ? "" : "/" + l);

const browser = await chromium.launch({ channel: "chrome", headless: true, args: ["--disable-dev-shm-usage"] });
async function ctx() {
  const c = await browser.newContext({ viewport: { width: 375, height: 667 }, hasTouch: true, isMobile: true, deviceScaleFactor: 2,
    userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1", extraHTTPHeaders: { "x-tah-qa": "1" } });
  await c.route(/\/api\/click|tradingview\.com/, (r) => r.abort());
  return c;
}
async function tapEl(page, loc) {
  await loc.scrollIntoViewIfNeeded();
  const b = await loc.boundingBox(); if (!b) throw new Error("no box");
  await page.touchscreen.tap(b.x + b.width / 2, b.y + b.height / 2); await page.waitForTimeout(350);
}
const tipOpen = (loc) => loc.evaluate((t) => t.classList.contains("open") && t.getBoundingClientRect().height > 8 && getComputedStyle(t).clip !== "rect(0px, 0px, 0px, 0px)");
// An open explanation must sit inside the 375 viewport and must not widen the page (no horizontal scroll / zoom-out).
const tipInView = (loc) => loc.evaluate((t) => { const r = t.getBoundingClientRect(), vw = document.documentElement.clientWidth; return r.left >= 0 && r.right <= vw && document.documentElement.scrollWidth <= vw; });

for (const l of LOCALES) {
  const c = await ctx(); const page = await c.newPage();
  // Cards: /tools/ lists every tool.
  const listUrl = `${BASE}${pre(l)}/tools/`;
  for (const k of CARD_KEYS) {
    await page.goto(listUrl, { waitUntil: "domcontentloaded" });
    const card = page.locator(`a.card:has([data-xp-toggle][data-xp="${k}"])`).first();
    if (!(await card.count())) { ok(false, `${l} card: no ${k} badge found`); continue; }
    const badge = card.locator(`[data-xp-toggle][data-xp="${k}"]`).first();
    await tapEl(page, badge);
    ok(page.url() === listUrl, `${l} card ${k}: tap navigated to ${page.url()}`);
    ok(await tipOpen(card.locator(`.xp-tip[data-xp="${k}"]`)), `${l} card ${k}: explanation not open after tap`);
    ok(await tipInView(card.locator(`.xp-tip[data-xp="${k}"]`)), `${l} card ${k}: explanation outside the viewport`);
    await tapEl(page, page.locator("h1").first());
    ok(!(await card.locator(`.xp-tip[data-xp="${k}"]`).evaluate((t) => t.classList.contains("open"))), `${l} card ${k}: tap outside did not close`);
  }
  // Card body still navigates.
  await page.goto(listUrl, { waitUntil: "domcontentloaded" });
  const card = page.locator("a.card:has([data-xp=secnote])").first();
  const href = await card.getAttribute("href");
  await Promise.all([page.waitForURL((u) => u.pathname === href, { timeout: 8000 }).catch(() => {}), tapEl(page, card.locator("h3, .card-t").first())]);
  ok(new URL(page.url()).pathname === href, `${l} card body tap did not navigate (at ${page.url()}, want ${href})`);

  // Tool pages: CCTT (stale, secnote) and an official clean tool.
  for (const slug of ["claude-code-trading-terminal", "alpha-vantage-api"]) {
    const url = `${BASE}${pre(l)}/tools/${slug}/`;
    await page.goto(url, { waitUntil: "domcontentloaded" });
    const btns = page.locator(".xp-scope button[data-xp-toggle]");
    const n = await btns.count(); ok(n >= 3, `${l} ${slug}: only ${n} explained buttons`);
    for (let i = 0; i < n; i++) {
      const b = btns.nth(i); const k = await b.getAttribute("data-xp");
      await tapEl(page, b);
      ok(page.url() === url, `${l} ${slug} ${k}: navigated`);
      ok((await b.getAttribute("aria-expanded")) === "true", `${l} ${slug} ${k}: aria-expanded not true`);
      ok(await tipOpen(page.locator(`#${await b.getAttribute("aria-controls")}`)), `${l} ${slug} ${k}: explanation not open`);
      ok(await tipInView(page.locator(`#${await b.getAttribute("aria-controls")}`)), `${l} ${slug} ${k}: explanation outside the viewport`);
    }
    await tapEl(page, page.locator("h1").first());
    ok((await page.locator(".xp-tip.open").count()) === 0, `${l} ${slug}: tap outside did not close`);
    // Partner banner: pill explains, body opens the partner link.
    const aside = page.locator("aside.partner").first();
    if (await aside.count()) {
      const pill = aside.locator(".partner-tag");
      await tapEl(page, pill);
      ok(page.url() === url, `${l} ${slug} partner pill: navigated`);
      ok(await tipOpen(aside.locator('.xp-tip[data-xp="partner"]')), `${l} ${slug} partner pill: explanation not open`);
      ok(await tipInView(aside.locator('.xp-tip[data-xp="partner"]')), `${l} ${slug} partner pill: explanation outside the viewport`);
      await tapEl(page, page.locator("h1").first());
      const pop = c.waitForEvent("page", { timeout: 5000 }).catch(() => null);
      await tapEl(page, aside.locator(".partner-body b, .partner-body h2").first());
      const p2 = await pop; let purl = p2 ? p2.url() : "";
      if (p2 && purl === "about:blank") { await p2.waitForURL(/./, { timeout: 2000 }).catch(() => {}); purl = p2.url(); }
      ok(!!p2, `${l} ${slug} partner banner body: tap did not open the partner link`);
      if (p2) { ok(/tradingview\.com/.test(purl) || purl.startsWith("chrome-error") || purl === "about:blank", `${l} ${slug} partner banner opened ${purl}`); await p2.close(); }
    }
  }
  await c.close();
}
await browser.close();
console.log(`touch_badges: ${passes} passed, ${fails.length} failed (BASE ${BASE}, ${LOCALES.join("/")})`);
process.exit(fails.length ? 1 : 0);
