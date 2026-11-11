// /mcp: remote MCP server (Streamable HTTP, stateless, JSON responses). Logic in functions/_lib/mcp.js.
import { rateLimit, LIMITS } from "../_lib/api.js";
import { handleMcp, MCP_CORS } from "../_lib/mcp.js";

export async function onRequest(ctx) {
  const { request } = ctx;
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: { ...MCP_CORS, "cache-control": "public, max-age=86400" } });
  // No server-initiated stream (GET/SSE) and no sessions to end (DELETE): 405, as the transport spec allows.
  if (request.method !== "POST") {
    return new Response(JSON.stringify({ jsonrpc: "2.0", id: null, error: { code: -32000, message: `${request.method} not allowed: POST JSON-RPC messages to this endpoint. Docs: https://tradingaihub.com/developers/` } }),
      { status: 405, headers: { ...MCP_CORS, allow: "POST, OPTIONS", "content-type": "application/json", "cache-control": "no-store" } });
  }
  const rl = await rateLimit(request, "mcp", LIMITS.mcp);
  if (!rl.ok) {
    return new Response(JSON.stringify({ jsonrpc: "2.0", id: null, error: { code: -32000, message: `Rate limited: retry after ${rl.retryAfter} s`, data: { retry_after: rl.retryAfter } } }),
      { status: 429, headers: { ...MCP_CORS, ...rl.headers, "content-type": "application/json", "cache-control": "no-store" } });
  }
  return handleMcp(ctx, rl.headers);
}
