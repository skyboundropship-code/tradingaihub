// node --test tests/  — unit tests for functions/api/subscribe.js with mocked KV and fetch (no network).
import test from "node:test";
import assert from "node:assert/strict";
import { onRequest } from "../functions/api/subscribe.js";

const ORIGIN = "https://tradingaihub.com";
const FAKE_KEY = "fake-test-key-not-real";

function makeKV() {
  const m = new Map();
  return {
    m,
    async get(k) { return m.has(k) ? m.get(k) : null; },
    async put(k, v) { m.set(k, v); },
  };
}

function req(body, { origin = ORIGIN, ip = "1.2.3.4", type = "application/json" } = {}) {
  return new Request(ORIGIN + "/api/subscribe", {
    method: "POST",
    headers: { origin, "content-type": type, "cf-connecting-ip": ip },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

async function run(r, env, mlImpl) {
  const calls = [];
  const realFetch = globalThis.fetch;
  globalThis.fetch = async (url, init) => { calls.push({ url, init }); return mlImpl(url, init); };
  const pending = [];
  try {
    const res = await onRequest({ request: r, env, waitUntil: (p) => pending.push(p) });
    await Promise.all(pending);
    return { res, body: await res.json(), calls };
  } finally { globalThis.fetch = realFetch; }
}

const baseEnv = (kv, extra = {}) => ({ NEWSLETTER: kv, RL_SALT: "x".repeat(32), ...extra });
const ok201 = async () => new Response("{}", { status: 201 });

test("new signup: KV written, MailerLite upsert with group + unconfirmed, ml:ok recorded", { timeout: 10000 }, async () => {
  const kv = makeKV();
  const { res, body, calls } = await run(req({ email: "A.User@Example.com", locale: "he" }), baseEnv(kv, { MAILERLITE_API_KEY: FAKE_KEY }), ok201);
  assert.equal(res.status, 200); assert.equal(body.ok, true);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "https://connect.mailerlite.com/api/subscribers");
  assert.equal(calls[0].init.method, "POST");
  assert.equal(calls[0].init.headers.authorization, `Bearer ${FAKE_KEY}`);
  assert.deepEqual(JSON.parse(calls[0].init.body), { email: "A.User@Example.com", groups: ["202680264761018021"], status: "unconfirmed" });
  const rec = JSON.parse(kv.m.get("sub:a.user@example.com"));
  assert.equal(rec.locale, "he"); assert.equal(rec.consent, true); assert.equal(rec.ml, "ok");
});

test("MailerLite error: signup still succeeds, ml:err recorded, no secret in logs", { timeout: 10000 }, async () => {
  const kv = makeKV();
  const logs = []; const ce = console.error; console.error = (...a) => logs.push(a.join(" "));
  try {
    const { res } = await run(req({ email: "b@example.com" }), baseEnv(kv, { MAILERLITE_API_KEY: FAKE_KEY }), async () => new Response("{}", { status: 500 }));
    assert.equal(res.status, 200);
  } finally { console.error = ce; }
  assert.equal(JSON.parse(kv.m.get("sub:b@example.com")).ml, "err");
  assert.ok(logs.some((l) => l.includes("http 500")));
  assert.ok(logs.every((l) => !l.includes(FAKE_KEY) && !l.includes("b@example.com")));
});

test("MailerLite network failure: signup still succeeds, ml:err", { timeout: 10000 }, async () => {
  const kv = makeKV();
  const ce = console.error; console.error = () => {};
  try {
    const { res } = await run(req({ email: "c@example.com" }), baseEnv(kv, { MAILERLITE_API_KEY: FAKE_KEY }), async () => { throw new TypeError("boom"); });
    assert.equal(res.status, 200);
  } finally { console.error = ce; }
  assert.equal(JSON.parse(kv.m.get("sub:c@example.com")).ml, "err");
});

test("no API key: skips quietly, record unchanged", async () => {
  const kv = makeKV();
  const { res, calls } = await run(req({ email: "d@example.com" }), baseEnv(kv), ok201);
  assert.equal(res.status, 200); assert.equal(calls.length, 0);
  assert.deepEqual(Object.keys(JSON.parse(kv.m.get("sub:d@example.com"))).sort(), ["consent", "email", "locale", "ts"]);
});

test("duplicate: no MailerLite call, original record kept", async () => {
  const kv = makeKV();
  kv.m.set("sub:e@example.com", '{"email":"e@example.com","locale":"en","ts":"x","consent":true}');
  const { calls } = await run(req({ email: "e@example.com" }), baseEnv(kv, { MAILERLITE_API_KEY: FAKE_KEY }), ok201);
  assert.equal(calls.length, 0);
  assert.equal(kv.m.get("sub:e@example.com"), '{"email":"e@example.com","locale":"en","ts":"x","consent":true}');
});

test("honeypot: fake ok, nothing stored, no MailerLite call", async () => {
  const kv = makeKV();
  const { body, calls } = await run(req({ email: "f@example.com", website: "spam" }), baseEnv(kv, { MAILERLITE_API_KEY: FAKE_KEY }), ok201);
  assert.equal(body.ok, true); assert.equal(calls.length, 0); assert.equal(kv.m.size, 0);
});

test("rate limit: 6th request from one IP gets 429", async () => {
  const kv = makeKV();
  const env = baseEnv(kv);
  for (let i = 0; i < 5; i++) assert.equal((await run(req({ email: `g${i}@example.com` }), env, ok201)).res.status, 200);
  assert.equal((await run(req({ email: "g9@example.com" }), env, ok201)).res.status, 429);
});

test("foreign Origin: 403, no KV, no MailerLite", async () => {
  const kv = makeKV();
  const { res, calls } = await run(req({ email: "h@example.com" }, { origin: "https://evil.example" }), baseEnv(kv, { MAILERLITE_API_KEY: FAKE_KEY }), ok201);
  assert.equal(res.status, 403); assert.equal(calls.length, 0); assert.equal(kv.m.size, 0);
});

test("oversized body: 400", async () => {
  const kv = makeKV();
  const { res } = await run(req({ email: "i@example.com", pad: "x".repeat(5000) }), baseEnv(kv), ok201);
  assert.equal(res.status, 400);
});

test("KV failure: 503 and no MailerLite call", async () => {
  const kv = makeKV(); kv.put = async () => { throw new Error("kv down"); };
  const { res, calls } = await run(req({ email: "j@example.com" }), baseEnv(kv, { MAILERLITE_API_KEY: FAKE_KEY }), ok201);
  assert.equal(res.status, 503); assert.equal(calls.length, 0);
});

test("MAILERLITE_API_URL override honoured only for localhost", async () => {
  for (const [u, expect] of [["http://127.0.0.1:9999/api/subscribers", "http://127.0.0.1:9999/api/subscribers"], ["https://evil.example/x", "https://connect.mailerlite.com/api/subscribers"]]) {
    const kv = makeKV();
    const { calls } = await run(req({ email: "k@example.com" }), baseEnv(kv, { MAILERLITE_API_KEY: FAKE_KEY, MAILERLITE_API_URL: u }), ok201);
    assert.equal(calls[0].url, expect);
  }
});

test("syncToMailerLite: times out and returns err", async () => {
  const { syncToMailerLite } = await import("../functions/api/subscribe.js");
  const realFetch = globalThis.fetch;
  globalThis.fetch = (u, init) => new Promise((_, rej) => init.signal.addEventListener("abort", () => rej(Object.assign(new Error("aborted"), { name: "AbortError" }))));
  const ce = console.error; const logs = []; console.error = (m) => logs.push(m);
  try { assert.equal(await syncToMailerLite(FAKE_KEY, "t@example.com", undefined, 50), "err"); }
  finally { globalThis.fetch = realFetch; console.error = ce; }
  assert.ok(logs[0].includes("timeout"));
});
