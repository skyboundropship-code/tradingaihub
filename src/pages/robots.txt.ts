import { SITE } from "../config";
import { CODES } from "../i18n";
export function GET() {
  const maps = [`${SITE.url}/sitemap-index.xml`, ...CODES.map((c) => `${SITE.url}/sitemap-${c}.xml`)];
  return new Response(`User-agent: *\nAllow: /\n\n${maps.map((m) => `Sitemap: ${m}`).join("\n")}\n`, { headers: { "content-type": "text/plain" } });
}
