---
title: "How to Read an IPO Filing (S-1) With Free SEC EDGAR APIs and an AI Assistant"
description: "Find an S-1 on EDGAR, pull it with the SEC's free APIs, and read it section by section with an AI assistant, with quotes and page numbers."
date: 2026-11-11
tags: [sec-filings, ai-agents, mcp, research]
tools: [sec-edgar-mcp]
---
> **Not financial advice.** This is an educational guide to finding and reading public SEC filings. It is not a recommendation to buy, sell or hold any security, and it says nothing about whether any IPO is a good or bad investment.

A large AI company's IPO is all over social media this week, and most of the conversation is opinion. The primary source is public and free: the registration statement the company filed with the US Securities and Exchange Commission. This guide shows how to find an S-1 on EDGAR, pull it with the SEC's free APIs, and use an AI assistant to help you read it without letting the assistant do your thinking for you.

We use Anthropic, PBC's filings as the worked example only because they are the ones people are asking about. Everything below works the same way for any company.

## What an S-1 is

Investor.gov, the SEC's investor-education site, [defines a registration statement](https://www.investor.gov/introduction-investing/investing-basics/glossary/registration-statement) as a filing "making required disclosures in connection with the registration of a security," which often includes a prospectus describing the offering, the securities and the company. Form S-1 is the form US companies commonly use for an IPO.

Two details trip people up:

- **Amendments.** Companies usually file an S-1 and then one or more **S-1/A** amendments as the SEC reviews it and as offering terms are filled in. Always check you are reading the latest one.
- **Draft filings.** Many companies first submit a confidential draft (shown on EDGAR as **DRS** and **DRS/A**) that becomes public later. Drafts can differ from the final document.

For example, as of today Anthropic's EDGAR filing history (CIK 0002130357) shows a DRS on June 1, 2026, five DRS/A amendments between July and October, the public S-1 on October 26, and S-1/A amendments on November 2 and November 10, 2026. That is eight versions before the one you should actually read.

## Step 1: Find the filing on EDGAR

The fastest manual route is [EDGAR full-text search](https://www.sec.gov/edgar/search/): type the company name and filter the form type to S-1. Every filing has an index page that lists all its documents, including exhibits.

If you would rather script it, the SEC publishes a free ticker-to-CIK file at `https://www.sec.gov/files/company_tickers.json`. The CIK (Central Index Key) is the permanent ID EDGAR gives every filer, and [the SEC notes](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data) that CIKs are never recycled.

## Step 2: Pull the filing list with the free submissions API

The SEC runs JSON APIs on `data.sec.gov`. According to the [SEC's API page](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), they "do not require any authentication or API keys," and the submissions data is updated in real time, typically within a second of a filing being disseminated.

A company's full filing history lives at:

```
https://data.sec.gov/submissions/CIK##########.json
```

where the number is the 10-digit CIK with leading zeros. A minimal Python example:

```python
import requests

HEADERS = {"User-Agent": "Your Name your@email.com"}  # the SEC asks you to declare who you are
cik = "0002130357"  # 10 digits, leading zeros

data = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=HEADERS).json()
recent = data["filings"]["recent"]

for form, date, acc, doc in zip(recent["form"], recent["filingDate"],
                                recent["accessionNumber"], recent["primaryDocument"]):
    if form.startswith(("S-1", "DRS", "424B")):
        folder = acc.replace("-", "")
        print(form, date, f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{folder}/{doc}")
```

That prints a direct link to the main document of each version. Including `424B` catches the final prospectus, which companies file once the offering is priced.

**Play by the SEC's fair-access rules.** The SEC's [Accessing EDGAR Data page](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data) lists a current maximum of 10 requests per second, asks you to declare a User-Agent with a name and contact email, and says it does not allow botnets or automated crawling outside its policy. `data.sec.gov` also does not support CORS, so call it from a script or server, not from browser JavaScript.

## Step 3: Know the map before you ask an AI anything

S-1s are long. The November 10 Anthropic S-1/A main document is about 14.8 MB of HTML and roughly 250,000 words when we stripped the markup, and its Risk Factors section alone runs from page 29 to page 122. That is more than many chat tools can take in one go, so pasting the whole thing is not a reliable way to read it.

Start from the table of contents. The sections in that filing are typical of an S-1:

| Section | What it tells you |
|---|---|
| Prospectus Summary | The company's own short version of everything that follows |
| Risk Factors | What the company says could go wrong; usually the longest section |
| Use of Proceeds | What the company says it will do with the money raised |
| Capitalization and Dilution | How the share structure changes with the offering |
| Management's Discussion and Analysis (MD&A) | Management's explanation of the financial results |
| Business | What the company does, in its own words |
| Governance, Management, Executive Compensation | Who runs it, how they are paid, and any special governance structure |
| Principal and Selling Stockholders | Who owns what before and after the offering |
| Description of Capital Stock | The rights attached to each class of shares |
| Shares Eligible for Future Sale | Lock-ups and when more shares could be sold |
| Index to Financial Statements (F-pages) | The audited financial statements and their notes |

Anthropic's version also has a section called "Our Governance Structure and Its Goals," which is the kind of company-specific section worth reading in full rather than in summary, because it is where unusual structures (in this case a public benefit corporation and a Long-Term Benefit Trust, both mentioned throughout the document) are explained.

## Step 4: Use AI to read section by section

Work one section at a time and keep the source next to the answer. Prompts that work well:

- "Here is the Risk Factors section. Group the risks into themes and quote the sentence each theme comes from, with its page number."
- "Here is Use of Proceeds. Summarize it in five bullet points using only what the text says. Flag anything vague."
- "Compare these two versions of the Prospectus Summary (S-1 and S-1/A) and list what changed."
- "List every defined term in this section and its definition from the filing."

Prompts to avoid: "Is this a good investment?", "What will the stock do?", or anything that asks the model to predict a price. A language model has no special insight into that, and an S-1 is a disclosure document, not a forecast.

Two habits keep the output honest:

1. **Ask for quotes and page numbers,** then spot-check a few against the filing.
2. **Get numbers from structured data, not from the model's reading of a table.** For companies that already file 10-Ks and 10-Qs, the SEC's XBRL APIs (`companyfacts` and `companyconcept`) return reported figures as JSON. A brand-new IPO filer may have little or none of that yet, so read the F-pages directly.

## Optional: connect an AI assistant to EDGAR with an MCP server

If you use Claude Desktop, Cursor or another MCP-compatible client, an MCP (Model Context Protocol) server lets the assistant call EDGAR itself instead of you pasting text.

[SEC EDGAR MCP](/tools/sec-edgar-mcp/) is an open-source server by Stefano Amorelli ([GitHub](https://github.com/stefanoamorelli/sec-edgar-mcp), AGPL-3.0). Its README lists tools for CIK lookup and company facts, 10-K, 10-Q and 8-K retrieval with section extraction, XBRL-parsed financial statements, and insider Forms 3, 4 and 5, and says all responses include SEC filing URLs for verification. A few things to know before wiring it in:

- It is **community-built, not an official SEC tool**; its README says it is not affiliated with or endorsed by the SEC.
- You set your own SEC User-Agent (name and email) in its configuration, which is how it complies with the fair-access rules above.
- Its listed filing tools focus on periodic reports (10-K, 10-Q, 8-K), not S-1s, so for an IPO filing you will likely still locate the document with the submissions API and hand the relevant section to the assistant.
- Its optional HTTP mode has no authentication, and the README says to use it only on private networks.

The rest of our [Research & filings category](/category/research-filings/) lists other filing and research tools, each with its pricing model, whether it is official or community-built, and the date we last checked it. The official [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) are listed there too.

## A short checklist

- Confirm you have the **latest** S-1/A, or the final 424B prospectus once it exists.
- Read the **table of contents** first and pick sections deliberately.
- Feed the AI **one section at a time** and ask for quotes with page numbers.
- Pull **numbers** from the filing's tables or XBRL data, not from a model's paraphrase.
- Read any **company-specific governance section** yourself.
- Keep your scripts under **10 requests per second** with a declared User-Agent.

The point of reading the filing is to replace other people's opinions with the company's own disclosures. AI makes a 250,000-word document manageable, but the filing is still the source, and the decision is still yours.

*TradingAIHub is a free directory of AI tools for finance and trading. We list tools and check that they are still alive; we do not give investment advice.*
