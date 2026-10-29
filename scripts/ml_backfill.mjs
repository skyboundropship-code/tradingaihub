#!/usr/bin/env node
// One-time backfill: copy existing newsletter signups from Workers KV (NEWSLETTER) into the MailerLite
// group "Website signups". Not part of the build. Run from the repo root (needs wrangler auth).
//
//   node scripts/ml_backfill.mjs                 # dry run (default): prints the count and masked emails only
//   ML_KEY_FILE=/path/to/key node scripts/ml_backfill.mjs --apply
//   MAILERLITE_API_KEY=... node scripts/ml_backfill.mjs --apply   (env var also accepted)
//
// Double opt-in: every subscriber is upserted with status "unconfirmed", so MailerLite sends its double
// opt-in confirmation email (account setting "Double opt-in for API and integrations" is ON). These people
// consented on our form but never confirmed by email, so nobody is made "active" without clicking the link.
// Records already synced (ml:"ok") are skipped, so re-running is safe. After a successful upsert the KV
// record gets ml:"ok"; failures get ml:"err" and are retried on the next run.
// The API key is read from a file or env var and is never printed or passed on a command line.
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const NAMESPACE_ID = process.env.NEWSLETTER_KV_ID || "a9f8a42d1ec641c8abe07640adb8241e"; // tradingaihub-newsletter (production)
const ML_ENDPOINT = "https://connect.mailerlite.com/api/subscribers";
const ML_GROUP = "202680264761018021"; // "Website signups"
const APPLY = process.argv.includes("--apply");
const INCLUDE_SYNCED = process.argv.includes("--include-synced");

const mask = (e) => {
  const [u, d = ""] = String(e).split("@");
  return `${u.slice(0, 1)}***@${d.replace(/^[^.]*/, (h) => h.slice(0, 1) + "***")}`;
};

function wrangler(args) {
  const r = spawnSync("npx", ["wrangler", ...args], { encoding: "utf8", maxBuffer: 64 << 20 });
  if (r.status !== 0) throw new Error(`wrangler ${args[0]} ${args[1]} ${args[2]} failed (exit ${r.status})`);
  return r.stdout;
}

function listKeys() {
  const out = wrangler(["kv", "key", "list", "--namespace-id", NAMESPACE_ID, "--prefix", "sub:", "--remote"]);
  const start = out.indexOf("[");
  return JSON.parse(out.slice(start)).map((k) => k.name).filter((n) => n.startsWith("sub:"));
}

function getRecord(name) {
  const raw = wrangler(["kv", "key", "get", name, "--namespace-id", NAMESPACE_ID, "--remote", "--text"]);
  const start = raw.indexOf("{");
  return JSON.parse(raw.slice(start));
}

function putRecord(name, rec) {
  const tmp = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "mlbf-")), "v.json");
  fs.writeFileSync(tmp, JSON.stringify(rec), { mode: 0o600 });
  try { wrangler(["kv", "key", "put", name, "--namespace-id", NAMESPACE_ID, "--remote", "--path", tmp]); }
  finally { fs.rmSync(path.dirname(tmp), { recursive: true, force: true }); }
}

function readKey() {
  const file = process.env.ML_KEY_FILE;
  const k = file ? fs.readFileSync(file, "utf8").trim() : String(process.env.MAILERLITE_API_KEY || "").trim();
  if (!k) throw new Error("no API key: set ML_KEY_FILE (path) or MAILERLITE_API_KEY");
  return k;
}

async function upsert(apiKey, email) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 10000);
  try {
    const res = await fetch(ML_ENDPOINT, {
      method: "POST",
      headers: { authorization: `Bearer ${apiKey}`, "content-type": "application/json", accept: "application/json" },
      body: JSON.stringify({ email, groups: [ML_GROUP], status: "unconfirmed" }),
      signal: ctrl.signal,
    });
    return res.status;
  } catch { return 0; } finally { clearTimeout(t); }
}

const keys = listKeys();
const records = [];
for (const name of keys) {
  try {
    const rec = getRecord(name);
    if (!rec || typeof rec.email !== "string") { console.log(`skip (unreadable record) ${mask(name.slice(4))}`); continue; }
    records.push({ name, rec });
  } catch { console.log(`skip (read error) ${mask(name.slice(4))}`); }
}
const todo = records.filter(({ rec }) => INCLUDE_SYNCED || rec.ml !== "ok");
console.log(`KV sub: records: ${records.length}; to sync: ${todo.length}${APPLY ? "" : " (dry run, nothing sent)"}`);
for (const { rec } of todo) console.log(`  ${mask(rec.email)}  locale=${rec.locale || "?"}  ml=${rec.ml || "-"}`);
if (!APPLY) process.exit(0);

const apiKey = readKey();
let ok = 0, err = 0;
for (const { name, rec } of todo) {
  const status = await upsert(apiKey, rec.email);
  const ml = status === 200 || status === 201 ? "ok" : "err";
  ml === "ok" ? ok++ : err++;
  console.log(`  ${mask(rec.email)} -> ${ml} (http ${status || "network"})`);
  try { putRecord(name, { ...rec, ml }); } catch { console.log(`  ${mask(rec.email)} kv status update failed`); }
  await new Promise((r) => setTimeout(r, 600)); // stay well under MailerLite's 120 req/min
}
console.log(`done: ok=${ok} err=${err}`);
process.exit(err ? 1 : 0);
