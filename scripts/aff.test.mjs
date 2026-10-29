// Host-matching tests for src/lib/aff.ts. Run: node --test scripts/aff.test.mjs
// Bundles aff.ts (and config.ts) with esbuild into a temp file, then imports it.
import { test } from "node:test";
import assert from "node:assert/strict";
import { buildSync } from "esbuild";
import fs from "node:fs"; import os from "node:os"; import path from "node:path"; import { pathToFileURL } from "node:url";

const out = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "aff-test-")), "aff.mjs");
buildSync({ entryPoints: [new URL("../src/lib/aff.ts", import.meta.url).pathname], bundle: true, format: "esm", platform: "node", outfile: out, logLevel: "silent" });
const { affUrl, isAff, untagUrl, relFor } = await import(pathToFileURL(out).href);
const via = (u) => new URL(u.startsWith("//") ? "https:" + u : u).searchParams.getAll("via");

test("eodhd.com and www.eodhd.com are tagged", () => {
  assert.deepEqual(via(affUrl("https://eodhd.com/")), ["tradingaihub"]);
  assert.deepEqual(via(affUrl("https://www.eodhd.com/pricing")), ["tradingaihub"]);
  assert.deepEqual(via(affUrl("https://EODHD.com/financial-apis/")), ["tradingaihub"]);
});
test("api. and mcp. subdomains are never tagged", () => {
  for (const u of ["https://mcp.eodhd.com/v2/mcp", "https://api.eodhd.com/api/eod/AAPL.US?api_token=demo", "https://eu.api.eodhd.com/x"]) {
    assert.equal(affUrl(u), u); assert.equal(isAff(u), false);
  }
});
test("trailing-dot host is tagged", () => {
  assert.deepEqual(via(affUrl("https://eodhd.com./pricing")), ["tradingaihub"]);
  assert.equal(isAff(affUrl("https://eodhd.com./pricing")), true);
});
test("protocol-relative //eodhd.com/ is tagged", () => {
  const t = affUrl("//eodhd.com/x"); assert.deepEqual(via(t), ["tradingaihub"]); assert.equal(isAff(t), true);
});
test("double / foreign via collapses to exactly one via=tradingaihub", () => {
  assert.deepEqual(via(affUrl("https://eodhd.com/?via=other&via=tradingaihub")), ["tradingaihub"]);
  assert.deepEqual(via(affUrl(affUrl("https://eodhd.com/"))), ["tradingaihub"]);
});
test("lookalike hosts are ignored", () => {
  for (const u of ["https://eodhd.com.evil.example/", "https://noteodhd.com/", "https://eodhd.co/", "https://example.com/?u=eodhd.com"]) {
    assert.equal(affUrl(u), u); assert.equal(isAff(u), false);
  }
});
test("untagUrl strips only the program's param on its hosts", () => {
  assert.equal(untagUrl("https://eodhd.com/financial-apis/?via=tradingaihub", "eodhd"), "https://eodhd.com/financial-apis/");
  assert.equal(untagUrl("https://eodhd.com/financial-apis/", "eodhd"), "https://eodhd.com/financial-apis/");
  assert.equal(untagUrl("https://mcp.eodhd.com/v2/mcp", "eodhd"), "https://mcp.eodhd.com/v2/mcp");
  const tv = affUrl("https://www.tradingview.com/");
  assert.equal(untagUrl(tv, "eodhd"), tv);
  assert.equal(untagUrl(undefined, "eodhd"), undefined);
});
test("TradingView subdomains are still tagged and rel is sponsored", () => {
  const u = affUrl("https://www.tradingview.com/pricing/");
  assert.equal(new URL(u).searchParams.get("aff_id"), "1173592"); assert.equal(isAff(u), true);
  assert.equal(relFor(u), "sponsored noopener"); assert.equal(relFor("https://github.com/x/y"), "noopener");
});
