// npm run test:functions — unit tests for functions/api/click.js with a mocked Analytics Engine binding (no network).
// QA scripts must send the header `x-tah-qa: 1` so their clicks are tagged is_bot=1 and excluded from reports.
import test from "node:test";
import assert from "node:assert/strict";
import { onRequest, parseEvent, HOSTS, TOOL_IDS, classify } from "../functions/api/click.js";

const ORIGIN = "https://tradingaihub.com";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36";
function makeAE() { const ae = { points: [], writeDataPoint(p) { ae.points.push(p); } }; return ae; }
function makeKV() { const kv = { n: 0, async get() { kv.n++; return null; }, async put() { kv.n++; } }; return kv; }
const ev = (o = {}) => ({ t: "alpha-vantage-api", h: "www.alphavantage.co", k: "plain", p: "/tools/alpha-vantage-api/", l: "en", ...o });
function req(body, { origin = ORIGIN, ua = UA, method = "POST", headers = {}, cf } = {}) {
  const h = { "content-type": "text/plain;charset=UTF-8", "cf-connecting-ip": "1.2.3.4", ...headers };
  if (origin) h.origin = origin; if (ua) h["user-agent"] = ua;
  const r = new Request(ORIGIN + "/api/click", { method, headers: h, body: method === "POST" && body != null ? (typeof body === "string" ? body : JSON.stringify(body)) : undefined });
  if (cf) Object.defineProperty(r, "cf", { value: cf });
  return r;
}
const call = (r, env) => onRequest({ request: r, env });

test("valid beacon writes exactly one AE datapoint with all dimensions and zero KV ops", async () => {
  const ae = makeAE(), kv = makeKV();
  const res = await call(req(ev({ p: "/he/tools/alpha-vantage-api/", l: "he", r: "www.Google.com" })), { CLICKS: ae, NEWSLETTER: kv });
  assert.equal(res.status, 204);
  assert.equal(kv.n, 0);
  assert.deepEqual(ae.points, [{ indexes: ["-"], blobs: ["alpha-vantage-api", "-", "plain", "alphavantage.co", "he", "/tools/alpha-vantage-api/", "google.com", "0", "human"], doubles: [1] }]);
});

test("affiliate ids: tradingview, eodhd, polar; partner fallback = host label; direct referrer", async () => {
  const ae = makeAE();
  await call(req(ev({ h: "www.tradingview.com", k: "affiliate", t: "" })), { CLICKS: ae });
  await call(req(ev({ h: "eodhd.com", k: "partner" })), { CLICKS: ae });
  await call(req(ev({ h: "buy.polar.sh", k: "affiliate", t: "" })), { CLICKS: ae });
  await call(req(ev({ h: "github.com", k: "partner" })), { CLICKS: ae });
  assert.deepEqual(ae.points.map((p) => p.blobs[1]), ["tradingview", "eodhd", "polar", "github"]);
  assert.equal(ae.points[0].blobs[0], "-"); assert.equal(ae.points[0].blobs[6], "(direct)");
});

test("bots, headless, curl, python, missing UA and verified bots are tagged is_bot=1 source=bot", async () => {
  for (const ua of ["Googlebot/2.1", "Mozilla/5.0 HeadlessChrome/130", "curl/8.0", "python-requests/2", "", "Mozilla/5.0 (compatible; GPTBot/1.0)"]) {
    const ae = makeAE();
    assert.equal((await call(req(ev(), { ua }), { CLICKS: ae })).status, 204);
    assert.equal(ae.points[0].blobs[7], "1", ua); assert.equal(ae.points[0].blobs[8], "bot");
  }
  const ae = makeAE();
  await call(req(ev(), { cf: { verifiedBotCategory: "Search Engine Crawler" } }), { CLICKS: ae });
  assert.equal(ae.points[0].blobs[7], "1");
});

test("x-tah-qa: 1 header tags QA traffic is_bot=1 source=qa, even with a browser UA", async () => {
  const ae = makeAE();
  await call(req(ev(), { headers: { "x-tah-qa": "1" } }), { CLICKS: ae });
  assert.deepEqual(ae.points[0].blobs.slice(7), ["1", "qa"]);
  assert.equal(classify(req(ev(), { headers: { "x-tah-qa": "0" } })), "");
});

test("nothing personal is stored: no IP or UA in the datapoint", async () => {
  const ae = makeAE();
  await call(req(ev()), { CLICKS: ae });
  const s = JSON.stringify(ae.points);
  assert.ok(!s.includes("1.2.3.4")); assert.ok(!s.includes("Mozilla")); assert.ok(!s.includes("Chrome"));
});

test("cross-origin or missing Origin is refused; GET is 405; nothing written", async () => {
  const ae = makeAE();
  assert.equal((await call(req(ev(), { origin: "https://evil.example" }), { CLICKS: ae })).status, 403);
  assert.equal((await call(req(ev(), { origin: null }), { CLICKS: ae })).status, 403);
  assert.equal((await call(req(null, { method: "GET" }), { CLICKS: ae })).status, 405);
  assert.equal(ae.points.length, 0);
});

test("allowlist: unknown host, tool id, kind, locale, bad path or bad referrer is rejected without writing", async () => {
  const bad = [ev({ h: "evil.example" }), ev({ t: "no-such-tool" }), ev({ k: "x" }), ev({ l: "xx" }), ev({ p: "https://evil.example/" }), ev({ p: "/a/../b" }), ev({ r: "evil host/<x>" }), ev({ r: 5 })];
  for (const b of bad) {
    const ae = makeAE();
    assert.equal((await call(req(b), { CLICKS: ae })).status, 400, JSON.stringify(b)); assert.equal(ae.points.length, 0);
  }
  for (const s of ["not json", "[]", "null"]) assert.equal((await call(req(s), { CLICKS: makeAE() })).status, 400);
});

test("oversized body is refused", async () => {
  const ae = makeAE();
  assert.equal((await call(req(JSON.stringify({ ...ev(), pad: "x".repeat(2000) })), { CLICKS: ae })).status, 400);
  assert.equal(ae.points.length, 0);
});

test("not configured (no CLICKS binding) or AE throwing: accepted, never an error, never touches KV", async () => {
  const kv = makeKV();
  assert.equal((await call(req(ev()), { NEWSLETTER: kv })).status, 204);
  assert.equal((await call(req(ev()), { CLICKS: { writeDataPoint() { throw new Error("down"); } } })).status, 204);
  assert.equal(kv.n, 0);
});

test("host allowlist covers share/featured/registry/affiliate hosts and www-normalises", () => {
  for (const h of ["tradingview.com", "eodhd.com", "github.com", "x.com", "reddit.com", "linkedin.com", "news.ycombinator.com", "fazier.com", "dang.ai", "npmjs.com", "pypi.org", "buy.polar.sh"]) assert.ok(HOSTS.has(h), h);
  assert.ok(parseEvent(JSON.stringify(ev({ h: "WWW.TradingView.com." }))));
  assert.equal(parseEvent(JSON.stringify(ev({ h: "tradingview.com.evil.example" }))), null);
  assert.equal(parseEvent(JSON.stringify(ev({ h: "eviltradingview.com" }))), null);
  assert.ok(TOOL_IDS.size > 50);
});
