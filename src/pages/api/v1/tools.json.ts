import { toolsDumpJson } from "../../../lib/publicApi";
// Static full dump for the public API. functions/api/v1/[[path]].js serves it (with CORS + rate limit) and reads it via env.ASSETS.
export const GET = () => new Response(toolsDumpJson(), { headers: { "content-type": "application/json" } });
