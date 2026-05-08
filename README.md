# Upwork AI Job Scraper & Notion Automation

<p align="center">
  <b>An automated Upwork lead discovery, scoring, AI proposal generation, and Notion CRM workflow.</b>
</p>

<p align="center">
  Built by <b>Mahdi Pourebadi</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-blue" />
  <img src="https://img.shields.io/badge/Automation-GitHub%20Actions-black" />
  <img src="https://img.shields.io/badge/CRM-Notion-white" />
  <img src="https://img.shields.io/badge/Scraper-Apify-orange" />
  <img src="https://img.shields.io/badge/AI-OpenAI-green" />
</p>

---

## Overview

**Upwork AI Job Scraper & Notion Automation** is a workflow automation project that finds relevant Upwork jobs, filters and scores them, generates AI-powered proposal drafts, and saves everything into a structured Notion database.

It is designed to reduce repetitive freelance lead-generation work such as:

- manually searching Upwork
- opening and reviewing job posts
- checking client quality
- copying job descriptions
- writing proposal drafts
- organizing leads in Notion
- tracking application status

Instead of starting from an empty search page every day, you get a clean pipeline of reviewed, scored, and proposal-ready jobs.

---

## Workflow

```text
┌────────────┐
│   Apify    │
│ Upwork Job │
│  Scraper   │
└─────┬──────┘
      │
      ▼
┌────────────┐
│   Python   │
│ Normalize  │
│ Filter     │
│ Deduplicate│
│ Score Jobs │
└─────┬──────┘
      │
      ▼
┌────────────┐
│   OpenAI   │
│ Proposal   │
│ Generator  │
└─────┬──────┘
      │
      ▼
┌────────────┐
│   Notion   │
│ Job CRM    │
│ Review Hub │
└────────────┘
````

---

## What It Does

The system runs on a schedule or manually through GitHub Actions.

It searches Upwork through Apify, collects structured job data, removes duplicates, scores each job, writes a proposal draft with OpenAI, and sends everything into Notion as a clean review page.

Each Notion entry includes:

* AI-generated proposal
* job summary
* job snapshot
* budget and client data
* proposal count
* payment status
* original job link
* full job description
* status tracking

---

## Features

### Job Discovery

* Automated Upwork scraping through Apify
* Configurable search queries
* Supports multiple niches and job categories
* Adjustable job age and result count
* Works with GitHub Actions for scheduled runs

### Filtering & Qualification

* Deduplication by Job ID and job URL
* Keyword relevance filtering
* Negative keyword filtering
* Client spend detection
* Client hire count detection
* Payment verification status
* Proposal count tracking
* Budget and hourly range parsing
* Project freshness detection

### Match Scoring

Every job receives a `Match Score` to help prioritize better opportunities first.

The score considers:

* service relevance
* client quality
* budget fit
* proposal competition
* payment status
* job freshness
* high-value keywords
* negative signals

### AI Proposal Generation

* Uses OpenAI API
* Reads the full Upwork job post
* Generates a short proposal draft
* Controlled by `proposal_template.md`
* Easy to customize for personal, freelancer, agency, or studio tone
* Stores the generated proposal directly inside the Notion job page

### Notion CRM

* Automatically creates missing Notion properties
* Keeps the table clean and scannable
* Stores long proposal and job text inside the page, not in crowded table columns
* Uses callouts and toggles for readable job pages
* Supports review status tracking

---

## Notion Page Layout

Each job becomes a structured Notion page:

```text
AI Proposal
└── Callout with generated proposal

Job Summary
└── Callout with short job summary

Job Snapshot
└── Match score, budget, client data, proposals, source query

Skills
└── Skill tags from the job post

Original Job
└── Bookmark link to Upwork

Full Job Description
└── Toggle with complete job description

AI Notes
└── Model and generation notes
```

---

## Project Structure

```text
upwork-ai-job-scraper/
├── notion_workspace.py
├── setup_notion_workspace.py
├── upwork_scraper.py
├── generate_requested_proposals.py
├── webhook_server.py
├── config.py
├── proposal_template.md
├── requirements.txt
├── .env.example
├── .gitignore
└── .github/
    └── workflows/
        ├── scraper.yml
        └── proposal-worker.yml
```

| File                            | Purpose                            |
| ------------------------------- | ---------------------------------- |
| `notion_workspace.py`           | Shared Notion workspace helpers    |
| `setup_notion_workspace.py`     | Creates all Notion databases       |
| `upwork_scraper.py`             | Main automation script             |
| `generate_requested_proposals.py` | Generates proposals on request   |
| `webhook_server.py`             | Receives Notion button webhooks    |
| `config.py`                     | Search queries and Apify settings  |
| `proposal_template.md`          | AI proposal writing prompt         |
| `requirements.txt`              | Python dependencies                |
| `.github/workflows/scraper.yml` | GitHub Actions automation          |

---

## Tech Stack

| Tool           | Role                           |
| -------------- | ------------------------------ |
| Python         | Core automation logic          |
| Apify          | Upwork scraping                |
| OpenAI API     | Proposal generation            |
| Notion API     | Lead database and CRM          |
| GitHub Actions | Cloud scheduling and execution |
| dotenv         | Local environment management   |

---

## Quick Start

### 1. Clone the project

```bash
git clone https://github.com/YOUR_USERNAME/upwork-ai-job-scraper.git
cd upwork-ai-job-scraper
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create environment file

```bash
cp .env.example .env
```

Add your API keys:

```env
APIFY_API_TOKEN=your_apify_token
NOTION_API_KEY=your_notion_secret
NOTION_PARENT_PAGE_ID=your_notion_parent_page_id
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-5.1
MAX_JOB_AGE_DAYS=14
```

### 4. Connect Notion

Create one parent Notion page, share that page with your integration, and copy the page ID.

Then run:

```bash
python setup_notion_workspace.py
```

### 5. Run the scraper

```bash
python upwork_scraper.py
```

### 6. Generate proposals only when requested

```bash
python generate_requested_proposals.py
```

Set `Manager Review = Approved` and `Proposal Status = Requested` in the `Jobs` database before running the proposal worker.

### 7. Run the instant webhook trigger

```bash
python webhook_server.py
```

This server receives a POST from a Notion button and immediately dispatches the `proposal-worker.yml` workflow.

---

## GitHub Actions Setup

Add these secrets in GitHub:

```text
Settings → Secrets and variables → Actions → New repository secret
```

Required secrets:

```text
APIFY_API_TOKEN
NOTION_API_KEY
NOTION_PARENT_PAGE_ID
OPENAI_API_KEY
OPENAI_MODEL
```

Optional secrets:

```text
MAX_JOB_AGE_DAYS
NOTIFICATION_WEBHOOK_URL
WEBHOOK_SHARED_SECRET
GITHUB_DISPATCH_TOKEN
GITHUB_REPOSITORY
GITHUB_REF
GITHUB_WORKFLOW_ID
```

Recommended workflow:

```yaml
name: Upwork Scraper

on:
  workflow_dispatch:
  schedule:
    - cron: "0 */6 * * *"

jobs:
  run-scraper:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Setup Notion workspace
        env:
          NOTION_API_KEY: ${{ secrets.NOTION_API_KEY }}
          NOTION_PARENT_PAGE_ID: ${{ secrets.NOTION_PARENT_PAGE_ID }}
          OPENAI_MODEL: ${{ secrets.OPENAI_MODEL }}
        run: python setup_notion_workspace.py

      - name: Run scraper
        env:
          APIFY_API_TOKEN: ${{ secrets.APIFY_API_TOKEN }}
          NOTION_API_KEY: ${{ secrets.NOTION_API_KEY }}
          NOTION_PARENT_PAGE_ID: ${{ secrets.NOTION_PARENT_PAGE_ID }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          OPENAI_MODEL: ${{ secrets.OPENAI_MODEL }}
          MAX_JOB_AGE_DAYS: ${{ secrets.MAX_JOB_AGE_DAYS }}
        run: python upwork_scraper.py
```

Proposal worker workflow:

```yaml
name: Proposal Worker

on:
  workflow_dispatch:
    inputs:
      notion_page_id:
        description: "Optional Notion page id to process immediately"
        required: false
        type: string
  schedule:
    - cron: "*/15 * * * *"
```

## Notion Button Setup

Create a database button in `Jobs` with these actions in order:

```text
1. Edit property → Manager Review = Approved
2. Edit property → Proposal Status = Requested
3. Send webhook → https://YOUR_WEBHOOK_DOMAIN/notion/proposal-request
4. Add custom header → X-Webhook-Secret: YOUR_SHARED_SECRET
5. Optional: Show confirmation
```

If the webhook payload includes a page id, the workflow will target that page immediately. If not, it will still run instantly and process all rows currently marked `Approved + Requested`.

---

## Search Configuration

Searches are now managed in the `Search Queries` Notion database.

Recommended properties:

```text
Query
Enabled
Results Per Page
Min Budget
Max Budget
Max Age Days
Category
Job Type
Experience Level
Locations
Notes
```

To get more jobs, add more enabled rows.

To reduce Apify usage, lower `Results Per Page`.

---

## Recommended Notion View

Recommended visible columns:

```text
Title
Manager Review
Proposal Status
Status
Match Score
Discovered Day
Published At
Source Query
Job Type
Budget
Proposals
Gig Link
```

Recommended sort:

```text
Match Score → Descending
Discovered Day → Descending
Published At → Descending
```

Recommended statuses:

| Status   | Meaning                   |
| -------- | ------------------------- |
| Draft    | Added automatically       |
| Review   | Worth checking manually   |
| Applied  | Proposal submitted        |
| Rejected | Not a fit                 |
| Skipped  | Ignored or duplicate-like |

---

## Configuration

Strict filters can be enabled or disabled in `upwork_scraper.py`.

```python
REQUIRE_PAYMENT_VERIFIED = False
REQUIRE_CLIENT_SPENT = False
REQUIRE_CLIENT_HIRES = False
REQUIRE_PROPOSALS_LIMIT = False
REQUIRE_PROJECT_LENGTH = False
REQUIRE_BUDGET_RANGE = False
REQUIRE_HOURLY_RANGE = False
```

For stricter production usage, a good starting point is:

```python
REQUIRE_PAYMENT_VERIFIED = True
REQUIRE_CLIENT_SPENT = True
REQUIRE_CLIENT_HIRES = True
REQUIRE_PROPOSALS_LIMIT = True
REQUIRE_PROJECT_LENGTH = False
REQUIRE_BUDGET_RANGE = False
REQUIRE_HOURLY_RANGE = False
```

---

## Customization

### Change search terms

Edit:

```text
config.py
```

### Change AI proposal style

Edit:

```text
proposal_template.md
```

### Change scoring logic

Edit:

```text
calculate_match_score()
```

inside:

```text
upwork_scraper.py
```

### Change Notion schema

Edit:

```text
setup_notion_schema.py
```

---

## Troubleshooting

| Issue                        | Fix                                                       |
| ---------------------------- | --------------------------------------------------------- |
| `APIFY_API_TOKEN missing`    | Add Apify token to `.env` or GitHub Secrets               |
| `NOTION_API_KEY missing`     | Add Notion integration secret                             |
| `NOTION_DATABASE_ID missing` | Add the correct Notion database ID                        |
| Notion 404 error             | Connect your Notion integration to the database           |
| `Status is not a property`   | Run `setup_notion_schema.py` before the scraper           |
| `model not found`            | Change `OPENAI_MODEL` to an available model               |
| No jobs found                | Add more queries or increase job age                      |
| Duplicate jobs               | Check that `Job ID` and `Gig Link` properties exist       |
| Rows are too tall in Notion  | Keep long text inside page callouts, not table properties |

---

## Security

Never commit:

```text
.env
API keys
Notion secrets
OpenAI keys
Apify tokens
scraper.log
```

Use GitHub Secrets for cloud runs.

If a key is exposed, rotate it immediately. چون API key لو رفته هم مثل کارت بانکی روی بیلبورد است، فقط با فونت geekier.

---

## Roadmap

* Category-based proposal templates
* Better negative keyword filtering
* Proposal quality scoring
* Auto-tagging by job type
* Slack or Discord daily digest
* Email summaries
* Win-rate tracking
* Multi-database support
* Portfolio link selection by category
* Analytics dashboard

---

## Author

Built by **Mahdi Pourebadi**.

---

## License

This project is released as an independent automation project.

You can use, modify, and extend it for your own workflow.

```
```
