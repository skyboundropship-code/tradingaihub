// Shared runtime for the public read-only API (/api/v1/*, /api/openapi.json) and the MCP server (/mcp).
// Not a route: wrangler only builds routes from files that export onRequest*, so functions/_lib/ is import-only.
// Data comes from the static dump dist/api/v1/tools.json (built from src/lib/publicApi.ts) via env.ASSETS, cached per isolate.
// No KV anywhere: KV free-tier writes (1,000/day) are reserved for the newsletter.

export const SITE = "https://tradingaihub.com";
export const CACHE_OK = "public, max-age=300, s-maxage=3600";
export const LIMITS = { api: 120, mcp: 60, windowMs: 60_000 };
const DATA_TTL_MS = 300_000;
const MAX_KEYS = 10_000;

export const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, HEAD, OPTIONS",
  "access-control-allow-headers": "content-type, accept, if-none-match",
  "access-control-expose-headers": "ratelimit-limit, ratelimit-remaining, ratelimit-reset, retry-after, etag",
  "access-control-max-age": "86400",
};

export function json(body, status = 200, headers = {}, method = "GET") {
  const h = new Headers({ "content-type": "application/json; charset=utf-8", "x-content-type-options": "nosniff", ...CORS, "cache-control": status === 200 ? CACHE_OK : status === 404 ? "public, max-age=60" : "no-store", ...headers });
  return new Response(method === "HEAD" ? null : typeof body === "string" ? body : JSON.stringify(body), { status, headers: h });
}
export const error = (status, code, message, extra = {}, headers = {}, method) => json({ error: { status, code, message, ...extra } }, status, headers, method);

/** OPTIONS -> 204 preflight; anything but GET/HEAD -> 405. Returns a Response to send, or null to continue. */
export function methodGate(request, cors = CORS) {
  const m = request.method;
  if (m === "OPTIONS") return new Response(null, { status: 204, headers: { ...cors, "cache-control": "public, max-age=86400" } });
  if (m !== "GET" && m !== "HEAD") return error(405, "method_not_allowed", `${m} is not allowed. This API is read-only: use GET.`, {}, { allow: "GET, HEAD, OPTIONS" });
  return null;
}

// ---- Rate limit: in-memory, per isolate. Cloudflare Pages Functions have no Rate Limiting binding and KV writes are
// reserved, so each isolate keeps a fixed-window counter per (bucket, hashed IP). The key is SHA-256 of a random
// per-isolate salt + the IP, truncated: raw IPs are never stored, and keys can't be correlated across isolates.
// A client spread over several edge isolates can exceed the nominal limit; the limit is a ceiling for abuse, not a quota.
let salt = null; // created on first use: no random generation in global scope
const windows = new Map(); // key -> { start, n }
async function ipKey(bucket, ip) {
  salt ??= [...crypto.getRandomValues(new Uint8Array(16))].join(".");
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`${salt}|${ip}`));
  return bucket + ":" + [...new Uint8Array(d).slice(0, 12)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
function prune(now) {
  for (const [k, w] of windows) if (now - w.start >= LIMITS.windowMs) windows.delete(k);
  while (windows.size >= MAX_KEYS) windows.delete(windows.keys().next().value); // oldest first (Map insertion order)
}
/** Returns { ok, headers, retryAfter }. `limit` requests per LIMITS.windowMs per IP per isolate. */
export async function rateLimit(request, bucket, limit, now = Date.now()) {
  const ip = request.headers.get("cf-connecting-ip") || request.headers.get("x-real-ip") || "unknown";
  const key = await ipKey(bucket, ip);
  let w = windows.get(key);
  if (!w || now - w.start >= LIMITS.windowMs) {
    if (!w && windows.size >= MAX_KEYS) prune(now);
    w = { start: now, n: 0 };
    windows.delete(key); windows.set(key, w);
  }
  w.n++;
  const reset = Math.max(1, Math.ceil((w.start + LIMITS.windowMs - now) / 1000));
  const headers = { "ratelimit-limit": String(limit), "ratelimit-remaining": String(Math.max(0, limit - w.n)), "ratelimit-reset": String(reset) };
  if (w.n > limit) return { ok: false, retryAfter: reset, headers: { ...headers, "retry-after": String(reset) } };
  return { ok: true, headers };
}
export const _rateLimitState = { windows, reset: () => windows.clear(), size: () => windows.size, MAX_KEYS };
export const tooMany = (rl, method) => error(429, "rate_limited", `Too many requests. Retry after ${rl.retryAfter} s.`, { retry_after: rl.retryAfter }, rl.headers, method);

// ---- Data
let cache = null; // { at, dump, bySlug }
export async function loadData(env, request) {
  if (cache && Date.now() - cache.at < DATA_TTL_MS) return cache;
  if (!env?.ASSETS) throw new Error("ASSETS binding missing");
  const [tr, cr] = await Promise.all([
    env.ASSETS.fetch(new Request(new URL("/api/v1/tools.json", request.url))),
    env.ASSETS.fetch(new Request(new URL("/api/v1/categories.json", request.url))),
  ]);
  if (!tr.ok || !cr.ok) throw new Error(`data dump unavailable (${tr.status}/${cr.status})`);
  const dump = await tr.json(), cats = await cr.json();
  cache = { at: Date.now(), dump, cats, toolsText: JSON.stringify(dump), catsText: JSON.stringify(cats), bySlug: new Map(dump.tools.map((t) => [t.slug, t])) };
  return cache;
}
export const _resetDataCache = () => { cache = null; };

// ---- Query helpers (shared by REST and MCP so both give identical answers)
export const FILTER_KEYS = ["category", "type", "language", "status"];
export function allowed(data) {
  const t = data.dump.tools;
  const uniq = (f) => [...new Set(t.flatMap(f))].filter(Boolean).sort();
  return { category: data.cats.categories.map((c) => c.slug), type: uniq((x) => [x.type]), language: uniq((x) => x.languages), status: uniq((x) => [x.status]) };
}
export function filterTools(tools, f) {
  return tools.filter((t) => (!f.category || t.category === f.category) && (!f.type || t.type === f.type) && (!f.language || t.languages.includes(f.language))
    && (!f.status || t.status === f.status) && (f.verified == null || t.verified === f.verified) && (f.official == null || t.official === f.official));
}
const norm = (s) => String(s ?? "").toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g, "");
/** Ranked keyword search (substring, plurals folded). Tools matching every word come first, then tools matching some of
 *  the words (more words first); within that: name > slug > package > category > description, then verified, then stars. */
export function searchTools(tools, q, limit) {
  // Light plural folding ("prices" -> "price") so natural queries match.
  const words = [...new Set(norm(q).split(/[^a-z0-9.+#-]+/).filter(Boolean).slice(0, 10).map((w) => (w.length > 3 && w.endsWith("s") && !w.endsWith("ss") ? w.slice(0, -1) : w)))];
  if (!words.length) return [];
  const scored = [];
  for (const t of tools) {
    const name = norm(t.name), slug = norm(t.slug), desc = norm(t.description), cat = norm(`${t.category} ${t.category_name} ${t.type} ${t.type_label}`);
    const pk = norm([t.packages?.npm?.name, t.packages?.pypi?.name].filter(Boolean).join(" "));
    let score = 0, hits = 0;
    for (const w of words) {
      const s = (name.includes(w) ? 10 : 0) + (slug.includes(w) ? 6 : 0) + (pk.includes(w) ? 4 : 0) + (cat.includes(w) ? 3 : 0) + (desc.includes(w) ? 2 : 0);
      if (!s) continue;
      hits++;
      score += s + (new RegExp(`(^|[^a-z0-9])${w.replace(/[.+#-]/g, "\\$&")}([^a-z0-9]|$)`).test(name) ? 5 : 0);
    }
    if (hits) scored.push({ t, score, hits });
  }
  scored.sort((a, b) => b.hits - a.hits || b.score - a.score || Number(b.t.verified) - Number(a.t.verified) || (b.t.github?.stars ?? -1) - (a.t.github?.stars ?? -1) || a.t.name.localeCompare(b.t.name));
  return scored.slice(0, limit).map((x) => x.t);
}
