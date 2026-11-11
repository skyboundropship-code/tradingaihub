// POST /api/click — anonymous, cookieless outbound-click counter (sent by navigator.sendBeacon from src/layouts/Base.astro).
// Links are never rewritten or redirected through us: the browser follows the original href (affiliate tags intact)
// and this beacon is fire-and-forget, so there is no redirect and no open-redirect surface.
// Body (JSON, sent as text/plain so the beacon needs no preflight), max 1 KB:
//   { t: tool id or "", h: target host, k: "affiliate" | "partner" | "plain", p: page path, l: locale, r: referrer host or "" }
// Nothing personal is collected or stored: no cookies, no localStorage, no IP, no user agent, no fingerprint.
//
// Storage: Workers Analytics Engine (binding CLICKS, see wrangler.toml). One datapoint per accepted beacon and ZERO KV
// reads or writes, so clicks can never use up the account-wide KV free-tier write budget the newsletter depends on.
//   indexes: [affiliate id]
//   blobs:   [tool id or "-", affiliate id, kind, target host, locale, page path, referrer host, is_bot "0"/"1", source]
//   doubles: [1]
// affiliate id = program name for affiliate/partner hosts (tradingview, eodhd, polar, ...), "-" for plain links.
// Our own and automated traffic is still written but tagged is_bot="1" so reports exclude it:
//   - user agents matching BOT_RE (crawlers, headless browsers, curl, python, ...) or Cloudflare verified bots -> source "bot"
//   - requests carrying the header `x-tah-qa: 1` (sent by our QA/test scripts) -> source "qa"
// Reports: `npm run clicks` (scripts/clicks.mjs) via the Analytics Engine SQL API.
// Without the CLICKS binding the beacon is accepted and dropped (204), never breaking the page.
import tools from "../../data/tools.json" with { type: "json" };

const LOCALES = ["en", "he", "es", "pt", "de", "fr", "ja", "ko", "zh", "hi", "tr", "ar", "ru"];
const KINDS = ["affiliate", "partner", "plain"];
const MAX_BODY = 1024;       // bytes
// Write cap per isolate (no IP or client key is ever used): at most RATE_MAX accepted datapoints per RATE_WINDOW_MS.
// Over the cap the beacon gets 429 and nothing is written. Bounds abuse of the AE free tier (100k datapoints/day).
export const RATE_MAX = 120;
export const RATE_WINDOW_MS = 60_000;
let rateStart = 0, rateCount = 0;
export function _resetRate() { rateStart = 0; rateCount = 0; }
function rateOk(now = Date.now()) {
  if (now - rateStart >= RATE_WINDOW_MS) { rateStart = now; rateCount = 0; }
  if (rateCount >= RATE_MAX) return false;
  rateCount++; return true;
}
// Affiliate / partner program ids by target host (without "www.").
export const AFFILIATES = { "tradingview.com": "tradingview", "eodhd.com": "eodhd", "buy.polar.sh": "polar" };
// Outbound hosts that appear on the site but not in data/tools.json (share buttons, featured-on badges, package registries,
// affiliate programs, our Polar checkout). Compared without a leading "www.".
const STATIC_HOSTS = ["tradingview.com", "eodhd.com", "github.com", "npmjs.com", "pypi.org", "x.com", "reddit.com",
  "linkedin.com", "news.ycombinator.com", "fazier.com", "dang.ai", "buy.polar.sh"];
export const BOT_RE = /bot|crawl|spider|slurp|bingpreview|facebookexternalhit|embedly|preview|lighthouse|headless|phantom|puppeteer|playwright|selenium|curl|wget|python|httpclient|okhttp|axios|node-fetch|go-http|java\/|libwww|scrapy/i;

const norm = (h) => String(h).toLowerCase().replace(/\.$/, "").replace(/^www\./, "");
const hostOf = (u) => { try { return u ? norm(new URL(u).hostname) : null; } catch { return null; } };
export const TOOL_IDS = new Set(tools.map((t) => t.id));
export const HOSTS = new Set(STATIC_HOSTS);
for (const t of tools) for (const u of [t.repo, t.homepage, t.docs, t.source_url, t.remote_mcp_url, t.pricing && t.pricing.source]) {
  const h = hostOf(u); if (h) HOSTS.add(h);
}

const res = (status, error) => new Response(error ? JSON.stringify({ ok: false, error }) : null, {
  status,
  headers: { ...(error ? { "content-type": "application/json; charset=utf-8" } : {}), "cache-control": "no-store", "x-content-type-options": "nosniff" },
});

async function readLimited(request) {
  const cl = request.headers.get("content-length");
  if (cl !== null && (!/^\d+$/.test(cl) || Number(cl) > MAX_BODY)) return null;
  if (!request.body) return null;
  const reader = request.body.getReader();
  const chunks = []; let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > MAX_BODY) { try { await reader.cancel(); } catch {} return null; }
    chunks.push(value);
  }
  const buf = new Uint8Array(size); let off = 0;
  for (const c of chunks) { buf.set(c, off); off += c.byteLength; }
  return new TextDecoder().decode(buf);
}

/** Validates the beacon payload. Returns the cleaned event or null. Unknown hosts/ids/kinds/locales are rejected. */
export function parseEvent(text) {
  let o; try { o = JSON.parse(text); } catch { return null; }
  if (!o || typeof o !== "object" || Array.isArray(o)) return null;
  const host = typeof o.h === "string" && o.h.length <= 253 ? norm(o.h) : "";
  if (!HOSTS.has(host)) return null;
  const kind = KINDS.includes(o.k) ? o.k : null;
  if (!kind) return null;
  const tool = o.t === "" || o.t == null ? "-" : (typeof o.t === "string" && TOOL_IDS.has(o.t) ? o.t : null);
  if (!tool) return null;
  const locale = LOCALES.includes(o.l) ? o.l : null;
  if (!locale) return null;
  // Page path: site-relative, no query/fragment, locale prefix removed so all locales share one page key.
  if (typeof o.p !== "string" || o.p.length > 200 || !/^\/[a-z0-9\-_/.]*$/i.test(o.p) || o.p.includes("//") || o.p.includes("..")) return null;
  let page = o.p.toLowerCase();
  const m = page.match(/^\/([a-z]{2})(\/.*|$)/);
  if (m && LOCALES.includes(m[1]) && m[1] !== "en") page = m[2] || "/";
  if (!page.endsWith("/") && !/\.[a-z0-9]+$/.test(page)) page += "/";
  let ref = "";
  if (o.r != null && o.r !== "") {
    if (typeof o.r !== "string" || o.r.length > 253) return null;
    ref = norm(o.r);
    if (!/^[a-z0-9.-]+$/.test(ref)) return null;
  }
  const affiliate = kind === "plain" ? "-" : (AFFILIATES[host] || host.split(".").slice(-2, -1)[0] || host);
  return { tool, host, kind, page, locale, ref: ref || "(direct)", affiliate };
}

/** Bot / QA classification. Returns "bot", "qa" or "" (human). The UA is only tested here, never stored. */
export function classify(request) {
  if (request.headers.get("x-tah-qa") === "1") return "qa";
  const ua = request.headers.get("user-agent") || "";
  const cf = request.cf || {};
  if (!ua || BOT_RE.test(ua) || cf.verifiedBotCategory || (cf.botManagement && cf.botManagement.verifiedBot)) return "bot";
  return "";
}

export function datapoint(ev, source) {
  return {
    indexes: [ev.affiliate],
    blobs: [ev.tool, ev.affiliate, ev.kind, ev.host, ev.locale, ev.page, ev.ref, source ? "1" : "0", source || "human"],
    doubles: [1],
  };
}

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  if (request.method !== "POST") return new Response(null, { status: 405, headers: { allow: "POST", "cache-control": "no-store" } });

  // Same-origin only (browsers send Origin on beacon POSTs). No CORS headers are ever emitted.
  if (request.headers.get("origin") !== url.origin) return res(403, "forbidden_origin");

  const text = await readLimited(request);
  if (text === null) return res(400, "bad_request");
  const ev = parseEvent(text);
  if (!ev) return res(400, "bad_request");

  const ae = env.CLICKS;
  if (!ae || typeof ae.writeDataPoint !== "function") return res(204); // not configured: accept and drop
  if (!rateOk()) return res(429, "rate_limited");
  try { ae.writeDataPoint(datapoint(ev, classify(request))); } catch {} // non-blocking; never surfaces as an error
  return res(204);
}
