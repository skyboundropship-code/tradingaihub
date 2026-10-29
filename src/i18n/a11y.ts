// Accessibility strings (widget + /accessibility/ statement), kept in their own files so they
// don't collide with edits to the main locale JSONs. Falls back to English per key.
import en from "./a11y/en.json";
const files = import.meta.glob("./a11y/*.json", { eager: true }) as Record<string, any>;
const get = (o: any, k: string) => k.split(".").reduce((a, p) => (a == null ? a : a[p]), o);
/** Date the accessibility statement was prepared / last reviewed (ISO, UTC). */
export const A11Y_STATEMENT_DATE = "2026-10-29";
export function useA11yT(code = "en") {
  const d = (files[`./a11y/${code}.json`]?.default ?? files[`./a11y/${code}.json`] ?? {}) as any;
  return (key: string, vars: Record<string, any> = {}): any => {
    let v = get(d, key); if (v == null || v === "") v = get(en, key); if (v == null) return key;
    if (typeof v === "string") v = v.replace(/\{(\w+)\}/g, (_: string, n: string) => (vars[n] ?? `{${n}}`));
    return v;
  };
}
