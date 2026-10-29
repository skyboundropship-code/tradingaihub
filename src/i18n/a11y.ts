// Accessibility strings (widget + /accessibility/ statement), kept in their own files so they
// don't collide with edits to the main locale JSONs. Falls back to English per key.
import en from "./a11y/en.json";
const files = import.meta.glob("./a11y/*.json", { eager: true }) as Record<string, any>;
const get = (o: any, k: string) => k.split(".").reduce((a, p) => (a == null ? a : a[p]), o);
/**
 * Accessibility statement settings: the ONE place to edit coordinator details, the reply
 * promise and the statement date (used by src/pages/[...lang]/accessibility.astro, all 13 locales).
 * Coordinator fields render only when non-empty. Do not invent values; fill them once confirmed.
 */
export const A11Y_STATEMENT = {
  /** Date the statement was prepared / last updated (ISO, UTC). Bump whenever the statement changes. */
  date: "2026-10-29",
  /** Business days within which we acknowledge an accessibility request (st.response {days}). */
  responseDays: 5,
  coordinator: {
    /** Full name of the accessibility coordinator, e.g. "Jane Doe". */
    name: "",
    /** Phone in international format, e.g. "+972-3-000-0000" (rendered as a tel: link). */
    phone: "",
    /** Contact email (rendered as a mailto: link whose subject is the localized w.title, e.g. "Accessibility"). */
    email: "hello@tradingaihub.com",
    /** Optional postal address for written requests (one line; use ", " between parts). */
    postal: "",
  },
} as const;
/** Kept for existing imports. */
export const A11Y_STATEMENT_DATE = A11Y_STATEMENT.date;
export function useA11yT(code = "en") {
  const d = (files[`./a11y/${code}.json`]?.default ?? files[`./a11y/${code}.json`] ?? {}) as any;
  return (key: string, vars: Record<string, any> = {}): any => {
    let v = get(d, key); if (v == null || v === "") v = get(en, key); if (v == null) return key;
    if (typeof v === "string") v = v.replace(/\{(\w+)\}/g, (_: string, n: string) => (vars[n] ?? `{${n}}`));
    return v;
  };
}
