import { llmsTxt } from "../lib/llms";
export const GET = () => new Response(llmsTxt(), { headers: { "content-type": "text/plain; charset=utf-8" } });
