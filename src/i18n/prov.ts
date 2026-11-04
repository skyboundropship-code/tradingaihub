// Package provenance strings (badge, tool-page row, /package-provenance/ page). Own files like a11y/ so they don't collide
// with edits to the main locale JSONs. Falls back to English per key.
import en from "./prov/en.json";
const files = import.meta.glob("./prov/*.json", { eager: true }) as Record<string, any>;
const get = (o: any, k: string) => k.split(".").reduce((a, p) => (a == null ? a : a[p]), o);
export function useProvT(code = "en") {
  const d = (files[`./prov/${code}.json`]?.default ?? files[`./prov/${code}.json`] ?? {}) as any;
  return (key: string, vars: Record<string, any> = {}): any => {
    let v = get(d, key); if (v == null || v === "") v = get(en, key); if (v == null) return key;
    if (typeof v === "string") v = v.replace(/\{(\w+)\}/g, (_: string, n: string) => (vars[n] ?? `{${n}}`));
    return v;
  };
}
