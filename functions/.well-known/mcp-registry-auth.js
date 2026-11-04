// /.well-known/mcp-registry-auth: MCP Registry HTTP namespace proof for com.tradingaihub/* (mcp-publisher login http).
// The registry fetches https://tradingaihub.com/.well-known/mcp-registry-auth without following redirects and needs a 200
// with the one-line record "v=MCPv1; k=ed25519; p=<base64 Ed25519 public key>". Public key only; the private key is never
// in this repo. Served by a Function (not a static file) so public/_headers stays untouched and the type is text/plain.
export const MCP_REGISTRY_AUTH = "v=MCPv1; k=ed25519; p=OL1SseVv2yp4F6slj+bKOX50o+KFqdjz4IH/fKzS/TQ=";
const H = { "content-type": "text/plain; charset=utf-8", "cache-control": "public, max-age=300", "access-control-allow-origin": "*", "x-content-type-options": "nosniff" };
export function onRequest({ request }) {
  if (request.method !== "GET" && request.method !== "HEAD") return new Response("Method not allowed\n", { status: 405, headers: { ...H, allow: "GET, HEAD" } });
  return new Response(request.method === "HEAD" ? null : MCP_REGISTRY_AUTH + "\n", { status: 200, headers: H });
}
