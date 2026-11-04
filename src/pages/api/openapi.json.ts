import { openapi } from "../../lib/openapi";
export const GET = () => new Response(JSON.stringify(openapi, null, 2), { headers: { "content-type": "application/json" } });
