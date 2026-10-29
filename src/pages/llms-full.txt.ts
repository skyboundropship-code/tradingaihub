import { llmsFullTxt } from "../lib/llms";
export const GET = () => new Response(llmsFullTxt(), { headers: { "content-type": "text/plain; charset=utf-8" } });
