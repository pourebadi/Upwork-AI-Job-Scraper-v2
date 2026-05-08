"""
Search Configuration for Apify Upwork Scraper
=============================================

Production setup:
- Focused on Product Design, UI/UX, Figma, Webflow, Framer, SaaS, Landing Pages
- Multiple focused searches to reduce missed opportunities
- Python post-filter inside upwork_scraper.py handles real filtering, freshness, scoring, and deduplication
"""

_BASE = {
    "results_per_page": 5,
    "fixed_budget_min": 1000,
    "fixed_budget_max": 100000,
    "payment_verified": True,
    "max_job_age": {"value": 14, "unit": "days"},
}

SEARCH_CONFIGS = [
    # Core UI/UX and Product Design
    {**_BASE, "query": "ui ux design"},
    {**_BASE, "query": "ux design"},
    {**_BASE, "query": "product design"},
    {**_BASE, "query": "product designer"},

    # Figma-heavy work
    {**_BASE, "query": "figma"},
    {**_BASE, "query": "figma design"},
    {**_BASE, "query": "figma prototype"},

    # Webflow / Framer
    {**_BASE, "query": "webflow"},
    {**_BASE, "query": "framer"},
    {**_BASE, "query": "figma webflow"},
    {**_BASE, "query": "figma to webflow"},
    {**_BASE, "query": "figma to framer"},

    # Website / landing page
    {**_BASE, "query": "website design"},
    {**_BASE, "query": "website redesign"},
    {**_BASE, "query": "landing page design"},
    {**_BASE, "query": "homepage design"},

    # SaaS / dashboard / web app
    {**_BASE, "query": "saas design"},
    {**_BASE, "query": "saas dashboard design"},
    {**_BASE, "query": "dashboard design"},
    {**_BASE, "query": "web app design"},

    # MVP / startup / prototyping
    {**_BASE, "query": "mvp design"},
    {**_BASE, "query": "startup product design"},
    {**_BASE, "query": "prototype design"},
    {**_BASE, "query": "wireframe design"},

    # Brand + web overlap
    {**_BASE, "query": "brand identity design"},
    {**_BASE, "query": "branding website design"},
]
