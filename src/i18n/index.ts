// i18n helpers. English is the default locale at the site root; other locales live under /<code>/.
import en from "./en.json";
const files = import.meta.glob("./*.json", { eager: true }) as Record<string, any>;
export const LOCALES = [
  { code: "en", name: "English", dir: "ltr", og: "en_US" },
  { code: "he", name: "עברית", dir: "rtl", og: "he_IL" },
  { code: "es", name: "Español", dir: "ltr", og: "es_ES" },
  { code: "pt", name: "Português", dir: "ltr", og: "pt_BR" },
  { code: "de", name: "Deutsch", dir: "ltr", og: "de_DE" },
  { code: "fr", name: "Français", dir: "ltr", og: "fr_FR" },
  { code: "ja", name: "日本語", dir: "ltr", og: "ja_JP" },
  { code: "ko", name: "한국어", dir: "ltr", og: "ko_KR" },
  { code: "zh", name: "中文", dir: "ltr", og: "zh_CN" },
  { code: "hi", name: "हिन्दी", dir: "ltr", og: "hi_IN" },
  { code: "tr", name: "Türkçe", dir: "ltr", og: "tr_TR" },
  { code: "ar", name: "العربية", dir: "rtl", og: "ar_AR" },
  { code: "ru", name: "Русский", dir: "ltr", og: "ru_RU" },
] as const;
export const DEFAULT = "en";
export const CODES = LOCALES.map((l) => l.code) as string[];
export const localeOf = (code?: string) => LOCALES.find((l) => l.code === (code || DEFAULT))!;
/** getStaticPaths helper: one entry per locale; English has no prefix (lang undefined). */
export const langParams = () => CODES.map((c) => ({ lang: c === DEFAULT ? undefined : c }));
const dict = (code: string) => (files[`./${code}.json`]?.default ?? files[`./${code}.json`] ?? {}) as any;
const get = (o: any, k: string) => k.split(".").reduce((a, p) => (a == null ? a : a[p]), o);
export function useT(code: string = DEFAULT) {
  const d = dict(code);
  const t = (key: string, vars: Record<string, any> = {}): any => {
    let v = get(d, key); if (v == null || v === "") v = get(en, key); if (v == null) return key;
    if (typeof v === "string") v = v.replace(/\{(\w+)\}/g, (_: string, n: string) => (vars[n] ?? `{${n}}`));
    return v;
  };
  /** Tool description: translated if available, otherwise the English one from data/tools.json (new tools fall back automatically). */
  const desc = (tool: any) => d.desc?.[tool.id] || tool.description;
  /** Locale-prefixed internal path. */
  const p = (path: string) => (code === DEFAULT ? path : `/${code}${path === "/" ? "/" : path}`);
  return { t, desc, p, code, dir: localeOf(code).dir };
}
/** Strip a locale prefix from a pathname → the English (root) path. */
export const basePath = (pathname: string) => { const m = pathname.match(/^\/([a-z]{2})(\/.*|$)/); return m && CODES.includes(m[1]) && m[1] !== DEFAULT ? (m[2] || "/") : pathname; };
export const pathFor = (code: string, base: string) => (code === DEFAULT ? base : `/${code}${base}`);
