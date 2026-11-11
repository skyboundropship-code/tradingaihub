# Writing for the TradingAIHub blog

For Growth and anyone else writing posts. **Every post goes through a pull request and QA before it goes live.** Nothing is published by pushing to `main` directly, and nothing is published from a CMS.

## 1. Create the post

1. Branch off `main`: `git checkout -b blog/<slug>`.
2. Copy `src/content/blog/sample-draft-post.md` to `src/content/blog/<slug>.md`. The file name is the URL: `/blog/<slug>/`. Use lowercase letters, digits and hyphens only.
3. Fill in the frontmatter:

| Key | Required | Notes |
| --- | --- | --- |
| `title` | yes | Shown as the H1, in the `<title>`, on the OG card and in RSS. |
| `description` | yes | About 155 characters, **max 160** (the build fails above that). Used for the meta description, RSS and llms.txt. |
| `date` | yes | `YYYY-MM-DD`, the publish date. Sets the order (newest first). |
| `updated` | no | `YYYY-MM-DD`, only after a real content change. Must not be earlier than `date`. |
| `tags` | no | e.g. `[mcp, market-data]`. Lowercase and hyphenated. Each tag gets a `/blog/tag/<tag>/` page. |
| `draft` | no | `true` keeps the post out of the production build, the index, RSS, the sitemap and llms.txt. |
| `canonical` | no | Absolute `https://` URL, **only** if the article was first published on another site. It sets rel=canonical, og:url and the JSON-LD url. Leave it out for original posts. Cross-posts on dev.to, Hashnode or Medium should point *their* canonical at `https://tradingaihub.com/blog/<slug>/`. |
| `ogImage` | no | A site path such as `/og/my-image.png`. By default the build generates `/og/blog-<slug>.png`. |
| `tools` | no | Tool ids from `data/tools.json`, shown as "Tools mentioned" cards. |
| `guides` | no | Guide slugs from `src/content/guides/`, shown as "Related guides". |

No other keys are allowed. The byline is fixed as **TradingAIHub Editorial**, so there is no author field.

## 2. Write

- Write plain Markdown. Use `##` for sections and `###` for subsections. Long posts (3 or more `##` sections, or more than 1,200 words) get a table of contents automatically.
- Link internal pages with site paths, such as `/tools/tradingview-mcp/`. The build fails on a link to a page that doesn't exist.
- Use `https://` for every external link. The build rejects `http://`.
- **Partner links:** paste the plain vendor URL (for example `https://www.tradingview.com/`). Never add `aff_id=`, `_go=`, `via=` or any other tracking parameter yourself. The build tags the link, adds `rel="sponsored"` and the Partner label, and shows the disclosure note. `check_aff` then verifies it like every other affiliate link on the site.
- Posts are English-only (the `/blog/` index is localized in all 13 languages; see docs/BLOG.md). Don't make up numbers, and add "Not investment advice" where relevant.

## 3. Preview

```bash
npm ci
npm run build                      # production build (drafts skipped). All gates run here.
BLOG_DRAFTS=1 npx astro build      # optional: also renders drafts, as noindex pages with a Draft badge
npm run test:blog                  # checks the draft handling
```

## 4. Open the PR

- Open a PR titled `blog: <title>`. Leave `draft: true` in place until the content is approved.
- QA reviews facts, links, partner disclosure, the OG card and the rendered page on the preview deploy (`npx wrangler pages deploy dist --project-name=tradingaihub --branch=<branch>`).
- After approval, set `draft: false` (or delete the line) in the same PR. CI and the build gates have to pass: check_aff, OG, sitemaps and tests.
- A maintainer merges and deploys. Merging is what publishes the post. It then shows up on `/blog/`, `/blog/rss.xml`, `sitemap-en.xml` and `llms.txt`.

## Fixing or removing a post

Fixes go through a PR, the same as new posts. Set `updated:` only when the change matters to readers. To unpublish a post, set `draft: true` in a PR. Don't rename a published file: that changes its URL.
