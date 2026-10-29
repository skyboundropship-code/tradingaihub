# Viral launch plan — every post/PR/email below is a DRAFT. Nothing is sent without Liran's approval (they go out under his accounts).

## Preconditions (approval needed)
1. Domain bought; site deployed (docs/HOSTING.md). 2. Public GitHub repo `awesome-finance-ai-tools` with the generated README. 3. Newsletter live. 4. Analytics on.

## Timeline
| Day | Channel | Account | Approval |
|---|---|---|---|
| D-7…D-1 | Badge outreach to the 56 "verified" makers (GitHub issue or email) so badges are live on launch day | Liran's GitHub | ✅ needed (per batch) |
| D-3 | PRs to awesome lists + directory submissions (below) | Liran's GitHub | ✅ |
| D0 Tue 15:00 Israel time (= 8am ET) | Show HN | Liran's HN | ✅ |
| D0 | X thread + post in r/mcp, r/ClaudeAI | Liran's X / Reddit | ✅ |
| D+2 | r/algotrading (only in their self-promo/weekly thread — rules are strict), r/LocalLLaMA, r/cursor, r/quant (if allowed), r/fintech | Reddit | ✅ |
| D+7 | Product Hunt (Tuesday 00:01 PT = 10:01 Israel time); first weekly "State of finance AI tools" issue | PH / newsletter | ✅ |
| Weekly | Changelog post on X + newsletter + /weekly page | X | ✅ once for a standing routine |

## Drafts
**Show HN** — Title: `Show HN: TradeSkills – a directory of finance/trading MCP servers and skills, re-verified weekly`
> I kept hitting dead finance MCP servers (abandoned repos, packages that never got published, pricing pages that don't match). So I built a free directory that checks every entry with a script every week: is the repo alive, when was the last commit, is the npm/PyPI package real and linked back to the repo, does the remote MCP endpoint respond, and what do the free tier and paid plan actually cost (with the source linked). It has 75 tools now: 56 pass, 14 are stale and 1 is archived, all shown openly. Each page has copy-paste config for Claude, Cursor, Gemini CLI, ChatGPT and Grok. The data is also published as JSON, RSS and a CC0 awesome list. It's not investment advice; I'd really like to know which tools are missing.

**Reddit r/mcp / r/ClaudeAI** — Title: `I checked 75 finance & trading MCP servers / skills — 19 are stale or archived. Free verified list + install configs`
> Body: what the check covers, the leaderboard link, the 3 most surprising findings (from /weekly), and "submit missing tools — free". No referral links.

**r/algotrading (weekly self-promo thread)**
> "Free list of MCP servers that let Claude/Cursor talk to brokers & market data (Alpaca, IBKR, Alpha Vantage, CCXT…), showing which ones are actually maintained and what the APIs cost. Paper-trade first."

**X thread (6 posts)**
1. "There are now 75+ MCP servers and agent skills for finance and trading. I checked all of them. 🧵"
2. Status breakdown chart (OG image of /weekly).
3. The best official servers: Alpaca, IBKR, Alpha Vantage, CoinGecko, Stripe, QuickBooks.
4. A market-data API pricing comparison (compare page OG image).
5. "Every page has 1-click install for Claude, Cursor, Gemini, ChatGPT and Grok."
6. Link, plus "makers: grab your free verified badge."
Tag the makers' official handles where they exist.

**Product Hunt** — Name TradeSkills; tagline "Verified AI tools for finance & trading — free"; 4 gallery images from screenshots/; maker comment = Show HN text.

**Maker badge outreach** (GitHub issue, title "Your MCP server is verified on TradeSkills (free badge)")
> Hi! We list <name> on TradeSkills, a free directory of finance AI tools that we re-check every week. It currently passes (last commit <date>, package <pkg>). If you'd like, here is a badge that updates itself: `[![TradeSkills](https://tradeskills.ai/badge/<id>.svg)](https://tradeskills.ai/tools/<id>/)`. If any of the info is wrong, reply here or use /submit. No cost, ever. Feel free to close this issue.
Send it only to repos that welcome issues; cap it at 10 a day so it doesn't look like spam.

## Awesome lists & registries (PRs/submissions — approval needed)
- PRs: BlockRunAI/awesome-finance-mcp (our seed source, CC0 — add "verified status" link), punkpeye/awesome-mcp-servers (Resources/Directories section), wong2/awesome-mcp-servers, appcypher/awesome-mcp-servers, awesome-claude-skills lists, awesome-quant (wilsonfreitas/awesome-quant), awesome-fintech lists. Check each repo's CONTRIBUTING rules first.
- Directory/registry listings of the *site* itself: TAAFT, Futurepedia, Glama, mcp.so, PulseMCP, mcpservers.org, Smithery (as resource), skills.sh. (The official MCP Registry is for servers, not directories — skip unless we ship an MCP server.)
- Growth idea (optional, phase 2): ship a tiny `tradeskills-mcp` server ("find a verified finance MCP for X") → then it's listable in the official MCP Registry, Smithery, Glama. Strong distribution loop.

## Built-in loops (already in the site)
Embeddable badges (/badge/<id>.svg + /badges), copy buttons on every snippet, share buttons + per-page OG images (93), /weekly changelog + leaderboard, /rss.xml, /tools.json, awesome/README.md mirror, free /submit, newsletter capture (inactive until a provider is approved).
