# Contributing to TradingAIHub

Thank you for wanting to help. This repository is the source of [tradingaihub.com](https://tradingaihub.com): the directory site, the weekly verifier, and the public API / MCP server.

**To suggest a tool for the directory**, do not open a tool-submission issue here. Use the [submit form](https://tradingaihub.com/submit/) or an issue / PR on [awesome-finance-ai-tools](https://github.com/tradingaihub/awesome-finance-ai-tools). Listing is free. Every submission is vetted before it is published.

Questions and ideas that are not a bug or a tool submission belong in [Discussions](https://github.com/tradingaihub/tradingaihub/discussions). No GitHub account? Email hello@tradingaihub.com.

## How we review inbound work

- First team reply within 2 business days.
- Tool submissions are labelled `under-review` while we check them, and `needs-info` if we need more from you (license, pricing, broker access, docs).
- Tools that can connect to or trade through a broker or exchange account are labelled `broker-access`.
- We will not merge or list anything until the review is done. A reply is not a promise that the tool will be listed.

## Bug reports and feedback

- [Bug report](../../issues/new?template=bug.yml) — something on the site, API or MCP server is broken.
- [Feedback](../../issues/new?template=feedback.yml) — typo, copy, accessibility or a product suggestion.
- Small, well-scoped tasks are labelled `good-first-issue`.

Please do not paste API keys, credentials or other private data into issues or PRs. GitHub is public.

## Pull requests

- Open one PR per change, against `main`, and fill in the PR template.
- Do not commit secrets, credentials or environment files.
- Directory data is licensed [CC BY 4.0](LICENSE-DATA) (attribution: "TradingAIHub, https://tradingaihub.com"). The API and MCP server code is [MIT](LICENSE-CODE). The rest of the site code is not licensed for reuse.
- Nothing here is investment advice.

## Development

```bash
npm ci
npm run build
npm run test:functions
```

`npm run build` is the full production build, including affiliate-link and OG checks. Please run it before you open a PR if you change pages, data or scripts.

By contributing you agree that directory data you submit is licensed under CC BY 4.0, and that code you submit to the API / MCP server is licensed under MIT.
