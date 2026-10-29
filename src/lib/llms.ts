// Builds /llms.txt and /llms-full.txt (https://llmstxt.org) at build time from the same data the pages use,
// so both files always match the live directory. English URLs; other locales live under /<code>/.
import { SITE } from "../config";
import { LOCALES, useT } from "../i18n";
import { tools, CATEGORIES, COMPARISONS, STATUS, TYPE_LABEL, byStars, verificationReport } from "./data";

const u = (path: string) => `${SITE.url}${path}`;
const md = (s: string) => String(s ?? "").replace(/\s+/g, " ").replace(/([\[\]])/g, "\\$1").trim();
const order: Record<string, number> = { verified: 0, aging: 1, warning: 2, stale: 3, archived: 4, unreachable: 5 };
export const toolsIn = (slug: string) => tools.filter((x) => x.category === slug).sort((a, b) => (order[a.verification.status] ?? 9) - (order[b.verification.status] ?? 9) || byStars(a, b));
const checked = () => String(verificationReport.checked_at || "").slice(0, 10);
const langs = () => LOCALES.map((l) => `${l.name} (${l.code === "en" ? "/" : `/${l.code}/`})`).join(", ");

function header(): string[] {
  const verified = tools.filter((x) => x.verification.status === "verified").length;
  return [
    `# ${SITE.name}`,
    "",
    `> ${SITE.description}`,
    "",
    `${SITE.name} (${SITE.url}) is an independent, free directory of ${tools.length} AI tools for finance and trading in ${CATEGORIES.length} categories. Every listing is re-checked automatically every week: repository reachable or archived, date of the latest commit and GitHub stars, npm/PyPI package published and linked to the repo, homepage/docs/hosted MCP endpoint alive. Pricing is copied from each vendor's own pricing page with the date; unknown values are shown as "unknown". Latest verification run: ${checked()} (${verified} of ${tools.length} tools have the status Verified). Listings are free; the site earns from clearly labelled sponsored placements and some affiliate links, which never affect verification status. Nothing on the site is investment advice.`,
    "",
    `The site is available in ${LOCALES.length} languages: ${langs()}. The URLs below are English; prefix any path with /<language code>/ for the other languages.`,
  ];
}

export function llmsTxt(): string {
  const { t } = useT("en");
  const L = [
    ...header(),
    "",
    "## Key pages",
    "",
    `- [Home](${u("/")}): editor's picks, categories, popular comparisons and recently updated tools`,
    `- [All tools](${u("/tools/")}): the full searchable directory, filterable by category and type`,
    `- [Categories](${u("/categories/")}): all ${CATEGORIES.length} categories`,
    `- [Comparisons](${u("/compare/")}): side-by-side comparison tables`,
    `- [About & how we verify](${u("/about/")}): methodology, status badges and how the site makes money`,
    `- [Latest verification report](${u("/verification/")}): results of the most recent weekly check`,
    `- [Weekly leaderboard](${u("/weekly/")}): most-starred verified tools and weekly changes`,
    `- [Submit a tool](${u("/submit/")}): free listing via a pre-filled GitHub issue or email to ${SITE.contactEmail}`,
    "",
    "## Categories",
    "",
    ...CATEGORIES.map((c) => `- [${md(c.name)}](${u(`/category/${c.slug}/`)}): ${md(c.blurb)} (${toolsIn(c.slug).length} tools)`),
    "",
    "## Comparisons",
    "",
    ...COMPARISONS.map((c) => `- [${md(c.title)}](${u(`/compare/${c.slug}/`)}): ${md(c.intro)}`),
    "",
    "## Machine-readable data",
    "",
    `- [llms-full.txt](${u("/llms-full.txt")}): every tool with its category, type, official/community status, verification status and canonical URL`,
    `- [tools.json](${u("/tools.json")}): the full tool list as JSON`,
    `- [RSS](${u("/rss.xml")}): weekly changes`,
    `- [Sitemap](${u("/sitemap-en.xml")}): English sitemap with hreflang alternates for all ${LOCALES.length} languages`,
    "",
    "## Optional",
    "",
    `- [Disclaimer](${u("/disclaimer/")}): ${md(t("footer.short"))}`,
    `- [Privacy](${u("/privacy/")})`,
    `- [Terms](${u("/terms/")})`,
    `- [Accessibility statement](${u("/accessibility/")})`,
    `- [Awesome list on GitHub](${SITE.githubAwesomeRepo})`,
  ];
  return L.join("\n") + "\n";
}

export function llmsFullTxt(): string {
  const statusLine = Object.entries(STATUS).map(([k, s]) => `- ${s.label}: ${s.help}`);
  const L = [
    ...header(),
    "",
    `Short index: ${u("/llms.txt")}. JSON: ${u("/tools.json")}.`,
    "",
    "## Verification statuses",
    "",
    ...statusLine,
    "",
    "Official = published by the vendor of the product itself; Community = built by someone other than the vendor.",
    "",
    `## Tools by category (${tools.length} tools)`,
  ];
  for (const c of CATEGORIES) {
    const list = toolsIn(c.slug);
    L.push("", `### ${c.name} (${list.length} tools)`, "", `${md(c.blurb)} Category page: ${u(`/category/${c.slug}/`)}`, "");
    for (const x of list) {
      const st = STATUS[x.verification.status]?.label ?? x.verification.status;
      const free = x.pricing?.free_tier && x.pricing.free_tier !== "unknown" ? ` · Free tier: ${md(x.pricing.free_tier)}` : "";
      L.push(`- [${md(x.name)}](${u(`/tools/${x.id}/`)}): ${md(x.description)} Category: ${c.name} · Type: ${TYPE_LABEL[x.type] ?? x.type} · ${x.official ? "Official (by the vendor)" : "Community"} · Status: ${st} (checked ${x.verification.checked_at})${free}`);
    }
  }
  return L.join("\n") + "\n";
}
