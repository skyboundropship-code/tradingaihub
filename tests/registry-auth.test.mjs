// npm run test:functions: /.well-known/mcp-registry-auth (MCP Registry HTTP auth record). No network.
import test from "node:test";
import assert from "node:assert/strict";
import { onRequest, MCP_REGISTRY_AUTH } from "../functions/.well-known/mcp-registry-auth.js";
const U = "https://tradingaihub.com/.well-known/mcp-registry-auth";
test("mcp-registry-auth: 200 text/plain one-line ed25519 record, public key only", async () => {
  const r = onRequest({ request: new Request(U) });
  assert.equal(r.status, 200);
  assert.equal(r.headers.get("location"), null);
  assert.match(r.headers.get("content-type"), /^text\/plain/);
  const body = await r.text();
  assert.equal(body.trim(), MCP_REGISTRY_AUTH);
  const m = /^v=MCPv1; k=ed25519; p=([A-Za-z0-9+/]{43}=)$/.exec(body.trim());
  assert.ok(m, body);
  assert.equal(Buffer.from(m[1], "base64").length, 32);
  assert.doesNotMatch(body, /PRIVATE|BEGIN/);
  assert.equal(onRequest({ request: new Request(U, { method: "HEAD" }) }).status, 200);
  assert.equal(onRequest({ request: new Request(U, { method: "POST" }) }).status, 405);
});
