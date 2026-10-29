// Backfill helpers with mocked fetch (no network, no KV, no wrangler).
import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mask, syncOne } from "../scripts/ml_backfill.mjs";

const K = "fake-backfill-key", G = "202680264761018021", ML = "https://connect.mailerlite.com/api/subscribers";
async function withFetch(routes, fn) {
  const calls = []; const rf = globalThis.fetch;
  globalThis.fetch = async (u, i) => { calls.push({ u: String(u), m: i.method, body: i.body ? JSON.parse(i.body) : undefined, auth: i.headers.authorization });
    const r = routes(String(u), i.method); return new Response(JSON.stringify(r.json ?? {}), { status: r.status }); };
  try { return { out: await fn(), calls }; } finally { globalThis.fetch = rf; }
}

test("mask hides multi-label domains", () => {
  assert.equal(mask("bob@mail.example.co.uk"), "b***@m***.uk");
  assert.equal(mask("alice@example.com"), "a***@e***.com");
  assert.equal(mask("x@localhost"), "x***@l***");
  assert.ok(!mask("bob@mail.example.co.uk").includes("example"));
});

test("new subscriber (404): upsert with group + unconfirmed (DOI email)", async () => {
  const { out, calls } = await withFetch((u, m) => (m === "GET" ? { status: 404 } : { status: 201 }), () => syncOne(K, "new@example.com"));
  assert.equal(out.result, "ok");
  assert.equal(calls.length, 2);
  assert.equal(calls[0].u, `${ML}/new%40example.com`); assert.equal(calls[0].auth, `Bearer ${K}`);
  assert.deepEqual(calls[1].body, { email: "new@example.com", groups: [G], status: "unconfirmed" });
});

for (const status of ["active", "unsubscribed", "unconfirmed", "bounced", "junk"]) {
  test(`existing ${status} already in group: no write, no status change`, async () => {
    const { out, calls } = await withFetch(() => ({ status: 200, json: { data: { id: "77", status, groups: [{ id: G }] } } }), () => syncOne(K, "e@example.com"));
    assert.equal(out.result, "ok"); assert.equal(calls.length, 1); assert.equal(calls[0].m, "GET");
  });
  test(`existing ${status} not in group: group assign only, never a status upsert`, async () => {
    const { out, calls } = await withFetch((u, m) => (m === "GET" ? { status: 200, json: { data: { id: "77", status, groups: [] } } } : { status: 200 }), () => syncOne(K, "e@example.com"));
    assert.equal(out.result, "ok"); assert.equal(calls.length, 2);
    assert.equal(calls[1].u, `${ML}/77/groups/${G}`); assert.equal(calls[1].m, "POST"); assert.equal(calls[1].body, undefined);
  });
}

test("lookup error (500/401) -> err, nothing written", async () => {
  for (const s of [500, 401, 429]) {
    const { out, calls } = await withFetch(() => ({ status: s }), () => syncOne(K, "e@example.com"));
    assert.equal(out.result, "err"); assert.equal(calls.length, 1);
  }
});

test("upsert 422 -> err", async () => {
  const { out } = await withFetch((u, m) => (m === "GET" ? { status: 404 } : { status: 422 }), () => syncOne(K, "e@example.com"));
  assert.equal(out.result, "err");
});

test("--apply without --remote-prod --yes refuses before touching KV or MailerLite", () => {
  for (const args of [["--apply"], ["--apply", "--yes"], ["--apply", "--remote-prod"]]) {
    const r = spawnSync(process.execPath, ["scripts/ml_backfill.mjs", ...args], { encoding: "utf8", env: { ...process.env, PATH: "/nonexistent" } });
    assert.equal(r.status, 2, args.join(" ")); assert.match(r.stderr, /refusing/);
  }
});
