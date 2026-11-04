// npm run test:functions: the public read-only API (functions/api/v1/[[path]].js, functions/api/openapi.json.js,
// functions/api/index.js) with a mocked env.ASSETS. No KV, no network.
import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { onRequest as v1 } from "../functions/api/v1/[[path]].js";
import { onRequest as openapi } from "../functions/api/openapi.json.js";
import { onRequest as apiIndex } from "../functions/api/index.js";
import { rateLimit, _rateLimitState, _resetDataCache, LIMITS } from "../functions/_lib/api.js";
import { makeAssets, freshIp, TOOLS } from "./fixtures/public-api.mjs";

const B = "https://tradingaihub.com";
async function call(path, { method = "GET", ip = freshIp(), env, headers = {} } = {}) {
  const url = new URL(path, B);
  const seg = url.pathname.replace(/^\/api\/v1\/?/, "").split("/").filter(Boolean);
  const request = new Request(url, { method, headers: { "cf-connecting-ip": ip, ...headers } });
  const res = await v1({ request, env: env ?? { ASSETS: makeAssets() }, params: seg.length ? { path: seg } : {} });
  const text = await res.text();
  return { res, text, body: text ? JSON.parse(text) : null };
}
test.beforeEach(() => { _resetDataCache(); _rateLimitState.reset(); });

test("index lists endpoints and the rate limit", async () => {
  const { res, body } = await call("/api/v1");
  assert.equal(res.status, 200);
  assert.ok(body.endpoints.includes(`${B}/api/v1/search?q=`));
  assert.equal(body.rate_limit.requests, LIMITS.api);
});

test("headers: JSON, CORS *, cache, rate-limit", async () => {
  const { res } = await call("/api/v1/tools");
  assert.match(res.headers.get("content-type"), /^application\/json/);
  assert.equal(res.headers.get("access-control-allow-origin"), "*");
  assert.equal(res.headers.get("cache-control"), "public, max-age=300, s-maxage=3600");
  assert.equal(res.headers.get("ratelimit-limit"), String(LIMITS.api));
  assert.equal(res.headers.get("ratelimit-remaining"), String(LIMITS.api - 1));
});

test("/tools: sorted, filters, pagination", async () => {
  let r = await call("/api/v1/tools");
  assert.equal(r.body.total, 4);
  assert.deepEqual(r.body.tools.map((t) => t.slug), ["alpha-vantage-mcp", "ccxt-mcp", "sec-edgar-api", "yfinance-mcp"]);
  assert.equal(r.body.next, null);
  r = await call("/api/v1/tools?category=market-data&verified=true");
  assert.deepEqual(r.body.tools.map((t) => t.slug), ["alpha-vantage-mcp"]);
  r = await call("/api/v1/tools?type=api");
  assert.deepEqual(r.body.tools.map((t) => t.slug), ["sec-edgar-api"]);
  r = await call("/api/v1/tools?language=python");
  assert.deepEqual(r.body.tools.map((t) => t.slug), ["yfinance-mcp"]);
  r = await call("/api/v1/tools?verified=false");
  assert.deepEqual(r.body.tools.map((t) => t.slug), ["yfinance-mcp"]);
  r = await call("/api/v1/tools?official=1&status=verified");
  assert.deepEqual(r.body.tools.map((t) => t.slug), ["alpha-vantage-mcp", "sec-edgar-api"]);
  r = await call("/api/v1/tools?limit=2&type=mcp");
  assert.equal(r.body.count, 2); assert.equal(r.body.total, 3);
  assert.equal(r.body.next, `${B}/api/v1/tools?limit=2&type=mcp&offset=2`);
  r = await call("/api/v1/tools?limit=2&offset=2&type=mcp");
  assert.deepEqual(r.body.tools.map((t) => t.slug), ["yfinance-mcp"]); assert.equal(r.body.next, null);
});

test("/tools: invalid parameters are 400 JSON with the allowed values", async () => {
  for (const [q, param] of [["category=nope", "category"], ["type=x", "type"], ["language=rust", "language"], ["status=bogus", "status"],
    ["verified=maybe", "verified"], ["limit=0", "limit"], ["limit=101", "limit"], ["limit=abc", "limit"], ["offset=-1", "offset"], ["offset=100001", "offset"]]) {
    const r = await call(`/api/v1/tools?${q}`);
    assert.equal(r.res.status, 400, q);
    assert.equal(r.body.error.code, "invalid_parameter");
    assert.equal(r.body.error.parameter, param);
    assert.equal(r.res.headers.get("access-control-allow-origin"), "*");
    assert.equal(r.res.headers.get("cache-control"), "no-store");
  }
  const r = await call("/api/v1/tools?category=nope");
  assert.deepEqual(r.body.error.allowed, ["market-data", "crypto", "research-filings"]);
  assert.equal((await call("/api/v1/tools?limit=100")).res.status, 200);
});

test("/tools/{slug} and JSON 404s", async () => {
  let r = await call("/api/v1/tools/ccxt-mcp");
  assert.equal(r.res.status, 200); assert.equal(r.body.tool.name, "CCXT MCP");
  for (const p of ["/api/v1/tools/nope", "/api/v1/tools/..%2Fx", "/api/v1/tools/a/b", "/api/v1/whatever"]) {
    r = await call(p);
    assert.equal(r.res.status, 404, p);
    assert.equal(r.body.error.code, "not_found");
    assert.match(r.res.headers.get("content-type"), /json/);
  }
});

test("/search: ranking, filters, caps", async () => {
  let r = await call("/api/v1/search?q=crypto");
  assert.equal(r.res.status, 200);
  assert.equal(r.body.tools[0].slug, "ccxt-mcp"); // name/category match beats description-only
  assert.ok(r.body.tools.some((t) => t.slug === "alpha-vantage-mcp"));
  r = await call("/api/v1/search?q=stock+prices");
  assert.equal(r.body.tools[0].slug, "yfinance-mcp"); // matches both words ("prices" folds to "price")
  assert.ok(r.body.tools.slice(1).some((t) => t.slug === "alpha-vantage-mcp")); // partial match ("stocks") ranks after
  r = await call("/api/v1/search?q=crypto&category=market-data");
  assert.deepEqual(r.body.tools.map((t) => t.slug), ["alpha-vantage-mcp"]);
  r = await call("/api/v1/search?q=mcp&limit=1");
  assert.equal(r.body.count, 1);
  r = await call("/api/v1/search?q=zzzz");
  assert.equal(r.body.count, 0);
  for (const q of ["", "q=", "q=%20", `q=${"a".repeat(101)}`, "q=x&limit=51", "q=x&type=nope"]) assert.equal((await call(`/api/v1/search?${q}`)).res.status, 400, q);
});

test("static dumps are served with CORS through the function", async () => {
  let r = await call("/api/v1/tools.json");
  assert.equal(r.res.status, 200); assert.equal(r.body.tools.length, TOOLS.length);
  assert.equal(r.res.headers.get("access-control-allow-origin"), "*");
  for (const p of ["/api/v1/categories", "/api/v1/categories.json"]) { r = await call(p); assert.equal(r.body.categories.length, 3); }
});

test("methods: OPTIONS preflight 204, HEAD no body, others 405", async () => {
  let r = await call("/api/v1/tools", { method: "OPTIONS" });
  assert.equal(r.res.status, 204);
  assert.equal(r.res.headers.get("access-control-allow-origin"), "*");
  assert.match(r.res.headers.get("access-control-allow-methods"), /GET/);
  r = await call("/api/v1/tools", { method: "HEAD" });
  assert.equal(r.res.status, 200); assert.equal(r.text, "");
  for (const m of ["POST", "PUT", "DELETE", "PATCH"]) {
    r = await call("/api/v1/tools", { method: m });
    assert.equal(r.res.status, 405, m);
    assert.equal(r.res.headers.get("allow"), "GET, HEAD, OPTIONS");
    assert.equal(r.body.error.code, "method_not_allowed");
  }
});

test("data comes from ASSETS and is cached per isolate; failure is 503 JSON", async () => {
  const assets = makeAssets();
  await call("/api/v1/tools", { env: { ASSETS: assets } });
  await call("/api/v1/search?q=crypto", { env: { ASSETS: assets } });
  assert.deepEqual(assets.calls.sort(), ["/api/v1/categories.json", "/api/v1/tools.json"]);
  _resetDataCache();
  const r = await call("/api/v1/tools", { env: { ASSETS: makeAssets({ fail: true }) } });
  assert.equal(r.res.status, 503); assert.equal(r.body.error.code, "unavailable");
  _resetDataCache();
  assert.equal((await call("/api/v1/tools", { env: {} })).res.status, 503);
});

test("rate limit: 429 + Retry-After after the limit, per IP, no KV", async () => {
  const ip = "203.0.113.7";
  const env = { ASSETS: makeAssets() }; // no KV binding at all: the limiter must not need one
  for (let i = 0; i < LIMITS.api; i++) assert.equal((await call("/api/v1/categories", { ip, env })).res.status, 200);
  const r = await call("/api/v1/categories", { ip, env });
  assert.equal(r.res.status, 429);
  assert.equal(r.body.error.code, "rate_limited");
  const ra = Number(r.res.headers.get("retry-after"));
  assert.ok(ra >= 1 && ra <= 60, String(ra));
  assert.equal(r.res.headers.get("ratelimit-remaining"), "0");
  assert.equal(r.res.headers.get("access-control-allow-origin"), "*");
  assert.equal((await call("/api/v1/categories", { ip: "203.0.113.8", env })).res.status, 200); // other IPs unaffected
});

test("rate limit: window resets, keys are hashed, memory is capped", async () => {
  const req = (ip) => new Request(`${B}/api/v1/tools`, { headers: { "cf-connecting-ip": ip } });
  const t0 = 1_000_000;
  for (let i = 0; i < 3; i++) await rateLimit(req("198.51.100.1"), "t", 3, t0);
  assert.equal((await rateLimit(req("198.51.100.1"), "t", 3, t0 + 1000)).ok, false);
  assert.equal((await rateLimit(req("198.51.100.1"), "t", 3, t0 + LIMITS.windowMs)).ok, true);
  for (const k of _rateLimitState.windows.keys()) { assert.ok(!k.includes("198.51.100.1")); assert.match(k, /^t:[0-9a-f]{24}$/); }
  _rateLimitState.reset();
  for (let i = 0; i < _rateLimitState.MAX_KEYS + 50; i++) await rateLimit(req(`ip-${i}`), "t", 3, t0 + i);
  assert.ok(_rateLimitState.size() <= _rateLimitState.MAX_KEYS);
});

test("/api/openapi.json via ASSETS with CORS; /api redirects to /developers/", async () => {
  const request = new Request(`${B}/api/openapi.json`, { headers: { "cf-connecting-ip": freshIp() } });
  const res = await openapi({ request, env: { ASSETS: makeAssets() } });
  assert.equal(res.status, 200);
  assert.equal((await res.json()).openapi, "3.1.0");
  assert.equal(res.headers.get("access-control-allow-origin"), "*");
  assert.equal((await openapi({ request: new Request(`${B}/api/openapi.json`, { method: "POST" }), env: {} })).status, 405);
  const r = await apiIndex({ request: new Request(`${B}/api/`) });
  assert.equal(r.status, 301);
  assert.equal(r.headers.get("location"), `${B}/developers/`);
});

// The built dump (dist/api/v1/tools.json, after `npm run build`) must carry no internals and no affiliate tags.
const DIST = new URL("../dist/api/v1/tools.json", import.meta.url);
test("built dump: no internals, no affiliate params", { skip: !existsSync(DIST) && "dist not built" }, () => {
  const text = readFileSync(DIST, "utf8");
  assert.doesNotMatch(text, /[?&](aff_id|via|_go)=/);
  for (const k of ["checks", "issues", "repo_keep", "source_url", "_note", "verification", "partner", "affiliate"]) assert.ok(!text.includes(`"${k}"`), k);
  const dump = JSON.parse(text);
  assert.ok(dump.tools.length >= 100);
  const keys = ["slug", "name", "type", "type_label", "category", "category_name", "description", "official", "url", "homepage", "docs", "repo", "remote_mcp_url", "license", "pricing", "languages", "packages", "status", "status_label", "verified", "checked_at", "github"];
  for (const t of dump.tools) {
    assert.deepEqual(Object.keys(t), keys, t.slug);
    assert.equal(t.url, `${B}/tools/${t.slug}/`);
    for (const l of t.languages) assert.ok(["javascript", "python"].includes(l));
  }
  const cats = JSON.parse(readFileSync(new URL("../dist/api/v1/categories.json", import.meta.url), "utf8"));
  assert.equal(cats.categories.reduce((s, c) => s + c.count, 0), dump.tools.length);
  const oa = JSON.parse(readFileSync(new URL("../dist/api/openapi.json", import.meta.url), "utf8"));
  assert.equal(oa.openapi, "3.1.0");
  for (const p of ["/api/v1/tools", "/api/v1/tools/{slug}", "/api/v1/search", "/api/v1/categories"]) assert.ok(oa.paths[p], p);
});
