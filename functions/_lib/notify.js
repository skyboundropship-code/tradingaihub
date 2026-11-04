// Phone alerts via ntfy (https://ntfy.sh). Shared by the Pages Functions; exports no onRequest, so it is not a route.
// Secrets/vars (never in this repo, never logged):
//   NTFY_TOPIC   private random topic (anyone who knows it can read it) - wrangler pages secret, production + preview
//   NTFY_SERVER  optional, defaults to https://ntfy.sh
//   NTFY_TOKEN   optional ntfy access token (Bearer), only if an account is ever needed
//   NTFY_TITLE_PREFIX optional plain var, "[TEST] " on preview (wrangler.toml [env.preview.vars])
// Every send is fire-and-forget through context.waitUntil with a short timeout; errors are swallowed, so an alert
// can never block or break the user-facing response. No IPs are ever sent; emails are masked (l***@gmail.com).

export const NTFY_TIMEOUT = 4000; // ms
const DEFAULT_SERVER = "https://ntfy.sh";

// One entry per event type: title, ntfy tags (first tag that matches an emoji shortcode is shown as the emoji),
// priority 1-5 (5 = urgent -> Time Sensitive on iOS, 4 = high, 3 = default). Different tags/priorities let Liran pick
// a different sound per event in the ntfy app.
export const EVENTS = {
  purchase:        { title: "New purchase",          tags: ["moneybag"],            priority: 5 },
  subscription:    { title: "New subscription",      tags: ["repeat"],              priority: 5 },
  renewal:         { title: "Subscription renewed",  tags: ["repeat", "moneybag"],  priority: 5 },
  canceled:        { title: "Subscription canceled", tags: ["x"],                   priority: 4 },
  subscriber:      { title: "New subscriber",        tags: ["envelope_with_arrow"], priority: 3 },
  submission:      { title: "New tool submission",   tags: ["toolbox"],             priority: 3 },
  contact:         { title: "New contact message",   tags: ["email"],               priority: 3 },
  click_milestone: { title: "Click milestone",       tags: ["dart"],                priority: 3 },
  daily:           { title: "Daily summary",         tags: ["bar_chart"],           priority: 3 },
};

/** l***@gmail.com  (first character of the local part, then ***). Anything that isn't an email becomes "***". */
export function maskEmail(email) {
  const s = String(email ?? "").trim();
  const at = s.lastIndexOf("@");
  if (at < 1 || at === s.length - 1) return "***";
  return `${Array.from(s.slice(0, at))[0]}***@${s.slice(at + 1).toLowerCase()}`;
}

/** Formats minor units (cents) as "$29.00" / "29.00 EUR". */
export function formatAmount(minor, currency = "usd") {
  const n = Number(minor);
  if (!Number.isFinite(n)) return "";
  const cur = String(currency || "usd").toUpperCase();
  const v = (n / 100).toFixed(2);
  return cur === "USD" ? `$${v}` : `${v} ${cur}`;
}

/** Click milestones: 10, 50, 100, 250, 500, 1000, then every 1000. Returns the milestone crossed going prev -> next, or 0. */
export const CLICK_MILESTONES = [10, 50, 100, 250, 500, 1000];
export function crossedMilestone(prev, next) {
  prev = Math.max(0, Math.floor(Number(prev) || 0)); next = Math.floor(Number(next) || 0);
  if (next <= prev) return 0;
  let hit = 0;
  for (const m of CLICK_MILESTONES) if (prev < m && next >= m) hit = m;
  if (next >= 2000) { const k = Math.floor(next / 1000) * 1000; if (k > prev && k > 1000) hit = Math.max(hit, k); }
  return hit;
}

// ntfy headers must be latin-1; titles with emoji/non-ASCII go RFC 2047 encoded (ntfy decodes =?UTF-8?B?...?=).
function headerSafe(s) {
  const v = String(s).replace(/[\r\n]+/g, " ").slice(0, 200);
  if (/^[\x20-\x7e]*$/.test(v)) return v;
  const b = new TextEncoder().encode(v);
  let bin = ""; for (const x of b) bin += String.fromCharCode(x);
  return `=?UTF-8?B?${btoa(bin)}?=`;
}

/** Builds the ntfy request (pure; used by tests). Returns null if NTFY_TOPIC isn't configured or the type is unknown. */
export function buildNtfyRequest(env, type, message, { titleSuffix = "", click } = {}) {
  const ev = EVENTS[type];
  const topic = typeof env?.NTFY_TOPIC === "string" ? env.NTFY_TOPIC.trim() : "";
  if (!ev || !/^[A-Za-z0-9_-]{16,64}$/.test(topic)) return null;
  const server = (typeof env.NTFY_SERVER === "string" && /^https:\/\/[a-z0-9.-]+(:\d+)?$/i.test(env.NTFY_SERVER.trim())
    ? env.NTFY_SERVER.trim() : DEFAULT_SERVER).replace(/\/$/, "");
  const prefix = typeof env.NTFY_TITLE_PREFIX === "string" ? env.NTFY_TITLE_PREFIX : "";
  const title = `${prefix}${ev.title}${titleSuffix ? ": " + titleSuffix : ""}`;
  const headers = {
    "content-type": "text/plain; charset=utf-8",
    title: headerSafe(title),
    priority: String(ev.priority),
    tags: ev.tags.join(","),
  };
  if (click && /^https:\/\//.test(click)) headers.click = click;
  const token = typeof env.NTFY_TOKEN === "string" ? env.NTFY_TOKEN.trim() : "";
  if (token) headers.authorization = `Bearer ${token}`;
  return { url: `${server}/${topic}`, init: { method: "POST", headers, body: String(message).slice(0, 3500) }, title, priority: ev.priority, tags: ev.tags };
}

/** Sends one alert and resolves to the HTTP status (0 on timeout/network error/not configured). Never throws. */
export async function sendNtfy(env, type, message, opts = {}, timeoutMs = NTFY_TIMEOUT) {
  let req;
  try { req = buildNtfyRequest(env, type, message, opts); } catch { return 0; }
  if (!req) return 0;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(req.url, { ...req.init, signal: ctrl.signal });
    if (!res.ok) console.error(`notify: ntfy ${type} failed (http ${res.status})`); // status only, never the topic
    try { await res.body?.cancel(); } catch {}
    return res.status;
  } catch (e) {
    console.error(`notify: ntfy ${type} failed (${e && e.name === "AbortError" ? "timeout" : "network"})`);
    return 0;
  } finally { clearTimeout(timer); }
}

/** Fire-and-forget: schedules the alert with context.waitUntil (or lets it run detached). Returns immediately. */
export function notify(context, type, message, opts = {}) {
  try {
    const p = sendNtfy(context?.env || {}, type, message, opts).catch(() => 0);
    if (typeof context?.waitUntil === "function") context.waitUntil(p);
    return p;
  } catch { return Promise.resolve(0); }
}

/** Ready for /api/click (PR #20): call with the day's count before and after a counted click. No extra KV writes. */
export function notifyClickMilestone(context, prev, next, scope = "outbound clicks today") {
  const m = crossedMilestone(prev, next);
  if (!m) return null;
  return notify(context, "click_milestone", `${m} ${scope}`, { titleSuffix: String(m) });
}
