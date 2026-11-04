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

CFD broker Century Financial launched **Century AI Connect** on Tuesday, November 3, according to [TradeInformer](https://tradeinformer.com/tech-news/century-financial-launches-claude-connector). It uses remote MCP and exposes more than 50 tools in six groups: account data such as positions, trading history and watchlists, plus indicative mid prices, Trading Central research, news sentiment, an economic calendar and company information.

The boundary is explicit. Assistants cannot place, change or close trades, move funds or edit account settings; execution stays in the Century Trader app. Clients sign in through a Century page rather than pasting API keys. TradeInformer also notes that Century says prompts and answers are processed by the AI provider under that provider's own terms, a detail worth reading before connecting any account.

### Coinbase: trading allowed, with guardrails

Coinbase opened a sign-up flow at [coinbase.com/agents](https://www.coinbase.com/agents) that lets users set up an account "for you" or "for your agent", as [Techiexpert reports](https://techiexpert.com/coinbase-launches-sign-up-page-allowing-ai-agents-to-trade-crypto-stocks-and-futures/). Connected assistants, including ChatGPT, Claude, Grok, Perplexity, Cursor or other MCP-compatible clients, can review portfolios and, depending on region and account tier, trade crypto, stocks and 24/7 futures and derivatives. A CLI is offered for tools without MCP support.

The controls are where this differs from Century. Users can place the agent in a separate sandbox portfolio, set hard spending limits, require manual approval before a trade goes through, or disconnect the agent. Agents cannot transfer or withdraw funds outside Coinbase. According to the report, Coinbase charges no extra fee for agent use beyond normal trading fees and reminds users that models can make mistakes and that account holders remain responsible for their trading.

### Tria: trade-only keys on live perpetuals

Tria published API trading tools that let agents place and cancel perpetual futures orders on Hyperliquid and Decibel, [Let's Data Science reports](https://letsdatascience.com/news/tria-opens-perpetuals-trading-to-ai-agents-with-trade-only-k-16b340f2), citing NewsBTC and Tria's documentation. The same surface is available through a TypeScript SDK, a Python SDK and an MCP server (`@tria-sdk/api-trading-mcp`).

Agent and delegate keys are trade-only: they can place, cancel, modify and batch orders, attach take-profit and stop-loss orders and close positions, but not withdraw. The MCP server is described as supporting per-call approval, with credentials that never reach the model.

Two caveats from the coverage stand out. First, both venues run on real mainnet with no testnet target, and the environment setting changes fees rather than switching to a simulated market, so a test order is a live order. Second, revoking a key stops new actions but does not by itself cancel open orders or close positions. Blocking withdrawals removes one risk; it does not stop a mis-sized or repeated order from losing money.

### QuantConnect: research and paper trading, remotely

[QuantConnect announced a remote MCP server](https://www.quantconnect.com/announcements/21675/remote-mcp-for-quantconnect/) that connects Claude Code, Codex or another compatible client to its data, project files, research environment and compute. It lists more than 45 tools across the quant workflow: creating and editing Python or C# projects and compiling them, exploring the Data Library, running Jupyter notebooks, running backtests and optimizations, deploying strategies to paper trading, and inspecting existing live algorithms, including holdings, performance and logs.

Its scope is the research loop rather than a brokerage account, which puts it in a different risk category from the other three. We list QuantConnect's MCP in the directory: [QuantConnect MCP](/tools/quantconnect-mcp/).

## Three permission models

Put side by side, the launches sort into three patterns.

| Model | Example | Assistant can | Main control |
|---|---|---|---|
| Read-only | Century AI Connect | Read positions, history, research, prices | No execution tools exposed |
| Act with limits | Coinbase agents | Trade within a sandbox and spending limits | Optional manual approval, no external withdrawals |
| Trade-only keys | Tria | Place, modify and cancel live orders | No withdrawals; per-call approval in MCP |

TradeInformer adds two more data points from other recent launches: Match-Trader's MCP integration lets assistants open, modify and close positions with approval steps before those actions run, and Webull's Cloud MCP lets assistants prepare orders that customers then confirm inside Webull. Our listing for Webull's developer integration is here: [Webull OpenAPI MCP](/tools/webull-openapi-mcp/).

The pattern across all of them: no one is letting agents move money off-platform, and most put a human confirmation step somewhere. Where that step sits, and whether it is on by default, varies.

## What to check before you connect an agent

None of this is a reason to connect or avoid any service. It is a checklist, drawn from the details the providers themselves chose to publish:

1. **Is execution exposed at all?** Read-only connectors like Century's remove the order-entry risk entirely. If you only want research and portfolio questions answered, that is the narrower choice.
2. **Is there a sandbox, and is it really separate?** Coinbase offers a separate sandbox portfolio. Tria's documentation, by contrast, says there is no testnet target; development mode still trades live.
3. **Where is the approval step, and is it on?** Per-call or manual approval only protects you if it is enabled for the tool you are using. NewsBTC's caveat on Tria applies broadly: whether a given trade needs approval depends on the tool and its configuration.
4. **What does revoking actually do?** Disconnecting an agent may not cancel its open orders. Know the separate steps for cancelling orders and closing positions.
5. **Where do your prompts go?** Account data shown to an assistant is processed under the AI provider's terms, as Century points out.
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
- Let's Data Science, "Tria Opens Perpetuals Trading to AI Agents With Trade-Only Keys," November 3, 2026: https://letsdatascience.com/news/tria-opens-perpetuals-trading-to-ai-agents-with-trade-only-k-16b340f2
- QuantConnect, "Remote MCP for QuantConnect": https://www.quantconnect.com/announcements/21675/remote-mcp-for-quantconnect/
