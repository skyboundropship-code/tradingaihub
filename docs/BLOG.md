# Blog: how it works (for Growth)

Step-by-step authoring (frontmatter, links, partner links, drafts, PRs) is in [CONTRIBUTING-BLOG.md](../CONTRIBUTING-BLOG.md). This page explains the structure around it: URLs, languages, SEO, comments and the community.

## URLs and languages

| URL | What | Languages |
| --- | --- | --- |
| `/blog/`, `/he/blog/`, `/de/blog/` … | Blog index | All 13 locales. Headings, lede, pager and community box are localized (`"blog"` block in `src/i18n/<lang>.json`). Post titles and summaries stay English and carry `lang="en"` (plus `dir="ltr"` on he/ar). |
| `/blog/<slug>/` | Article | English only. hreflang `en` + `x-default`. In the language menu, other languages lead to their localized `/blog/` index. |
| `/blog/tag/<tag>/` | Tag page | English only. |
| `/blog/page/<n>/` | Older posts | English only; exists after 20 posts. |
| `/blog/rss.xml` | RSS 2.0 | Published posts only, never drafts. |

Why articles aren't translated: each article is checked line by line against primary sources. Machine translations would need the same checking in 12 more languages. If we translate one later, it gets its own file and hreflang pair; until then readers in other languages get the localized index and English articles.

## SEO built in (nothing to do per post)

- rel=canonical = the post's own URL, unless frontmatter `canonical` says the article first appeared elsewhere.
- JSON-LD: `BlogPosting` (author: Organization "TradingAIHub Editorial", publisher: TradingAIHub, dates, image, keywords) + `BreadcrumbList`. The index has `Blog` with its posts.
- OG card generated per post (`/og/blog-<slug>.png`), `og:type=article` with published/modified times.
- Sitemaps: articles in `sitemap-en.xml`, the index in every locale sitemap with hreflang alternates. Drafts and draft-only tags are never listed.
- `llms.txt` lists every published post.

## Comments (giscus + GitHub Discussions)

- Comments live in the public repo **[tradingaihub/community](https://github.com/tradingaihub/community)**, Discussions category **Articles**. Each article gets one thread, matched by its slug (`mapping: specific`, `strict`), created by giscus the first time someone comments.
- Privacy: the article page loads **nothing** from GitHub or giscus until the reader clicks **Load comments**. Commenting needs a GitHub sign-in. The privacy policy (13 locales) describes this; its paragraph only appears when comments are on.
- The comment box follows the site's light/dark theme and switches with it.
- Every article also has a plain **Discuss on GitHub** link, and the index has a Community box linking to the Discussions.
- Config: `src/lib/giscus.ts` (repo id, category id, on/off switch). **Comments are off until the giscus GitHub App is installed on tradingaihub/community** (https://github.com/apps/giscus/installations/new, "Only select repositories" → community). After that, set `ENABLED: true` in a PR. Preview builds can test it with `GISCUS=1`.
- CSP: the site sends no Content-Security-Policy today, so giscus needs no header change. If a CSP is added later it needs `script-src https://giscus.app` and `frame-src https://giscus.app`.

## Community categories and moderation

| Category | Format | Use |
| --- | --- | --- |
| Articles | Announcement (only maintainers and giscus start threads; anyone can reply) | One thread per article |
| Tools & Platforms | Open discussion | Experiences and setup questions about specific tools |
| Ideas & Requests | Open discussion | Tools to list, site/API/MCP feature ideas |
| Q&A | Question/Answer (an answer can be marked accepted) | Questions |

Moderation rules are in the repo README and Code of Conduct (Contributor Covenant 2.1, reports to hello@tradingaihub.com). In short: no investment advice or trade calls, no undisclosed promotion or referral links, never post secrets, report security issues privately. Moderators can hide, lock or delete. Turn on GitHub's notification emails for the repo so new comments are seen within a day.

## Seed posts (Nov 2026)

`read-an-s1-with-sec-edgar-apis-and-ai`, `weekly-verification-report-2026-11-09`, `occ-ai-agent-risk-tiers-trading-agents`, `brokers-ai-agents-mcp-permissions`, `free-api-and-mcp-server-for-finance-ai-tools`, `official-vs-community-finance-mcp-servers`, `we-re-check-104-finance-ai-tools-every-week`. Converted from `/workspace/growth/blog/` and `outreach/crossposts/article-3.md`: our frontmatter, the fixed byline, links to tradingaihub.com made internal (so the build checks them), wording unchanged.
