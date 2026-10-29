// Fails the build if any TradingView link in dist/ lacks the affiliate ID or rel="sponsored".
import fs from "node:fs"; import path from "node:path";
const ID = "1173592"; let bad = 0, ok = 0;
const walk = (d) => fs.readdirSync(d, { withFileTypes: true }).flatMap((e) => e.isDirectory() ? walk(path.join(d, e.name)) : [path.join(d, e.name)]);
for (const f of walk("dist").filter((f) => f.endsWith(".html"))) {
  for (const m of fs.readFileSync(f, "utf8").matchAll(/<a\b[^>]*href="(https?:\/\/(?:[\w-]+\.)*tradingview\.com[^"]*)"[^>]*>/g)) {
    if (m[1].includes("aff_id=" + ID) && /rel="sponsored noopener"/.test(m[0])) ok++; else { bad++; console.error("BAD", f, m[0]); }
  }
}
console.log(`TradingView links: ${ok} ok, ${bad} bad`); process.exit(bad ? 1 : 0);
