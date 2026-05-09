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
├── cloudflare_worker.js
├── wrangler.toml.example
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
| `cloudflare_worker.js`          | Public webhook router for Notion   |
| `wrangler.toml.example`         | Cloudflare Worker deploy template  |
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

### 7. Run the webhook trigger

```bash
python webhook_server.py
```

This server receives POST requests from Notion buttons and dispatches the matching GitHub Actions workflow. Managers stay inside Notion; GitHub only runs the automation.

For production, deploy the same router as a public Cloudflare Worker using `cloudflare_worker.js`. The local Python server is useful for development, but Notion cannot call it unless it is reachable from the public internet.

Available Notion webhook routes:

```text
/notion/run-scraper        → dispatch scraper.yml
/notion/proposal-request   → dispatch proposal-worker.yml
/notion/generate-proposal  → dispatch proposal-worker.yml
/notion/refresh-workspace  → dispatch scraper.yml with setup_only=true
```

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

Optional GitHub Actions secrets:

```text
MAX_JOB_AGE_DAYS
NOTIFICATION_WEBHOOK_URL
```

Webhook server environment:

```text
GITHUB_REPOSITORY=pourebadi/Upwork-AI-Job-Scraper-v2
GITHUB_DISPATCH_TOKEN=github_pat_or_fine_grained_token
WEBHOOK_SHARED_SECRET=your_shared_secret
GITHUB_REF=main
GITHUB_PROPOSAL_WORKFLOW_ID=proposal-worker.yml
GITHUB_SCRAPER_WORKFLOW_ID=scraper.yml
```

Cloudflare Worker setup:

```bash
cp wrangler.toml.example wrangler.toml
wrangler secret put GITHUB_DISPATCH_TOKEN
wrangler secret put WEBHOOK_SHARED_SECRET
wrangler deploy
```

After deployment, use the Worker URL as your public webhook base URL.

## Notion-First Automation

The repository now supports a fully coded Notion-first flow with no daily GitHub clicks.

When `setup_notion_workspace.py` runs, it also creates or refreshes a Persian knowledge-base page under the same parent page in Notion. That page explains the databases, properties, daily workflow, and troubleshooting steps for the team.

### Daily manager workflow

```text
1. Open Jobs in Notion.
2. Review a job in the list or open its page.
3. Tick Generate Proposal on that row.
4. Wait for Proposal Status to move to Generating and then Ready.
5. Read the generated proposal inside the same job page.
6. If you need fresh jobs, open Automation Control and tick Fetch New Jobs.
```

### What the code creates in Notion

`Jobs` database:

```text
Generate Proposal (checkbox)
```

`Automation Control` database:

```text
Primary Control
Fetch New Jobs
Fetch Status
Last Fetch At
Help
```

### How it works

Proposal generation:

```text
Manager ticks Generate Proposal
→ Notion database automation sends a webhook to /notion/generate-proposal
→ cloudflare_worker.js or webhook_server.py dispatches proposal-worker.yml immediately
→ generate_requested_proposals.py picks up checked jobs
→ it auto-approves the job and sets Proposal Status to Generating
→ proposal text is written back into the same page
→ Proposal Status becomes Ready
```

List refresh / workspace refresh:

```text
Manager ticks Fetch New Jobs in Automation Control
→ Notion database automation sends a webhook to /notion/run-scraper
→ cloudflare_worker.js or webhook_server.py dispatches scraper.yml immediately
→ run_notion_controlled_scraper.py runs setup_notion_workspace.py and/or upwork_scraper.py
→ Fetch Status and Last Fetch At are updated in the same row
```

Required Notion automations:

```text
Jobs automation
Trigger: Generate Proposal is checked
Action: Send webhook
URL: https://YOUR_WORKER_URL/notion/generate-proposal
Header: X-Webhook-Secret = your_shared_secret

Automation Control automation
Trigger: Fetch New Jobs is checked
Action: Send webhook
URL: https://YOUR_WORKER_URL/notion/run-scraper
Header: X-Webhook-Secret = your_shared_secret
```

The scheduled polling workflows remain as a fallback, but they are not the recommended manager-facing trigger. Old admin-only properties still exist behind the scenes for compatibility, but they should stay hidden from daily users.

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

## Digital Marketing Manager Workflow

The `Jobs` database is configured as a review inbox, not one endless table. Use these views for daily management:

```text
01 Today
Review only jobs discovered today with Manager Review = New.

02 Yesterday
Review only yesterday's unreviewed jobs.

03 Older
Unreviewed jobs from before yesterday, limited to the recent week.

04 Review
All unreviewed jobs. Use this only as the full backlog.

05 Week
Weekly unreviewed review sorted by day and match score.

06 Proposal
Approved jobs that still need proposal generation.

07 Ready
Generated proposals ready to submit on Upwork.

08 Applied
Jobs already submitted.

09 Archive
Archived decisions that should not pollute active views.

10 All
Fallback archive sorted by newest discovered day first.
```

Daily operating flow:

```text
1. Start in 01 Today.
2. Move to 02 Yesterday, then 03 Older if today's queue is clear.
3. Review from highest Match Score downward.
4. Set Manager Review to Approved, Rejected, or leave New for later.
5. Tick Generate Proposal for approved jobs.
6. Submit ready proposals from 07 Ready.
```

The active review views show decision columns such as `Generate Proposal`, `Manager Review`, `Proposal Status`, and `Status`. Long/internal fields such as `Job Summary`, `AI Notes`, and `Proposal Preview` stay hidden from table views.

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
