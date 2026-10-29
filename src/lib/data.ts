import { useT } from "../i18n";
import raw from "../../data/tools.json";
import report from "../../data/verification-report.json";
import { affUrl } from "./aff";
// Every outbound URL in the data goes through affUrl, so any TradingView link automatically carries the affiliate ID.
export const tools: any[] = (raw as any[]).map((t) => ({ ...t, homepage: affUrl(t.homepage), docs: affUrl(t.docs), source_url: affUrl(t.source_url), pricing: t.pricing ? { ...t.pricing, source: affUrl(t.pricing.source) } : t.pricing }));
export const verificationReport: any = report;

export const CATEGORIES = [
  { slug: "market-data", name: "Market data APIs & MCPs", short: "Market data", icon: "📈", blurb: "Real-time and historical prices, fundamentals and indicators for stocks, ETFs, forex and more." },
  { slug: "trading-brokers", name: "Trading & broker MCPs", short: "Trading & brokers", icon: "⚡", blurb: "Let an AI agent read positions and place orders through a real or paper brokerage account." },
  { slug: "crypto", name: "Crypto & DeFi", short: "Crypto", icon: "🪙", blurb: "Prices, DEX analytics, exchange trading and onchain actions for crypto agents." },
  { slug: "accounting", name: "Accounting & bookkeeping", short: "Accounting", icon: "🧾", blurb: "Connect agents to QuickBooks, Xero and close/reconciliation workflows." },
  { slug: "payments-banking", name: "Payments & business banking", short: "Payments", icon: "💳", blurb: "Stripe, business bank accounts, spend management and agent payments." },
  { slug: "personal-finance", name: "Personal finance & budgeting", short: "Personal finance", icon: "🏦", blurb: "Budgeting apps, net worth and equity-compensation helpers." },
  { slug: "research-filings", name: "Research & SEC filings", short: "Research", icon: "🔎", blurb: "SEC EDGAR, 13F, insider trades, deep research and equity reports." },
  { slug: "quant-backtesting", name: "Quant & backtesting", short: "Quant", icon: "🧪", blurb: "Strategy research, backtests, chart patterns and trading skills." },
  { slug: "macro", name: "Macro & economics", short: "Macro", icon: "🌍", blurb: "FRED series, economic calendars, FX and macro indicators." },
];
export const catBySlug = Object.fromEntries(CATEGORIES.map((c) => [c.slug, c]));
export const TYPE_LABEL: Record<string, string> = { mcp: "MCP server", skill: "Agent skill", api: "API" };

export const STATUS: Record<string, { label: string; tone: string; help: string }> = {
  verified: { label: "Verified", tone: "good", help: "Reachable, links alive, and (for repos) a commit in the last 180 days." },
  aging: { label: "Aging", tone: "warn", help: "Reachable, but no commits in 180–365 days." },
  stale: { label: "Stale", tone: "bad", help: "Reachable, but no commits in over a year. Test before relying on it." },
  archived: { label: "Archived", tone: "bad", help: "The repository is archived by its owner." },
  warning: { label: "Check links", tone: "warn", help: "A homepage, docs or endpoint link failed in the last check." },
  unreachable: { label: "Unreachable", tone: "bad", help: "The repository or homepage could not be reached." },
};
export const pkgOf = (t: any) => t.verification?.npm || t.verification?.pypi || null;
// Stars of a shared list / monorepo (repo_is_collection) belong to the whole collection, not to one entry,
// so such entries show no stars and are left out of every star ranking.
export const isCollection = (t: any) => !!(t.repo_is_collection || t.verification?.github?.collection);
export const starsOf = (t: any): number | null => (isCollection(t) ? null : t.verification?.github?.stars ?? null);
export const byStars = (a: any, b: any) => (starsOf(b) ?? -1) - (starsOf(a) ?? -1);
export const lastCommit = (t: any) => (t.verification?.github?.last_commit || "").slice(0, 10) || null;
export const ownerRepo = (t: any) => (t.repo || "").replace("https://github.com/", "").replace(/\/tree\/.*$/, "") || null;
const subPath = (t: any) => (t.repo || "").match(/\/tree\/[^/]+\/(.+?)\/?$/)?.[1] || null;
const cloneOf = (t: any) => (subPath(t) ? `git clone https://github.com/${ownerRepo(t)}  # skill folder: ${subPath(t)}/` : `git clone ${t.repo}`);
export const fmtStars = (n: number | null) => (n == null ? "—" : n >= 1000 ? (n / 1000).toFixed(1) + "k" : String(n));
export const slugName = (t: any) => t.id.replace(/[^a-z0-9-]/g, "");

export function snippets(t: any, tr: (k: string, v?: any) => string = useT("en").t) {
  const name = slugName(t);
  const v = t.verification || {};
  const out: { client: string; lang: string; code: string; note?: string }[] = [];
  const pkg = v.npm ? { cmd: "npx", args: ["-y", v.npm.name] } : v.pypi ? { cmd: "uvx", args: [v.pypi.name] } : null;
  const remote = t.remote_mcp_url;
  const keyNote = tr("snip.keyNote");
  if (t.type === "mcp" && pkg) {
    const block = JSON.stringify({ mcpServers: { [name]: { command: pkg.cmd, args: pkg.args } } }, null, 2);
    out.push({ client: "Claude Desktop", lang: "json", code: block, note: tr("snip.claudeDesktop") + " " + keyNote });
    out.push({ client: "Claude Code", lang: "bash", code: `claude mcp add ${name} -- ${pkg.cmd} ${pkg.args.join(" ")}` });
    out.push({ client: "Cursor", lang: "json", code: block, note: tr("snip.cursor") });
    out.push({ client: "Gemini CLI", lang: "json", code: block, note: tr("snip.gemini") });
  }
  if (t.type === "mcp" && remote) {
    out.push({ client: "Claude (connector)", lang: "text", code: remote, note: tr("snip.claudeConnector") });
    out.push({ client: "Claude Code", lang: "bash", code: `claude mcp add --transport http ${name} ${remote}` });
    out.push({ client: "Cursor", lang: "json", code: JSON.stringify({ mcpServers: { [name]: { url: remote } } }, null, 2) });
    out.push({ client: "ChatGPT", lang: "text", code: remote, note: tr("snip.chatgpt") });
    out.push({ client: "Grok (xAI API)", lang: "json", code: JSON.stringify({ tools: [{ type: "mcp", server_url: remote, server_label: name }] }, null, 2), note: tr("snip.grok") });
    out.push({ client: "Gemini CLI", lang: "json", code: JSON.stringify({ mcpServers: { [name]: { httpUrl: remote } } }, null, 2) });
  }
  if (t.type === "mcp" && !pkg && !remote && t.repo) {
    out.push({ client: tr("snip.allClients"), lang: "text", code: cloneOf(t), note: tr("snip.fromSource") });
  }
  if (t.type === "mcp" && !pkg && !remote && !t.repo) {
    out.push({ client: tr("snip.allClients"), lang: "text", code: t.docs || t.homepage, note: tr("snip.accountUrl") });
  }
  if (t.type === "mcp" && pkg && !remote) {
    out.push({ client: "ChatGPT / Grok", lang: "text", code: tr("snip.needsRemote"), note: tr("snip.stdioOnly") });
  }
  if (t.type === "skill") {
    const or = ownerRepo(t);
    if (v.claude_marketplace) out.push({ client: "Claude Code", lang: "bash", code: `/plugin marketplace add ${or}`, note: tr("snip.marketplace") });
    out.push({ client: tr("snip.anySkills"), lang: "bash", code: `npx skills add ${subPath(t) ? t.repo : or}`, note: tr("snip.skillsCli") });
    out.push({ client: tr("snip.manual"), lang: "bash", code: cloneOf(t), note: tr("snip.manualSkill") });
  }
  if (t.type === "api") {
    const mcp = tools.filter((x) => x.type === "mcp" && x.pricing?.source && x.pricing.source === t.pricing?.source);
    out.push({ client: tr("snip.anyAgent"), lang: "text", code: t.docs || t.homepage, note: mcp.length ? tr("snip.viaMcp", { list: mcp.map((m) => m.name).join(", ") }) : tr("snip.rest") });
  }
  return out;
}

export const COMPARISONS = [
  { slug: "market-data-api-pricing", title: "Market data APIs for AI agents: free tiers & pricing compared", intro: "Published free-tier limits and entry prices of the major market-data APIs, each linked to the vendor's pricing page.", filter: (t: any) => t.type === "api" && ["market-data", "crypto"].includes(t.category) , cols: "pricing" },
  { slug: "best-stock-market-mcp-servers", title: "Stock market MCP servers compared", intro: "MCP servers that bring stock and fundamentals data into Claude, Cursor and other AI clients — by maintenance status, stars, license and install method.", filter: (t: any) => t.type === "mcp" && t.category === "market-data", cols: "repo" },
  { slug: "broker-trading-mcp-servers", title: "Broker & trading MCP servers compared", intro: "MCP servers that can read positions or place orders. Always start in paper-trading mode.", filter: (t: any) => t.category === "trading-brokers", cols: "repo" },
  { slug: "crypto-mcp-servers", title: "Crypto MCP servers compared", intro: "Crypto market data, DEX analytics, exchanges and onchain tools.", filter: (t: any) => t.category === "crypto" && t.type !== "api", cols: "repo" },
  { slug: "accounting-mcp-servers", title: "Accounting, payments & banking MCPs compared", intro: "Official and community servers for QuickBooks, Xero, Stripe, Ramp, Qonto and more.", filter: (t: any) => ["accounting", "payments-banking"].includes(t.category), cols: "repo" },
  { slug: "sec-filings-research-tools", title: "SEC filings & research tools for AI agents", intro: "EDGAR, 13F, insider trades and research agents compared.", filter: (t: any) => t.category === "research-filings", cols: "repo" },
  { slug: "trading-skills-for-claude", title: "Finance & trading agent skills compared", intro: "SKILL.md-based skills and Claude Code plugins for finance and trading work.", filter: (t: any) => t.type === "skill", cols: "repo" },
];
import changelogRaw from "../../data/changelog.json";
export const changelog: any[] = changelogRaw as any[];
