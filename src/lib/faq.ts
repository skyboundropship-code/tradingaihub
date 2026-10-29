// Visible FAQ content + matching FAQPage JSON-LD. Every answer is built from repo data (tools.json, the
// verification report, config) so the numbers stay true after each weekly run. Values that may be LTR inside
// RTL text (tool names, dates, emails, language names) are wrapped in U+2068/U+2069 isolates: Faq.astro renders
// them as <bdi>, and the JSON-LD strips them, so the visible text and the structured data stay identical.
import { SITE } from "../config";
import { LOCALES, useT } from "../i18n";
import { tools, CATEGORIES, starsOf, verificationReport } from "./data";

export type QA = { q: string; a: string };
const iso = (s: string) => `\u2068${s}\u2069`;
export const plain = (s: string) => s.replace(/[\u2068\u2069]/g, "");
const listOf = (lang: string, items: string[]) => new Intl.ListFormat(lang, { style: "long", type: "conjunction" }).format(items.map(iso));
const checkedDate = () => String(verificationReport.checked_at || "").slice(0, 10);

export function homeFaq(lang: string): QA[] {
  const { t } = useT(lang);
  const site = SITE.name;
  return [
    { q: t("faq.q1", { site }), a: t("faq.a1", { site, n: tools.length, c: CATEGORIES.length }) },
    { q: t("faq.q2", { site }), a: t("faq.a2", { site, date: iso(checkedDate()) }) },
    { q: t("faq.q3", { site }), a: t("faq.a3", { site }) },
    { q: t("faq.q4", { site }), a: t("faq.a4", { site, page: t("submit.title"), email: iso(SITE.contactEmail) }) },
    { q: t("faq.q5", { site }), a: t("faq.a5", { site, n: LOCALES.length, list: listOf(lang, LOCALES.map((l) => l.name)) }) },
  ];
}

/** Per-category FAQ, templated from the tools in that category. The "most popular" answer is omitted if no verified tool has stars. */
export function categoryFaq(lang: string, slug: string): QA[] {
  const { t } = useT(lang);
  const name = t(`cat.${slug}`)[0];
  const list = tools.filter((x) => x.category === slug);
  const verified = list.filter((x) => x.verification.status === "verified");
  const top = verified.filter((x) => starsOf(x) != null).sort((a, b) => (starsOf(b) ?? 0) - (starsOf(a) ?? 0)).slice(0, 3);
  const official = list.filter((x) => x.official).length;
  const out: QA[] = [
    { q: t("faq.cq1", { name }), a: t("faq.ca1", { n: list.length, v: verified.length, date: iso(checkedDate()), status: t("status.verified")[0] }) },
  ];
  if (top.length) out.push({ q: t("faq.cq2", { name }), a: t("faq.ca2", { list: listOf(lang, top.map((x) => x.name)) }) });
  out.push({ q: t("faq.cq3", { name }), a: t("faq.ca3", { n: list.length, o: official, c: list.length - official, badge: t("common.official") }) });
  return out;
}

export const faqLd = (items: QA[], lang: string) => ({
  "@context": "https://schema.org", "@type": "FAQPage", inLanguage: lang,
  mainEntity: items.map(({ q, a }) => ({ "@type": "Question", name: plain(q), acceptedAnswer: { "@type": "Answer", text: plain(a) } })),
});

