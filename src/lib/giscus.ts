// Blog comments: GitHub Discussions in the public repo tradingaihub/community, shown through giscus (https://giscus.app).
// One thread per post in the "Articles" category, matched by the post slug (mapping "specific" + strict), so a thread
// survives URL or locale changes. Nothing loads from giscus.app or GitHub until the reader clicks "Load comments".
//
// ENABLED: the giscus GitHub App is installed on tradingaihub/community only (confirmed Nov 11, 2026 via
// https://giscus.app/api/discussions/categories). Set it to false to hide every comment box and the privacy paragraph.
// The category is "Articles" (announcement format: only maintainers and giscus start threads, anyone can reply).
// giscus looks threads up by category NAME, so if the category is ever renamed, change `category` here too (the id survives).
export const GISCUS = {
  ENABLED: true,
  repo: "tradingaihub/community",
  repoId: "R_kgDOVrGWCA",
  category: "Articles",
  categoryId: "DIC_kwDOVrGWCM4DK6jB",
  discussions: "https://github.com/tradingaihub/community/discussions",
};
// giscus UI locales (https://github.com/giscus/giscus/tree/main/locales). Locales giscus doesn't ship fall back to English.
const GISCUS_LANG: Record<string, string> = { en: "en", he: "he", es: "es", pt: "pt", de: "de", fr: "fr", ja: "ja", ko: "ko", zh: "zh-CN", tr: "tr", ar: "ar", ru: "ru", hi: "en" };
export const giscusLang = (code: string) => GISCUS_LANG[code] ?? "en";
