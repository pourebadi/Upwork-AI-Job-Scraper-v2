import json
import os
from datetime import datetime, timezone
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_PARENT_PAGE_ID = os.getenv("NOTION_PARENT_PAGE_ID", "")
NOTION_API_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
NOTION_VIEWS_VERSION = "2026-03-11"
WORKSPACE_STATE_PATH = ".notion_workspace.json"

DATABASE_TITLES = {
    "jobs": "Jobs",
    "search_queries": "Search Queries",
    "scraper_settings": "Scraper Settings",
    "run_history": "Run History",
    "prompt_templates": "Prompt Templates",
}

DATABASE_ID_ENV_MAP = {
    "jobs": "NOTION_JOBS_DATABASE_ID",
    "search_queries": "NOTION_SEARCH_QUERIES_DATABASE_ID",
    "scraper_settings": "NOTION_SCRAPER_SETTINGS_DATABASE_ID",
    "run_history": "NOTION_RUN_HISTORY_DATABASE_ID",
    "prompt_templates": "NOTION_PROMPT_TEMPLATES_DATABASE_ID",
}

_SETTINGS_CACHE = None
_SEARCH_QUERIES_CACHE = None
_PROMPT_TEMPLATE_PAGES_CACHE = None
_PROMPT_TEMPLATE_BODY_CACHE = {}

JOBS_TABLE_VISIBLE_ORDER = [
    "Title",
    "Match Score",
    "Published At",
    "Source Query",
    "Payment Status",
    "Job Type",
    "Budget",
    "Client Hires",
    "Client Spent",
    "Proposals",
    "Hourly Rate",
    "Project Length",
    "Gig Link",
    "Job ID",
    "Last Seen",
    "Freshness Days",
    "Status",
]


def notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def notion_views_headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VIEWS_VERSION,
    }


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat()


def today_iso() -> str:
    return now_utc().date().isoformat()


def safe_text(value, limit: int = 1900) -> str:
    if value is None:
        return ""
    return str(value)[:limit]


def chunk_text(text: str, chunk_size: int = 1800) -> list[str]:
    text = text or ""
    return [text[index:index + chunk_size] for index in range(0, len(text), chunk_size)] or [""]


def title_property(text: str) -> dict:
    return {
        "title": [
            {
                "text": {
                    "content": safe_text(text, 1900)
                }
            }
        ]
    }


def rich_text_property(text: str) -> dict:
    text = safe_text(text, 1900)
    if not text:
        return {"rich_text": []}
    return {
        "rich_text": [
            {
                "text": {
                    "content": text
                }
            }
        ]
    }


def checkbox_property(value: bool) -> dict:
    return {"checkbox": bool(value)}


def number_property(value) -> dict:
    return {"number": value}


def url_property(value: str) -> dict:
    return {"url": value or None}


def select_property(value: str) -> dict:
    if not value:
        return {"select": None}
    return {"select": {"name": safe_text(value, 100)}}


def status_property(value: str) -> dict:
    if not value:
        return {"status": None}
    return {"status": {"name": safe_text(value, 100)}}


def date_property(value: str) -> dict:
    if not value:
        return {"date": None}
    return {"date": {"start": value}}


def paragraph_block(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {
                        "content": safe_text(text, 1900)
                    }
                }
            ]
        }
    }


def heading_block(text: str) -> dict:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {
                        "content": safe_text(text, 1900)
                    }
                }
            ]
        }
    }


def callout_block(text: str, emoji: str = "💬") -> dict:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {
                        "content": safe_text(text, 1900)
                    }
                }
            ],
            "icon": {"emoji": emoji},
        }
    }


def toggle_block(title: str, children: list[dict]) -> dict:
    return {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {
                        "content": safe_text(title, 1900)
                    }
                }
            ],
            "children": children,
        },
    }


def divider_block() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def blocks_from_text(text: str) -> list[dict]:
    blocks = []
    for chunk in chunk_text(text):
        if chunk.strip():
            blocks.append(paragraph_block(chunk))
    return blocks or [paragraph_block("")]


def load_workspace_state() -> dict:
    if not os.path.exists(WORKSPACE_STATE_PATH):
        return {}

    try:
        with open(WORKSPACE_STATE_PATH, "r", encoding="utf-8") as file:
            data = json.load(file)
            if isinstance(data, dict):
                return data
    except Exception:
        pass

    return {}


def save_workspace_state(state: dict):
    with open(WORKSPACE_STATE_PATH, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)


def notion_get(path: str, **kwargs) -> dict:
    response = requests.get(
        f"{NOTION_API_URL}{path}",
        headers=notion_headers(),
        timeout=30,
        **kwargs,
    )
    response.raise_for_status()
    return response.json()


def notion_post(path: str, payload: Optional[dict] = None, **kwargs) -> dict:
    response = requests.post(
        f"{NOTION_API_URL}{path}",
        headers=notion_headers(),
        json=payload or {},
        timeout=30,
        **kwargs,
    )
    response.raise_for_status()
    return response.json()


def notion_patch(path: str, payload: Optional[dict] = None, **kwargs) -> dict:
    response = requests.patch(
        f"{NOTION_API_URL}{path}",
        headers=notion_headers(),
        json=payload or {},
        timeout=30,
        **kwargs,
    )
    response.raise_for_status()
    return response.json()


def notion_views_get(path: str, params: Optional[dict] = None) -> dict:
    response = requests.get(
        f"{NOTION_API_URL}{path}",
        headers=notion_views_headers(),
        params=params or {},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def notion_views_patch(path: str, payload: Optional[dict] = None) -> dict:
    response = requests.patch(
        f"{NOTION_API_URL}{path}",
        headers=notion_views_headers(),
        json=payload or {},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def notion_views_post(path: str, payload: Optional[dict] = None) -> dict:
    response = requests.post(
        f"{NOTION_API_URL}{path}",
        headers=notion_views_headers(),
        json=payload or {},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def search_databases_by_title(title: str) -> list[dict]:
    results = []
    cursor = None

    while True:
        payload = {
            "query": title,
            "filter": {"value": "database", "property": "object"},
            "page_size": 100,
        }
        if cursor:
            payload["start_cursor"] = cursor

        data = notion_post("/search", payload)
        results.extend(data.get("results", []))

        if not data.get("has_more"):
            break

        cursor = data.get("next_cursor")

    return results


def get_database_title(database: dict) -> str:
    parts = database.get("title", [])
    return "".join(part.get("plain_text", "") for part in parts).strip()


def find_database_under_parent(parent_page_id: str, title: str) -> Optional[dict]:
    for database in search_databases_by_title(title):
        if get_database_title(database) != title:
            continue

        parent = database.get("parent", {})
        if parent.get("type") == "page_id" and parent.get("page_id") == parent_page_id:
            return database

    return None


def get_database(database_id: str) -> dict:
    return notion_get(f"/databases/{database_id}")


def list_database_views(database_id: str) -> list[dict]:
    results = []
    cursor = None

    while True:
        params = {
            "database_id": database_id,
            "page_size": 100,
        }
        if cursor:
            params["start_cursor"] = cursor

        data = notion_views_get("/views", params=params)
        results.extend(data.get("results", []))

        if not data.get("has_more"):
            break

        cursor = data.get("next_cursor")

    return results


def retrieve_view(view_id: str) -> dict:
    return notion_views_get(f"/views/{view_id}")


def update_view(view_id: str, payload: dict) -> dict:
    return notion_views_patch(f"/views/{view_id}", payload)


def create_view(payload: dict) -> dict:
    return notion_views_post("/views", payload)


def patch_database_properties(database_id: str, properties: dict):
    notion_patch(f"/databases/{database_id}", {"properties": properties})


def create_database(parent_page_id: str, title: str, properties: dict) -> dict:
    payload = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": title}}],
        "properties": properties,
    }
    return notion_post("/databases", payload)


def ensure_database(parent_page_id: str, key: str, properties: dict) -> str:
    title = DATABASE_TITLES[key]
    existing = find_database_under_parent(parent_page_id, title)

    if existing:
        existing_properties = existing.get("properties", {})
        missing = {
            name: schema
            for name, schema in properties.items()
            if name not in existing_properties
        }
        if missing:
            patch_database_properties(existing["id"], missing)
        return existing["id"]

    created = create_database(parent_page_id, title, properties)
    return created["id"]


def query_database(database_id: str, payload: Optional[dict] = None) -> list[dict]:
    payload = payload.copy() if payload else {}
    payload.setdefault("page_size", 100)

    results = []
    cursor = None

    while True:
        current_payload = payload.copy()
        if cursor:
            current_payload["start_cursor"] = cursor

        data = notion_post(f"/databases/{database_id}/query", current_payload)
        results.extend(data.get("results", []))

        if not data.get("has_more"):
            break

        cursor = data.get("next_cursor")

    return results


def create_page(database_id: str, properties: dict, children: Optional[list[dict]] = None) -> dict:
    payload = {
        "parent": {"database_id": database_id},
        "properties": properties,
    }
    if children:
        payload["children"] = children
    return notion_post("/pages", payload)


def update_page(page_id: str, properties: dict) -> dict:
    return notion_patch(f"/pages/{page_id}", {"properties": properties})


def append_block_children(block_id: str, children: list[dict]) -> dict:
    return notion_patch(f"/blocks/{block_id}/children", {"children": children})


def list_block_children(block_id: str) -> list[dict]:
    results = []
    cursor = None

    while True:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor

        data = notion_get(f"/blocks/{block_id}/children", params=params)
        results.extend(data.get("results", []))

        if not data.get("has_more"):
            break

        cursor = data.get("next_cursor")

    return results


def find_page_by_title(database_id: str, title: str) -> Optional[dict]:
    pages = query_database(database_id)
    for page in pages:
        if get_page_title(page) == title:
            return page
    return None


def get_page_title(page: dict) -> str:
    for property_value in page.get("properties", {}).values():
        if property_value.get("type") == "title":
            return "".join(item.get("plain_text", "") for item in property_value.get("title", [])).strip()
    return ""


def get_plain_text_property(page: dict, property_name: str) -> str:
    property_value = page.get("properties", {}).get(property_name, {})
    property_type = property_value.get("type")

    if property_type == "title":
        return "".join(item.get("plain_text", "") for item in property_value.get("title", [])).strip()

    if property_type == "rich_text":
        return "".join(item.get("plain_text", "") for item in property_value.get("rich_text", [])).strip()

    if property_type == "select":
        return (property_value.get("select") or {}).get("name", "")

    if property_type == "status":
        return (property_value.get("status") or {}).get("name", "")

    if property_type == "url":
        return property_value.get("url") or ""

    if property_type == "checkbox":
        return "true" if property_value.get("checkbox") else "false"

    if property_type == "date":
        return (property_value.get("date") or {}).get("start", "")

    if property_type == "number":
        number = property_value.get("number")
        return "" if number is None else str(number)

    return ""


def get_number_property(page: dict, property_name: str, default=None):
    value = page.get("properties", {}).get(property_name, {}).get("number")
    return default if value is None else value


def get_checkbox_property(page: dict, property_name: str, default: bool = False) -> bool:
    value = page.get("properties", {}).get(property_name, {}).get("checkbox")
    return default if value is None else bool(value)


def get_database_ids(refresh: bool = False) -> dict:
    ids = {}
    state = {} if refresh else load_workspace_state()

    for key, env_name in DATABASE_ID_ENV_MAP.items():
        if os.getenv(env_name):
            ids[key] = os.getenv(env_name, "")
        elif not refresh and state.get(key):
            ids[key] = state[key]

    if len(ids) == len(DATABASE_TITLES) or not NOTION_PARENT_PAGE_ID:
        return ids

    for key, title in DATABASE_TITLES.items():
        if ids.get(key):
            continue
        database = find_database_under_parent(NOTION_PARENT_PAGE_ID, title)
        if database:
            ids[key] = database["id"]

    if ids:
        save_workspace_state(ids)

    return ids


def require_database_id(key: str) -> str:
    ids = get_database_ids()
    database_id = ids.get(key, "")
    if not database_id:
        env_name = DATABASE_ID_ENV_MAP[key]
        raise RuntimeError(
            f"Missing database id for '{key}'. Run setup_notion_workspace.py or set {env_name}."
        )
    return database_id


def get_jobs_database_id() -> str:
    legacy = os.getenv("NOTION_DATABASE_ID", "")
    if legacy:
        return legacy
    return require_database_id("jobs")


def build_jobs_table_view_configuration(database: dict) -> dict:
    properties = database.get("properties", {})
    ordered_names = []
    seen = set()

    for name in JOBS_TABLE_VISIBLE_ORDER:
        if name in properties:
            ordered_names.append(name)
            seen.add(name)

    for name in properties.keys():
        if name not in seen:
            ordered_names.append(name)

    property_config = []
    for name in ordered_names:
        property_config.append(
            {
                "property_id": name,
                "visible": name in JOBS_TABLE_VISIBLE_ORDER,
            }
        )

    return {
        "type": "table",
        "properties": property_config,
    }


def build_jobs_table_view_sorts() -> list[dict]:
    return [
        {"property": "Match Score", "direction": "descending"},
        {"property": "Published At", "direction": "descending"},
    ]


def build_jobs_named_view_specs() -> list[dict]:
    return [
        {
            "name": "Jobs Table",
            "filter": None,
            "sorts": build_jobs_table_view_sorts(),
        },
        {
            "name": "Today",
            "filter": {
                "property": "Discovered Day",
                "date": {"equals": "today"},
            },
            "sorts": build_jobs_table_view_sorts(),
        },
        {
            "name": "Approved",
            "filter": {
                "property": "Manager Review",
                "status": {"equals": "Approved"},
            },
            "sorts": build_jobs_table_view_sorts(),
        },
        {
            "name": "Proposal Ready",
            "filter": {
                "property": "Proposal Status",
                "status": {"equals": "Ready"},
            },
            "sorts": build_jobs_table_view_sorts(),
        },
    ]


def configure_jobs_table_view(database_id: str):
    database = get_database(database_id)
    views = list_database_views(database_id)

    if not views:
        return

    detailed_views = []
    for view_ref in views:
        view = retrieve_view(view_ref["id"])
        detailed_views.append(view)

    table_views = [view for view in detailed_views if view.get("type") == "table"]
    if not table_views:
        return

    configuration = build_jobs_table_view_configuration(database)
    data_source_id = table_views[0].get("data_source_id")

    for spec in build_jobs_named_view_specs():
        existing = next((view for view in table_views if view.get("name") == spec["name"]), None)
        payload = {
            "name": spec["name"],
            "filter": spec["filter"],
            "sorts": spec["sorts"],
            "configuration": configuration,
        }

        if existing:
            update_view(existing["id"], payload)
            continue

        if not data_source_id:
            continue

        create_view(
            {
                "database_id": database_id,
                "data_source_id": data_source_id,
                "name": spec["name"],
                "type": "table",
                "filter": spec["filter"],
                "sorts": spec["sorts"],
                "configuration": configuration,
            }
        )


def extract_plain_text_from_block(block: dict) -> str:
    block_type = block.get("type", "")
    block_data = block.get(block_type, {})
    texts = block_data.get("rich_text", [])
    return "".join(item.get("plain_text", "") for item in texts).strip()


def collect_block_text(block_id: str) -> str:
    parts = []
    for block in list_block_children(block_id):
        text = extract_plain_text_from_block(block)
        if text:
            parts.append(text)
        if block.get("has_children"):
            child_text = collect_block_text(block["id"])
            if child_text:
                parts.append(child_text)
    return "\n".join(part for part in parts if part).strip()


def get_template_body(page_id: str) -> str:
    if page_id in _PROMPT_TEMPLATE_BODY_CACHE:
        return _PROMPT_TEMPLATE_BODY_CACHE[page_id]

    body = collect_block_text(page_id).strip()
    _PROMPT_TEMPLATE_BODY_CACHE[page_id] = body
    return body


def build_jobs_schema() -> dict:
    return {
        "Title": {"title": {}},
        "Status": {
            "status": {
                "options": [
                    {"name": "Draft", "color": "gray"},
                    {"name": "Review", "color": "yellow"},
                    {"name": "Applied", "color": "green"},
                    {"name": "Rejected", "color": "red"},
                    {"name": "Skipped", "color": "default"},
                ]
            }
        },
        "Manager Review": {
            "status": {
                "options": [
                    {"name": "New", "color": "gray"},
                    {"name": "Approved", "color": "green"},
                    {"name": "Rejected", "color": "red"},
                ]
            }
        },
        "Proposal Status": {
            "status": {
                "options": [
                    {"name": "Not Requested", "color": "gray"},
                    {"name": "Requested", "color": "yellow"},
                    {"name": "Generating", "color": "blue"},
                    {"name": "Ready", "color": "green"},
                    {"name": "Failed", "color": "red"},
                ]
            }
        },
        "Match Score": {"number": {"format": "number"}},
        "Freshness Days": {"number": {"format": "number"}},
        "Published At": {"date": {}},
        "Discovered At": {"date": {}},
        "Discovered Day": {"date": {}},
        "Proposal Requested At": {"date": {}},
        "Proposal Generated At": {"date": {}},
        "Source Query": {"rich_text": {}},
        "Job Type": {
            "select": {
                "options": [
                    {"name": "Hourly", "color": "blue"},
                    {"name": "Fixed", "color": "green"},
                    {"name": "Unknown", "color": "gray"},
                ]
            }
        },
        "Budget": {"rich_text": {}},
        "Hourly Rate": {"rich_text": {}},
        "Project Length": {
            "select": {
                "options": [
                    {"name": "Less than one month", "color": "green"},
                    {"name": "1 to 3 months", "color": "blue"},
                    {"name": "More than 6 months", "color": "red"},
                    {"name": "Unknown", "color": "gray"},
                ]
            }
        },
        "Proposals": {"number": {"format": "number"}},
        "Client Spent": {"rich_text": {}},
        "Client Hires": {"number": {"format": "number"}},
        "Payment Status": {
            "select": {
                "options": [
                    {"name": "Verified", "color": "green"},
                    {"name": "Not verified", "color": "red"},
                    {"name": "Unknown", "color": "gray"},
                ]
            }
        },
        "Gig Link": {"url": {}},
        "Job ID": {"rich_text": {}},
        "Skills": {"rich_text": {}},
        "Category": {"rich_text": {}},
        "Category Group": {"rich_text": {}},
        "Job Summary": {"rich_text": {}},
        "Proposal Preview": {"rich_text": {}},
        "Prompt Template": {"rich_text": {}},
        "AI Model": {"rich_text": {}},
        "AI Notes": {"rich_text": {}},
        "Proposal Error": {"rich_text": {}},
        "Last Seen": {"rich_text": {}},
    }


def build_search_queries_schema() -> dict:
    return {
        "Query": {"title": {}},
        "Enabled": {"checkbox": {}},
        "Results Per Page": {"number": {"format": "number"}},
        "Min Budget": {"number": {"format": "number"}},
        "Max Budget": {"number": {"format": "number"}},
        "Max Age Days": {"number": {"format": "number"}},
        "Category": {"select": {"options": []}},
        "Job Type": {
            "select": {
                "options": [
                    {"name": "Any", "color": "default"},
                    {"name": "Hourly", "color": "blue"},
                    {"name": "Fixed", "color": "green"},
                ]
            }
        },
        "Experience Level": {
            "select": {
                "options": [
                    {"name": "Any", "color": "default"},
                    {"name": "Entry", "color": "green"},
                    {"name": "Intermediate", "color": "yellow"},
                    {"name": "Expert", "color": "red"},
                ]
            }
        },
        "Locations": {"rich_text": {}},
        "Notes": {"rich_text": {}},
    }


def build_scraper_settings_schema() -> dict:
    return {
        "Setting": {"title": {}},
        "Value": {"rich_text": {}},
        "Type": {
            "select": {
                "options": [
                    {"name": "string", "color": "default"},
                    {"name": "int", "color": "blue"},
                    {"name": "float", "color": "yellow"},
                    {"name": "bool", "color": "green"},
                ]
            }
        },
        "Enabled": {"checkbox": {}},
        "Description": {"rich_text": {}},
    }


def build_prompt_templates_schema() -> dict:
    return {
        "Template Name": {"title": {}},
        "Enabled": {"checkbox": {}},
        "Template Key": {"rich_text": {}},
        "Notes": {"rich_text": {}},
    }


def build_run_history_schema() -> dict:
    return {
        "Run Name": {"title": {}},
        "Run Type": {
            "select": {
                "options": [
                    {"name": "Scraper", "color": "blue"},
                    {"name": "Proposal Generator", "color": "green"},
                    {"name": "Setup", "color": "yellow"},
                ]
            }
        },
        "Started At": {"date": {}},
        "Finished At": {"date": {}},
        "Status": {
            "status": {
                "options": [
                    {"name": "Started", "color": "yellow"},
                    {"name": "Success", "color": "green"},
                    {"name": "Failed", "color": "red"},
                ]
            }
        },
        "Jobs Scraped": {"number": {"format": "number"}},
        "Jobs Added": {"number": {"format": "number"}},
        "Duplicates": {"number": {"format": "number"}},
        "Rejected": {"number": {"format": "number"}},
        "Proposals Generated": {"number": {"format": "number"}},
        "Error Message": {"rich_text": {}},
        "GitHub Run URL": {"url": {}},
    }


def get_default_search_rows() -> list[dict]:
    from config import SEARCH_CONFIGS

    rows = []
    for item in SEARCH_CONFIGS:
        query = item.get("query", "")
        rows.append(
            {
                "properties": {
                    "Query": title_property(query),
                    "Enabled": checkbox_property(True),
                    "Results Per Page": number_property(item.get("results_per_page", 5)),
                    "Min Budget": number_property(item.get("fixed_budget_min")),
                    "Max Budget": number_property(item.get("fixed_budget_max")),
                    "Max Age Days": number_property((item.get("max_job_age") or {}).get("value", 14)),
                    "Category": select_property("Primary"),
                    "Job Type": select_property("Any"),
                    "Experience Level": select_property("Any"),
                    "Locations": rich_text_property(""),
                    "Notes": rich_text_property("Seeded from config.py"),
                }
            }
        )
    return rows


def get_default_settings_rows() -> list[dict]:
    defaults = [
        ("openai_model", os.getenv("OPENAI_MODEL", "gpt-5.1"), "string", True, "Model used by proposal generator."),
        ("max_job_age_days", os.getenv("MAX_JOB_AGE_DAYS", "14"), "int", True, "Reject jobs older than this many days."),
        ("default_results_per_page", "5", "int", True, "Fallback results per page when a query row is missing a value."),
        ("require_payment_verified", "false", "bool", True, "When true, reject jobs without verified payment."),
        ("require_client_spent", "false", "bool", True, "When true, require minimum client spend."),
        ("require_client_hires", "false", "bool", True, "When true, require client hires > 0."),
        ("require_proposals_limit", "false", "bool", True, "When true, reject jobs above maximum proposals."),
        ("require_project_length", "false", "bool", True, "When true, only accept preferred project lengths."),
        ("require_budget_range", "false", "bool", True, "When true, enforce fixed budget range."),
        ("require_hourly_range", "false", "bool", True, "When true, enforce hourly range."),
        ("minimum_client_spent", "100", "int", True, "Minimum client spend threshold."),
        ("maximum_proposals", "20", "int", True, "Maximum allowed proposal count."),
        ("minimum_fixed_budget", "1000", "int", True, "Minimum fixed budget threshold."),
        ("maximum_fixed_budget", "100000", "int", True, "Maximum fixed budget threshold."),
        ("minimum_hourly_rate", "10", "int", True, "Minimum hourly rate threshold."),
        ("maximum_hourly_rate", "50", "int", True, "Maximum hourly rate threshold."),
        ("default_prompt_template", "default-proposal-template", "string", True, "Template key used when a job does not specify another template."),
        ("proposal_prompt_mode", "lean", "string", True, "Proposal prompt mode: lean or full."),
        ("proposal_max_description_chars", "3500", "int", True, "Maximum job description characters sent to the model."),
        ("proposal_max_template_chars", "2200", "int", True, "Maximum template characters sent when full mode is used."),
    ]

    rows = []
    for name, value, value_type, enabled, description in defaults:
        rows.append(
            {
                "properties": {
                    "Setting": title_property(name),
                    "Value": rich_text_property(str(value)),
                    "Type": select_property(value_type),
                    "Enabled": checkbox_property(enabled),
                    "Description": rich_text_property(description),
                }
            }
        )
    return rows


def get_default_prompt_templates() -> list[dict]:
    content = ""
    if os.path.exists("proposal_template.md"):
        with open("proposal_template.md", "r", encoding="utf-8") as file:
            content = file.read()

    return [
        {
            "properties": {
                "Template Name": title_property("Default Proposal Template"),
                "Enabled": checkbox_property(True),
                "Template Key": rich_text_property("default-proposal-template"),
                "Notes": rich_text_property("Seeded from proposal_template.md"),
            },
            "children": blocks_from_text(content),
        }
    ]


def ensure_seed_rows(database_id: str, rows: list[dict], title_property_name: str):
    existing_titles = {get_page_title(page) for page in query_database(database_id)}
    for row in rows:
        title = "".join(
            item.get("plain_text", "")
            for item in row["properties"][title_property_name].get("title", [])
        ).strip()
        if title in existing_titles:
            continue
        create_page(database_id, row["properties"], row.get("children"))


def record_run_history(
    run_type: str,
    status: str,
    started_at: str,
    finished_at: str,
    jobs_scraped: int = 0,
    jobs_added: int = 0,
    duplicates: int = 0,
    rejected: int = 0,
    proposals_generated: int = 0,
    error_message: str = "",
):
    try:
        run_history_database_id = require_database_id("run_history")
    except Exception:
        return

    github_run_url = os.getenv("GITHUB_SERVER_URL", "").strip()
    if github_run_url and os.getenv("GITHUB_REPOSITORY") and os.getenv("GITHUB_RUN_ID"):
        github_run_url = (
            f"{os.getenv('GITHUB_SERVER_URL')}/{os.getenv('GITHUB_REPOSITORY')}"
            f"/actions/runs/{os.getenv('GITHUB_RUN_ID')}"
        )
    else:
        github_run_url = ""

    run_name = f"{run_type} {started_at[:19].replace('T', ' ')}"

    properties = {
        "Run Name": title_property(run_name),
        "Run Type": select_property(run_type),
        "Started At": date_property(started_at),
        "Finished At": date_property(finished_at),
        "Status": status_property(status),
        "Jobs Scraped": number_property(jobs_scraped),
        "Jobs Added": number_property(jobs_added),
        "Duplicates": number_property(duplicates),
        "Rejected": number_property(rejected),
        "Proposals Generated": number_property(proposals_generated),
        "Error Message": rich_text_property(error_message),
        "GitHub Run URL": url_property(github_run_url),
    }
    create_page(run_history_database_id, properties)


def load_scraper_settings(refresh: bool = False) -> dict:
    global _SETTINGS_CACHE

    if _SETTINGS_CACHE is not None and not refresh:
        return dict(_SETTINGS_CACHE)

    settings_database_id = require_database_id("scraper_settings")
    rows = query_database(settings_database_id)
    settings = {}

    for row in rows:
        if not get_checkbox_property(row, "Enabled", True):
            continue

        key = get_page_title(row)
        value = get_plain_text_property(row, "Value")
        value_type = get_plain_text_property(row, "Type") or "string"

        if value_type == "bool":
            settings[key] = value.strip().lower() in {"1", "true", "yes", "on"}
        elif value_type == "int":
            settings[key] = int(float(value or 0))
        elif value_type == "float":
            settings[key] = float(value or 0)
        else:
            settings[key] = value

    _SETTINGS_CACHE = dict(settings)
    return settings


def load_search_queries(refresh: bool = False) -> list[dict]:
    global _SEARCH_QUERIES_CACHE

    if _SEARCH_QUERIES_CACHE is not None and not refresh:
        return [dict(item) for item in _SEARCH_QUERIES_CACHE]

    queries_database_id = require_database_id("search_queries")
    rows = query_database(queries_database_id)
    configs = []

    for row in rows:
        if not get_checkbox_property(row, "Enabled", True):
            continue

        query = get_page_title(row)
        if not query:
            continue

        max_age_days = int(get_number_property(row, "Max Age Days", 14) or 14)
        locations_text = get_plain_text_property(row, "Locations")
        locations = [item.strip() for item in locations_text.split(",") if item.strip()]
        job_type = get_plain_text_property(row, "Job Type")
        experience_level = get_plain_text_property(row, "Experience Level")

        config = {
            "query": query,
            "results_per_page": int(get_number_property(row, "Results Per Page", 5) or 5),
            "fixed_budget_min": get_number_property(row, "Min Budget"),
            "fixed_budget_max": get_number_property(row, "Max Budget"),
            "max_job_age": {"value": max_age_days, "unit": "days"},
        }

        if locations:
            config["locations"] = locations
        if job_type and job_type != "Any":
            config["job_type"] = job_type.lower()
        if experience_level and experience_level != "Any":
            config["experience_level"] = experience_level.lower()

        configs.append(config)

    _SEARCH_QUERIES_CACHE = [dict(item) for item in configs]
    return configs


def get_prompt_template_pages(refresh: bool = False) -> list[dict]:
    global _PROMPT_TEMPLATE_PAGES_CACHE

    if _PROMPT_TEMPLATE_PAGES_CACHE is not None and not refresh:
        return list(_PROMPT_TEMPLATE_PAGES_CACHE)

    templates_database_id = require_database_id("prompt_templates")
    rows = query_database(templates_database_id)
    enabled_rows = [row for row in rows if get_checkbox_property(row, "Enabled", True)]
    _PROMPT_TEMPLATE_PAGES_CACHE = list(enabled_rows)
    return enabled_rows


def find_prompt_template_page(identifier: str = "", refresh: bool = False) -> Optional[dict]:
    enabled_rows = get_prompt_template_pages(refresh=refresh)

    if identifier:
        for row in enabled_rows:
            if identifier in {
                get_page_title(row),
                get_plain_text_property(row, "Template Key"),
            }:
                return row

    for row in enabled_rows:
        if get_plain_text_property(row, "Template Key") == "default-proposal-template":
            return row

    return enabled_rows[0] if enabled_rows else None


def get_default_prompt_template_page() -> Optional[dict]:
    return find_prompt_template_page()
