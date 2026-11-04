// npm run test:blog: builds the site with BLOG_DRAFTS=1 into a temp dir and checks the draft handling of the blog:
// the sample draft (src/content/blog/sample-draft-post.md) renders as a noindex page with BlogPosting + BreadcrumbList,
// and never reaches RSS, the sitemap or llms.txt. Then checks that the production dist (if built) has no draft at all.
// Uses the OG PNGs already in public/og (run `npm run build` first, or `node scripts/og.mjs`).
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
const SLUG = "sample-draft-post";
const out = fs.mkdtempSync(path.join(os.tmpdir(), "blog-drafts-"));
let fail = 0, pass = 0;
const ok = (c, m) => { if (c) pass++; else { fail++; console.error(`FAIL ${m}`); } };
const read = (d, p) => (fs.existsSync(path.join(d, p)) ? fs.readFileSync(path.join(d, p), "utf8") : "");
try {
  execFileSync("npx", ["astro", "build", "--outDir", out], { env: { ...process.env, BLOG_DRAFTS: "1" }, stdio: ["ignore", "ignore", "inherit"] });
  const page = read(out, `blog/${SLUG}/index.html`);
  ok(page, "draft page is built with BLOG_DRAFTS=1");
  ok(/<meta name="robots" content="noindex/.test(page), "draft page is noindex");
  const lds = [...page.matchAll(/<script type="application\/ld\+json">(.*?)<\/script>/gs)].map((m) => JSON.parse(m[1]));
  const bp = lds.find((x) => x["@type"] === "BlogPosting");
  ok(bp && bp.author?.["@type"] === "Organization" && bp.author.name === "TradingAIHub Editorial", "BlogPosting author is the Organization byline");
  ok(bp && bp.datePublished === "2026-11-04" && bp.mainEntityOfPage?.["@id"] === `https://tradingaihub.com/blog/${SLUG}/` && /\/og\/blog-sample-draft-post\.png$/.test(bp.image?.url ?? bp.image ?? ""), "BlogPosting dates, mainEntityOfPage, image");
  const bc = lds.find((x) => x["@type"] === "BreadcrumbList");
  ok(bc && bc.itemListElement.map((i) => i.name).join(">") === "Home>Blog>How to evaluate an MCP server for market data (sample draft)", "BreadcrumbList Home > Blog > Post");
  ok(!/aff_id=|_go=|via=/.test(lds.map((x) => JSON.stringify(x)).join("")), "no affiliate params in JSON-LD");
  ok(/href="https:\/\/www\.tradingview\.com\/\?aff_id=\d+"[^>]*rel="sponsored noopener"/.test(page) && /aff-note/.test(page), "partner link tagged, rel=sponsored, aff-note shown");
  ok(/class="toc"/.test(page), "TOC rendered (3+ h2)");
  ok(!/<link rel="alternate" hreflang="(?!en"|x-default")/.test(page), "no hreflang to translations");
  ok(read(out, "blog/index.html").includes(`/blog/${SLUG}/`), "preview index lists the draft (with Draft badge)");
  ok(!read(out, "blog/rss.xml").includes(SLUG), "draft not in RSS");
  ok(!read(out, "sitemap-0.xml").includes(`/blog/${SLUG}/`), "draft not in sitemap-0.xml");
  ok(!read(out, "llms.txt").includes(SLUG) && !read(out, "llms-full.txt").includes(SLUG), "draft not in llms.txt / llms-full.txt");
  ok(!fs.existsSync(path.join(out, "he/blog")), "no translated blog pages");
} finally { fs.rmSync(out, { recursive: true, force: true }); }
if (fs.existsSync("dist/index.html")) {
  ok(!fs.existsSync(`dist/blog/${SLUG}`), "production dist: draft page not built");
  for (const f of ["blog/index.html", "blog/rss.xml", "sitemap-0.xml", "sitemap-en.xml", "llms.txt", "llms-full.txt"]) ok(!read("dist", f).includes(SLUG), `production dist: draft not in ${f}`);
}
console.log(`test:blog ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
