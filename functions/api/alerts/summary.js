// GET /api/alerts/summary - read-only numbers for the daily phone summary, for the scheduled GitHub Actions workflow
// (.github/workflows/alerts-daily.yml), which posts the returned `message` to ntfy itself (from GitHub's IPs).
// This endpoint never sends a notification, so it can't be used to spam the topic. It never writes to KV.
// Auth: "Authorization: Bearer <ALERTS_TOKEN>" (wrangler pages secret + repo secret). Missing secret -> 503, wrong -> 401.
// Data (all from KV binding NEWSLETTER, read-only):
//   subscribers  sub:<email>   metadata {ts} (new records) or the JSON value's ts (older records)
//   Polar        pw:<id>       metadata {k,a,c,ts}, written by /api/polar-webhook
//   clicks       click:<day>   {"n":N}, written by /api/click (PR #20) - "n/a" until that ships
import { formatAmount, EVENTS } from "../../_lib/notify.js";

const WINDOW_MS = 24 * 3600 * 1000;
const MAX_PAGES = 20;     // 20 x 1000 keys
const MAX_GETS = 400;     // value reads for legacy subscriber records without metadata (subrequest budget)

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff", "x-robots-tag": "noindex" },
});

async function digest(s) { return new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s))); }
export async function tokenOk(given, expected) {
  if (typeof expected !== "string" || expected.length < 32 || typeof given !== "string") return false;
  const [a, b] = await Promise.all([digest(given), digest(expected)]);
  let d = 0; for (let i = 0; i < a.length; i++) d |= a[i] ^ b[i];
  return d === 0;
}

async function listAll(kv, prefix) {
  const out = []; let cursor;
  for (let i = 0; i < MAX_PAGES; i++) {
    const r = await kv.list({ prefix, cursor });
    out.push(...r.keys);
    if (r.list_complete || !r.cursor) return { keys: out, complete: true };
    cursor = r.cursor;
  }
  return { keys: out, complete: false };
}

export async function computeSummary(kv, now = Date.now()) {
  const since = now - WINDOW_MS;
  const inWindow = (ts) => { const t = Date.parse(ts); return Number.isFinite(t) && t > since && t <= now + 60000; };

  const subs = await listAll(kv, "sub:");
  let newSubs = 0, gets = 0, unknown = 0;
  for (const k of subs.keys) {
    let ts = k.metadata && k.metadata.ts;
    if (!ts) {
      if (gets >= MAX_GETS) { unknown++; continue; }
      gets++;
      try { ts = JSON.parse((await kv.get(k.name)) || "null")?.ts; } catch {}
    }
    if (ts && inWindow(ts)) newSubs++;
  }

  const polar = await listAll(kv, "pw:");
  const p = { purchase: { n: 0, a: {} }, subscription: { n: 0, a: {} }, renewal: { n: 0, a: {} }, canceled: { n: 0, a: {} } };
  for (const k of polar.keys) {
    const m = k.metadata || {};
    if (!p[m.k] || !inWindow(m.ts)) continue;
    p[m.k].n++;
    const c = String(m.c || "usd").toLowerCase();
    p[m.k].a[c] = (p[m.k].a[c] || 0) + (Number(m.a) || 0);
  }

  const day = (t) => new Date(t).toISOString().slice(0, 10);
  const clicksFor = async (d) => { try { const v = JSON.parse((await kv.get(`click:${d}`)) || "null"); return v && Number.isInteger(v.n) ? v.n : null; } catch { return null; } };
  const [cy, ct] = await Promise.all([clicksFor(day(now - 86400000)), clicksFor(day(now))]);

  const money = (a) => Object.entries(a).map(([c, v]) => formatAmount(v, c)).join(" + ") || "$0.00";
  const revenue = {};
  for (const k of ["purchase", "subscription", "renewal"]) for (const [c, v] of Object.entries(p[k].a)) revenue[c] = (revenue[c] || 0) + v;
  const lines = [
    `New subscribers: ${newSubs}${unknown ? ` (+${unknown} unchecked)` : ""} (total ${subs.keys.length}${subs.complete ? "" : "+"})`,
    `Purchases: ${p.purchase.n} | New subscriptions: ${p.subscription.n} | Renewals: ${p.renewal.n} | Cancellations: ${p.canceled.n}`,
    `Revenue: ${money(revenue)}`,
    `Outbound clicks: ${cy === null && ct === null ? "n/a (click tracking not live)" : `${cy ?? 0} yesterday (UTC), ${ct ?? 0} today so far`}`,
  ];
  return {
    window_hours: 24,
    subscribers: { new: newSubs, total: subs.keys.length, unchecked: unknown },
    polar: Object.fromEntries(Object.entries(p).map(([k, v]) => [k, { n: v.n, amount: v.a }])),
    clicks: { yesterday_utc: cy, today_utc: ct },
    title: EVENTS.daily.title,
    tags: EVENTS.daily.tags.join(","),
    priority: EVENTS.daily.priority,
    message: lines.join("\n"),
  };
}

export async function onRequest(context) {
  const { request, env } = context;
  if (request.method !== "GET") return new Response(null, { status: 405, headers: { allow: "GET", "cache-control": "no-store" } });
  const expected = typeof env.ALERTS_TOKEN === "string" ? env.ALERTS_TOKEN.trim() : "";
  if (expected.length < 32) return json({ ok: false, error: "not_configured" }, 503);
  const auth = request.headers.get("authorization") || "";
  const given = auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
  if (!(await tokenOk(given, expected))) return json({ ok: false, error: "unauthorized" }, 401);
  if (!env.NEWSLETTER) return json({ ok: false, error: "not_configured" }, 503);
  try { return json({ ok: true, ...(await computeSummary(env.NEWSLETTER)) }); }
  catch { return json({ ok: false, error: "server" }, 503); }
}
