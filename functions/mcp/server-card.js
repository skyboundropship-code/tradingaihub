// /mcp/server-card: MCP Server Card (SEP-2127; <streamable-http-url>/server-card is the reserved default location).
import { serveDiscoveryDoc } from "../_lib/discovery.js";
import { SERVER_CARD } from "../_lib/mcp.js";
export const onRequest = ({ request }) => serveDiscoveryDoc(request, SERVER_CARD, "application/mcp-server-card+json");
