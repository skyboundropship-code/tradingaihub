// Blog comments: GitHub Discussions in the public repo tradingaihub/community, shown through giscus (https://giscus.app).
// One thread per post in the "Articles" category, matched by the post slug (mapping "specific" + strict), so a thread
// survives URL or locale changes. Nothing loads from giscus.app or GitHub until the reader clicks "Load comments".
//
// ENABLED stays false until the giscus GitHub App is installed on tradingaihub/community
// (https://github.com/apps/giscus/installations/new). Until then no comment UI and no privacy text about it is rendered.
// A preview build can show it with GISCUS=1 (never set it for production before the app is installed).
// Category ids survive a rename in the GitHub UI, so renaming "Announcements" to "Articles" doesn't need a code change.
export const GISCUS = {
  ENABLED: false || /^(1|true|yes)$/i.test(String(process.env.GISCUS ?? "")),
  repo: "tradingaihub/community",
  repoId: "R_kgDOVrGWCA",
  category: "Articles",
  categoryId: "DIC_kwDOVrGWCM4DK6jB",
  discussions: "https://github.com/tradingaihub/community/discussions",
};
// giscus UI locales (https://github.com/giscus/giscus/tree/main/locales). Locales giscus doesn't ship fall back to English.
const GISCUS_LANG: Record<string, string> = { en: "en", he: "he", es: "es", pt: "pt", de: "de", fr: "fr", ja: "ja", ko: "ko", zh: "zh-CN", tr: "tr", ar: "ar", ru: "ru", hi: "en" };
export const giscusLang = (code: string) => GISCUS_LANG[code] ?? "en";
