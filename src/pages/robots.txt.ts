import { SITE } from "../config";
export const GET = () => new Response(`User-agent: *\nAllow: /\nSitemap: ${SITE.url}/sitemap-index.xml\n`);
