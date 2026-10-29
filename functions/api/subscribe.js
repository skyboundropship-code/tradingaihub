// POST /api/subscribe — newsletter signup stored in Workers KV (binding: NEWSLETTER).
// Body: JSON or form-encoded { email, locale, source, website (honeypot) }.
// Keys:  sub:<lowercased email> -> {email, locale, ts, source, consent:true}
//        rl:<sha256(ip)>        -> request count, expires after 1 hour
const LOCALES = ["en", "he", "es", "pt", "de", "fr", "ja", "ko", "zh", "hi", "tr", "ar", "ru"];
const EMAIL_RE = /^[^\s@"<>()[\]\\,;:]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/;
const RATE_MAX = 5;          // requests per IP per window
const RATE_WINDOW = 3600;    // seconds
const MAX_BODY = 4096;       // bytes

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff" },
  });

async function sha256(s) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function readBody(request) {
  const text = await request.text();
  if (text.length > MAX_BODY) return null;
  const type = (request.headers.get("content-type") || "").toLowerCase();
  if (type.includes("application/json")) {
    try { const o = JSON.parse(text); return o && typeof o === "object" ? o : null; } catch { return null; }
  }
  if (type.includes("application/x-www-form-urlencoded") || type.includes("multipart/form-data") || type === "") {
    if (type.includes("multipart/form-data")) return null; // keep it simple: JSON or urlencoded only
    return Object.fromEntries(new URLSearchParams(text));
  }
  return null;
}

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);

  if (request.method !== "POST") {
    return new Response(JSON.stringify({ ok: false, error: "method_not_allowed" }), {
      status: 405, headers: { allow: "POST", "content-type": "application/json; charset=utf-8" },
    });
  }

  // Same-origin only: browsers always send Origin on cross-site POSTs. No CORS headers are ever emitted.
  const origin = request.headers.get("origin");
  if (origin && origin !== url.origin) return json({ ok: false, error: "forbidden_origin" }, 403);

  const kv = env.NEWSLETTER;
  if (!kv) return json({ ok: false, error: "not_configured" }, 503);

  const body = await readBody(request);
  if (!body) return json({ ok: false, error: "bad_request" }, 400);

  // Honeypot: real users never fill this hidden field. Pretend success, store nothing.
  if (typeof body.website === "string" && body.website.trim() !== "") return json({ ok: true });

  // Rate limit per IP (hashed; raw IPs are never stored).
  const ip = request.headers.get("cf-connecting-ip") || request.headers.get("x-forwarded-for") || "unknown";
  const rlKey = "rl:" + (await sha256("tah-nl:" + ip));
  const count = parseInt((await kv.get(rlKey)) || "0", 10) || 0;
  if (count >= RATE_MAX) return json({ ok: false, error: "rate_limited" }, 429);
  await kv.put(rlKey, String(count + 1), { expirationTtl: RATE_WINDOW });

  const email = String(body.email ?? "").trim();
  if (!email || email.length > 254 || !EMAIL_RE.test(email) || email.split("@")[0].length > 64) {
    return json({ ok: false, error: "invalid_email" }, 400);
  }
  const locale = LOCALES.includes(String(body.locale)) ? String(body.locale) : "en";
  let source = String(body.source ?? "").slice(0, 200);
  if (!source.startsWith("/")) source = "";

  const key = "sub:" + email.toLowerCase();
  if (await kv.get(key)) return json({ ok: true }); // duplicate: keep the original record/timestamp

  await kv.put(key, JSON.stringify({ email, locale, ts: new Date().toISOString(), source, consent: true }));
  return json({ ok: true });
}
