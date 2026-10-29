// POST /api/subscribe — newsletter signup stored in Workers KV (binding: NEWSLETTER).
// Body: JSON or form-encoded { email, locale, website (honeypot) }.
// Keys:  sub:<lowercased email>      -> {email, locale, ts, consent:true}   (nothing else is stored)
//        rl:<sha256(RL_SALT + ip)>   -> request count, expires after 1 hour (raw IPs are never stored)
// Secret: RL_SALT (wrangler pages secret). Without it, writes are refused with 503.
const LOCALES = ["en", "he", "es", "pt", "de", "fr", "ja", "ko", "zh", "hi", "tr", "ar", "ru"];
const EMAIL_RE = /^[^\s@"<>()[\]\\,;:]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/;
const RATE_MAX = 5;          // requests per IP per window
const RATE_WINDOW = 3600;    // seconds
const MAX_BODY = 4096;       // bytes

const json = (body, status = 200, extra = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff", ...extra },
  });
const serverError = () => json({ ok: false, error: "server" }, 503);

async function sha256(s) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// Reads at most MAX_BODY bytes. Returns null if the body is larger (checked via Content-Length first,
// then enforced while streaming, so an oversized or lying body is never buffered whole).
async function readLimited(request) {
  const cl = request.headers.get("content-length");
  if (cl !== null && (!/^\d+$/.test(cl) || Number(cl) > MAX_BODY)) return null;
  if (!request.body) return "";
  const reader = request.body.getReader();
  const chunks = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > MAX_BODY) { try { await reader.cancel(); } catch {} return null; }
    chunks.push(value);
  }
  const buf = new Uint8Array(size);
  let off = 0;
  for (const c of chunks) { buf.set(c, off); off += c.byteLength; }
  return new TextDecoder().decode(buf);
}

async function readBody(request) {
  const type = (request.headers.get("content-type") || "").toLowerCase();
  const isJson = type.includes("application/json");
  const isForm = type.includes("application/x-www-form-urlencoded") || type === "";
  if (!isJson && !isForm) return null; // JSON or urlencoded only
  const text = await readLimited(request);
  if (text === null) return null;
  if (isJson) {
    try { const o = JSON.parse(text); return o && typeof o === "object" && !Array.isArray(o) ? o : null; } catch { return null; }
  }
  return Object.fromEntries(new URLSearchParams(text));
}

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);

  if (request.method !== "POST") {
    return json({ ok: false, error: "method_not_allowed" }, 405, { allow: "POST" });
  }

  // Same-origin only. Browsers send Origin on every POST (fetch and native forms); scripts without it are refused.
  // No CORS headers are ever emitted.
  const origin = request.headers.get("origin");
  if (!origin || origin !== url.origin) return json({ ok: false, error: "forbidden_origin" }, 403);

  const kv = env.NEWSLETTER;
  if (!kv) return json({ ok: false, error: "not_configured" }, 503);

  const body = await readBody(request);
  if (!body) return json({ ok: false, error: "bad_request" }, 400);

  // Honeypot: real users never fill this hidden field. Pretend success, store nothing.
  if (typeof body.website === "string" && body.website.trim() !== "") return json({ ok: true });

  // The IP hash salt is a secret; without it the rate limit can't be applied safely, so refuse writes.
  const salt = typeof env.RL_SALT === "string" ? env.RL_SALT : "";
  if (salt.length < 16) return serverError();

  try {
    // Rate limit per IP (hashed with a secret salt). One KV write per accepted request.
    const ip = request.headers.get("cf-connecting-ip") || request.headers.get("x-forwarded-for") || "unknown";
    const rlKey = "rl:" + (await sha256(salt + "|" + ip));
    const count = parseInt((await kv.get(rlKey)) || "0", 10) || 0;
    if (count >= RATE_MAX) return json({ ok: false, error: "rate_limited" }, 429);
    await kv.put(rlKey, String(count + 1), { expirationTtl: RATE_WINDOW });

    const email = String(body.email ?? "").trim();
    if (!email || email.length > 254 || !EMAIL_RE.test(email) || email.split("@")[0].length > 64) {
      return json({ ok: false, error: "invalid_email" }, 400);
    }
    const locale = LOCALES.includes(String(body.locale)) ? String(body.locale) : "en";

    const key = "sub:" + email.toLowerCase();
    if ((await kv.get(key)) !== null) return json({ ok: true }); // duplicate: no write, original record kept

    await kv.put(key, JSON.stringify({ email, locale, ts: new Date().toISOString(), consent: true }));
    return json({ ok: true });
  } catch {
    return serverError();
  }
}
