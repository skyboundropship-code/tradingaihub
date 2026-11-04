import { categoriesJson } from "../../../lib/publicApi";
// Static categories file; /api/v1/categories (no extension) is served from it by functions/api/v1/[[path]].js.
export const GET = () => new Response(categoriesJson(), { headers: { "content-type": "application/json" } });
