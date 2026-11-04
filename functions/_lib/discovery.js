// Static discovery documents (server card, AI catalog) with the CORS / cache / ETag headers the Server Card spec asks for.
const enc = new TextEncoder();
const etags = new WeakMap();
async function etagOf(doc, body) {
  if (!etags.has(doc)) {
    const d = await crypto.subtle.digest("SHA-256", enc.encode(body));
    etags.set(doc, `"${[...new Uint8Array(d).slice(0, 8)].map((b) => b.toString(16).padStart(2, "0")).join("")}"`);
  }
  return etags.get(doc);
}
export async function serveDiscoveryDoc(request, doc, type) {
  const cors = { "access-control-allow-origin": "*", "access-control-allow-methods": "GET, HEAD, OPTIONS", "access-control-allow-headers": "content-type, if-none-match", "access-control-expose-headers": "etag" };
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: { ...cors, "access-control-max-age": "86400" } });
  if (request.method !== "GET" && request.method !== "HEAD") return new Response(JSON.stringify({ error: { status: 405, code: "method_not_allowed", message: "Use GET." } }), { status: 405, headers: { ...cors, allow: "GET, HEAD, OPTIONS", "content-type": "application/json" } });
  const body = JSON.stringify(doc, null, 2);
  const etag = await etagOf(doc, body);
  const h = { ...cors, "content-type": `${type}; charset=utf-8`, "cache-control": "public, max-age=3600", etag, vary: "accept" };
  const inm = request.headers.get("if-none-match");
  if (inm && inm.split(",").map((s) => s.trim().replace(/^W\//, "")).includes(etag)) return new Response(null, { status: 304, headers: h });
  return new Response(request.method === "HEAD" ? null : body, { headers: h });
}
