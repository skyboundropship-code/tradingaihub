---
title: "What the OCC's New AI Risk Tiers Mean for Anyone Connecting an Agent to a Trading Account"
description: "The OCC's AI framework scores risk by what an agent can do, not how smart it is. How its four tiers map onto MCP trading tools."
date: 2026-11-05
tags: [regulation, ai-agents, mcp, brokers]
tools: [quantconnect-mcp, paper-mcp, alpaca-mcp]
---
> **Not financial advice.** This article explains regulatory guidance and product announcements for information only. It is not legal advice, and it is not a recommendation to buy, sell or trade any asset, or to use any particular service.

On Wednesday, November 4, the US Office of the Comptroller of the Currency (OCC) published [Bulletin 2026-54](https://www.occ.gov/news-issuances/bulletins/2026/bulletin-2026-54.html), a supervisory framework for how its examiners should evaluate banks' use of what the agency now calls "Super Intelligence" (SI), its term for AI. [Reuters described it](https://www.investing.com/news/economy-news/us-bank-regulator-issues-firstever-ai-guidance-for-examiners-4998329) as the OCC's first-ever guidance on how examiners should probe banks' AI use. The same day, the Monetary Authority of Singapore said its [Future of Finance Institute had begun operations](https://fintechnews.sg/140394/ai/future-of-finance-institute-mas-ai-operations/) with a focus on agentic AI, and two more trading platforms announced MCP connections that let AI assistants act on accounts.

The OCC document is written for bank examiners, not for retail traders or developers. But its core idea, that risk depends on what an agent is allowed to do rather than how clever the model is, is a useful lens for anyone wiring Claude, ChatGPT or a custom agent to a brokerage or exchange. This piece walks through what the framework actually says and how its questions map onto trading tools.

## What the OCC published

The bulletin is explicit about its limits. It "does not establish supervisory expectations for banks," and nothing in it is "intended to establish new regulatory expectations or set forth enforceable standards or prescriptive requirements," according to the [OCC's summary](https://www.occ.gov/news-issuances/bulletins/2026/bulletin-2026-54.html). Examiners are told not to treat AI as a separate risk category, and banks are not required to define a separate AI risk appetite. As [Reuters notes](https://www.investing.com/news/economy-news/us-bank-regulator-issues-firstever-ai-guidance-for-examiners-4998329), guidance like this is not legally binding, but banks typically follow it closely.

The [full framework (PDF)](https://www.occ.gov/news-issuances/news-releases/2026/nr-occ-2026-97a.pdf) sets out sixteen components grouped into six pillars: purpose, risk, control, oversight, resilience and assurance. It also notes that the document itself "was prepared with the assistance of SI" and was reviewed, edited and approved by a human.

Its overarching principle is one sentence worth quoting in full: "A bank's control intensity could increase with the potential consequences of an SI agent's failure or misuse." The framework gives an example that will sound familiar to anyone who has followed this month's broker launches: "a simple rules-based agent authorized to initiate transactions could present greater risk than a sophisticated model limited to internal drafting assistance."

## The four illustrative tiers

The most practical part of the framework is an illustrative risk-tiering method. Each use case is scored on decision consequence, reversibility, customer or financial impact, autonomy level, data sensitivity, explainability and provenance, meaning whether the system is built in-house, fine-tuned from a third-party model or consumed as an external service. Those factors combine into a composite tier:

| Tier | Profile (as described by the OCC) | OCC's illustrative examples |
|---|---|---|
| Tier 1: Critical | Direct action, low or no reversibility, high financial or customer impact, autonomous or partially autonomous | Autonomous payment agent; real-time credit decisioning; fraud-hold release; market access |
| Tier 2: High | Direct action or high-weight decision support, human-on-the-loop, moderate-to-high impact | SI-assisted underwriting; agent-initiated customer communications; AML alert disposition |
| Tier 3: Moderate | Decision support with mandatory human-in-the-loop, limited data sensitivity, reversible | Internal document summarization for credit memos; agent-assisted research |
| Tier 4: Low | No customer or financial data exposure, no direct action, fully human-controlled | Internal productivity tools; code assistance; general employee Q&A |

"Market access" sits in Tier 1. The framework adds that a fully autonomous, customer-facing payment agent sits at Tier 1 "regardless of how well it performs in testing."

The OCC also draws a distinction that trading tools rarely spell out. **Human-in-the-loop** means review and approval before an action is executed. **Human-on-the-loop** means active monitoring with the authority and practical ability to intervene. The framework warns that approval should be "more than a nominal click," and that high volumes or bulk approval can reduce review quality and contribute to alert fatigue.

## Mapping the tiers onto trading agents

These tiers were written for banks, and a personal trading setup is not a bank. Still, the same questions sort the tools people are connecting today into clear groups.

**Research and data only.** An agent that reads market data, filings or a backtest result and returns analysis takes no direct action. In the OCC's terms that is closest to Tier 3 or Tier 4. Many tools in our [quant and backtesting category](/category/quant-backtesting/) work this way. [QuantConnect's remote MCP](https://www.quantconnect.com/announcements/21675/remote-mcp-for-quantconnect/), listed as [QuantConnect MCP](/tools/quantconnect-mcp/), is mostly research, backtesting and paper deployment, though its announcement says agents can also inspect existing live algorithms.

**Execution with per-order confirmation.** PrimeXBT's [MCP launch on November 4](https://www.globenewswire.com/news-release/2026/11/04/3395052/0/en/primexbt-launches-ai-assisted-trading-with-mcp-integration-connecting-chatgpt-and-claude-to-trading-accounts.html) lets assistants prepare market, limit and stop orders and preview estimated prices, fees, margin and liquidation levels. According to the company, every order requires explicit trader confirmation, Read-only and Read & Trade permissions are available, and withdrawals and fund transfers through AI assistants are not allowed. That is a human-in-the-loop design on a direct-action use case.

**Execution without per-order confirmation.** B2BROKER's [B2TRADER update](https://www.globenewswire.com/news-release/2026/11/04/3395078/0/en/b2broker-expands-b2trader-ai-strategy-with-mcp-trading-agents-and-in-terminal-chat.html), also announced November 4, shows how both models can exist in one product. Trades proposed through its in-terminal AI chat require explicit confirmation, while external agents granted full access "can execute permitted trades without individual order confirmations," according to the announcement. Brokers using the platform can disable MCP or choose read-only or full access. Direct action with no per-trade checkpoint is the profile the OCC places at the top of its scale.

**Paper trading.** A simulated account removes financial impact entirely, which is why it is the natural first step for testing any agent. Our listings include [Paper Invest MCP](/tools/paper-mcp/) and broker integrations with paper modes, such as [Alpaca MCP](/tools/alpaca-mcp/).

## Questions the framework suggests asking

None of this tells you whether to use any service. It does give a useful checklist, drawn from the framework's own language:

1. **What is the agent permitted to do?** The OCC's first component is a defined purpose: what the system is designed to do, what it is not designed to do, and which accounts and actions it can reach. For a trading agent, that means knowing whether order tools are exposed at all.
2. **Can a mistake be undone?** Reversibility is a scoring factor. A filled market order generally cannot be undone the way a draft can be deleted.
3. **Where is the human, and is the check real?** Per-order confirmation is human-in-the-loop. Watching a dashboard is human-on-the-loop. Neither helps if approvals become reflexive.
4. **How do you stop it?** The framework lists "circuit breakers, rate limits, least-privilege permissions, and kill switches" as ways to contain an agent that is running but acting incorrectly. Know how to revoke access and, separately, how to cancel open orders.
5. **Who built it?** Provenance matters to the OCC, and it matters for MCP servers too. Official, broker-run servers and community projects have different maintenance profiles. Our [verification process](/verification/) re-checks every listing on a schedule.

## Singapore takes a parallel route

Singapore is approaching the same problem through industry collaboration. According to [Fintech News Singapore](https://fintechnews.sg/140394/ai/future-of-finance-institute-mas-ai-operations/), MAS's Future of Finance Institute has three programmes: PathFin.ai for knowledge sharing, BuildFin.ai for guidance, standards and shared tools for deploying AI including agentic AI, and SafeFin.ai for implementing MAS's Guidelines on AI Risk Management. BuildFin.ai will build on the Safeguards for Agentic Finance at Runtime (SAFR) framework, which MAS developed with industry partners.

## The takeaway

Regulators are converging on a simple idea: the riskiest AI in finance is not necessarily the most advanced model, but the one with permission to act without a meaningful human check. The same test is worth applying before connecting any agent to a trading account. Start with what it can do, then decide how much oversight that deserves.

You can browse broker integrations in our [trading and broker tools category](/category/trading-brokers/), compare data servers in [best MCP servers for stock market data](/compare/best-stock-market-mcp-servers/), or see the full [directory of verified tools](/tools/).

## Sources

- OCC, Bulletin 2026-54, "Super Intelligence: Supervisory Framework," November 4, 2026: https://www.occ.gov/news-issuances/bulletins/2026/bulletin-2026-54.html
- OCC, "Supervisory Framework for Bank Use of Super Intelligence" (PDF): https://www.occ.gov/news-issuances/news-releases/2026/nr-occ-2026-97a.pdf
- Reuters via Investing.com, "US bank regulator issues first-ever AI guidance for examiners," November 4, 2026: https://www.investing.com/news/economy-news/us-bank-regulator-issues-firstever-ai-guidance-for-examiners-4998329
- Fintech News Singapore, "MAS' Future of Finance Institute Begins Operations with AI Focus," November 4, 2026: https://fintechnews.sg/140394/ai/future-of-finance-institute-mas-ai-operations/
- PrimeXBT via GlobeNewswire, November 4, 2026: https://www.globenewswire.com/news-release/2026/11/04/3395052/0/en/primexbt-launches-ai-assisted-trading-with-mcp-integration-connecting-chatgpt-and-claude-to-trading-accounts.html
- B2BROKER via GlobeNewswire, November 4, 2026: https://www.globenewswire.com/news-release/2026/11/04/3395078/0/en/b2broker-expands-b2trader-ai-strategy-with-mcp-trading-agents-and-in-terminal-chat.html
- QuantConnect, "Remote MCP for QuantConnect": https://www.quantconnect.com/announcements/21675/remote-mcp-for-quantconnect/
