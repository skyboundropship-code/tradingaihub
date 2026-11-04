// npm run test:functions: the remote MCP server (functions/mcp/index.js + functions/_lib/mcp.js) and the discovery
// documents (functions/mcp/server-card.js, functions/.well-known/ai-catalog.json.js). Mocked env.ASSETS, no network.
import test from "node:test";
import assert from "node:assert/strict";
import { onRequest as mcp } from "../functions/mcp/index.js";
import { onRequest as card } from "../functions/mcp/server-card.js";
import { onRequest as catalog } from "../functions/.well-known/ai-catalog.json.js";
import { _rateLimitState, _resetDataCache, LIMITS } from "../functions/_lib/api.js";
import { MODERN, SUPPORTED, TOOLS, hdr } from "../functions/_lib/mcp.js";
import { makeAssets, freshIp } from "./fixtures/public-api.mjs";

const URL_ = "https://tradingaihub.com/mcp";
const META = "io.modelcontextprotocol/protocolVersion";
async function rpc(msg, { headers = {}, ip = freshIp(), method = "POST", raw, env } = {}) {
  const request = new Request(URL_, { method, headers: { "content-type": "application/json", accept: "application/json, text/event-stream", "cf-connecting-ip": ip, ...headers },
    body: method === "POST" ? (raw ?? JSON.stringify(msg)) : undefined });
  const res = await mcp({ request, env: env ?? { ASSETS: makeAssets() } });
  const text = await res.text();
  return { res, text, body: text ? JSON.parse(text) : null };
}
// 2026-07-28 request: version in _meta and in the MCP-Protocol-Version header, method/name mirrored in headers.
const modern = (method, params = {}, extraHeaders = {}) => rpc({ jsonrpc: "2.0", id: 7, method, params: { ...params, _meta: { [META]: MODERN } } },
  { headers: { "mcp-protocol-version": MODERN, "mcp-method": method, ...(method === "tools/call" ? { "mcp-name": params.name } : {}), ...extraHeaders } });
test.beforeEach(() => { _resetDataCache(); _rateLimitState.reset(); });

test("legacy flow: initialize -> initialized -> tools/list -> tools/call", async () => {
  let r = await rpc({ jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "t", version: "1" } } });
  assert.equal(r.res.status, 200);
  assert.equal(r.body.result.protocolVersion, "2025-06-18");
  assert.equal(r.body.result.serverInfo.name, "tradingaihub");
  assert.ok(r.body.result.capabilities.tools);
  assert.equal(r.res.headers.get("mcp-session-id"), null); // stateless
  assert.equal(r.res.headers.get("access-control-allow-origin"), "*");
  r = await rpc({ jsonrpc: "2.0", id: 9, method: "initialize", params: { protocolVersion: "1999-01-01" } });
  assert.equal(r.body.result.protocolVersion, "2025-11-25"); // negotiates down to our latest handshake version
  const H = { "mcp-protocol-version": "2025-11-25" };
  r = await rpc({ jsonrpc: "2.0", method: "notifications/initialized" }, { headers: H });
  assert.equal(r.res.status, 202); assert.equal(r.text, "");
  r = await rpc({ jsonrpc: "2.0", id: 2, method: "tools/list" }, { headers: H });
  assert.deepEqual(r.body.result.tools.map((t) => t.name), ["search_tools", "get_tool", "list_categories"]);
  assert.equal(r.body.result.resultType, undefined);
  for (const t of r.body.result.tools) assert.equal(t.annotations.readOnlyHint, true);
  r = await rpc({ jsonrpc: "2.0", id: 3, method: "tools/call", params: { name: "search_tools", arguments: { query: "stock prices" } } }, { headers: H });
  assert.equal(r.body.result.isError, false);
  assert.equal(r.body.result.structuredContent.tools[0].slug, "yfinance-mcp");
  assert.deepEqual(JSON.parse(r.body.result.content[0].text), r.body.result.structuredContent);
  r = await rpc({ jsonrpc: "2.0", id: 4, method: "tools/call", params: { name: "get_tool", arguments: { slug: "ccxt-mcp" } } }, { headers: H });
  assert.equal(r.body.result.structuredContent.tool.packages.npm.name, "ccxt-mcp");
  r = await rpc({ jsonrpc: "2.0", id: 5, method: "tools/call", params: { name: "list_categories", arguments: {} } }, { headers: H });
  assert.equal(r.body.result.structuredContent.count, 3);
  r = await rpc({ jsonrpc: "2.0", id: "p", method: "ping" }, { headers: H });
  assert.deepEqual(r.body, { jsonrpc: "2.0", id: "p", result: {} });
});

test("tool errors are isError results; unknown tool is -32602", async () => {
  const H = { "mcp-protocol-version": "2025-11-25" };
  const call = (name, args) => rpc({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name, arguments: args } }, { headers: H });
  for (const [n, a] of [["get_tool", { slug: "nope" }], ["get_tool", {}], ["search_tools", {}], ["search_tools", { query: "x", limit: 26 }], ["search_tools", { query: "x", category: "nope" }]]) {
    const r = await call(n, a);
    assert.equal(r.res.status, 200); assert.equal(r.body.result.isError, true, JSON.stringify(a));
  }
  assert.equal((await call("search_tools", { query: "crypto", category: "crypto", limit: 1 })).body.result.structuredContent.count, 1);
  const r = await call("delete_everything", {});
  assert.equal(r.body.error.code, -32602);
  const u = await rpc({ jsonrpc: "2.0", id: 1, method: "resources/list" }, { headers: H });
  assert.equal(u.res.status, 200); assert.equal(u.body.error.code, -32601);
});

test("modern 2026-07-28: server/discover, tools/list, tools/call with headers", async () => {
  let r = await modern("server/discover");
  assert.equal(r.res.status, 200);
  assert.equal(r.body.result.resultType, "complete");
  assert.deepEqual(r.body.result.supportedVersions, SUPPORTED);
  assert.equal(r.res.headers.get("mcp-protocol-version"), MODERN);
  r = await modern("tools/list");
  assert.equal(r.body.result.tools.length, TOOLS.length);
  assert.ok(r.body.result.ttlMs > 0);
  r = await modern("tools/call", { name: "get_tool", arguments: { slug: "alpha-vantage-mcp" } });
  assert.equal(r.body.result.resultType, "complete");
  assert.equal(r.body.result.structuredContent.tool.official, true);
  // Base64 header form for Mcp-Name
  r = await modern("tools/call", { name: "list_categories", arguments: {} }, { "mcp-name": `=?base64?${btoa("list_categories")}?=` });
  assert.equal(r.res.status, 200);
  assert.equal(hdr(new Request(URL_, { headers: { x: "=?base64?aGk=?=" } }), "x"), "hi");
});

test("modern: header mismatches -> -32020, unknown version -> -32022, unknown method -> HTTP 404", async () => {
  let r = await rpc({ jsonrpc: "2.0", id: 1, method: "tools/list", params: { _meta: { [META]: MODERN } } }, { headers: { "mcp-method": "tools/list" } });
  assert.equal(r.res.status, 400); assert.equal(r.body.error.code, -32020);
  r = await modern("tools/list", {}, { "mcp-method": "tools/call" });
  assert.equal(r.body.error.code, -32020);
  r = await modern("tools/call", { name: "get_tool", arguments: { slug: "x" } }, { "mcp-name": "search_tools" });
  assert.equal(r.body.error.code, -32020);
  r = await rpc({ jsonrpc: "2.0", id: 1, method: "tools/list", params: { _meta: { [META]: "2099-01-01" } } }, { headers: { "mcp-protocol-version": "2099-01-01", "mcp-method": "tools/list" } });
  assert.equal(r.res.status, 400); assert.equal(r.body.error.code, -32022);
  assert.deepEqual(r.body.error.data, { supported: SUPPORTED, requested: "2099-01-01" });
  r = await modern("resources/list");
  assert.equal(r.res.status, 404); assert.equal(r.body.error.code, -32601);
  r = await rpc({ jsonrpc: "2.0", id: 1, method: "tools/list" }, { headers: { "mcp-protocol-version": "2099-01-01" } });
  assert.equal(r.res.status, 400); // unknown legacy header
});

test("transport: notifications/responses 202, GET/DELETE 405, OPTIONS 204, bad input 4xx", async () => {
  assert.equal((await rpc({ jsonrpc: "2.0", method: "notifications/cancelled", params: { requestId: 1 } })).res.status, 202);
  assert.equal((await rpc({ jsonrpc: "2.0", id: 1, result: {} })).res.status, 202);
  for (const m of ["GET", "DELETE", "PUT"]) {
    const r = await rpc(null, { method: m });
    assert.equal(r.res.status, 405, m); assert.equal(r.res.headers.get("allow"), "POST, OPTIONS");
  }
  const o = await rpc(null, { method: "OPTIONS" });
  assert.equal(o.res.status, 204); assert.match(o.res.headers.get("access-control-allow-headers"), /mcp-protocol-version/);
  assert.equal((await rpc(null, { raw: "{nope" })).res.status, 400);
  assert.equal((await rpc(null, { raw: "[]" })).body.error.message, "JSON-RPC batches are not supported");
  assert.equal((await rpc({ id: 1, method: "ping" })).body.error.code, -32600);
  assert.equal((await rpc(null, { raw: "{}", headers: { "content-type": "text/plain" } })).res.status, 415);
  assert.equal((await rpc(null, { raw: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "ping", params: { pad: "x".repeat(70000) } }) })).res.status, 413);
});

test("Origin: browsers allowed (public, no credentials); malformed or opaque origins 403", async () => {
  const ping = (origin) => rpc({ jsonrpc: "2.0", id: 1, method: "ping" }, { headers: { origin } });
  assert.equal((await ping("https://claude.ai")).res.status, 200);
  assert.equal((await ping("http://localhost:6274")).res.status, 200);
  assert.equal((await ping("null")).res.status, 403);
  assert.equal((await ping("file://x")).res.status, 403);
  assert.equal((await ping("https://a.com/path")).res.status, 403);
});

test("MCP rate limit: JSON-RPC 429 with Retry-After; data failure -> -32603", async () => {
  const ip = "203.0.113.50";
  for (let i = 0; i < LIMITS.mcp; i++) assert.equal((await rpc({ jsonrpc: "2.0", id: i, method: "ping" }, { ip })).res.status, 200);
  const r = await rpc({ jsonrpc: "2.0", id: 99, method: "ping" }, { ip });
  assert.equal(r.res.status, 429);
  assert.ok(Number(r.res.headers.get("retry-after")) >= 1);
  assert.equal(r.body.jsonrpc, "2.0");
  const f = await rpc({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name: "list_categories" } }, { env: { ASSETS: makeAssets({ fail: true }) } });
  assert.equal(f.body.error.code, -32603);
});

test("server card + AI catalog: types, CORS, ETag/304, 405", async () => {
  const get = (fn, path, h = {}, method = "GET") => fn({ request: new Request(`https://tradingaihub.com${path}`, { method, headers: h }) });
  let res = await get(card, "/mcp/server-card");
  assert.equal(res.status, 200);
  assert.match(res.headers.get("content-type"), /^application\/mcp-server-card\+json/);
  assert.equal(res.headers.get("access-control-allow-origin"), "*");
  assert.equal(res.headers.get("cache-control"), "public, max-age=3600");
  const c = await res.json();
  assert.equal(c.remotes[0].type, "streamable-http");
  assert.equal(c.remotes[0].url, URL_);
  assert.deepEqual(c.remotes[0].supportedProtocolVersions, SUPPORTED);
  const etag = res.headers.get("etag");
  assert.match(etag, /^"[0-9a-f]{16}"$/);
  assert.equal((await get(card, "/mcp/server-card", { "if-none-match": etag })).status, 304);
  assert.equal((await get(card, "/mcp/server-card", {}, "POST")).status, 405);
  res = await get(catalog, "/.well-known/ai-catalog.json");
  assert.match(res.headers.get("content-type"), /^application\/ai-catalog\+json/);
  const cat = await res.json();
  assert.equal(cat.entries[0].url, "https://tradingaihub.com/mcp/server-card");
  assert.equal(cat.entries[0].type, "application/mcp-server-card+json");
  assert.equal((await get(catalog, "/.well-known/ai-catalog.json", { "if-none-match": `W/${res.headers.get("etag")}` })).status, 304);
});
