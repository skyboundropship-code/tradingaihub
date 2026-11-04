---
title: "How to evaluate an MCP server for market data (sample draft)"
description: "Sample draft post for authors: shows the frontmatter, headings, internal links and a tagged partner link. Never published while draft is true."
date: 2026-11-04
tags: [mcp, market-data]
draft: true
tools: [tradingview-mcp]
---

This is the **sample draft** that documents the blog format. It is built only by `npm run test:blog` and by preview builds with `BLOG_DRAFTS=1`; production builds skip it. Copy it to start a new post, then set `draft: false` (or delete the line) when the post is ready for review.

## Start with the listing

Every tool on the site has a listing with its verification status, for example the [TradingView MCP](/tools/tradingview-mcp/). Link to listings, [categories](/categories/) and [comparisons](/compare/) with site paths: the build fails on a link to a page that does not exist.

## Check the data source

Charting and screeners are only as good as the data behind them. If you mention a partner, use its plain homepage URL, such as [TradingView](https://www.tradingview.com/): the build adds the partner tag, `rel="sponsored"` and the disclosure note.

### Licence and rate limits

Read the vendor's terms before you recommend a free tier for anything automated.

## Keep it factual

State what you checked and when. Not investment advice.
