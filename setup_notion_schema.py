"""
Setup Notion Database Schema
============================

Creates missing Notion database properties required by upwork_scraper.py.

Recommended visible table columns:
1. Title
2. Status
3. Match Score
4. Freshness Days
5. Published At
6. Source Query
7. Job Type
8. Budget
9. Hourly Rate
10. Project Length
11. Proposals
12. Client Spent
13. Client Hires
14. Payment Status
15. Gig Link

Recommended hidden columns:
- Job ID
- AI Model
- AI Notes
- Last Seen
- Summary
- Proposal
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")
NOTION_API_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def get_database() -> dict:
    response = requests.get(
        f"{NOTION_API_URL}/databases/{NOTION_DATABASE_ID}",
        headers=notion_headers(),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def update_database_properties(properties_to_add: dict):
    payload = {
        "properties": properties_to_add
    }

    response = requests.patch(
        f"{NOTION_API_URL}/databases/{NOTION_DATABASE_ID}",
        headers=notion_headers(),
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def main():
    if not NOTION_API_KEY:
        raise RuntimeError("NOTION_API_KEY is missing")

    if not NOTION_DATABASE_ID:
        raise RuntimeError("NOTION_DATABASE_ID is missing")

    database = get_database()
    existing_properties = database.get("properties", {})

    title_property = None

    for property_name, property_schema in existing_properties.items():
        if property_schema.get("type") == "title":
            title_property = property_name
            break

    if title_property:
        print(f"Detected title property: {title_property}")
    else:
        print("Warning: No title property detected.")

    required_properties = {
        "Status": {
            "status": {
                "options": [
                    {"name": "Draft", "color": "gray"},
                    {"name": "Review", "color": "yellow"},
                    {"name": "Applied", "color": "green"},
                    {"name": "Rejected", "color": "red"},
                    {"name": "Skipped", "color": "default"}
                ]
            }
        },
        "Match Score": {
            "number": {"format": "number"}
        },
        "Freshness Days": {
            "number": {"format": "number"}
        },
        "Published At": {
            "date": {}
        },
        "Source Query": {
            "rich_text": {}
        },
        "Job Type": {
            "select": {
                "options": [
                    {"name": "Hourly", "color": "blue"},
                    {"name": "Fixed", "color": "green"},
                    {"name": "Unknown", "color": "gray"}
                ]
            }
        },
        "Budget": {
            "rich_text": {}
        },
        "Hourly Rate": {
            "rich_text": {}
        },
        "Project Length": {
            "select": {
                "options": [
                    {"name": "Less than one month", "color": "green"},
                    {"name": "1 to 3 months", "color": "blue"},
                    {"name": "More than 6 months", "color": "red"},
                    {"name": "Unknown", "color": "gray"}
                ]
            }
        },
        "Proposals": {
            "number": {"format": "number"}
        },
        "Client Spent": {
            "rich_text": {}
        },
        "Client Hires": {
            "number": {"format": "number"}
        },
        "Payment Status": {
            "select": {
                "options": [
                    {"name": "Verified", "color": "green"},
                    {"name": "Not verified", "color": "red"},
                    {"name": "Unknown", "color": "gray"}
                ]
            }
        },
        "Gig Link": {
            "url": {}
        },
        "Job ID": {
            "rich_text": {}
        },
        "AI Model": {
            "rich_text": {}
        },
        "AI Notes": {
            "rich_text": {}
        },
        "Last Seen": {
            "rich_text": {}
        }
    }

    properties_to_add = {}

    for property_name, property_schema in required_properties.items():
        if property_name not in existing_properties:
            properties_to_add[property_name] = property_schema

    if not properties_to_add:
        print("All required Notion properties already exist.")
        print("Recommended view sort:")
        print("1. Match Score descending")
        print("2. Freshness Days ascending")
        print("3. Published At descending")
        return

    print("Creating missing Notion properties:")

    for property_name in properties_to_add:
        print(f"- {property_name}")

    update_database_properties(properties_to_add)

    print("Notion database schema updated successfully.")
    print("Recommended visible columns:")
    print("Title, Status, Match Score, Freshness Days, Published At, Source Query, Job Type, Budget, Hourly Rate, Project Length, Proposals, Client Spent, Client Hires, Payment Status, Gig Link")


if __name__ == "__main__":
    main()
