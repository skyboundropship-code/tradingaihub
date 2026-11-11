// /api/openapi.json: the static OpenAPI 3.1 document (built from src/lib/openapi.ts), served with CORS + cache headers.
import { json, error, methodGate, rateLimit, tooMany, LIMITS } from "../_lib/api.js";
let doc = null;
export async function onRequest({ request, env }) {
  const gate = methodGate(request);
  if (gate) return gate;
  const rl = await rateLimit(request, "api", LIMITS.api);
  if (!rl.ok) return tooMany(rl, request.method);
  if (!doc) {
    const r = env?.ASSETS ? await env.ASSETS.fetch(new Request(new URL("/api/openapi.json", request.url))) : null;
    if (!r?.ok) return error(503, "unavailable", "OpenAPI document temporarily unavailable.", {}, rl.headers, request.method);
    doc = await r.text();
  }
  return json(doc, 200, rl.headers, request.method);
}
