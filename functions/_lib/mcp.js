// Remote MCP server for the TradingAIHub directory (hand-written, Streamable HTTP, JSON responses, stateless).
// Speaks MCP 2026-07-28 (stateless: per-request _meta protocolVersion + MCP-Protocol-Version / Mcp-Method / Mcp-Name
// headers, server/discover) AND the earlier initialize-handshake versions 2025-11-25 / 2025-06-18 / 2025-03-26, so
// current clients (Claude, Cursor, ChatGPT, mcp-remote, the Inspector) work. No sessions: Mcp-Session-Id is never
// issued and ignored if sent. GET (SSE stream) and DELETE return 405. Read-only tools over the public API dump.
import { loadData, searchTools, filterTools, allowed, SITE } from "./api.js";

export const MODERN = "2026-07-28";
export const LEGACY = ["2025-11-25", "2025-06-18", "2025-03-26"];
export const SUPPORTED = [MODERN, ...LEGACY];
export const SERVER_INFO = { name: "tradingaihub", title: "TradingAIHub directory", version: "1.0.0", websiteUrl: `${SITE}/developers/` };
export const INSTRUCTIONS = "Read-only directory of AI tools for finance and trading (MCP servers, agent skills and APIs), re-verified weekly by TradingAIHub. Use search_tools to find tools for a task, get_tool for full details (links, pricing, license, install packages, verification status) and list_categories to browse. Data is informational only and is not investment advice.";
const TTL_MS = 300_000;
const MAX_BODY = 64 * 1024;

const RO = { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };
export const TOOLS = [
  { name: "search_tools", title: "Search finance AI tools",
    description: "Search the TradingAIHub directory of AI tools for finance and trading (MCP servers, agent skills, APIs) by keywords, e.g. \"stock prices\", \"crypto exchange\", \"options\". Tools matching all words rank first. Returns the best matches with slug, links, pricing and weekly verification status.",
    inputSchema: { type: "object", properties: {
      query: { type: "string", minLength: 1, maxLength: 100, description: "Keywords to search for." },
      category: { type: "string", description: "Optional category slug (see list_categories), e.g. market-data." },
      limit: { type: "integer", minimum: 1, maximum: 25, default: 10, description: "Max results (1-25, default 10)." } },
      required: ["query"], additionalProperties: false },
    annotations: RO },
  { name: "get_tool", title: "Get one tool",
    description: "Full details for one tool in the TradingAIHub directory by its slug (from search_tools): homepage, docs, repo, remote MCP URL, pricing, license, npm/PyPI packages, GitHub stars and verification status.",
    inputSchema: { type: "object", properties: { slug: { type: "string", pattern: "^[a-z0-9-]+$", description: "Tool slug, e.g. alpha-vantage-mcp." } }, required: ["slug"], additionalProperties: false },
    annotations: RO },
  { name: "list_categories", title: "List categories",
    description: "All categories of the TradingAIHub directory with their slug, description and number of tools.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
    annotations: RO },
];

// Compact tool object for search results (full object comes from get_tool).
const brief = (t) => ({ slug: t.slug, name: t.name, type: t.type, category: t.category, description: t.description, status: t.status, official: t.official,
  url: t.url, homepage: t.homepage, remote_mcp_url: t.remote_mcp_url, pricing_model: t.pricing?.model ?? null, free_tier: t.pricing?.free_tier ?? null, stars: t.github?.stars ?? null });

const textResult = (obj, isError = false) => ({ content: [{ type: "text", text: JSON.stringify(obj, null, 2) }], ...(isError ? {} : { structuredContent: obj }), isError });
const toolError = (msg) => ({ content: [{ type: "text", text: msg }], isError: true });

export async function callTool(name, args, ctx) {
  args = args && typeof args === "object" && !Array.isArray(args) ? args : {};
  const data = await loadData(ctx.env, ctx.request);
  if (name === "list_categories") return textResult({ count: data.cats.categories.length, categories: data.cats.categories.map(({ slug, name, description, count, url }) => ({ slug, name, description, count, url })) });
  if (name === "get_tool") {
    const slug = typeof args.slug === "string" ? args.slug.trim().toLowerCase() : "";
    if (!slug) return toolError("slug is required (a tool slug from search_tools, e.g. alpha-vantage-mcp).");
    const t = data.bySlug.get(slug);
    return t ? textResult({ tool: t }) : toolError(`No tool with slug "${slug.slice(0, 100)}". Use search_tools to find slugs.`);
  }
  if (name === "search_tools") {
    const q = typeof args.query === "string" ? args.query.trim() : "";
    if (!q || q.length > 100) return toolError("query is required (1-100 characters).");
    const cats = allowed(data).category;
    if (args.category != null && args.category !== "" && !cats.includes(args.category)) return toolError(`Unknown category "${String(args.category).slice(0, 60)}". Valid: ${cats.join(", ")}.`);
    let limit = args.limit == null ? 10 : Number(args.limit);
    if (!Number.isInteger(limit) || limit < 1 || limit > 25) return toolError("limit must be an integer from 1 to 25.");
    const res = searchTools(filterTools(data.dump.tools, { category: args.category || undefined }), q, limit).map(brief);
    return textResult({ query: q, count: res.length, tools: res, ...(res.length ? {} : { hint: "No match. Try fewer or broader words, or list_categories." }) });
  }
  return null;
}

// ---- HTTP layer
export const MCP_CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "POST, GET, OPTIONS",
  "access-control-allow-headers": "content-type, accept, authorization, mcp-protocol-version, mcp-session-id, mcp-method, mcp-name, last-event-id",
  "access-control-expose-headers": "mcp-protocol-version, ratelimit-limit, ratelimit-remaining, ratelimit-reset, retry-after",
  "access-control-max-age": "86400",
};
const rpcRes = (status, body, headers = {}) => new Response(body == null ? null : JSON.stringify(body), { status, headers: { ...MCP_CORS, "cache-control": "no-store", ...(body == null ? {} : { "content-type": "application/json" }), ...headers } });
const rpcErr = (status, id, code, message, data, headers) => rpcRes(status, { jsonrpc: "2.0", id: id ?? null, error: { code, message, ...(data ? { data } : {}) } }, headers);

/** Header value, decoding the `=?base64?...?=` form the 2026-07-28 transport allows for non-ASCII values. */
export function hdr(request, name) {
  const v = request.headers.get(name);
  if (v == null) return null;
  const m = /^=\?base64\?(.*)\?=$/i.exec(v.trim());
  if (!m) return v.trim();
  try { return new TextDecoder().decode(Uint8Array.from(atob(m[1]), (c) => c.charCodeAt(0))); } catch { return undefined; }
}

/** Origin check (spec: servers MUST validate Origin; 403 if present and invalid). This server is public, read-only and
 *  credential-less with CORS *, so any well-formed http(s) origin is accepted; only malformed / opaque ("null") origins
 *  are refused. There is no local or authenticated surface for DNS rebinding to reach. */
export function originOk(request) {
  const o = request.headers.get("origin");
  if (o == null) return true;
  try { const u = new URL(o); return (u.protocol === "https:" || u.protocol === "http:") && u.origin === o.replace(/\/$/, ""); } catch { return false; }
}

export async function handleMcp({ request, env }, rlHeaders = {}) {
  const H = rlHeaders;
  if (!originOk(request)) return rpcErr(403, null, -32600, "Forbidden: invalid Origin header", null, H);
  const ct = request.headers.get("content-type") || "";
  if (!/^application\/json\b/i.test(ct)) return rpcErr(415, null, -32700, "Content-Type must be application/json", null, H);
  const len = Number(request.headers.get("content-length") || 0);
  if (len > MAX_BODY) return rpcErr(413, null, -32600, "Request body too large", null, H);
  let text, msg;
  try { text = await request.text(); } catch { return rpcErr(400, null, -32700, "Parse error", null, H); }
  if (text.length > MAX_BODY) return rpcErr(413, null, -32600, "Request body too large", null, H);
  try { msg = JSON.parse(text); } catch { return rpcErr(400, null, -32700, "Parse error", null, H); }
  if (Array.isArray(msg)) return rpcErr(400, null, -32600, "JSON-RPC batches are not supported", null, H);
  if (!msg || typeof msg !== "object" || msg.jsonrpc !== "2.0") return rpcErr(400, msg?.id, -32600, "Invalid Request", null, H);

  const isResponse = !("method" in msg) && ("result" in msg || "error" in msg);
  if (isResponse) return rpcRes(202, null, H); // we never send requests, so nothing to match
  if (typeof msg.method !== "string") return rpcErr(400, msg.id, -32600, "Invalid Request: method must be a string", null, H);
  const isNotification = !("id" in msg);
  if (!isNotification && !(typeof msg.id === "string" || (typeof msg.id === "number" && Number.isFinite(msg.id)))) return rpcErr(400, null, -32600, "Invalid Request: id must be a string or number", null, H);
  const id = msg.id, method = msg.method, params = msg.params && typeof msg.params === "object" ? msg.params : {};

  const hv = request.headers.get("mcp-protocol-version");
  const metaV = params._meta?.["io.modelcontextprotocol/protocolVersion"];
  // Modern (2026-07-28) when either the header or _meta says so, or _meta names a version we don't know (-> -32022).
  const modern = hv === MODERN || metaV === MODERN || (typeof metaV === "string" && !LEGACY.includes(metaV));

  if (modern && method !== "initialize") {
    // 2026-07-28: per-request version in _meta, mirrored in headers that intermediaries can route on.
    if (typeof metaV !== "string" || hv !== metaV) return rpcErr(400, id, -32020, `MCP-Protocol-Version header (${hv ?? "missing"}) does not match _meta io.modelcontextprotocol/protocolVersion (${metaV ?? "missing"})`, null, H);
    if (metaV !== MODERN) return rpcErr(400, id, -32022, `Unsupported protocol version: ${String(metaV).slice(0, 40)}`, { supported: SUPPORTED, requested: metaV }, H);
    const mh = hdr(request, "mcp-method");
    if (mh !== method) return rpcErr(400, id, -32020, `Mcp-Method header (${mh ?? "missing"}) does not match the request method`, null, H);
    if (method === "tools/call") {
      const nh = hdr(request, "mcp-name");
      if (nh !== params.name) return rpcErr(400, id, -32020, `Mcp-Name header (${nh ?? "missing"}) does not match params.name`, null, H);
    }
  } else if (hv != null && method !== "initialize" && !SUPPORTED.includes(hv)) {
    return rpcErr(400, id, -32600, `Unsupported MCP-Protocol-Version: ${hv.slice(0, 40)}`, { supported: SUPPORTED, requested: hv }, H);
  }
  const era = modern && method !== "initialize" ? metaV : (hv && SUPPORTED.includes(hv) ? hv : "2025-03-26");
  const out = { "mcp-protocol-version": era, ...H };
  const isModern = era === MODERN;
  const ok = (result) => rpcRes(200, { jsonrpc: "2.0", id, result: isModern ? { resultType: "complete", ...result } : result }, out);

  if (isNotification) return rpcRes(202, null, out); // notifications/initialized, cancelled, etc.

  switch (method) {
    case "initialize": {
      const req = params.protocolVersion;
      const v = LEGACY.includes(req) ? req : LEGACY[0];
      return rpcRes(200, { jsonrpc: "2.0", id, result: { protocolVersion: v, capabilities: { tools: { listChanged: false } }, serverInfo: SERVER_INFO, instructions: INSTRUCTIONS } }, { ...out, "mcp-protocol-version": v });
    }
    case "server/discover":
      return ok({ supportedVersions: SUPPORTED, capabilities: { tools: {} }, instructions: INSTRUCTIONS, ttlMs: TTL_MS, cacheScope: "public", _meta: { "io.modelcontextprotocol/serverInfo": SERVER_INFO } });
    case "ping":
      return ok({});
    case "tools/list":
      return ok(isModern ? { tools: TOOLS, ttlMs: TTL_MS, cacheScope: "public" } : { tools: TOOLS });
    case "tools/call": {
      const name = params.name;
      if (typeof name !== "string" || !TOOLS.some((t) => t.name === name)) return rpcErr(200, id, -32602, `Unknown tool: ${String(name).slice(0, 60)}`, null, out);
      let r;
      try { r = await callTool(name, params.arguments, { env, request }); } catch { return rpcErr(200, id, -32603, "Internal error: data temporarily unavailable", null, out); }
      return ok(r);
    }
    default:
      // Modern transport: unknown methods are HTTP 404 + -32601. Older versions: HTTP 200 with the JSON-RPC error.
      return rpcErr(isModern ? 404 : 200, id, -32601, `Method not found: ${method.slice(0, 60)}`, null, out);
  }
}

export const SERVER_CARD = {
  $schema: "https://static.modelcontextprotocol.io/schemas/v1/server-card.schema.json",
  name: "com.tradingaihub/directory",
  version: SERVER_INFO.version,
  title: SERVER_INFO.title,
  description: "Search the TradingAIHub directory of AI tools for finance and trading: MCP servers, agent skills and APIs, re-verified weekly. Read-only, no sign-in.",
  websiteUrl: `${SITE}/developers/`,
  icons: [{ src: `${SITE}/logo-512.png`, mimeType: "image/png", sizes: ["512x512"] }],
  remotes: [{ type: "streamable-http", url: `${SITE}/mcp`, supportedProtocolVersions: SUPPORTED }],
};
