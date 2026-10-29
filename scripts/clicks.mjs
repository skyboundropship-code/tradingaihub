#!/usr/bin/env node
// npm run clicks [-- --days 7] [--env preview] [--local] [--json]
// Reads the anonymous outbound-click counters written by functions/api/click.js (KV binding NEWSLETTER, keys
// click:<YYYY-MM-DD>:<tool id or ->:<kind>) with your own `wrangler` login. Nothing is exposed publicly: there is no
// stats endpoint, so reading the counts needs Cloudflare account access (wrangler login or CLOUDFLARE_API_TOKEN).
import { execFileSync } from "node:child_process";
import fs from "node:fs"; import os from "node:os"; import path from "node:path";
import { pathToFileURL } from "node:url";

/** Sums counter records [{name, value}] into totals by kind, tool, host, page, locale and day. */
export function aggregate(entries) {
  const out = { total: 0, byKind: {}, byTool: {}, byHost: {}, byPage: {}, byLocale: {}, byDay: {} };
  const add = (m, k, n) => { m[k] = (m[k] || 0) + n; };
  for (const { name, value } of entries) {
    const m = /^click:(\d{4}-\d{2}-\d{2}):([^:]+):(affiliate|partner|plain)$/.exec(name);
    if (!m) continue;
    let v; try { v = typeof value === "string" ? JSON.parse(value) : value; } catch { continue; }
    if (!v || !Number.isInteger(v.n)) continue;
    const [, day, tool, kind] = m;
    out.total += v.n; add(out.byKind, kind, v.n); add(out.byDay, day, v.n); add(out.byTool, `${tool} (${kind})`, v.n);
    for (const [k, n] of Object.entries(v.hosts || {})) add(out.byHost, k, n);
    for (const [k, n] of Object.entries(v.pages || {})) add(out.byPage, k, n);
    for (const [k, n] of Object.entries(v.locales || {})) add(out.byLocale, k, n);
  }
  return out;
}

export function lastDays(n, now = new Date()) {
  const days = [];
  for (let i = 0; i < n; i++) days.push(new Date(now.getTime() - i * 86400000).toISOString().slice(0, 10));
  return new Set(days);
}

function main() {
  const argv = process.argv.slice(2);
  const opt = (k, d) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : d; };
  const days = Math.max(1, parseInt(opt("--days", "7"), 10) || 7);
  const env = opt("--env", null);
  const where = argv.includes("--local") ? ["--local"] : ["--remote"];
  const base = ["wrangler", "kv", "--binding", "NEWSLETTER", ...where, ...(env ? ["--env", env] : [])];
  const run = (args) => {
    const out = execFileSync("npx", args, { encoding: "utf8", stdio: ["ignore", "pipe", "inherit"], maxBuffer: 64 << 20 });
    const i = out.search(/^[[{]/m); // skip any banner lines before the JSON
    if (i < 0) throw new Error("unexpected wrangler output");
    return out.slice(i);
  };
  const keys = JSON.parse(run([...base.slice(0, 2), "key", "list", "--prefix", "click:", ...base.slice(2)]));
  const want = lastDays(days);
  const names = keys.map((k) => k.name).filter((n) => want.has(n.split(":")[1]));
  let entries = [];
  if (names.length) {
    const tmp = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "clicks-")), "keys.json");
    fs.writeFileSync(tmp, JSON.stringify(names));
    try {
      const got = JSON.parse(run([...base.slice(0, 2), "bulk", "get", tmp, ...base.slice(2)]));
      // wrangler returns { "<key>": { "value": "<json>" } } (older versions: [{ name, value }]).
      entries = Array.isArray(got) ? got : Object.entries(got).map(([name, v]) => ({ name, value: v && typeof v === "object" && "value" in v ? v.value : v }));
    } finally { fs.rmSync(path.dirname(tmp), { recursive: true, force: true }); }
  }
  const a = aggregate(entries);
  if (argv.includes("--json")) { console.log(JSON.stringify(a, null, 2)); return; }
  const top = (m, n = 20) => Object.entries(m).sort((x, y) => y[1] - x[1]).slice(0, n);
  console.log(`Outbound clicks, last ${days} day(s) (UTC)${env ? ` [${env}]` : ""}: ${a.total}`);
  for (const [title, m] of [["By kind", a.byKind], ["By day", a.byDay], ["Top tools", a.byTool], ["Top hosts", a.byHost], ["Top pages", a.byPage], ["By locale", a.byLocale]]) {
    console.log(`\n${title}`);
    for (const [k, n] of title === "By day" ? Object.entries(m).sort() : top(m)) console.log(`  ${String(n).padStart(6)}  ${k}`);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main();
