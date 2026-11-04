// /.well-known/ai-catalog.json: domain-level discovery (MCP Server Cards SEP-2127 / AI Catalog), pointing at /mcp/server-card.
import { serveDiscoveryDoc } from "../_lib/discovery.js";
const CATALOG = { specVersion: "1.0", entries: [{ identifier: "urn:air:tradingaihub.com:mcp:directory", type: "application/mcp-server-card+json", url: "https://tradingaihub.com/mcp/server-card" }],
  _meta: { "com.tradingaihub/api": { openapi: "https://tradingaihub.com/api/openapi.json", docs: "https://tradingaihub.com/developers/" } } };
export const onRequest = ({ request }) => serveDiscoveryDoc(request, CATALOG, "application/ai-catalog+json");
