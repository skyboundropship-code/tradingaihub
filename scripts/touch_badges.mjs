#!/usr/bin/env node
// Touch test for badge explanations (src/components/XpTip.astro + the [data-xp-toggle] script in src/layouts/Base.astro).
// BASE=https://<preview>.tradingaihub.pages.dev node scripts/touch_badges.mjs   (npm run test:touch)
// Playwright (playwright-core + system Chrome), 375x667, hasTouch + isMobile, real touchscreen.tap, all 13 locales.
// Checks: every badge type on cards opens its explanation without navigating; a tap on the card body still navigates;
// every explained badge on tool pages opens (aria-expanded=true); a tap outside closes; the Partner pill in the
// TradingView banner opens its explanation, and a tap on the banner body opens the partner link (stretched link).
// Also asserts that every visible badge's bounding box sits fully inside its row and the viewport, and the page is
// not horizontally overflowed (scrollWidth <= clientWidth). An open tip must stay inside the viewport vertically
// too (top >= 0, bottom <= vh), including when its badge is parked near the bottom of the 375x667 viewport.
// Network: /api/click and tradingview.com are aborted (no beacons, no partner hits). Exit code 1 on any failure.
const PW = process.env.PW_CORE || "/workspace/qa/visual-2026-11-11/node_modules/playwright-core/index.mjs";
const { chromium } = await import(PW);
const BASE = (process.env.BASE || "https://tradingaihub.com").replace(/\/$/, "");
const LOCALES = (process.env.LOCALES || "en,he,es,pt,de,fr,ja,ko,zh,hi,tr,ar,ru").split(",");
const CARD_KEYS = ["type", "official", "status", "scan", "secnote", "pricing", "stars"];
const TOOL_PAGES = ["claude-code-trading-terminal", "alpha-vantage-api", "alpaca-skills"];
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
// An open explanation must sit inside the 375 viewport (horizontally and vertically) and must not widen the page.
const tipInView = async (loc) => { const v = await loc.evaluate((t) => { const r = t.getBoundingClientRect(), vw = document.documentElement.clientWidth, vh = document.documentElement.clientHeight; return { l: Math.round(r.left), r: Math.round(r.right), t: Math.round(r.top), b: Math.round(r.bottom), vw, vh, sw: document.documentElement.scrollWidth }; });
  const good = v.l >= 0 && v.r <= v.vw && v.t >= 0 && v.b <= v.vh && v.sw <= v.vw; if (!good) console.log("  tip box", JSON.stringify(v)); return good; };

// Park a badge near the bottom of the viewport, tap it, and assert the open tip stays fully on screen.
async function assertTipAtBottom(page, badge, tipLoc, label) {
  await badge.scrollIntoViewIfNeeded();
  await page.evaluate((el) => {
    const r = el.getBoundingClientRect(), vh = document.documentElement.clientHeight;
    window.scrollBy(0, r.bottom - (vh - 8));
  }, await badge.elementHandle());
  await page.waitForTimeout(80);
  const box = await badge.boundingBox();
  // A badge near the top of the document cannot be scrolled to the bottom of the viewport; skip that case.
  if (!box || box.y + box.height < 667 - 80) {
    console.log(`  skip park ${label}: badge bottom ${box ? Math.round(box.y + box.height) : "none"}`);
    return;
  }
  await page.touchscreen.tap(box.x + box.width / 2, box.y + box.height / 2);
  await page.waitForTimeout(350);
  ok(await tipOpen(tipLoc), `${label}: explanation not open after bottom tap`);
  ok(await tipInView(tipLoc), `${label}: explanation not inside the viewport (vertical)`);
}

// Every visible badge must sit fully inside its row and the viewport; the page must not be horizontally overflowed.
async function assertBadgesFit(page, label) {
  const problems = await page.evaluate(() => {
    const vw = document.documentElement.clientWidth, sw = document.documentElement.scrollWidth, out = [];
    if (sw > vw + 1) out.push({ k: "page", issue: "overflow", sw, vw });
    for (const el of document.querySelectorAll("[data-xp-toggle]")) {
      const r = el.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) continue;
      const row = el.closest(".meta, .secnote-row, .sec-badge-row, .tool-head-meta, aside.partner, .partner-body, .secnote-wrap");
      const pr = row ? row.getBoundingClientRect() : null;
      const k = el.getAttribute("data-xp") || el.className;
      const text = (el.textContent || "").trim().slice(0, 48);
      if (r.left < -1 || r.right > vw + 1) out.push({ k, text, issue: "viewport", l: +r.left.toFixed(1), r: +r.right.toFixed(1), vw });
      if (pr && (r.left < pr.left - 1 || r.right > pr.right + 1 || r.top < pr.top - 1 || r.bottom > pr.bottom + 1))
        out.push({ k, text, issue: "row", l: +r.left.toFixed(1), r: +r.right.toFixed(1), t: +r.top.toFixed(1), b: +r.bottom.toFixed(1), pl: +pr.left.toFixed(1), pr: +pr.right.toFixed(1), pt: +pr.top.toFixed(1), pb: +pr.bottom.toFixed(1) });
    }
    return out;
  });
  ok(!problems.length, `${label}: badges not fully in row/viewport ${JSON.stringify(problems.slice(0, 6))}${problems.length > 6 ? ` (+${problems.length - 6})` : ""}`);
}

for (const l of LOCALES) {
  const c = await ctx(); const page = await c.newPage();
  // Cards: /tools/ lists every tool.
  const listUrl = `${BASE}${pre(l)}/tools/`;
  await page.goto(listUrl, { waitUntil: "domcontentloaded" });
  await assertBadgesFit(page, `${l} /tools/`);
  for (const k of CARD_KEYS) {
    await page.goto(listUrl, { waitUntil: "domcontentloaded" });
    const card = page.locator(`.card:has([data-xp-toggle][data-xp="${k}"])`).first();
    if (!(await card.count())) { ok(false, `${l} card: no ${k} badge found`); continue; }
    const badge = card.locator(`[data-xp-toggle][data-xp="${k}"]`).first();
    await tapEl(page, badge);
    ok(page.url() === listUrl, `${l} card ${k}: tap navigated to ${page.url()}`);
    ok(await tipOpen(card.locator(`.xp-tip[data-xp="${k}"]`)), `${l} card ${k}: explanation not open after tap`);
    ok(await tipInView(card.locator(`.xp-tip[data-xp="${k}"]`)), `${l} card ${k}: explanation outside the viewport`);
    await tapEl(page, page.locator("h1").first());
    ok(!(await card.locator(`.xp-tip[data-xp="${k}"]`).evaluate((t) => t.classList.contains("open"))), `${l} card ${k}: tap outside did not close`);
  }
  // Card body still navigates (stretched title link).
  await page.goto(listUrl, { waitUntil: "domcontentloaded" });
  const card = page.locator(".card:has([data-xp=secnote])").first();
  const href = await card.locator("a.card-link").getAttribute("href");
  await Promise.all([page.waitForURL((u) => u.pathname === href, { timeout: 8000 }).catch(() => {}), tapEl(page, card.locator("h3, .card-t").first())]);
  ok(new URL(page.url()).pathname === href, `${l} card body tap did not navigate (at ${page.url()}, want ${href})`);

  // Card badge parked near the bottom of the 375x667 viewport: the tip must flip/shift to stay on screen.
  await page.goto(listUrl, { waitUntil: "domcontentloaded" });
  {
    const bottomCard = page.locator(".card:has([data-xp-toggle][data-xp=\"status\"])").nth(20);
    const bottomBadge = bottomCard.locator("[data-xp-toggle][data-xp=\"status\"]").first();
    await assertTipAtBottom(page, bottomBadge, bottomCard.locator('.xp-tip[data-xp="status"]'), `${l} card status at bottom`);
  }

  // Tool pages: CCTT (stale, secnote), an official clean API, and an official+verified+scan head (alpaca-skills).
  for (const slug of TOOL_PAGES) {
    const url = `${BASE}${pre(l)}/tools/${slug}/`;
    await page.goto(url, { waitUntil: "domcontentloaded" });
    await assertBadgesFit(page, `${l} /tools/${slug}/`);
    // Related-tool cards on the same page are covered on /tools/; only the tool-head / secnote buttons here.
    const btns = page.locator(".xp-scope:not(.card) button[data-xp-toggle]");
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
      // Partner pill parked near the bottom of the viewport (the known overflow case on long-locale tool pages).
      await page.goto(url, { waitUntil: "domcontentloaded" });
      await assertTipAtBottom(page, aside.locator(".partner-tag"), aside.locator('.xp-tip[data-xp="partner"]'), `${l} ${slug} partner pill at bottom`);
    }
  }
  await c.close();
}
await browser.close();
console.log(`touch_badges: ${passes} passed, ${fails.length} failed (BASE ${BASE}, ${LOCALES.join("/")})`);
process.exit(fails.length ? 1 : 0);
