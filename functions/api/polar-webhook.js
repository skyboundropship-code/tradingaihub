// POST /api/polar-webhook - Polar (https://polar.sh) webhook -> phone alert (functions/_lib/notify.js).
// Verified per Standard Webhooks, exactly like Polar's SDK validateEvent: headers webhook-id, webhook-timestamp,
// webhook-signature ("v1,<base64>" entries, space separated); HMAC-SHA256 over `${id}.${timestamp}.${rawBody}`;
// +-300 s clock tolerance. Key candidates (as in @polar-sh/sdk): the UTF-8 bytes of the whole secret, and the
// base64-decoded secret after an optional "whsec_" prefix. Bad, missing or stale signatures get 401.
// Secret: POLAR_WEBHOOK_SECRET (wrangler pages secret; production = the real Polar endpoint, preview = a test secret).
// Events (endpoint subscription in Polar): order.created, order.paid, subscription.created, subscription.canceled.
//   order.paid  billing_reason=purchase            -> "New purchase"          (priority 5)
//   order.paid  billing_reason=subscription_cycle  -> "Subscription renewed"  (priority 5)
//   order.paid  subscription_create/_update, order.created -> acknowledged, no alert (subscription.created covers a new sub)
//   subscription.created                           -> "New subscription"      (priority 5)
//   subscription.canceled                          -> "Subscription canceled" (priority 4)
// Alerts carry product, amount and a masked customer email only. Dedupe: KV key pw:<webhook-id> (8-day TTL), written
// only for alerted events (1 read + 1 write per alerted delivery). Its metadata also feeds /api/alerts/summary.
// Always answers quickly; the alert and the KV write run after the response (context.waitUntil).
import { notify, maskEmail, formatAmount } from "../_lib/notify.js";

export const TOLERANCE_S = 300;
const MAX_BODY = 256 * 1024;
const DEDUPE_TTL = 8 * 86400;

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff" },
});

function b64decode(v) {
  try {
    const s = atob(v);
    const out = new Uint8Array(s.length);
    for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
    return out;
  } catch { return null; }
}
const sameBytes = (a, b) => a.byteLength === b.byteLength && a.every((x, i) => x === b[i]);

export function hmacKeys(secret) {
  const utf8 = new TextEncoder().encode(secret);
  const keys = [utf8];
  const decoded = b64decode(secret.startsWith("whsec_") ? secret.slice(6) : secret);
  if (decoded && decoded.byteLength > 0 && !sameBytes(decoded, utf8)) keys.push(decoded);
  return keys;
}

/** Returns "ok" | "missing" | "stale" | "bad". `now` in seconds (tests). */
export async function verifySignature(body, headers, secret, now = Date.now() / 1000) {
  if (typeof secret !== "string" || !secret) return "bad";
  const id = headers.get("webhook-id"), ts = headers.get("webhook-timestamp"), sigs = headers.get("webhook-signature");
  if (!id || !ts || !sigs) return "missing";
  if (!/^\d{1,12}$/.test(ts)) return "bad";
  const t = Number(ts);
  if (t < now - TOLERANCE_S || t > now + TOLERANCE_S) return "stale";
  const data = new TextEncoder().encode(`${id}.${t}.${body}`);
  const keys = await Promise.all(hmacKeys(secret).map((k) =>
    crypto.subtle.importKey("raw", k, { name: "HMAC", hash: "SHA-256" }, false, ["verify"])));
  for (const entry of sigs.split(" ")) {
    const [ver, sig] = entry.split(",", 2);
    if (ver !== "v1" || !sig) continue;
    const raw = b64decode(sig);
    if (!raw) continue;
    for (const k of keys) if (await crypto.subtle.verify("HMAC", k, raw, data)) return "ok"; // constant-time compare
  }
  return "bad";
}

async function readLimited(request) {
  const cl = request.headers.get("content-length");
  if (cl !== null && (!/^\d+$/.test(cl) || Number(cl) > MAX_BODY)) return null;
  if (!request.body) return "";
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

const clean = (s, n = 80) => String(s ?? "").replace(/[\u0000-\u001f\u007f]+/g, " ").trim().slice(0, n);

/** Maps a verified Polar event to an alert, or null (acknowledged without an alert). Pure; used by tests. */
export function alertFor(event) {
  const type = event && event.type;
  const d = (event && event.data) || {};
  const product = clean(d.product?.name || d.product_name || "Unknown product");
  const who = maskEmail(d.customer?.email || d.user?.email || "");
  const currency = d.currency || "usd";
  if (type === "order.paid") {
    const amount = formatAmount(d.total_amount ?? d.net_amount ?? d.amount, currency);
    const reason = d.billing_reason || "purchase";
    if (reason === "purchase") return { kind: "purchase", amount: d.total_amount ?? d.amount, currency, message: `${product} - ${amount}\nCustomer: ${who}` };
    if (reason === "subscription_cycle") return { kind: "renewal", amount: d.total_amount ?? d.amount, currency, message: `${product} - ${amount}\nCustomer: ${who}` };
    return null;
  }
  if (type === "subscription.created") {
    const per = d.recurring_interval ? `/${d.recurring_interval === "month" ? "mo" : d.recurring_interval === "year" ? "yr" : d.recurring_interval}` : "";
    return { kind: "subscription", amount: d.amount, currency, message: `${product} - ${formatAmount(d.amount, currency)}${per}\nCustomer: ${who}` };
  }
  if (type === "subscription.canceled") {
    const end = typeof d.current_period_end === "string" ? d.current_period_end.slice(0, 10) : "";
    const when = d.cancel_at_period_end && end ? `\nActive until ${end}` : "";
    return { kind: "canceled", amount: d.amount, currency, message: `${product} - ${formatAmount(d.amount, currency)}\nCustomer: ${who}${when}` };
  }
  return null; // order.created and anything else: ack only
}

export async function onRequest(context) {
  const { request, env } = context;
  if (request.method !== "POST") return new Response(null, { status: 405, headers: { allow: "POST", "cache-control": "no-store" } });
  const secret = typeof env.POLAR_WEBHOOK_SECRET === "string" ? env.POLAR_WEBHOOK_SECRET.trim() : "";
  if (!secret) return json({ ok: false, error: "not_configured" }, 503);

  const body = await readLimited(request);
  if (body === null) return json({ ok: false, error: "too_large" }, 413);
  const v = await verifySignature(body, request.headers, secret);
  if (v !== "ok") return json({ ok: false, error: v === "stale" ? "stale_timestamp" : "invalid_signature" }, 401);

  let event;
  try { event = JSON.parse(body); } catch { return json({ ok: false, error: "bad_json" }, 400); }
  const alert = alertFor(event);
  if (!alert) return json({ ok: true, alerted: false }, 202);

  const id = request.headers.get("webhook-id").slice(0, 200);
  const kv = env.NEWSLETTER;
  const key = `pw:${id}`;
  try { if (kv && (await kv.get(key)) !== null) return json({ ok: true, duplicate: true }); } catch {}

  notify(context, alert.kind, alert.message);
  if (kv) {
    const meta = { k: alert.kind, a: Number(alert.amount) || 0, c: String(alert.currency).slice(0, 3), ts: new Date().toISOString() };
    const p = kv.put(key, "1", { expirationTtl: DEDUPE_TTL, metadata: meta }).catch(() => console.error("polar-webhook: kv dedupe write failed"));
    if (typeof context.waitUntil === "function") context.waitUntil(p);
  }
  return json({ ok: true, alerted: true });
}
