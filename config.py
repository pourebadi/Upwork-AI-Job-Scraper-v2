"""
Search Configuration for Apify Upwork Scraper
=============================================

Production setup:
- Focused on Heli Studio's three service lines:
  Branding, Product Design, and Web Development
- Multiple focused searches to catch high-intent jobs without turning the inbox
  into a generic design feed
- Python post-filter inside upwork_scraper.py handles real filtering, freshness, scoring, and deduplication
"""

_BASE = {
    "results_per_page": 8,
    "fixed_budget_min": 500,
    "fixed_budget_max": 100000,
    "payment_verified": True,
    "max_job_age": {"value": 10, "unit": "days"},
}

SEARCH_CONFIGS = [
    # Branding: identity systems, logos, brand books, motion, illustration.
    {**_BASE, "query": "brand identity design", "service_line": "Branding"},
    {**_BASE, "query": "logo and brand identity", "service_line": "Branding"},
    {**_BASE, "query": "visual identity design", "service_line": "Branding"},
    {**_BASE, "query": "brand guidelines design", "service_line": "Branding"},
    {**_BASE, "query": "brand style guide", "service_line": "Branding"},
    {**_BASE, "query": "brand book design", "service_line": "Branding"},
    {**_BASE, "query": "brand system design", "service_line": "Branding"},
    {**_BASE, "query": "startup branding", "service_line": "Branding"},
    {**_BASE, "query": "rebrand design", "service_line": "Branding"},
    {**_BASE, "query": "brand refresh design", "service_line": "Branding"},
    {**_BASE, "query": "brand strategy design", "service_line": "Branding"},
    {**_BASE, "query": "packaging brand identity", "service_line": "Branding"},
    {**_BASE, "query": "social media brand kit", "service_line": "Branding"},
    {**_BASE, "query": "brand illustration design", "service_line": "Branding"},
    {**_BASE, "query": "motion brand identity", "service_line": "Branding"},
    {**_BASE, "query": "logo redesign brand identity", "service_line": "Branding"},

    # Product Design: UX research, wireframes, prototypes, SaaS, apps.
    {**_BASE, "query": "product design", "service_line": "Product Design"},
    {**_BASE, "query": "product designer figma", "service_line": "Product Design"},
    {**_BASE, "query": "ux ui design", "service_line": "Product Design"},
    {**_BASE, "query": "ui ux designer", "service_line": "Product Design"},
    {**_BASE, "query": "figma ui design", "service_line": "Product Design"},
    {**_BASE, "query": "ux research design", "service_line": "Product Design"},
    {**_BASE, "query": "ux audit", "service_line": "Product Design"},
    {**_BASE, "query": "ux wireframe", "service_line": "Product Design"},
    {**_BASE, "query": "user flow wireframe", "service_line": "Product Design"},
    {**_BASE, "query": "figma prototype", "service_line": "Product Design"},
    {**_BASE, "query": "ui ux prototype", "service_line": "Product Design"},
    {**_BASE, "query": "mvp product design", "service_line": "Product Design"},
    {**_BASE, "query": "startup product design", "service_line": "Product Design"},
    {**_BASE, "query": "saas product design", "service_line": "Product Design"},
    {**_BASE, "query": "b2b saas product design", "service_line": "Product Design"},
    {**_BASE, "query": "web app product design", "service_line": "Product Design"},
    {**_BASE, "query": "dashboard ux design", "service_line": "Product Design"},
    {**_BASE, "query": "mobile app ux ui", "service_line": "Product Design"},
    {**_BASE, "query": "figma design system", "service_line": "Product Design"},
    {**_BASE, "query": "product redesign", "service_line": "Product Design"},

    # Web Development: Framer, Webflow, WordPress, landing pages, performance.
    {**_BASE, "query": "webflow developer", "service_line": "Web Development"},
    {**_BASE, "query": "framer website", "service_line": "Web Development"},
    {**_BASE, "query": "wordpress website design", "service_line": "Web Development"},
    {**_BASE, "query": "website redesign", "service_line": "Web Development"},
    {**_BASE, "query": "landing page design", "service_line": "Web Development"},
    {**_BASE, "query": "figma to webflow", "service_line": "Web Development"},
    {**_BASE, "query": "figma to framer", "service_line": "Web Development"},
    {**_BASE, "query": "responsive website design", "service_line": "Web Development"},
    {**_BASE, "query": "saas website design", "service_line": "Web Development"},
    {**_BASE, "query": "webflow cms website", "service_line": "Web Development"},
]
