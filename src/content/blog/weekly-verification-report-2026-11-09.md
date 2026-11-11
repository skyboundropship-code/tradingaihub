---
title: "Weekly Verification Report, November 9, 2026: One Comeback, One Slip, and a Quiet Week for 104 Finance AI Tools"
description: "The Nov 9, 2026 run: 81 of 104 finance AI tools verified, Valyu MCP back from stale, Bankless Onchain MCP aging, and five package releases."
date: 2026-11-10
tags: [verification, mcp, weekly-report]
tools: [valyu-mcp, bankless-onchain-mcp, norman-finance-mcp]
---
*Not financial advice. This report describes the maintenance status of software tools. It is not a recommendation to use, buy, sell or trade anything.*

Every Monday at 05:00 UTC, TradingAIHub re-checks every listing in its directory of AI tools for finance and trading: MCP servers, agent skills and data APIs. The run on **November 9, 2026** finished at 05:50 UTC. This report compares it with the previous run on **November 2, 2026**, using the two versions of our public dataset ([tools.json](/tools.json)) and the per-run reports stored in the site's repository.

The short version: no tools were added or removed, the number of fully verified tools held steady at 81, and underneath that flat number two tools traded places.

## Status counts, week over week

| Status | Nov 2 run | Nov 9 run | Change |
|---|---|---|---|
| Verified | 81 | 81 | 0 |
| Aging | 4 | 5 | +1 |
| Stale | 13 | 12 | −1 |
| Archived | 3 | 3 | 0 |
| Needs review | 3 | 3 | 0 |
| **Total** | **104** | **104** | 0 |

The directory has 73 MCP servers, 16 APIs and 15 agent skills, the same mix as last week. You can see every row on the [latest verification run](/verification/) page.

A quick reminder of what the badges mean, from our [verification method](/about/): **Verified** means the repository is reachable, its links respond, and (for repos) it had a commit in the last 180 days. **Aging** means no commits in 180 to 365 days. **Stale** means no commits in over a year. **Needs review** means a link answered but refused our checker, usually because of a sign-in wall or bot protection, so we can't fully confirm it.

## What improved: Valyu MCP comes back from stale

The biggest move of the week is [Valyu MCP](/tools/valyu-mcp/), the official MCP server for Valyu's financial deep-research search platform, listed in our [research and filings category](/category/research-filings/).

Last week its repository's most recent commit dated to April 4, 2025, 576 days before the check, which put it in the Stale group. This week the checker found a commit dated November 6, 2026, and it moved straight to **Verified**. In the same run, the license we record for it changed from "unknown" to **MIT**, because the checker could now read a license from the repository.

That is exactly why we re-check weekly. A tool that looked abandoned last Monday is actively maintained this Monday, and a list that was checked once would still be showing it as stale.

## What slipped: Bankless Onchain MCP crosses the 180-day line

[Bankless Onchain MCP](/tools/bankless-onchain-mcp/), which lets agents query onchain data and ERC-20 token information, moved from **Verified** to **Aging**. Nothing broke. Its last commit is still dated May 5, 2026, and its npm package (`@bankless/onchain-mcp@1.0.6`) is still published. The repository simply went from 180 days without a commit last week to 187 days this week, which crosses our 180-day line.

Aging is not a warning that a tool doesn't work. It is a signal to check the repository's issues and recent activity before you wire it into anything that matters. Other options are listed in our [crypto category](/category/crypto/) and the [crypto MCP servers comparison](/compare/crypto-mcp-servers/).

## A package check to watch: Norman Finance MCP

[Norman Finance MCP](/tools/norman-finance-mcp/) keeps its **Verified** badge, with recent commits and an MIT license. One check changed, though. Last week our checker recorded the published package `norman-mcp-server@0.1.7`. This week it reported "no npm/PyPI package detected at repo root", so the package check no longer passed.

We don't know the reason yet, and we won't guess. Our package check only counts a package that is named in the repository and links back to it, so changes to how a repository is laid out can affect this check. If you install it from a package manager, confirm the package name against the project's own README. Related tools are in the [accounting category](/category/accounting/) and the [accounting MCP servers comparison](/compare/accounting-mcp-servers/).

## Package releases we picked up this week

Five tools shipped new package versions between the two runs, according to the versions our checker recorded:

- [Financial Modeling Prep MCP (community)](/tools/fmp-mcp-community/): `financial-modeling-prep-mcp-server` 2.8.0 to 2.9.0
- [Alpaca MCP Server](/tools/alpaca-mcp/): `alpaca-mcp-server` 2.4.0 to 2.4.1
- [DexPaprika MCP](/tools/dexpaprika-mcp/): `dexpaprika-mcp` 2.9.2 to 2.9.3
- [Lunch Money MCP](/tools/lunchmoney-mcp/): `@akutishevsky/lunchmoney-mcp` 3.0.0 to 4.0.1
- [YNAB MCP Server (community)](/tools/ynab-mcp/): `ynab-mcp-server` 0.7.2 to 0.8.0

The Lunch Money MCP jump is a new major version. Under common semantic-versioning practice a major bump can include breaking changes, so if you depend on it, read the project's release notes before upgrading. These and similar tools are grouped in our [personal finance category](/category/personal-finance/).

## What didn't change

No tool was added or removed this week, and none became unreachable or failed a link check.

The three **archived** repositories are unchanged: Base MCP, Ramp MCP and MCP Trader. Their owners archived them, so they won't get updates.

The three tools in **Needs review** are also unchanged:

- [OpenBB Platform (MCP)](/tools/openbb/): the repository redirects to a different owner, and our stored link hasn't been updated to match yet.
- [Mercury MCP (official)](/tools/mercury-mcp/): the hosted MCP endpoint answered with a 401 (sign-in required), so the checker couldn't confirm it.
- [Firefly III API](/tools/firefly-iii-api/): the homepage and docs returned a bot-challenge page (403) to our checker.

In all three cases the service answered, so this is not evidence the tools are down. It only means an automated check can't confirm them.

The 12 **stale** entries now range from the Invoice Organizer skill (387 days without a commit) to Claude Investor (956 days). The four tools that were already **aging** last week, MetaTrader 5 MCP, Crypto Indicators MCP, DexScreener Trending MCP and Actual Budget MCP, all got seven days older with no new commits. Crypto Indicators MCP is at 338 days, so if nothing lands in the next four weeks it will cross the one-year mark and move to Stale.

## How to use this report

If you are picking an MCP server or agent skill to connect to a brokerage, data feed or accounting system, maintenance status is one input, not the whole decision. A verified badge tells you a project is alive and its links work. It doesn't tell you the tool is secure, accurate or right for your use case. Read the code or docs, test with paper or sandbox accounts first, and keep credentials scoped as tightly as the service allows.

For a ranked view of what's actively maintained, see the [weekly leaderboard](/weekly/). For side-by-side picks, start with the [best stock market MCP servers comparison](/compare/best-stock-market-mcp-servers/) or browse [all tools](/tools/).

The next run is scheduled for Monday, November 16, 2026 at 05:00 UTC.

*Data sources: TradingAIHub weekly verification runs of November 2 and November 9, 2026 ([public dataset](/tools.json), [latest run](/verification/)). Statuses are generated automatically from public repository, package-registry and link checks. Not financial advice.*
