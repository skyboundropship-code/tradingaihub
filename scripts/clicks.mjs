#!/usr/bin/env node
// npm run clicks [-- --env preview] [--json]
// Reports anonymous outbound clicks written by functions/api/click.js to Workers Analytics Engine
// (dataset tah_clicks, or tah_clicks_preview with --env preview) through the AE SQL API.
// Needs env CLOUDFLARE_API_TOKEN (Account > Account Analytics: Read) and CLOUDFLARE_ACCOUNT_ID (or a token that can list
// exactly one account). The token is only sent in the Authorization header and is never printed.
// Bot and QA traffic (blob8 is_bot = "1": crawler/headless/curl/python UAs, verified bots, `x-tah-qa: 1` header) is excluded.
// Blobs: 1 tool, 2 affiliate id, 3 kind, 4 host, 5 locale, 6 page, 7 referrer host, 8 is_bot, 9 source. Sums use _sample_interval.
import { pathToFileURL } from "node:url";

export const WINDOWS = [1, 7, 30];
const DATASETS = { production: "tah_clicks", preview: "tah_clicks_preview" };

/** Builds the SQL for one breakdown ("affiliate" -> blob2, "tool" -> blob1) over the last N days, humans only. */
export function buildQuery(dataset, by, days) {
  if (!/^[a-z0-9_]+$/.test(dataset)) throw new Error("bad dataset");
  const col = { affiliate: "blob2", tool: "blob1", kind: "blob3" }[by];
  if (!col || !Number.isInteger(days) || days < 1 || days > 90) throw new Error("bad query");
  return `SELECT ${col} AS k, SUM(_sample_interval) AS n FROM ${dataset} WHERE timestamp > NOW() - INTERVAL '${days}' DAY AND blob8 = '0' GROUP BY k ORDER BY n DESC LIMIT 50 FORMAT JSON`;
}

/** Turns AE JSON rows into {key: count}. */
export function rowsToMap(json) {
  const out = {};
  for (const r of (json && json.data) || []) out[r.k] = (out[r.k] || 0) + Number(r.n || 0);
  return out;
}

/** Classifies an AE SQL API failure into a message that never contains the token. */
export function explainError(status, body) {
  if (status === 401 || status === 403 || /authori[sz]ation|authentication/i.test(body || ""))
    return "The Cloudflare API token has no Analytics Engine read permission (needs Account > Account Analytics: Read). Create a token with that permission and set CLOUDFLARE_API_TOKEN.";
  if (/unknown table|does not exist|not found/i.test(body || "")) return "No clicks recorded yet (the dataset is created on the first datapoint).";
  return `Analytics Engine SQL API error (HTTP ${status}).`;
}

async function main() {
  const argv = process.argv.slice(2);
  const env = argv.includes("--env") ? argv[argv.indexOf("--env") + 1] : "production";
  const dataset = DATASETS[env];
  if (!dataset) { console.error("--env must be production or preview"); process.exit(2); }
  const token = process.env.CLOUDFLARE_API_TOKEN;
  if (!token) { console.log("CLOUDFLARE_API_TOKEN is not set: cannot query Analytics Engine."); process.exit(1); }
  const auth = { authorization: `Bearer ${token}` };
  let account = process.env.CLOUDFLARE_ACCOUNT_ID;
  if (!account) {
    const r = await fetch("https://api.cloudflare.com/client/v4/accounts", { headers: auth });
    const j = await r.json().catch(() => ({}));
    if (j.result && j.result.length === 1) account = j.result[0].id;
    else { console.log("Set CLOUDFLARE_ACCOUNT_ID (could not pick a single account from the token)."); process.exit(1); }
  }
  const api = `https://api.cloudflare.com/client/v4/accounts/${account}/analytics_engine/sql`;
  const report = { dataset, excludes: "is_bot=1 (bots, headless, curl/python, x-tah-qa: 1)", windows: {} };
  for (const days of WINDOWS) {
    const w = {};
    for (const by of ["affiliate", "tool", "kind"]) {
      const r = await fetch(api, { method: "POST", headers: auth, body: buildQuery(dataset, by, days) });
      const body = await r.text();
      if (!r.ok || !body.trim().startsWith("{")) { const msg = explainError(r.status, body); if (argv.includes("--json")) console.log(JSON.stringify({ error: msg })); else console.log(msg); process.exit(r.status === 401 || r.status === 403 || /authori/i.test(body) ? 3 : 1); }
      w[by] = rowsToMap(JSON.parse(body));
    }
    w.total = Object.values(w.kind).reduce((a, b) => a + b, 0);
    report.windows[`${days}d`] = w;
  }
  if (argv.includes("--json")) { console.log(JSON.stringify(report, null, 2)); return; }
  console.log(`Outbound clicks (${dataset}), humans only; ${report.excludes} excluded`);
  for (const [name, w] of Object.entries(report.windows)) {
    console.log(`\n== Last ${name}: ${w.total}`);
    for (const [title, m] of [["By affiliate/partner", w.affiliate], ["By tool", w.tool]]) {
      console.log(`  ${title}`);
      for (const [k, n] of Object.entries(m).slice(0, 20)) console.log(`    ${String(n).padStart(6)}  ${k}`);
    }
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main().catch((e) => { console.error("clicks report failed:", e.message); process.exit(1); });
