# Domain options (checked 2026-10-29 via authoritative RDAP; NOT purchased)

RDAP 404 = not registered. Premium/reserved pricing can't be seen via RDAP — confirm at checkout.
Prices: Cloudflare Registrar = at-cost (no markup). Porkbun from its public pricing API (cross-check).

| # | Domain | RDAP | Cloudflare 1st yr / renew | Porkbun 1st / renew | Why |
|---|---|---|---|---|---|
| 1 | **tradeskills.ai** (current placeholder) | available | $80 / $80 (.ai usually 2-yr min ≈ $160 upfront) | $82.70 / $82.70 | "trade" + "skills" (Agent Skills trend, skills.sh) + AI TLD. Instantly says what it is. |
| 2 | fin.directory | available | Cloudflare price not confirmed | $4.63 / $25.23 | Mirrors cursor.directory exactly. Very short. |
| 3 | tradermcp.ai | available | $80 / $80 | $82.70 | Keyword-exact for "MCP for traders". |
| 4 | stockmcp.ai | available | $80 / $80 | $82.70 | Exact-match "stock MCP" search. |
| 5 | quantmcp.ai | available | $80 / $80 | $82.70 | Quant/algotrading crowd. |
| 6 | mcpfinance.ai | available | $80 / $80 | $82.70 | Like mcp.so / mcpservers.org pattern. |
| 7 | marketmcp.ai | available | $80 / $80 | $82.70 | Market-data angle. |
| 8 | finskills.dev | available | $8.20 / $12.20 | $8.75 / $12.87 | Cheap, dev-credible. |
| 9 | finskills.io | available | $32 / $50 | $28.12 / $51.80 | |
| 10 | finmcp.io | available | $32 / $50 | $28.12 / $51.80 | Shortest MCP+finance name (.com taken). |
| 11 | wallstreetmcp.com | available | $10.46 (Verisign raises .com wholesale ~Nov 2026; expect ≈$11.2) | $11.08 | Only memorable .com left; catchy. |
| 12 | mcpfortraders.com | available | $10.46 (same note) | $11.08 | Descriptive .com. |
| + | tradeskills.dev / tradeskills.io | available | $8.20 / $32 | — | Defensive redirects for #1. |

Taken (not options): finmcp.com, tradeskills.com, finskills.com/.ai, tradingskills.com/.ai, finagents.com/.ai, stockmcp.com, financemcp.com/.ai/.dev, tradingmcp.com/.ai, alphamcp.com/.ai, fintools.ai, mcp.finance, finance.directory, trading.directory.

**Recommendation:** tradeskills.ai (+ tradeskills.dev $8.20 as a redirect). Budget option: wallstreetmcp.com (~$10.5) or fin.directory.

**Why this style (max reach):** the directories that won devs are short, exact-keyword names on a techy TLD —
cursor.directory, mcp.so, skills.sh, glama.ai, mcpservers.org — they rank for the literal search and are self-explanatory when shared.
Catchy-phrase brands (theresanaiforthat.com / TAAFT) and category+suffix (Futurepedia) also work but need more marketing.
"TradeSkills" combines both: a keyword pair people search for and a word that reads as a brand.

**Swap brand:** edit `src/config.ts` (`SITE.name`, `domain`, `url`), `wrangler.toml` name, then `npm run weekly`.
