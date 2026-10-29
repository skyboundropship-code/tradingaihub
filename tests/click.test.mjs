// npm run test:functions — unit tests for functions/api/click.js with a mocked KV (no network).
import test from "node:test";
import assert from "node:assert/strict";
import { onRequest, parseEvent, HOSTS, TOOL_IDS } from "../functions/api/click.js";

const ORIGIN = "https://tradingaihub.com";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36";
const SALT = "s".repeat(32);
const day = () => new Date().toISOString().slice(0, 10);

function makeKV() {
  const m = new Map(), opts = new Map();
  return { m, opts, async get(k) { return m.has(k) ? m.get(k) : null; }, async put(k, v, o) { m.set(k, v); opts.set(k, o); } };
}
const ev = (o = {}) => ({ t: "alpha-vantage-api", h: "www.alphavantage.co", k: "plain", p: "/tools/alpha-vantage-api/", l: "en", ...o });
function req(body, { origin = ORIGIN, ip = "1.2.3.4", ua = UA, method = "POST", type = "text/plain;charset=UTF-8", cf } = {}) {
  const r = new Request(ORIGIN + "/api/click", {
    method, headers: { ...(origin ? { origin } : {}), ...(ua ? { "user-agent": ua } : {}), "content-type": type, "cf-connecting-ip": ip },
    body: method === "POST" ? (typeof body === "string" ? body : JSON.stringify(body)) : undefined,
  });
  if (cf) Object.defineProperty(r, "cf", { value: cf });
  return r;
}
const env = (kv, extra = {}) => ({ NEWSLETTER: kv, RL_SALT: SALT, ...extra });
const call = (r, e) => onRequest({ request: r, env: e });

test("valid beacon increments the daily counter with host/page/locale breakdown", async () => {
  const kv = makeKV();
  const res = await call(req(ev({ p: "/he/tools/alpha-vantage-api/", l: "he" })), env(kv));
  assert.equal(res.status, 204);
  const key = `click:${day()}:alpha-vantage-api:plain`;
  assert.deepEqual(JSON.parse(kv.m.get(key)), { n: 1, hosts: { "alphavantage.co": 1 }, pages: { "/tools/alpha-vantage-api/": 1 }, locales: { he: 1 } });
});

test("affiliate and partner kinds and site-wide links (no tool) get their own keys", async () => {
  const kv = makeKV();
  assert.equal((await call(req(ev({ t: "", h: "www.tradingview.com", k: "partner", p: "/" })), env(kv))).status, 204);
  assert.equal((await call(req(ev({ t: "", h: "eodhd.com", k: "affiliate", p: "/compare/x/" })), env(kv))).status, 204);
  assert.ok(kv.m.has(`click:${day()}:-:partner`));
  assert.ok(kv.m.has(`click:${day()}:-:affiliate`));
});

test("same visitor, same tool/kind/host on the same day counts once; a different visitor counts again", async () => {
  const kv = makeKV();
  await call(req(ev()), env(kv)); await call(req(ev()), env(kv));
  const key = `click:${day()}:alpha-vantage-api:plain`;
  assert.equal(JSON.parse(kv.m.get(key)).n, 1);
  await call(req(ev(), { ip: "5.6.7.8" }), env(kv));
  assert.equal(JSON.parse(kv.m.get(key)).n, 2);
});

test("nothing personal is stored: no raw IP or UA anywhere, visitor key is a salted daily hash that expires", async () => {
  const kv = makeKV();
  await call(req(ev(), { ip: "203.0.113.77" }), env(kv));
  const dump = JSON.stringify([...kv.m.entries()]);
  assert.ok(!dump.includes("203.0.113.77")); assert.ok(!dump.includes("Mozilla")); assert.ok(!dump.includes(SALT));
  const rl = [...kv.m.keys()].find((k) => k.startsWith("crl:"));
  assert.match(rl, /^crl:[0-9a-f]{64}$/);
  assert.equal(kv.opts.get(rl).expirationTtl, 86400);
  assert.deepEqual(Object.keys(JSON.parse(kv.m.get(rl))).sort(), ["n", "seen"]);
});

test("rate limit: 429 after 60 beacons per visitor per day", async () => {
  const kv = makeKV();
  const ids = [...TOOL_IDS];
  let last;
  for (let i = 0; i < 61; i++) last = await call(req(ev({ t: ids[i % ids.length], h: "github.com" })), env(kv));
  assert.equal(last.status, 429);
});

test("bots, headless browsers and missing UA are ignored (204, nothing written)", async () => {
  for (const ua of ["Googlebot/2.1", "Mozilla/5.0 HeadlessChrome/130", "curl/8.0", "python-requests/2", ""]) {
    const kv = makeKV();
    const res = await call(req(ev(), { ua }), env(kv));
    assert.equal(res.status, 204); assert.equal(kv.m.size, 0, ua);
  }
  const kv = makeKV();
  assert.equal((await call(req(ev(), { cf: { verifiedBotCategory: "Search Engine Crawler" } }), env(kv))).status, 204);
  assert.equal(kv.m.size, 0);
});

test("cross-origin or missing Origin is refused; GET is 405", async () => {
  const kv = makeKV();
  assert.equal((await call(req(ev(), { origin: "https://evil.example" }), env(kv))).status, 403);
  assert.equal((await call(req(ev(), { origin: null }), env(kv))).status, 403);
  assert.equal((await call(req(null, { method: "GET" }), env(kv))).status, 405);
  assert.equal(kv.m.size, 0);
});

test("allowlist: unknown host, tool id, kind, locale or bad path is rejected without writing", async () => {
  const bad = [ev({ h: "evil.example" }), ev({ t: "not-a-tool" }), ev({ k: "other" }), ev({ l: "xx" }), ev({ p: "https://x.com/" }),
    ev({ p: "/a//b" }), ev({ p: "/../x" }), ev({ p: "/x?q=1" }), ev({ p: "/" + "a".repeat(250) }), ev({ h: 5 }), ev({ t: ["x"] })];
  for (const b of bad) {
    const kv = makeKV();
    const res = await call(req(b), env(kv));
    assert.equal(res.status, 400, JSON.stringify(b)); assert.equal(kv.m.size, 0);
  }
  for (const s of ["not json", "[]", "null"]) assert.equal((await call(req(s), env(makeKV()))).status, 400);
});

test("oversized body is refused", async () => {
  const kv = makeKV();
  assert.equal((await call(req(JSON.stringify({ ...ev(), pad: "x".repeat(2000) })), env(kv))).status, 400);
  assert.equal(kv.m.size, 0);
});

test("not configured (no KV or no salt): accepted and dropped", async () => {
  assert.equal((await call(req(ev()), { RL_SALT: SALT })).status, 204);
  const kv = makeKV();
  assert.equal((await call(req(ev()), { NEWSLETTER: kv })).status, 204);
  assert.equal(kv.m.size, 0);
});

test("KV failure never surfaces as an error", async () => {
  const kv = { async get() { throw new Error("kv down"); }, async put() { throw new Error("kv down"); } };
  assert.equal((await call(req(ev()), env(kv))).status, 204);
});

test("host allowlist covers share/featured/registry/affiliate hosts and www-normalises", () => {
  for (const h of ["tradingview.com", "eodhd.com", "github.com", "x.com", "reddit.com", "linkedin.com", "news.ycombinator.com", "fazier.com", "dang.ai", "npmjs.com", "pypi.org"]) assert.ok(HOSTS.has(h), h);
  assert.ok(parseEvent(JSON.stringify(ev({ h: "WWW.TradingView.com." }))));
  assert.equal(parseEvent(JSON.stringify(ev({ h: "tradingview.com.evil.example" }))), null);
  assert.equal(parseEvent(JSON.stringify(ev({ h: "eviltradingview.com" }))), null);
});

test("counter page map is bounded", async () => {
  const kv = makeKV();
  for (let i = 0; i < 105; i++) await call(req(ev({ t: "", h: "github.com", p: `/p${i}/` }), { ip: `10.0.0.${i}` }), env(kv));
  const c = JSON.parse(kv.m.get(`click:${day()}:-:plain`));
  assert.equal(c.n, 105); assert.equal(Object.keys(c.pages).length, 101); assert.equal(c.pages["(other)"], 5);
});
