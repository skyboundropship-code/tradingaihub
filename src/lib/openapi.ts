// OpenAPI 3.1 description of the public read-only API, served at /api/openapi.json (built static, CORS via functions/api/openapi.json.js).
import { SITE } from "../config";
import { API_VERSION, DOCS_URL, FILTERS, RATE_LIMITS } from "./publicApi";

const str = { type: "string" };
const nstr = { type: ["string", "null"] };
const nurl = { type: ["string", "null"], format: "uri" };
const pkg = { type: ["object", "null"], properties: { name: str, version: nstr, url: nurl }, required: ["name"] };
const rl = { $ref: "#/components/headers/RateLimitLimit" };
const okHeaders = { "Access-Control-Allow-Origin": { $ref: "#/components/headers/ACAO" }, "Cache-Control": { $ref: "#/components/headers/CacheControl" }, "RateLimit-Limit": rl, "RateLimit-Remaining": { $ref: "#/components/headers/RateLimitRemaining" }, "RateLimit-Reset": { $ref: "#/components/headers/RateLimitReset" } };
const json = (schema: any, description: string, headers: any = okHeaders) => ({ description, headers, content: { "application/json": { schema } } });
const err = (d: string) => json({ $ref: "#/components/schemas/Error" }, d, { "Access-Control-Allow-Origin": { $ref: "#/components/headers/ACAO" } });
const errors = { "400": err("Invalid parameter (JSON error body names the parameter and the allowed values)."), "405": err("Method not allowed (only GET, HEAD and OPTIONS)."), "429": { $ref: "#/components/responses/RateLimited" } };
const lic = { license: { type: "string", const: "CC BY 4.0", description: "Licence of the data." }, license_url: { type: "string", format: "uri" }, attribution: { type: "string", description: "Required credit when you reuse the data: \"TradingAIHub, https://tradingaihub.com\"." } };
const meta = { ...lic, api_version: str, source: { type: "string", format: "uri" }, docs: { type: "string", format: "uri" }, terms: { type: "string", format: "uri" }, notice: str, data_checked_at: nstr };

export const openapi = {
  openapi: "3.1.0",
  info: {
    title: "TradingAIHub public API",
    version: API_VERSION,
    summary: "Free, read-only, no-sign-in API for the TradingAIHub directory of AI tools for finance and trading.",
    description: `Every MCP server, agent skill and API listed on ${SITE.url}, with pricing, license, packages and the weekly verification status. No API key, CORS enabled (\`Access-Control-Allow-Origin: *\`), JSON only. Rate limit: about ${RATE_LIMITS.api} requests per minute per IP (enforced per edge instance, so treat it as a ceiling, not a guarantee); over the limit you get HTTP 429 with \`Retry-After\`. Responses are cacheable for 5 minutes. A remote MCP server with the same data is at ${SITE.url}/mcp. Data licence: CC BY 4.0, credit \"TradingAIHub, https://tradingaihub.com\"; the API and MCP server code is MIT. Not investment advice.`,
    termsOfService: `${SITE.url}/terms/`,
    license: { name: "CC BY 4.0", url: "https://creativecommons.org/licenses/by/4.0/" },
    contact: { name: SITE.name, url: DOCS_URL, email: SITE.contactEmail },
  },
  externalDocs: { description: "Developer docs, examples and MCP install snippets", url: DOCS_URL },
  servers: [{ url: SITE.url }],
  tags: [{ name: "tools" }, { name: "categories" }, { name: "dumps", description: "Static full-data JSON files" }],
  paths: {
    "/api/v1/tools": { get: {
      operationId: "listTools", tags: ["tools"], summary: "List tools, with filters and pagination",
      parameters: [
        { name: "category", in: "query", schema: { type: "string", enum: FILTERS.category } },
        { name: "type", in: "query", schema: { type: "string", enum: FILTERS.type } },
        { name: "language", in: "query", description: "Language of the published package: npm = javascript, PyPI = python. Tools without a package have no language.", schema: { type: "string", enum: FILTERS.language } },
        { name: "status", in: "query", schema: { type: "string", enum: FILTERS.status } },
        { name: "verified", in: "query", description: "true = only tools whose latest weekly check is `verified`; false = all others.", schema: { type: "boolean" } },
        { name: "official", in: "query", description: "true = only tools published by the vendor itself.", schema: { type: "boolean" } },
        { name: "limit", in: "query", schema: { type: "integer", minimum: 1, maximum: 100, default: 50 } },
        { name: "offset", in: "query", schema: { type: "integer", minimum: 0, default: 0 } },
      ],
      responses: { "200": json({ $ref: "#/components/schemas/ToolList" }, "Matching tools (sorted by name)."), ...errors },
    } },
    "/api/v1/tools/{slug}": { get: {
      operationId: "getTool", tags: ["tools"], summary: "One tool by slug",
      parameters: [{ name: "slug", in: "path", required: true, schema: { type: "string", pattern: "^[a-z0-9-]+$" }, example: "alpha-vantage-mcp" }],
      responses: { "200": json({ type: "object", properties: { ...lic, tool: { $ref: "#/components/schemas/Tool" } }, required: ["tool"] }, "The tool."), "404": err("No tool with that slug."), ...errors },
    } },
    "/api/v1/search": { get: {
      operationId: "searchTools", tags: ["tools"], summary: "Full-text search over name, description, category and packages",
      parameters: [
        { name: "q", in: "query", required: true, schema: { type: "string", minLength: 1, maxLength: 100 }, example: "stock prices" },
        { name: "category", in: "query", schema: { type: "string", enum: FILTERS.category } },
        { name: "type", in: "query", schema: { type: "string", enum: FILTERS.type } },
        { name: "limit", in: "query", schema: { type: "integer", minimum: 1, maximum: 50, default: 10 } },
      ],
      responses: { "200": json({ $ref: "#/components/schemas/SearchResult" }, "Best matches first: tools matching every word of q, then partial matches."), ...errors },
    } },
    "/api/v1/categories": { get: {
      operationId: "listCategories", tags: ["categories"], summary: "All categories with tool counts",
      responses: { "200": json({ type: "object", properties: { ...meta, count: { type: "integer" }, categories: { type: "array", items: { $ref: "#/components/schemas/Category" } } }, required: ["count", "categories"] }, "Categories."), ...errors },
    } },
    "/api/v1/tools.json": { get: {
      operationId: "dumpTools", tags: ["dumps"], summary: "Full dump of every tool (static file, same objects as /api/v1/tools)",
      responses: { "200": json({ type: "object", properties: { ...meta, count: { type: "integer" }, tools: { type: "array", items: { $ref: "#/components/schemas/Tool" } } }, required: ["count", "tools"] }, "All tools."), ...errors },
    } },
    "/api/v1/categories.json": { get: {
      operationId: "dumpCategories", tags: ["dumps"], summary: "Static copy of /api/v1/categories",
      responses: { "200": { $ref: "#/paths/~1api~1v1~1categories/get/responses/200" }, ...errors },
    } },
    "/api/openapi.json": { get: { operationId: "openapi", tags: ["dumps"], summary: "This document", responses: { "200": { description: "OpenAPI 3.1 document", content: { "application/json": {} } } } } },
  },
  components: {
    headers: {
      ACAO: { description: "Always `*`.", schema: str },
      CacheControl: { description: "`public, max-age=300, s-maxage=3600` on success.", schema: str },
      RateLimitLimit: { description: "Requests allowed per window.", schema: { type: "integer" } },
      RateLimitRemaining: { description: "Requests left in the current window.", schema: { type: "integer" } },
      RateLimitReset: { description: "Seconds until the window resets.", schema: { type: "integer" } },
    },
    responses: {
      RateLimited: { description: `Too many requests (about ${RATE_LIMITS.api}/min per IP).`, headers: { "Retry-After": { description: "Seconds to wait.", schema: { type: "integer" } } }, content: { "application/json": { schema: { $ref: "#/components/schemas/Error" } } } },
    },
    schemas: {
      Error: { type: "object", required: ["error"], properties: { error: { type: "object", required: ["status", "code", "message"], properties: { status: { type: "integer" }, code: { type: "string", examples: ["not_found", "invalid_parameter", "method_not_allowed", "rate_limited"] }, message: str, allowed: { type: "array", items: str } } } } },
      Category: { type: "object", required: ["slug", "name", "count"], properties: { slug: str, name: str, short: str, icon: str, description: str, url: { type: "string", format: "uri" }, count: { type: "integer" } } },
      Tool: { type: "object", required: ["slug", "name", "type", "category", "description", "url", "website_url", "vendor_url", "affiliate", "disclosure", "status", "verified"], properties: {
        slug: str, name: str, type: { type: "string", enum: FILTERS.type }, type_label: str, category: { type: "string", enum: FILTERS.category }, category_name: nstr, description: str,
        official: { type: "boolean", description: "Published by the vendor itself." },
        url: { type: "string", format: "uri", description: "The tool's page on TradingAIHub." },
        website_url: { ...nurl, description: "The vendor link exactly as the TradingAIHub site renders it. For affiliate partners this is the tagged affiliate link (affiliate = true)." },
        vendor_url: { ...nurl, description: "The same vendor link, always plain (never tagged)." },
        affiliate: { type: "boolean", description: "true when website_url is an affiliate link; TradingAIHub may earn a commission." },
        disclosure: { ...nstr, description: "Short English affiliate disclosure when affiliate is true, otherwise null." },
        homepage: nurl, docs: nurl, repo: nurl, remote_mcp_url: nurl, license: nstr,
        pricing: { type: ["object", "null"], properties: { model: nstr, free_tier: nstr, paid_from: nstr, details: nstr, source: nurl, checked: nstr } },
        languages: { type: "array", items: { type: "string", enum: FILTERS.language } },
        packages: { type: "object", properties: { npm: pkg, pypi: pkg } },
        status: { type: "string", enum: FILTERS.status }, status_label: str, verified: { type: "boolean" }, checked_at: nstr,
        github: { type: ["object", "null"], properties: { stars: { type: ["integer", "null"], description: "null for shared collection repos" }, last_commit: nstr, archived: { type: "boolean" }, collection: { type: "boolean" } } },
      } },
      ToolList: { type: "object", required: ["total", "count", "limit", "offset", "tools"], properties: { ...lic, total: { type: "integer" }, count: { type: "integer" }, limit: { type: "integer" }, offset: { type: "integer" }, next: { type: ["string", "null"], description: "URL of the next page, or null." }, tools: { type: "array", items: { $ref: "#/components/schemas/Tool" } } } },
      SearchResult: { type: "object", required: ["query", "count", "tools"], properties: { ...lic, query: str, count: { type: "integer" }, tools: { type: "array", items: { $ref: "#/components/schemas/Tool" } } } },
    },
  },
};
