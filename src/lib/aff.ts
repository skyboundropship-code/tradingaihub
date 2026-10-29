import { AFFILIATES } from "../config";
/** Append the affiliate param to any URL on an affiliate host; other URLs are returned unchanged. */
export function affUrl(url?: string | null): string | undefined {
  if (!url) return url ?? undefined;
  try {
    const u = new URL(url.startsWith("//") ? "https:" + url : url);
    for (const a of Object.values(AFFILIATES)) {
      if (onHost(a, u.hostname)) { u.searchParams.set(a.param, a.id); return u.toString(); }
    }
  } catch {}
  return url;
}
/** Host match for one program: trailing dot ignored; `exact` programs match only their listed hosts (no other subdomains). */
function onHost(a: { hosts: string[]; exact?: boolean }, hostname: string) {
  const h = hostname.toLowerCase().replace(/\.$/, "");
  return a.exact ? a.hosts.includes(h) : a.hosts.some((x) => h === x || h.endsWith("." + x));
}
/** The same URL without one program's affiliate param, for copy-paste snippets and the data export. Other URLs are returned unchanged. */
export function untagUrl(url: string | null | undefined, program: keyof typeof AFFILIATES): string | undefined {
  if (!url) return url ?? undefined;
  const a = AFFILIATES[program];
  try {
    const u = new URL(url);
    if (!onHost(a, u.hostname) || !u.searchParams.has(a.param)) return url;
    u.searchParams.delete(a.param); return u.toString();
  } catch { return url; }
}
/** True for any URL on an affiliate host: untagged ones (affUrl would add the param) and ones already tagged by affUrl. */
export const isAff = (url?: string | null) => {
  if (!url) return false;
  if (affUrl(url) !== url) return true;
  try {
    const u = new URL(url);
    return Object.values(AFFILIATES).some((a) => onHost(a, u.hostname) && u.searchParams.get(a.param) === a.id);
  } catch { return false; }
};
export const relFor = (url?: string | null) => (isAff(url) ? "sponsored noopener" : "noopener");
export const tvUrl = (path = "/") => affUrl(new URL(path, AFFILIATES.tradingview.home).toString())!;
