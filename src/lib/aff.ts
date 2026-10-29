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
export const isAff = (url?: string | null) => !!url && affUrl(url) !== url;
export const relFor = (url?: string | null) => (isAff(url) ? "sponsored noopener" : "noopener");
export const tvUrl = (path = "/") => affUrl(new URL(path, AFFILIATES.tradingview.home).toString())!;
