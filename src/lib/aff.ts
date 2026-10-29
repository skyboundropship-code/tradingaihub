import { AFFILIATES } from "../config";
/** Append the affiliate param to any URL on an affiliate host; other URLs are returned unchanged. */
export function affUrl(url?: string | null): string | undefined {
  if (!url) return url ?? undefined;
  try {
    const u = new URL(url);
    for (const a of Object.values(AFFILIATES)) {
      if (a.hosts.some((h) => u.hostname === h || u.hostname.endsWith("." + h))) { u.searchParams.set(a.param, a.id); return u.toString(); }
    }
  } catch {}
  return url;
}
/** True for any URL on an affiliate host: untagged ones (affUrl would add the param) and ones already tagged by affUrl. */
export const isAff = (url?: string | null) => {
  if (!url) return false;
  if (affUrl(url) !== url) return true;
  try {
    const u = new URL(url);
    return Object.values(AFFILIATES).some((a) => a.hosts.some((h) => u.hostname === h || u.hostname.endsWith("." + h)) && u.searchParams.get(a.param) === a.id);
  } catch { return false; }
};
export const relFor = (url?: string | null) => (isAff(url) ? "sponsored noopener" : "noopener");
export const tvUrl = (path = "/") => affUrl(new URL(path, AFFILIATES.tradingview.home).toString())!;
