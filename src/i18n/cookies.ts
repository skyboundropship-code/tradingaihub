// Cookie-consent strings (banner + /cookies/ policy), kept in their own files so they don't
// collide with edits to the main locale JSONs. Falls back to English per key.
import en from "./cookies/en.json";
const files = import.meta.glob("./cookies/*.json", { eager: true }) as Record<string, any>;
const get = (o: any, k: string) => k.split(".").reduce((a, p) => (a == null ? a : a[p]), o);
/** Date the cookie policy was last updated (ISO, UTC). */
export const COOKIE_POLICY_DATE = "2026-10-29";
/** Bump when the policy changes materially; stored choices with an older version are asked again. */
export const CONSENT_VERSION = 1;
/** Stored choices older than this are asked again. */
export const CONSENT_MAX_AGE_DAYS = 365;
export function useCookieT(code = "en") {
  const d = (files[`./cookies/${code}.json`]?.default ?? files[`./cookies/${code}.json`] ?? {}) as any;
  return (key: string, vars: Record<string, any> = {}): any => {
    let v = get(d, key); if (v == null || v === "") v = get(en, key); if (v == null) return key;
    if (typeof v === "string") v = v.replace(/\{(\w+)\}/g, (_: string, n: string) => (vars[n] ?? `{${n}}`));
    return v;
  };
}
