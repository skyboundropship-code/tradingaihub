// Public read-only API v1 router: /api/v1, /api/v1/tools, /api/v1/tools/{slug}, /api/v1/search, /api/v1/categories,
// and the static dumps /api/v1/tools.json + /api/v1/categories.json (served from ASSETS so they get CORS, cache and the
// rate limit too). Scoped to /api/v1/* on purpose: /api/subscribe keeps its own handler and headers.
import { CORS, json, error, methodGate, rateLimit, tooMany, loadData, allowed, filterTools, searchTools, LIMITS, SITE } from "../../_lib/api.js";

const intParam = (sp, name, def, min, max) => {
  const raw = sp.get(name);
  if (raw == null || raw === "") return { v: def };
  if (!/^\d+$/.test(raw)) return { err: `${name} must be an integer between ${min} and ${max}` };
  const v = Number(raw);
  if (v < min || v > max) return { err: `${name} must be an integer between ${min} and ${max}` };
  return { v };
};
const boolParam = (sp, name) => {
  const raw = sp.get(name);
  if (raw == null || raw === "") return { v: null };
  if (/^(true|1|yes)$/i.test(raw)) return { v: true };
  if (/^(false|0|no)$/i.test(raw)) return { v: false };
  return { err: `${name} must be true or false` };
};

export async function onRequest({ request, env, params }) {
  const gate = methodGate(request);
  if (gate) return gate;
  const m = request.method;
  const rl = await rateLimit(request, "api", LIMITS.api);
  if (!rl.ok) return tooMany(rl, m);
  const h = rl.headers;
  const seg = [].concat(params?.path ?? []).filter(Boolean);
  const url = new URL(request.url);
  const sp = url.searchParams;
  let data;
  try { data = await loadData(env, request); } catch { return error(503, "unavailable", "Data temporarily unavailable. Try again shortly.", {}, h, m); }
  const bad = (msg, extra = {}) => error(400, "invalid_parameter", msg, extra, h, m);

  if (seg.length === 0) {
    return json({ name: "TradingAIHub public API", version: data.dump.api_version, docs: `${SITE}/developers/`, openapi: `${SITE}/api/openapi.json`, mcp: `${SITE}/mcp`,
      endpoints: ["/api/v1/tools", "/api/v1/tools/{slug}", "/api/v1/search?q=", "/api/v1/categories", "/api/v1/tools.json", "/api/v1/categories.json"].map((p) => SITE + p),
      rate_limit: { requests: LIMITS.api, window_seconds: LIMITS.windowMs / 1000, scope: "per IP, per edge instance" } }, 200, h, m);
  }
  const [a, b, ...rest] = seg;
  if (rest.length) return error(404, "not_found", "Unknown endpoint. See /api/openapi.json.", {}, h, m);

  if (a === "tools.json" && !b) return json(data.toolsText, 200, h, m);
  if ((a === "categories" || a === "categories.json") && !b) return json(data.catsText, 200, h, m);

  if (a === "tools" && !b) {
    const al = allowed(data), f = {};
    for (const k of ["category", "type", "language", "status"]) {
      const v = sp.get(k);
      if (v == null || v === "") continue;
      if (!al[k].includes(v)) return bad(`Unknown ${k} "${v.slice(0, 60)}".`, { parameter: k, allowed: al[k] });
      f[k] = v;
    }
    for (const k of ["verified", "official"]) { const r = boolParam(sp, k); if (r.err) return bad(r.err, { parameter: k }); f[k] = r.v; }
    const lim = intParam(sp, "limit", 50, 1, 100); if (lim.err) return bad(lim.err, { parameter: "limit" });
    const off = intParam(sp, "offset", 0, 0, 100000); if (off.err) return bad(off.err, { parameter: "offset" });
    const all = filterTools(data.dump.tools, f).sort((x, y) => x.name.localeCompare(y.name));
    const page = all.slice(off.v, off.v + lim.v);
    let next = null;
    if (off.v + lim.v < all.length) { const n = new URL(url.pathname, SITE); for (const [k, v] of sp) n.searchParams.set(k, v); n.searchParams.set("offset", String(off.v + lim.v)); n.searchParams.set("limit", String(lim.v)); next = n.href; }
    return json({ total: all.length, count: page.length, limit: lim.v, offset: off.v, next, tools: page }, 200, h, m);
  }

  if (a === "tools" && b) {
    const t = /^[a-z0-9-]{1,100}$/.test(b) ? data.bySlug.get(b) : null;
    if (!t) return error(404, "not_found", `No tool with slug "${b.slice(0, 100)}". List slugs at /api/v1/tools.`, {}, h, m);
    return json({ tool: t }, 200, h, m);
  }

  if (a === "search" && !b) {
    const q = (sp.get("q") ?? "").trim();
    if (!q) return bad("q is required, e.g. /api/v1/search?q=stock+prices", { parameter: "q" });
    if (q.length > 100) return bad("q must be at most 100 characters", { parameter: "q" });
    const al = allowed(data), f = {};
    for (const k of ["category", "type"]) {
      const v = sp.get(k);
      if (v == null || v === "") continue;
      if (!al[k].includes(v)) return bad(`Unknown ${k} "${v.slice(0, 60)}".`, { parameter: k, allowed: al[k] });
      f[k] = v;
    }
    const lim = intParam(sp, "limit", 10, 1, 50); if (lim.err) return bad(lim.err, { parameter: "limit" });
    const tools = searchTools(filterTools(data.dump.tools, f), q, lim.v);
    return json({ query: q, count: tools.length, tools }, 200, h, m);
  }

  return error(404, "not_found", "Unknown endpoint. See /api/openapi.json.", {}, h, m);
}
