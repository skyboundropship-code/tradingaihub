#!/usr/bin/env node
// One-time backfill: copy existing newsletter signups from Workers KV (NEWSLETTER) into the MailerLite
// group "Website signups". Not part of the build. Run from the repo root (needs wrangler auth).
//
//   node scripts/ml_backfill.mjs                 # dry run (default): prints target, count and masked emails only
//   ML_KEY_FILE=/path/to/key node scripts/ml_backfill.mjs --apply --remote-prod --yes
//   (MAILERLITE_API_KEY env var also accepted instead of ML_KEY_FILE)
// --apply refuses to run without BOTH --remote-prod and --yes (explicit confirmation that it writes to
// production KV and to the live MailerLite account).
//
// Double opt-in: each subscriber is first looked up (GET /api/subscribers/{email}).
//   - not in MailerLite (404): upserted with status "unconfirmed", so MailerLite sends its double opt-in
//     confirmation email (account setting "Double opt-in for API and integrations" is ON). These people consented
//     on our form but never confirmed by email, so nobody is made "active" without clicking the link.
//   - already in MailerLite (any status: active, unconfirmed, unsubscribed, bounced, junk): status is never
//     touched, so no confirmation is re-sent and unsubscribes are never overridden; if they are not yet in the
//     group they are only assigned to it (POST /api/subscribers/{id}/groups/{group}, no status change).
// Records already synced (ml:"ok") are skipped. After success the KV record gets ml:"ok"; failures get ml:"err"
// and are retried on the next run.
// The API key is read from a file or env var and is never printed or passed on a command line.
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const NAMESPACE_ID = process.env.NEWSLETTER_KV_ID || "a9f8a42d1ec641c8abe07640adb8241e"; // tradingaihub-newsletter (production)
const ML_ENDPOINT = "https://connect.mailerlite.com/api/subscribers";
const ML_GROUP = "202680264761018021"; // "Website signups"
const APPLY = process.argv.includes("--apply");
const CONFIRMED = process.argv.includes("--remote-prod") && process.argv.includes("--yes");
const INCLUDE_SYNCED = process.argv.includes("--include-synced");

// a***@e***.com — only the first character of the local part and of the domain, plus the last label (TLD).
export const mask = (e) => {
  const s = String(e);
  const at = s.lastIndexOf("@");
  const u = at >= 0 ? s.slice(0, at) : s;
  const d = at >= 0 ? s.slice(at + 1) : "";
  const labels = d.split(".");
  const tld = labels.length > 1 ? "." + labels[labels.length - 1] : "";
  return `${u.slice(0, 1)}***@${d.slice(0, 1)}***${tld}`;
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

async function ml(apiKey, method, url, body) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 10000);
  try {
    const res = await fetch(url, {
      method,
      headers: { authorization: `Bearer ${apiKey}`, "content-type": "application/json", accept: "application/json" },
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    });
    let json = null;
    try { json = await res.json(); } catch {}
    return { status: res.status, json };
  } catch { return { status: 0, json: null }; } finally { clearTimeout(t); }
}

// Returns { result: "ok"|"err", action, status } — never logs the key or the full email.
export async function syncOne(apiKey, email) {
  const look = await ml(apiKey, "GET", `${ML_ENDPOINT}/${encodeURIComponent(email)}`);
  if (look.status === 404) {
    const up = await ml(apiKey, "POST", ML_ENDPOINT, { email, groups: [ML_GROUP], status: "unconfirmed" });
    const ok = up.status === 200 || up.status === 201;
    return { result: ok ? "ok" : "err", action: "created unconfirmed (DOI email)", status: up.status };
  }
  if (look.status !== 200 || !look.json || !look.json.data) return { result: "err", action: "lookup failed", status: look.status };
  const sub = look.json.data;
  const inGroup = Array.isArray(sub.groups) && sub.groups.some((g) => String(g.id) === ML_GROUP);
  if (inGroup) return { result: "ok", action: `exists (${sub.status}), already in group, untouched`, status: 200 };
  const add = await ml(apiKey, "POST", `${ML_ENDPOINT}/${encodeURIComponent(sub.id)}/groups/${ML_GROUP}`);
  const ok = add.status === 200 || add.status === 201;
  return { result: ok ? "ok" : "err", action: `exists (${sub.status}), added to group, status untouched`, status: add.status };
}

if (process.argv[1] && import.meta.url !== new URL(`file://${path.resolve(process.argv[1])}`).href) {
  // imported (tests): don't run
} else await main();

async function main() {
console.log(`target: production KV namespace ${NAMESPACE_ID} (remote), MailerLite group ${ML_GROUP}`);
if (APPLY && !CONFIRMED) {
  console.error("refusing: --apply writes to production KV and the live MailerLite account; add --remote-prod --yes to confirm");
  process.exit(2);
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
if (!APPLY) return;

const apiKey = readKey();
let ok = 0, err = 0;
for (const { name, rec } of todo) {
  const r = await syncOne(apiKey, rec.email);
  r.result === "ok" ? ok++ : err++;
  console.log(`  ${mask(rec.email)} -> ${r.result}: ${r.action} (http ${r.status || "network"})`);
  try { putRecord(name, { ...rec, ml: r.result }); } catch { console.log(`  ${mask(rec.email)} kv status update failed`); }
  await new Promise((r) => setTimeout(r, 1100)); // up to 2 calls per record: stays under MailerLite's 120 req/min
}
console.log(`done: ok=${ok} err=${err}`);
process.exitCode = err ? 1 : 0;
}
