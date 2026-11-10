// Phone alerts: functions/_lib/notify.js, functions/api/polar-webhook.js, functions/api/alerts/summary.js and the
// /api/subscribe hook. Mocked fetch + KV, no network. All secrets/topics here are fake test values.
import test from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { EVENTS, maskEmail, formatAmount, buildNtfyRequest, sendNtfy, notify, crossedMilestone, notifyClickMilestone } from "../functions/_lib/notify.js";
import * as webhook from "../functions/api/polar-webhook.js";
import * as summary from "../functions/api/alerts/summary.js";
import { onRequest as subscribe } from "../functions/api/subscribe.js";

const TOPIC = "tah-TESTtopicNotReal0123456789abcdef";
// Same format as the real Polar secret: "whsec_" + base64 (50 chars). Fake value.
const SECRET = "whsec_" + Buffer.from("0123456789abcdef0123456789abcdefXYZ").toString("base64").slice(0, 44);
const now = () => Math.floor(Date.now() / 1000);

function sign(body, { id = "msg_test_1", ts = now(), key = "utf8", secret = SECRET } = {}) {
  const k = key === "utf8" ? Buffer.from(secret, "utf8") : Buffer.from(secret.replace(/^whsec_/, ""), "base64");
  const sig = createHmac("sha256", k).update(`${id}.${ts}.${body}`).digest("base64");
  return { "webhook-id": id, "webhook-timestamp": String(ts), "webhook-signature": `v1,${sig}` };
}
function makeKV() {
  const m = new Map(), meta = new Map(); let gets = 0;
  return {
    m, meta, get gets() { return gets; },
    async get(k) { gets++; return m.has(k) ? m.get(k) : null; },
    async put(k, v, o = {}) { m.set(k, v); meta.set(k, o.metadata); },
    async list({ prefix }) { return { keys: [...m.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name, metadata: meta.get(name) })), list_complete: true }; },
  };
}
async function withFetch(impl, fn) {
  const calls = []; const real = globalThis.fetch;
  globalThis.fetch = async (url, init) => { calls.push({ url: String(url), init }); return impl(url, init); };
  try { return { out: await fn(), calls }; } finally { globalThis.fetch = real; }
}
const ok200 = async () => new Response("{}", { status: 200 });
async function callWebhook(body, headers, env) {
  const pending = [];
  const req = new Request("https://tradingaihub.com/api/polar-webhook", { method: "POST", headers: { "content-type": "application/json", ...headers }, body });
  const res = await webhook.onRequest({ request: req, env, waitUntil: (p) => pending.push(p) });
  await Promise.all(pending);
  return res;
}
const ORDER = (over = {}) => JSON.stringify({ type: "order.paid", timestamp: "2026-11-04T16:00:00Z", data: {
  id: "ord_1", total_amount: 2900, currency: "usd", billing_reason: "purchase",
  product: { name: "Category Featured" }, customer: { email: "user.test@example.com", name: "Secret Name" }, ...over } });

// ---- notify helper ----
test("event table: titles, tags, priorities", () => {
  assert.deepEqual(EVENTS.purchase, { title: "New purchase", tags: ["moneybag"], priority: 5 });
  assert.deepEqual(EVENTS.subscription, { title: "New subscription", tags: ["repeat"], priority: 5 });
  assert.equal(EVENTS.renewal.priority, 5);
  assert.deepEqual(EVENTS.canceled, { title: "Subscription canceled", tags: ["x"], priority: 4 });
  assert.deepEqual(EVENTS.subscriber, { title: "New subscriber", tags: ["envelope_with_arrow"], priority: 3 });
  assert.deepEqual(EVENTS.submission, { title: "New tool submission", tags: ["toolbox"], priority: 3 });
  assert.deepEqual(EVENTS.contact, { title: "New contact message", tags: ["email"], priority: 3 });
  assert.deepEqual(EVENTS.click_milestone, { title: "Click milestone", tags: ["dart"], priority: 3 });
  assert.deepEqual(EVENTS.daily, { title: "Daily summary", tags: ["bar_chart"], priority: 3 });
  const tagSets = Object.values(EVENTS).map((e) => e.tags.join(","));
  assert.equal(new Set(tagSets).size, tagSets.length, "each event has its own tag set");
});

test("buildNtfyRequest: headers per event, preview prefix, server default, no topic -> null", () => {
  for (const [type, ev] of Object.entries(EVENTS)) {
    const r = buildNtfyRequest({ NTFY_TOPIC: TOPIC }, type, "hi");
    assert.equal(r.url, `https://ntfy.sh/${TOPIC}`);
    assert.equal(r.init.headers.priority, String(ev.priority));
    assert.equal(r.init.headers.tags, ev.tags.join(","));
    assert.equal(r.init.headers.title, ev.title);
    assert.equal(r.init.headers.authorization, undefined);
  }
  const t = buildNtfyRequest({ NTFY_TOPIC: TOPIC, NTFY_TITLE_PREFIX: "[TEST] ", NTFY_TOKEN: "tk_fake" }, "purchase", "x");
  assert.equal(t.init.headers.title, "[TEST] New purchase");
  assert.equal(t.init.headers.authorization, "Bearer tk_fake");
  assert.equal(buildNtfyRequest({}, "purchase", "x"), null);
  assert.equal(buildNtfyRequest({ NTFY_TOPIC: "short" }, "purchase", "x"), null);
  assert.equal(buildNtfyRequest({ NTFY_TOPIC: "../etc/passwd/xxxxxxxxxxxx" }, "purchase", "x"), null);
  assert.equal(buildNtfyRequest({ NTFY_TOPIC: TOPIC }, "nope", "x"), null);
  assert.equal(buildNtfyRequest({ NTFY_TOPIC: TOPIC, NTFY_SERVER: "http://evil.test" }, "daily", "x").url, `https://ntfy.sh/${TOPIC}`);
  const nonAscii = buildNtfyRequest({ NTFY_TOPIC: TOPIC }, "daily", "x", { titleSuffix: "שלום" });
  assert.match(nonAscii.init.headers.title, /^=\?UTF-8\?B\?/);
});

test("maskEmail / formatAmount: no PII beyond a masked email", () => {
  assert.equal(maskEmail("user@example.com"), "u***@example.com");
  assert.equal(maskEmail("A.User@Example.COM"), "A***@example.com");
  assert.equal(maskEmail(""), "***"); assert.equal(maskEmail("nope"), "***"); assert.equal(maskEmail(undefined), "***");
  assert.equal(formatAmount(2900, "usd"), "$29.00"); assert.equal(formatAmount(9900, "eur"), "99.00 EUR");
});

test("sendNtfy: timeout, network error and HTTP errors are swallowed (no throw, topic never logged)", async () => {
  const logs = []; const ce = console.error; console.error = (...a) => logs.push(a.join(" "));
  try {
    const { out: s1 } = await withFetch(async () => { throw new TypeError("net"); }, () => sendNtfy({ NTFY_TOPIC: TOPIC }, "purchase", "m"));
    assert.equal(s1, 0);
    const { out: s2 } = await withFetch(async () => new Response("no", { status: 429 }), () => sendNtfy({ NTFY_TOPIC: TOPIC }, "purchase", "m"));
    assert.equal(s2, 429);
    const { out: s3 } = await withFetch((u, init) => new Promise((_, rej) => init.signal.addEventListener("abort", () => rej(Object.assign(new Error("a"), { name: "AbortError" })))),
      () => sendNtfy({ NTFY_TOPIC: TOPIC }, "purchase", "m", {}, 50));
    assert.equal(s3, 0);
    const { out: s4, calls } = await withFetch(ok200, () => sendNtfy({}, "purchase", "m"));
    assert.equal(s4, 0); assert.equal(calls.length, 0, "no topic configured: no request");
  } finally { console.error = ce; }
  assert.ok(logs.length >= 3);
  for (const l of logs) assert.ok(!l.includes(TOPIC), "topic must never be logged");
});

test("notify: fire-and-forget through waitUntil", async () => {
  const pending = [];
  const { calls } = await withFetch(ok200, async () => {
    const r = notify({ env: { NTFY_TOPIC: TOPIC }, waitUntil: (p) => pending.push(p) }, "subscriber", "x");
    assert.ok(r instanceof Promise); assert.equal(pending.length, 1);
    await Promise.all(pending);
  });
  assert.equal(calls.length, 1); assert.equal(calls[0].init.headers.priority, "3");
});

test("click milestones: 10, 50, 100, 250, 500, 1000, then every 1000", async () => {
  assert.equal(crossedMilestone(9, 10), 10); assert.equal(crossedMilestone(10, 11), 0); assert.equal(crossedMilestone(0, 1), 0);
  assert.equal(crossedMilestone(49, 50), 50); assert.equal(crossedMilestone(99, 100), 100); assert.equal(crossedMilestone(249, 250), 250);
  assert.equal(crossedMilestone(499, 500), 500); assert.equal(crossedMilestone(999, 1000), 1000); assert.equal(crossedMilestone(1000, 1500), 0);
  assert.equal(crossedMilestone(1999, 2000), 2000); assert.equal(crossedMilestone(2999, 3001), 3000); assert.equal(crossedMilestone(5, 5), 0);
  const pending = [];
  const { calls } = await withFetch(ok200, async () => {
    assert.equal(notifyClickMilestone({ env: { NTFY_TOPIC: TOPIC }, waitUntil: (p) => pending.push(p) }, 11, 12), null);
    notifyClickMilestone({ env: { NTFY_TOPIC: TOPIC }, waitUntil: (p) => pending.push(p) }, 49, 50);
    await Promise.all(pending);
  });
  assert.equal(calls.length, 1); assert.equal(calls[0].init.headers.title, "Click milestone: 50"); assert.equal(calls[0].init.headers.tags, "dart");
});

// ---- Polar webhook signature ----
test("signature: valid (Polar SDK utf8 key AND standard-webhooks base64 key), invalid, stale, future, missing", async () => {
  const body = ORDER(); const H = (h) => new Headers(h);
  assert.equal(SECRET.length, 50);
  assert.equal(await webhook.verifySignature(body, H(sign(body)), SECRET), "ok");
  assert.equal(await webhook.verifySignature(body, H(sign(body, { key: "b64" })), SECRET), "ok");
  assert.equal(await webhook.verifySignature(body + " ", H(sign(body)), SECRET), "bad", "tampered body");
  assert.equal(await webhook.verifySignature(body, H(sign(body, { secret: SECRET.slice(0, -2) + "AA" })), SECRET), "bad", "wrong secret");
  const h = sign(body); h["webhook-id"] = "msg_other";
  assert.equal(await webhook.verifySignature(body, H(h), SECRET), "bad", "id is signed");
  assert.equal(await webhook.verifySignature(body, H(sign(body, { ts: now() - 301 })), SECRET), "stale");
  assert.equal(await webhook.verifySignature(body, H(sign(body, { ts: now() + 301 })), SECRET), "stale");
  assert.equal(await webhook.verifySignature(body, H(sign(body, { ts: now() - 290 })), SECRET), "ok", "within 5 min skew");
  assert.equal(await webhook.verifySignature(body, H({ "webhook-id": "x" }), SECRET), "missing");
  const multi = sign(body); multi["webhook-signature"] = `v1,AAAA v2,zzz ${multi["webhook-signature"]}`;
  assert.equal(await webhook.verifySignature(body, H(multi), SECRET), "ok", "any matching v1 entry");
  const notB64 = sign(body); notB64["webhook-signature"] = "v1,%%%";
  assert.equal(await webhook.verifySignature(body, H(notB64), SECRET), "bad");
});

test("webhook: 401 on bad/stale signature, no alert, no KV", async () => {
  const kv = makeKV(); const env = { POLAR_WEBHOOK_SECRET: SECRET, NTFY_TOPIC: TOPIC, NEWSLETTER: kv };
  const body = ORDER();
  const { out: r1, calls } = await withFetch(ok200, async () => [
    await callWebhook(body, { ...sign(body), "webhook-signature": "v1,AAAA" }, env),
    await callWebhook(body, sign(body, { ts: now() - 600 }), env),
    await callWebhook(body, {}, env),
  ]);
  assert.deepEqual(r1.map((r) => r.status), [401, 401, 401]);
  assert.equal((await r1[1].json()).error, "stale_timestamp");
  assert.equal(calls.length, 0); assert.equal(kv.m.size, 0);
  const r503 = await callWebhook(body, sign(body), { NTFY_TOPIC: TOPIC });
  assert.equal(r503.status, 503);
  const r405 = await webhook.onRequest({ request: new Request("https://tradingaihub.com/api/polar-webhook"), env });
  assert.equal(r405.status, 405);
});

test("webhook: order.paid purchase -> priority 5 'New purchase' with product + amount + masked email; dedupe by webhook-id", async () => {
  const kv = makeKV(); const env = { POLAR_WEBHOOK_SECRET: SECRET, NTFY_TOPIC: TOPIC, NEWSLETTER: kv };
  const body = ORDER();
  const { out, calls } = await withFetch(ok200, async () => [
    await callWebhook(body, sign(body, { id: "msg_A" }), env),
    await callWebhook(body, sign(body, { id: "msg_A" }), env),
  ]);
  assert.deepEqual(out.map((r) => r.status), [200, 200]);
  assert.equal((await out[1].json()).duplicate, true);
  assert.equal(calls.length, 1, "retry of same webhook-id does not alert twice");
  const h = calls[0].init.headers;
  assert.equal(h.title, "New purchase"); assert.equal(h.priority, "5"); assert.equal(h.tags, "moneybag");
  assert.match(calls[0].init.body, /Category Featured - \$29\.00/);
  assert.match(calls[0].init.body, /u\*\*\*@example\.com/);
  assert.ok(!calls[0].init.body.includes("user.test"), "no full email");
  assert.ok(!calls[0].init.body.includes("Secret Name"), "no name");
  assert.deepEqual(kv.meta.get("pw:msg_A"), { k: "purchase", a: 2900, c: "usd", ts: kv.meta.get("pw:msg_A").ts });
});

test("webhook: every event type -> its own title/tag/priority; order.created and subscription_create orders ack without alert", async () => {
  const env = { POLAR_WEBHOOK_SECRET: SECRET, NTFY_TOPIC: TOPIC, NEWSLETTER: makeKV() };
  const sub = (type, over = {}) => JSON.stringify({ type, data: { id: "sub_1", amount: 9900, currency: "usd", recurring_interval: "month", status: "active",
    product: { name: "Homepage Feature" }, customer: { email: "buyer@example.com" }, ...over } });
  const cases = [
    [sub("subscription.created"), 200, { title: "New subscription", priority: "5", tags: "repeat" }, /Homepage Feature - \$99\.00\/mo/],
    [sub("subscription.canceled", { cancel_at_period_end: true, current_period_end: "2026-12-04T00:00:00Z" }), 200, { title: "Subscription canceled", priority: "4", tags: "x" }, /Active until 2026-12-04/],
    [ORDER({ billing_reason: "subscription_cycle", product: { name: "Homepage Feature" }, total_amount: 9900 }), 200, { title: "Subscription renewed", priority: "5", tags: "repeat,moneybag" }, /\$99\.00/],
    [ORDER({ billing_reason: "subscription_create" }), 202, null],
    [JSON.stringify({ type: "order.created", data: { id: "o" } }), 202, null],
    [JSON.stringify({ type: "checkout.updated", data: {} }), 202, null],
  ];
  let i = 0;
  for (const [body, status, hdr, re] of cases) {
    const { out, calls } = await withFetch(ok200, () => callWebhook(body, sign(body, { id: `msg_${i++}` }), env));
    assert.equal(out.status, status, body);
    if (!hdr) { assert.equal(calls.length, 0); continue; }
    assert.equal(calls.length, 1);
    for (const [k, v] of Object.entries(hdr)) assert.equal(calls[0].init.headers[k], v);
    assert.match(calls[0].init.body, re);
    assert.match(calls[0].init.body, /Customer: [a-z]\*\*\*@(example\.com|gmail\.com)$/m);
  }
});

test("webhook: ntfy down -> Polar still gets 2xx", async () => {
  const body = ORDER(); const env = { POLAR_WEBHOOK_SECRET: SECRET, NTFY_TOPIC: TOPIC, NEWSLETTER: makeKV() };
  const ce = console.error; console.error = () => {};
  try {
    const { out } = await withFetch(async () => { throw new TypeError("down"); }, () => callWebhook(body, sign(body, { id: "msg_down" }), env));
    assert.equal(out.status, 200);
  } finally { console.error = ce; }
});

// ---- /api/subscribe hook ----
function subReq(email) {
  return new Request("https://tradingaihub.com/api/subscribe", { method: "POST",
    headers: { origin: "https://tradingaihub.com", "content-type": "application/json", "cf-connecting-ip": "9.9.9.9" }, body: JSON.stringify({ email, locale: "he" }) });
}
async function runSub(email, env, impl) {
  const pending = [];
  const { out, calls } = await withFetch(impl, async () => {
    const res = await subscribe({ request: subReq(email), env, waitUntil: (p) => pending.push(p) });
    await Promise.all(pending); return res;
  });
  return { res: out, calls };
}

test("subscribe: new signup -> one 'New subscriber' alert (masked, no IP); duplicate -> no alert", async () => {
  const kv = makeKV(); const env = { NEWSLETTER: kv, RL_SALT: "x".repeat(32), NTFY_TOPIC: TOPIC };
  const a = await runSub("User@Example.com", env, ok200);
  assert.equal(a.res.status, 200);
  const ntfy = a.calls.filter((c) => c.url.startsWith("https://ntfy.sh/"));
  assert.equal(ntfy.length, 1);
  assert.equal(ntfy[0].init.headers.title, "New subscriber"); assert.equal(ntfy[0].init.headers.priority, "3"); assert.equal(ntfy[0].init.headers.tags, "envelope_with_arrow");
  assert.equal(ntfy[0].init.body, "U***@example.com (he)");
  assert.ok(!JSON.stringify(ntfy[0].init).includes("9.9.9.9"));
  assert.ok(kv.meta.get("sub:user@example.com").ts, "metadata ts for the daily summary");
  const b = await runSub("user@example.com", env, ok200);
  assert.equal(b.res.status, 200); assert.equal(b.calls.length, 0, "duplicate: no alert");
});

test("subscribe: a failing ntfy (throw / 500 / hang) never breaks the signup", { timeout: 15000 }, async () => {
  const ce = console.error; console.error = () => {};
  try {
    for (const impl of [async () => { throw new TypeError("down"); }, async () => new Response("x", { status: 500 })]) {
      const kv = makeKV();
      const r = await runSub(`u${Math.random()}@example.com`, { NEWSLETTER: kv, RL_SALT: "x".repeat(32), NTFY_TOPIC: TOPIC, MAILERLITE_API_KEY: "fake" }, impl);
      assert.equal(r.res.status, 200); assert.equal((await r.res.json()).ok, true);
      assert.equal([...kv.m.keys()].filter((k) => k.startsWith("sub:")).length, 1);
    }
    // ntfy hangs: the response is not delayed (alert runs in waitUntil)
    const kv = makeKV(); const pending = [];
    const { out } = await withFetch(() => new Promise(() => {}), async () => {
      const t0 = Date.now();
      const res = await subscribe({ request: subReq("hang@example.com"), env: { NEWSLETTER: kv, RL_SALT: "x".repeat(32), NTFY_TOPIC: TOPIC }, waitUntil: (p) => pending.push(p) });
      return { res, ms: Date.now() - t0 };
    });
    assert.equal(out.res.status, 200); assert.ok(out.ms < 1000, `response not blocked (${out.ms} ms)`);
    assert.equal(pending.length, 1);
  } finally { console.error = ce; }
});

// ---- daily summary endpoint ----
test("summary: token required (503 unset, 401 wrong), read-only counts, never calls ntfy", async () => {
  const kv = makeKV();
  const iso = (msAgo) => new Date(Date.now() - msAgo).toISOString();
  await kv.put("sub:a@x.com", JSON.stringify({ ts: iso(3600e3) }), { metadata: { ts: iso(3600e3) } });
  await kv.put("sub:b@x.com", JSON.stringify({ ts: iso(2 * 86400e3) }), { metadata: { ts: iso(2 * 86400e3) } });
  await kv.put("sub:legacy@x.com", JSON.stringify({ ts: iso(600e3) })); // no metadata
  await kv.put("pw:1", "1", { metadata: { k: "purchase", a: 2900, c: "usd", ts: iso(1000) } });
  await kv.put("pw:2", "1", { metadata: { k: "subscription", a: 9900, c: "usd", ts: iso(1000) } });
  await kv.put("pw:3", "1", { metadata: { k: "canceled", a: 9900, c: "usd", ts: iso(1000) } });
  await kv.put("pw:old", "1", { metadata: { k: "purchase", a: 2900, c: "usd", ts: iso(3 * 86400e3) } });
  const TOKEN = "t".repeat(48);
  const call = (auth, env) => summary.onRequest({ request: new Request("https://tradingaihub.com/api/alerts/summary", { headers: auth ? { authorization: auth } : {} }), env });
  const writes = kv.m.size;
  const { out, calls } = await withFetch(ok200, async () => [
    await call(`Bearer ${TOKEN}`, { NEWSLETTER: kv }),
    await call("Bearer wrong", { NEWSLETTER: kv, ALERTS_TOKEN: TOKEN }),
    await call(null, { NEWSLETTER: kv, ALERTS_TOKEN: TOKEN }),
    await call(`Bearer ${TOKEN}`, { NEWSLETTER: kv, ALERTS_TOKEN: TOKEN, NTFY_TOPIC: TOPIC }),
  ]);
  assert.deepEqual(out.map((r) => r.status), [503, 401, 401, 200]);
  assert.equal(calls.length, 0, "summary endpoint never sends a notification");
  assert.equal(kv.m.size, writes, "no KV writes");
  const s = await out[3].json();
  assert.equal(s.subscribers.new, 2); assert.equal(s.subscribers.total, 3);
  assert.equal(s.polar.purchase.n, 1); assert.equal(s.polar.subscription.n, 1); assert.equal(s.polar.canceled.n, 1);
  assert.equal(s.title, "Daily summary"); assert.equal(s.tags, "bar_chart"); assert.equal(s.priority, 3);
  assert.match(s.message, /New subscribers: 2/); assert.match(s.message, /Revenue: \$128\.00/); assert.match(s.message, /n\/a/);
  assert.ok(!s.message.includes("@"), "no emails in the summary");
  const post = await summary.onRequest({ request: new Request("https://tradingaihub.com/api/alerts/summary", { method: "POST" }), env: {} });
  assert.equal(post.status, 405);
});
