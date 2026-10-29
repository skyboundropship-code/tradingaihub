// Submits every URL from dist/sitemap-*.xml to IndexNow (api.indexnow.org → Bing, Yandex, Seznam, Naver, Yep).
// Run after build+deploy. Key file lives at public/<key>.txt → https://<host>/<key>.txt
import fs from "node:fs";
const host = "tradingaihub.com";
const keyFile = fs.readdirSync("public").find((f) => /^[0-9a-f]{32}\.txt$/.test(f));
if (!keyFile) { console.error("no IndexNow key file in public/"); process.exit(1); }
const key = keyFile.slice(0, -4);
const urls = new Set();
for (const f of fs.readdirSync("dist").filter((f) => /^sitemap.*\.xml$/.test(f))) {
  for (const m of fs.readFileSync(`dist/${f}`, "utf8").matchAll(/<loc>([^<]+)<\/loc>/g)) if (!m[1].endsWith(".xml")) urls.add(m[1]);
}
const list = [...urls].filter((u) => new URL(u).host === host);
console.log("IndexNow: submitting", list.length, "URLs");
let fail = 0;
for (let i = 0; i < list.length; i += 10000) {
  const r = await fetch("https://api.indexnow.org/indexnow", { method: "POST", headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify({ host, key, keyLocation: `https://${host}/${keyFile}`, urlList: list.slice(i, i + 10000) }) });
  console.log(`batch ${i / 10000 + 1}: HTTP ${r.status} ${r.statusText}`, (await r.text()).slice(0, 200));
  if (![200, 202].includes(r.status)) fail++;
}
process.exit(fail ? 1 : 0);
