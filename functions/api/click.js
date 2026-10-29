// POST /api/click — anonymous, cookieless outbound-click counter (sent by navigator.sendBeacon from src/layouts/Base.astro).
// Body (JSON, sent as text/plain so the beacon needs no preflight), max 1 KB:
//   { t: tool id or "" , h: target host, k: "affiliate" | "partner" | "plain", p: page path, l: locale }
// Nothing personal is collected or stored: no cookies, no localStorage, no IP, no user agent, no fingerprint.
// KV (binding NEWSLETTER, shared with /api/subscribe; keys never collide):
//   click:<YYYY-MM-DD>:<tool id or ->:<kind>  -> {"n":N,"hosts":{host:N},"pages":{path:N},"locales":{code:N}}
//   crl:<sha256(RL_SALT|YYYY-MM-DD|ip)>        -> {"n":N,"seen":["tool|kind|host",...]}  expires after 1 day
// The crl hash includes the UTC date, so it rotates daily and can't link a visitor across days; the raw IP is never stored.
// It is used for the rate limit and for de-duplication (the same tool/kind/host counts once per visitor per day).
// Secret: RL_SALT (same as /api/subscribe). Without it nothing is counted.
// Counters are read-modify-write (Workers KV has no atomic increment), so simultaneous clicks may rarely undercount.
import tools from "../../data/tools.json" with { type: "json" };

const LOCALES = ["en", "he", "es", "pt", "de", "fr", "ja", "ko", "zh", "hi", "tr", "ar", "ru"];
const KINDS = ["affiliate", "partner", "plain"];
const MAX_BODY = 1024;       // bytes
const RATE_MAX = 60;         // beacons per visitor-hash per UTC day
const SEEN_MAX = 60;         // dedup entries kept per visitor-hash
const MAP_MAX = 100;         // distinct pages kept per counter (bounded value size)
const DAY = 86400;
// Outbound hosts that appear on the site but not in data/tools.json (share buttons, featured-on badges, package registries,
// affiliate programs, our Polar checkout). Compared without a leading "www.".
const STATIC_HOSTS = ["tradingview.com", "eodhd.com", "github.com", "npmjs.com", "pypi.org", "x.com", "reddit.com",
  "linkedin.com", "news.ycombinator.com", "fazier.com", "dang.ai", "buy.polar.sh"];
const BOT_RE = /bot|crawl|spider|slurp|bingpreview|facebookexternalhit|embedly|preview|lighthouse|headless|phantom|puppeteer|playwright|selenium|curl|wget|python|httpclient|okhttp|axios|node-fetch|go-http|java\/|libwww|scrapy/i;

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

async function sha256(s) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

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
  return { tool, host, kind, page, locale };
}

const bump = (map, key) => {
  if (key in map) map[key]++;
  else if (Object.keys(map).length < MAP_MAX) map[key] = 1;
  else map["(other)"] = (map["(other)"] || 0) + 1;
};

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  if (request.method !== "POST") return new Response(null, { status: 405, headers: { allow: "POST", "cache-control": "no-store" } });

  // Same-origin only (browsers send Origin on beacon POSTs). No CORS headers are ever emitted.
  if (request.headers.get("origin") !== url.origin) return res(403, "forbidden_origin");

  // Bots: the user agent is only tested here, never stored.
  const ua = request.headers.get("user-agent") || "";
  const cf = request.cf || {};
  if (!ua || BOT_RE.test(ua) || cf.verifiedBotCategory || (cf.botManagement && cf.botManagement.verifiedBot)) return res(204);

  const kv = env.NEWSLETTER;
  const salt = typeof env.RL_SALT === "string" ? env.RL_SALT : "";
  if (!kv || salt.length < 16) return res(204); // not configured: accept and drop, never break the page

  const text = await readLimited(request);
  if (text === null) return res(400, "bad_request");
  const ev = parseEvent(text);
  if (!ev) return res(400, "bad_request");

  try {
    const day = new Date().toISOString().slice(0, 10);
    const ip = request.headers.get("cf-connecting-ip") || "unknown";
    const rlKey = "crl:" + (await sha256(`${salt}|${day}|${ip}`));
    let rl = { n: 0, seen: [] };
    try { const v = JSON.parse((await kv.get(rlKey)) || "null"); if (v && Number.isInteger(v.n) && Array.isArray(v.seen)) rl = v; } catch {}
    if (rl.n >= RATE_MAX) return res(429, "rate_limited");
    const sig = `${ev.tool}|${ev.kind}|${ev.host}`;
    const dup = rl.seen.includes(sig);
    rl.n++;
    if (!dup && rl.seen.length < SEEN_MAX) rl.seen.push(sig);
    await kv.put(rlKey, JSON.stringify(rl), { expirationTtl: DAY });
    if (dup) return res(204);

    const key = `click:${day}:${ev.tool}:${ev.kind}`;
    let c = { n: 0, hosts: {}, pages: {}, locales: {} };
    try { const v = JSON.parse((await kv.get(key)) || "null"); if (v && Number.isInteger(v.n)) c = { hosts: {}, pages: {}, locales: {}, ...v }; } catch {}
    c.n++; bump(c.hosts, ev.host); bump(c.pages, ev.page); bump(c.locales, ev.locale);
    await kv.put(key, JSON.stringify(c));
    return res(204);
  } catch {
    return res(204); // KV hiccup (e.g. same-key write limit): drop the event quietly
  }
}
