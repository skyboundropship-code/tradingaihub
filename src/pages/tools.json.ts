import { tools } from "../lib/data";
export const GET = () => new Response(JSON.stringify(tools.map(({ id, name, type, category, description, repo, homepage, pricing, license, verification }) => ({ id, name, type, category, description, repo, homepage, pricing, license, status: verification.status, checked_at: verification.checked_at }))), { headers: { "content-type": "application/json" } });
