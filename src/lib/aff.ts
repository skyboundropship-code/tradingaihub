import { AFFILIATES } from "../config";
/** Append the affiliate param to any URL on an affiliate host; other URLs are returned unchanged. */
export function affUrl(url?: string | null): string | undefined {
  if (!url) return url ?? undefined;
  try {
    const u = new URL(url.startsWith("//") ? "https:" + url : url);
    for (const a of Object.values(AFFILIATES)) {
      if (!onHost(a, u.hostname)) continue;
      if (tracked(a, u.pathname)) { u.searchParams.set(a.param, a.id); return u.toString(); }
      // On the program's host but not a tracked path: keep it plain (drop a stray param, otherwise leave the URL as is).
      if (u.searchParams.has(a.param)) { u.searchParams.delete(a.param); return u.toString(); }
      return url;
    }
  } catch {}
  return url;
}
/** Host match for one program: trailing dot ignored; `exact` programs match only their listed hosts (no other subdomains). */
function onHost(a: { hosts: string[]; exact?: boolean }, hostname: string) {
  const h = hostname.toLowerCase().replace(/\.$/, "");
  return a.exact ? a.hosts.includes(h) : a.hosts.some((x) => h === x || h.endsWith("." + x));
}
/** Path allowlist for programs with `paths` (attribution only works on those pages); programs without it track every path. */
function tracked(a: { paths?: string[] }, pathname: string) {
  return !a.paths || a.paths.includes(pathname);
}
/** The same URL without one program's affiliate param, for copy-paste snippets and the data export. Other URLs are returned unchanged. */
export function untagUrl(url: string | null | undefined, program: keyof typeof AFFILIATES): string | undefined {
  if (!url) return url ?? undefined;
  const a = AFFILIATES[program];
  try {
    const rel = url.startsWith("//"), u = new URL(rel ? "https:" + url : url);
    if (!onHost(a, u.hostname) || !u.searchParams.has(a.param)) return url;
    u.searchParams.delete(a.param); const s = u.toString(); return rel ? s.slice("https:".length) : s;
  } catch { return url; }
}
/** True for any URL that is (or affUrl would make) an affiliate link: on an affiliate host and, for programs with a path
 *  allowlist, on a tracked path. Untracked EODHD pages (e.g. /financial-apis/) are not affiliate links. */
export const isAff = (url?: string | null) => {
  if (!url) return false;
  try {
    const u = new URL(url.startsWith("//") ? "https:" + url : url);
    return Object.values(AFFILIATES).some((a) => onHost(a, u.hostname) && tracked(a, u.pathname));
  } catch { return false; }
};
export const relFor = (url?: string | null) => (isAff(url) ? "sponsored noopener" : "noopener");
export const tvUrl = (path = "/") => affUrl(new URL(path, AFFILIATES.tradingview.home).toString())!;
