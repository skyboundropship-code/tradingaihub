---
title: "Brokers Are Opening Accounts to AI Agents. Here's What Each One Lets Them Do"
description: "Century Financial, Coinbase, Tria and QuantConnect opened MCP access for AI agents. What each lets an agent do, from read-only to live trades."
date: 2026-11-04
tags: [mcp, ai-agents, brokers, crypto]
tools: [quantconnect-mcp, webull-openapi-mcp, alpaca-mcp, robinhood-trading-mcp, schwab-mcp, coinbase-agentkit, binance-mcp]
---

> **Not financial advice.** This article covers product announcements for information only. It is not a recommendation to buy, sell or trade any asset, or to use any particular service.

Within a few days, four finance platforms have shipped ways for AI assistants to reach real accounts over the Model Context Protocol (MCP). On the surface they look alike: connect Claude, ChatGPT or another MCP client, and talk to your account in plain language. Underneath, they draw the line between "the assistant can see" and "the assistant can act" in very different places. For anyone wiring an agent to money, that line is the most important part of the setup.

This piece walks through what each launch actually permits, based on the announcements and documentation, and what the differences mean in practice.

## The four launches

### Century Financial: read-only by design

CFD broker Century Financial launched **Century AI Connect** on Tuesday, November 3, according to [TradeInformer](https://tradeinformer.com/tech-news/century-financial-launches-claude-connector) and [FXBrokerTrust](https://www.fxbrokertrust.com/insights/century-financial-launches-ai-readonly-account-access-service). We could not find an announcement on Century's own websites, so the details here are as those outlets report them. According to TradeInformer, it uses remote MCP and exposes more than 50 tools in six groups: account data such as positions, trading history and watchlists, plus indicative mid prices, Trading Central research, news sentiment, an economic calendar and company information.

The boundary, as reported, is explicit. Assistants cannot place, change or close trades, move funds or edit account settings; execution stays in the Century Trader app. Clients sign in through a Century page rather than pasting API keys. TradeInformer also notes that Century says prompts and answers are processed by the AI provider under that provider's own terms, a detail worth reading before connecting any account.

### Coinbase: trading allowed, with guardrails

Coinbase opened a sign-up flow at [coinbase.com/agents](https://www.coinbase.com/agents) that lets users set up an account "for you" or "for your agent", as [Techiexpert reports](https://techiexpert.com/coinbase-launches-sign-up-page-allowing-ai-agents-to-trade-crypto-stocks-and-futures/). Coinbase's [Coinbase for Agents documentation](https://docs.cdp.coinbase.com/coinbase-for-agents/overview) describes a remote MCP server at `https://agents.coinbase.com/mcp` with OAuth sign-in, covering crypto, equities and derivatives trading, portfolio management and x402 payments, and a CLI for clients without MCP support. Supported clients listed there include ChatGPT, Claude, Grok, Perplexity and Codex CLI. What an account can trade depends on region and eligibility.

The controls are where this differs from Century. Coinbase's docs recommend a separate Advanced portfolio, funded only with what you are willing to risk, with the agent's access scoped to it on the approval screen. The Transfer permission moves funds between your own portfolios only and does not allow withdrawals to external addresses. Approval of individual trades is handled by the AI app you connect rather than enforced by Coinbase, according to Coinbase's FAQ as quoted by [The Agent Floor](https://theagentfloor.beehiiv.com/p/coinbase-ai-agent-spending-limits), which also found no user-set spending limit that Coinbase enforces, only a fixed per-order ceiling. According to Techiexpert, Coinbase charges no extra fee for agent use beyond normal trading fees and reminds users that models can make mistakes and that account holders remain responsible for their trading.

### Tria: trade-only keys on live perpetuals

Tria [announced Agentic Trading](https://blogs.tria.so/en/agentic-trading-on-tria), which lets agents open and close perpetual futures positions on Hyperliquid and Decibel from a user's own self-custodial Tria account. Its [API trading documentation](https://api-docs.tria.so/) describes the same surface through a TypeScript SDK, a Python SDK and an [MCP server](https://api-docs.tria.so/mcp) (`@tria-sdk/api-trading-mcp`, currently a private-beta package). [NewsBTC](https://www.newsbtc.com/news/tria-lets-ai-agents-trade-perpetuals-with-restricted-keys/) and [Let's Data Science](https://letsdatascience.com/news/tria-opens-perpetuals-trading-to-ai-agents-with-trade-only-k-16b340f2) covered the launch.

According to Tria's [credentials documentation](https://api-docs.tria.so/credentials), agent and delegate keys are trade-only: they can place, cancel, modify and batch orders, attach take-profit and stop-loss orders and close positions, but not withdraw. Keys default to a 90-day expiry and can be revoked from the Tria app. The [MCP security model](https://api-docs.tria.so/mcp/security) says credentials never reach the model and recommends keeping write tools such as `place_order` on manual approval in the MCP client.

Two caveats stand out. First, Tria's [documentation](https://api-docs.tria.so/) states that both venues always trade on real mainnet with no testnet target, and the only environment setting changes which fees apply, so a test order is a live order. Second, as [NewsBTC](https://www.newsbtc.com/news/tria-lets-ai-agents-trade-perpetuals-with-restricted-keys/) points out, revoking a key stops new actions but does not by itself cancel open orders or close positions. Blocking withdrawals removes one risk; it does not stop a mis-sized or repeated order from losing money.

### QuantConnect: research and paper trading, remotely

[QuantConnect announced a remote MCP server](https://www.quantconnect.com/announcements/21675/remote-mcp-for-quantconnect/) that connects Claude Code, Codex or another compatible client to its data, project files, research environment and compute. It lists more than 45 tools across the quant workflow: creating and editing Python or C# projects and compiling them, exploring the Data Library, running Jupyter notebooks, running backtests and optimizations, deploying strategies to paper trading, and inspecting existing live algorithms, including holdings, performance and logs.

Its scope is the research loop rather than a brokerage account, which puts it in a different risk category from the other three. We list QuantConnect's MCP in the directory: [QuantConnect MCP](/tools/quantconnect-mcp/).

## Three permission models

Put side by side, the launches sort into three patterns.

| Model | Example | Assistant can | Main control |
|---|---|---|---|
| Read-only | Century AI Connect (as reported) | Read positions, history, research, prices | No execution tools exposed |
| Act within a portfolio | Coinbase for Agents | Trade within the portfolios you grant | Portfolio scoping, no external withdrawals; trade approval set in the AI app |
| Trade-only keys | Tria | Place, modify and cancel live orders | No withdrawals; key expiry; manual approval recommended in the MCP client |

According to TradeInformer, two other recent launches add more data points: Match-Trader's MCP integration lets assistants open, modify and close positions with approval steps before those actions run, and Webull's Cloud MCP lets assistants prepare orders that customers then confirm inside Webull. Our listing for Webull's developer integration is here: [Webull OpenAPI MCP](/tools/webull-openapi-mcp/).

The pattern across all of them: no one is letting agents move money off-platform, and most put a human confirmation step somewhere. Where that step sits, and whether it is on by default, varies.

## What to check before you connect an agent

None of this is a reason to connect or avoid any service. It is a checklist, drawn from the details the providers themselves chose to publish:

1. **Is execution exposed at all?** Read-only connectors like Century's remove the order-entry risk entirely. If you only want research and portfolio questions answered, that is the narrower choice.
2. **Is there a sandbox, and is it really separate?** Coinbase recommends a separate, limited-funds portfolio for the agent, which is real money rather than a simulation. Tria's documentation says there is no testnet target, so every order trades live.
3. **Where is the approval step, and is it on?** Per-call or manual approval only protects you if it is enabled for the tool you are using. [NewsBTC's caveat on Tria](https://www.newsbtc.com/news/tria-lets-ai-agents-trade-perpetuals-with-restricted-keys/) applies broadly: whether a given trade needs approval depends on the tool and its configuration.
4. **What does revoking actually do?** Disconnecting an agent may not cancel its open orders. Know the separate steps for cancelling orders and closing positions.
5. **Where do your prompts go?** Account data shown to an assistant is processed under the AI provider's terms, as Century points out according to TradeInformer.
6. **Who maintains the server?** Official broker-run servers and community-built ones carry different maintenance and trust profiles. We re-check every listing in our directory on a schedule; our [verification process](/verification/) explains how.

## Where these fit in the directory

TradingAIHub tracks MCP servers, skills and APIs for trading and finance. Relevant pages for this week's news:

- [Trading and broker tools](/category/trading-brokers/), including [Alpaca MCP](/tools/alpaca-mcp/), [Robinhood Trading MCP](/tools/robinhood-trading-mcp/) and [Schwab MCP](/tools/schwab-mcp/)
- [Crypto tools](/category/crypto/), including [Coinbase AgentKit](/tools/coinbase-agentkit/) and [Binance MCP](/tools/binance-mcp/)
- [Quant and backtesting tools](/category/quant-backtesting/), including [QuantConnect MCP](/tools/quantconnect-mcp/)
- [Best MCP servers for stock market data](/compare/best-stock-market-mcp-servers/)

Coinbase's new agent sign-up, Century AI Connect and Tria's MCP server are new launches, and we have not yet reviewed them for listing. We will assess them against the same verification criteria as everything else in the directory.

## The takeaway

Agent access to trading accounts has moved from community experiments to features shipped by the platforms themselves. The useful question is no longer whether an assistant can connect, but what it is allowed to do once it does. Read-only, limited execution and trade-only keys are different products with different failure modes, and the details are in the documentation, not the headline.

## Sources

- TradeInformer, "Century Financial links client accounts to Claude, but blocks trading," November 3, 2026: https://tradeinformer.com/tech-news/century-financial-launches-claude-connector
- Techiexpert, "Coinbase Launches Sign Up Page Allowing AI Agents to Trade Crypto, Stocks, and Futures," November 3, 2026: https://techiexpert.com/coinbase-launches-sign-up-page-allowing-ai-agents-to-trade-crypto-stocks-and-futures/
- Coinbase agents sign-up: https://www.coinbase.com/agents
- Coinbase, "Coinbase for Agents" documentation: https://docs.cdp.coinbase.com/coinbase-for-agents/overview
- The Agent Floor, "Can you set spending limits on Coinbase's AI agent?": https://theagentfloor.beehiiv.com/p/coinbase-ai-agent-spending-limits
- FXBrokerTrust, "Century Financial Launches AI Read-Only Account Access Service": https://www.fxbrokertrust.com/insights/century-financial-launches-ai-readonly-account-access-service
- Tria, "Introducing Agentic Trading on Tria": https://blogs.tria.so/en/agentic-trading-on-tria
- Tria API Trading documentation (overview, credentials, MCP security model): https://api-docs.tria.so/ , https://api-docs.tria.so/credentials , https://api-docs.tria.so/mcp/security
- NewsBTC, "Tria Lets AI Agents Trade Perpetuals With Restricted Keys": https://www.newsbtc.com/news/tria-lets-ai-agents-trade-perpetuals-with-restricted-keys/
- Let's Data Science, "Tria Opens Perpetuals Trading to AI Agents With Trade-Only Keys," November 3, 2026: https://letsdatascience.com/news/tria-opens-perpetuals-trading-to-ai-agents-with-trade-only-k-16b340f2
- QuantConnect, "Remote MCP for QuantConnect": https://www.quantconnect.com/announcements/21675/remote-mcp-for-quantconnect/
