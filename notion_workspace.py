import json
import os
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_PARENT_PAGE_ID = os.getenv("NOTION_PARENT_PAGE_ID", "")
WEBHOOK_PUBLIC_BASE_URL = os.getenv("WEBHOOK_PUBLIC_BASE_URL", "").strip().rstrip("/")
WEBHOOK_SHARED_SECRET = os.getenv("WEBHOOK_SHARED_SECRET", "").strip()
NOTION_LOCAL_TIMEZONE = os.getenv("NOTION_LOCAL_TIMEZONE", os.getenv("TZ", "UTC")).strip() or "UTC"
NOTION_API_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
NOTION_VIEWS_VERSION = "2026-03-11"
WORKSPACE_STATE_PATH = ".notion_workspace.json"
KNOWLEDGE_BASE_PAGE_TITLE = "راهنمای فارسی سیستم جذب و مدیریت جاب"

DATABASE_TITLES = {
    "jobs": "Jobs",
    "automation_control": "Automation Control",
    "search_queries": "Search Queries",
    "scraper_settings": "Scraper Settings",
    "run_history": "Run History",
    "prompt_templates": "Prompt Templates",
}

DATABASE_ID_ENV_MAP = {
    "jobs": "NOTION_JOBS_DATABASE_ID",
    "automation_control": "NOTION_AUTOMATION_CONTROL_DATABASE_ID",
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

JOBS_REVIEW_VISIBLE_ORDER = [
    "Title",
    "Generate Proposal",
    "Manager Review",
    "Proposal Status",
    "Status",
    "Match Score",
    "Discovered Day",
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
]

JOBS_TABLE_HIDDEN_PROPERTIES = {
    "Generate Proposal Now",
    "AI Model",
    "AI Notes",
    "Job ID",
    "Job Summary",
    "Prompt Template",
    "Proposal Error",
    "Proposal Preview",
    "Proposal Requested At",
}


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


def get_local_timezone():
    try:
        return ZoneInfo(NOTION_LOCAL_TIMEZONE)
    except Exception:
        return timezone.utc


def now_local() -> datetime:
    return now_utc().astimezone(get_local_timezone())


def now_iso() -> str:
    return now_utc().isoformat()


def today_iso() -> str:
    return now_utc().date().isoformat()


def local_today_iso() -> str:
    return now_local().date().isoformat()


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


def rich_text_link_property(text: str, url: str) -> dict:
    text = safe_text(text, 1900)
    if not text or not url:
        return {"rich_text": []}
    return {
        "rich_text": [
            {
                "text": {
                    "content": text,
                    "link": {"url": url},
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


def notion_delete(path: str, **kwargs) -> dict:
    response = requests.delete(
        f"{NOTION_API_URL}{path}",
        headers=notion_headers(),
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


def notion_views_delete(path: str) -> dict:
    response = requests.delete(
        f"{NOTION_API_URL}{path}",
        headers=notion_views_headers(),
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


def search_pages_by_title(title: str) -> list[dict]:
    results = []
    cursor = None

    while True:
        payload = {
            "query": title,
            "filter": {"value": "page", "property": "object"},
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


def find_page_under_parent(parent_page_id: str, title: str) -> Optional[dict]:
    for page in search_pages_by_title(title):
        if get_page_title(page) != title:
            continue

        parent = page.get("parent", {})
        if parent.get("type") == "page_id" and parent.get("page_id") == parent_page_id:
            return page

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


def delete_view(view_id: str) -> dict:
    return notion_views_delete(f"/views/{view_id}")


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


def create_child_page(parent_page_id: str, title: str, children: Optional[list[dict]] = None) -> dict:
    payload = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "properties": {
            "title": title_property(title),
        },
    }
    if children:
        payload["children"] = children
    return notion_post("/pages", payload)


def update_page(page_id: str, properties: dict) -> dict:
    return notion_patch(f"/pages/{page_id}", {"properties": properties})


def append_block_children(block_id: str, children: list[dict]) -> dict:
    return notion_patch(f"/blocks/{block_id}/children", {"children": children})


def insert_block_children_after(block_id: str, after_block_id: str, children: list[dict]) -> dict:
    return notion_patch(
        f"/blocks/{block_id}/children",
        {
            "after": after_block_id,
            "children": children,
        },
    )


def delete_block(block_id: str) -> dict:
    return notion_delete(f"/blocks/{block_id}")


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


def replace_page_children(page_id: str, children: list[dict]):
    for block in list_block_children(page_id):
        delete_block(block["id"])
    if children:
        append_block_children(page_id, children)


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


def get_primary_automation_control_row() -> Optional[dict]:
    try:
        database_id = get_automation_control_database_id()
    except Exception:
        return None

    row = find_page_by_title(database_id, "Primary Control")
    if row:
        return row

    rows = query_database(database_id)
    return rows[0] if rows else None


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


def get_automation_control_database_id() -> str:
    return require_database_id("automation_control")


def build_jobs_table_view_configuration(database: dict, visible_order: Optional[list[str]] = None) -> dict:
    properties = database.get("properties", {})
    visible_order = visible_order or JOBS_TABLE_VISIBLE_ORDER
    ordered_names = []
    seen = set()

    for name in visible_order:
        if name in properties:
            ordered_names.append(name)
            seen.add(name)

    for name in properties.keys():
        if name not in seen:
            ordered_names.append(name)

    property_config = []
    for name in ordered_names:
        is_visible = (
            name in visible_order
            and name not in JOBS_TABLE_HIDDEN_PROPERTIES
        )
        property_config.append(
            {
                "property_id": name,
                "visible": is_visible,
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
    needs_review_filter = {
        "property": "Manager Review",
        "status": {"equals": "New"},
    }
    approved_filter = {
        "property": "Manager Review",
        "status": {"equals": "Approved"},
    }
    rejected_filter = {
        "or": [
            {"property": "Manager Review", "status": {"equals": "Rejected"}},
            {"property": "Status", "status": {"equals": "Rejected"}},
            {"property": "Status", "status": {"equals": "Skipped"}},
        ]
    }
    proposal_not_requested_filter = {
        "property": "Proposal Status",
        "status": {"equals": "Not Requested"},
    }
    today_review_filter = {
        "and": [
            {"property": "Discovered Day", "date": {"equals": "today"}},
            needs_review_filter,
        ]
    }
    yesterday_review_filter = {
        "and": [
            {"property": "Discovered Day", "date": {"equals": "yesterday"}},
            needs_review_filter,
        ]
    }
    older_this_week_review_filter = {
        "and": [
            {"property": "Discovered Day", "date": {"before": "yesterday"}},
            {"property": "Discovered Day", "date": {"on_or_after": "one_week_ago"}},
            needs_review_filter,
        ]
    }
    week_review_filter = {
        "and": [
            {"property": "Discovered Day", "date": {"past_week": {}}},
            needs_review_filter,
        ]
    }

    return [
        {
            "name": "01 Today",
            "visible_order": JOBS_REVIEW_VISIBLE_ORDER,
            "filter": today_review_filter,
            "sorts": build_jobs_table_view_sorts(),
        },
        {
            "name": "02 Yesterday",
            "visible_order": JOBS_REVIEW_VISIBLE_ORDER,
            "filter": yesterday_review_filter,
            "sorts": build_jobs_table_view_sorts(),
        },
        {
            "name": "03 Older",
            "visible_order": JOBS_REVIEW_VISIBLE_ORDER,
            "filter": older_this_week_review_filter,
            "sorts": [
                {"property": "Discovered Day", "direction": "descending"},
                *build_jobs_table_view_sorts(),
            ],
        },
        {
            "name": "04 Review",
            "visible_order": JOBS_REVIEW_VISIBLE_ORDER,
            "filter": needs_review_filter,
            "sorts": [
                {"property": "Discovered Day", "direction": "descending"},
                *build_jobs_table_view_sorts(),
            ],
        },
        {
            "name": "05 Week",
            "visible_order": JOBS_REVIEW_VISIBLE_ORDER,
            "filter": week_review_filter,
            "sorts": [
                {"property": "Discovered Day", "direction": "descending"},
                *build_jobs_table_view_sorts(),
            ],
        },
        {
            "name": "06 Proposal",
            "visible_order": JOBS_REVIEW_VISIBLE_ORDER,
            "filter": {
                "and": [
                    approved_filter,
                    proposal_not_requested_filter,
                ]
            },
            "sorts": build_jobs_table_view_sorts(),
        },
        {
            "name": "07 Ready",
            "visible_order": JOBS_REVIEW_VISIBLE_ORDER,
            "filter": {
                "property": "Proposal Status",
                "status": {"equals": "Ready"},
            },
            "sorts": [
                {"property": "Proposal Generated At", "direction": "descending"},
                *build_jobs_table_view_sorts(),
            ],
        },
        {
            "name": "08 Applied",
            "visible_order": JOBS_REVIEW_VISIBLE_ORDER,
            "filter": {
                "property": "Status",
                "status": {"equals": "Applied"},
            },
            "sorts": [
                {"property": "Proposal Generated At", "direction": "descending"},
                *build_jobs_table_view_sorts(),
            ],
        },
        {
            "name": "09 Archive",
            "filter": rejected_filter,
            "sorts": [
                {"property": "Discovered Day", "direction": "descending"},
                *build_jobs_table_view_sorts(),
            ],
        },
        {
            "name": "10 All",
            "filter": None,
            "sorts": [
                {"property": "Discovered Day", "direction": "descending"},
                *build_jobs_table_view_sorts(),
            ],
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

    data_source_id = table_views[0].get("data_source_id")
    available_table_views = list(table_views)
    claimed_view_ids = set()

    for spec in build_jobs_named_view_specs():
        existing = next((view for view in table_views if view.get("name") == spec["name"]), None)
        target_view = existing

        if existing:
            claimed_view_ids.add(existing["id"])
            available_table_views = [
                view for view in available_table_views
                if view["id"] not in claimed_view_ids
            ]

        if target_view is None and available_table_views:
            target_view = available_table_views.pop(0)
            claimed_view_ids.add(target_view["id"])

        configuration = build_jobs_table_view_configuration(
            database,
            spec.get("visible_order"),
        )
        payload = {
            "name": spec["name"],
            "filter": spec["filter"],
            "sorts": spec["sorts"],
            "configuration": configuration,
        }

        if target_view:
            update_view(target_view["id"], payload)
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

    remaining_table_views = [
        view for view in available_table_views
        if view["id"] not in claimed_view_ids
    ]

    for view in remaining_table_views:
        try:
            delete_view(view["id"])
        except Exception:
            continue


SCRAPER_SETTINGS_TABLE_VISIBLE_ORDER = [
    "Setting",
    "Value",
    "Type",
    "Enabled",
    "Description",
]

SCRAPER_SETTINGS_TABLE_HIDDEN_PROPERTIES = {
    "Setting Key",
}

AUTOMATION_CONTROL_VISIBLE_ORDER = [
    "Control",
    "Fetch New Jobs",
    "Fetch Status",
    "Last Fetch At",
    "Help",
]


def build_scraper_settings_table_view_configuration(database: dict) -> dict:
    properties = database.get("properties", {})
    ordered_names = []
    seen = set()

    for name in SCRAPER_SETTINGS_TABLE_VISIBLE_ORDER:
        if name in properties:
            ordered_names.append(name)
            seen.add(name)

    for name in properties.keys():
        if name not in seen:
            ordered_names.append(name)

    property_config = []
    for name in ordered_names:
        is_visible = (
            name in SCRAPER_SETTINGS_TABLE_VISIBLE_ORDER
            and name not in SCRAPER_SETTINGS_TABLE_HIDDEN_PROPERTIES
        )
        property_config.append(
            {
                "property_id": name,
                "visible": is_visible,
            }
        )

    return {
        "type": "table",
        "properties": property_config,
    }


def configure_scraper_settings_table_view(database_id: str):
    database = get_database(database_id)
    views = list_database_views(database_id)

    if not views:
        return

    detailed_views = [retrieve_view(view_ref["id"]) for view_ref in views]
    table_views = [view for view in detailed_views if view.get("type") == "table"]
    if not table_views:
        return

    configuration = build_scraper_settings_table_view_configuration(database)
    payload = {
        "name": "Settings",
        "configuration": configuration,
    }

    update_view(table_views[0]["id"], payload)


def build_automation_control_table_view_configuration(database: dict) -> dict:
    properties = database.get("properties", {})
    ordered_names = []
    seen = set()

    for name in AUTOMATION_CONTROL_VISIBLE_ORDER:
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
                "visible": name in AUTOMATION_CONTROL_VISIBLE_ORDER,
            }
        )

    return {
        "type": "table",
        "properties": property_config,
    }


def configure_automation_control_table_view(database_id: str):
    database = get_database(database_id)
    views = list_database_views(database_id)

    if not views:
        return

    detailed_views = [retrieve_view(view_ref["id"]) for view_ref in views]
    table_views = [view for view in detailed_views if view.get("type") == "table"]
    if not table_views:
        return

    payload = {
        "name": "Control Panel",
        "configuration": build_automation_control_table_view_configuration(database),
    }

    update_view(table_views[0]["id"], payload)


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
        "Generate Proposal": {"checkbox": {}},
        "Generate Proposal Now": {"url": {}},
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


def build_automation_control_schema() -> dict:
    return {
        "Control": {"title": {}},
        "Fetch New Jobs": {"checkbox": {}},
        "Fetch Status": {
            "status": {
                "options": [
                    {"name": "Idle", "color": "gray"},
                    {"name": "Running", "color": "blue"},
                    {"name": "Success", "color": "green"},
                    {"name": "Failed", "color": "red"},
                ]
            }
        },
        "Last Fetch At": {"date": {}},
        "Help": {"rich_text": {}},
        "Run Scraper Now": {"checkbox": {}},
        "Run Scraper Link": {"url": {}},
        "Refresh Workspace Now": {"checkbox": {}},
        "Refresh Workspace Link": {"url": {}},
        "Last Action": {"rich_text": {}},
        "Last Result": {
            "status": {
                "options": [
                    {"name": "Idle", "color": "gray"},
                    {"name": "Running", "color": "blue"},
                    {"name": "Success", "color": "green"},
                    {"name": "Failed", "color": "red"},
                ]
            }
        },
        "Last Message": {"rich_text": {}},
        "Last Completed At": {"date": {}},
        "Last Scraper Run At": {"date": {}},
        "Last Workspace Refresh At": {"date": {}},
    }


def build_webhook_action_url(path: str) -> str:
    if not WEBHOOK_PUBLIC_BASE_URL:
        return ""

    url = f"{WEBHOOK_PUBLIC_BASE_URL}{path}"
    if WEBHOOK_SHARED_SECRET:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}secret={WEBHOOK_SHARED_SECRET}"
    return url


def build_generate_proposal_action_url(page_id: str) -> str:
    page_id = str(page_id or "").strip()
    if not page_id:
        return ""

    base = build_webhook_action_url("/notion/generate-proposal")
    if not base:
        return ""

    separator = "&" if "?" in base else "?"
    return f"{base}{separator}page_id={page_id}"


def build_scraper_settings_schema() -> dict:
    return {
        "Setting": {"title": {}},
        "Setting Key": {"rich_text": {}},
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
        "Job URL": {"url": {}},
        "Job Links": {"rich_text": {}},
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


def get_default_automation_control_rows() -> list[dict]:
    run_scraper_link = build_webhook_action_url("/notion/run-scraper")
    refresh_workspace_link = build_webhook_action_url("/notion/refresh-workspace")
    usage_message = "برای دریافت جاب جدید فقط تیک Fetch New Jobs را بزن. بعد از چند دقیقه Fetch Status و Last Fetch At را ببین."
    return [
        {
            "properties": {
                "Control": title_property("Primary Control"),
                "Fetch New Jobs": checkbox_property(False),
                "Fetch Status": status_property("Idle"),
                "Last Fetch At": date_property(""),
                "Help": rich_text_property(usage_message),
                "Run Scraper Now": checkbox_property(False),
                "Run Scraper Link": url_property(run_scraper_link),
                "Refresh Workspace Now": checkbox_property(False),
                "Refresh Workspace Link": url_property(refresh_workspace_link),
                "Last Action": rich_text_property(""),
                "Last Result": status_property("Idle"),
                "Last Message": rich_text_property(usage_message),
                "Last Completed At": date_property(""),
                "Last Scraper Run At": date_property(""),
                "Last Workspace Refresh At": date_property(""),
            }
        }
    ]


def get_default_settings_rows() -> list[dict]:
    defaults = [
        ("openai_model", "OpenAI Model", os.getenv("OPENAI_MODEL", "gpt-5.1"), "string", True, "AI model used to generate proposal drafts."),
        ("max_job_age_days", "Max Job Age (Days)", os.getenv("MAX_JOB_AGE_DAYS", "14"), "int", True, "Reject jobs older than this many days."),
        ("default_results_per_page", "Default Results Per Query", "5", "int", True, "Fallback Upwork result count when a search query has no value."),
        ("require_payment_verified", "Require Verified Payment", "false", "bool", True, "When true, reject jobs from clients without verified payment."),
        ("require_client_spent", "Require Client Spend", "false", "bool", True, "When true, require clients to meet the minimum spend setting."),
        ("require_client_hires", "Require Client Hires", "false", "bool", True, "When true, reject jobs from clients with zero hires."),
        ("require_proposals_limit", "Enforce Proposal Limit", "false", "bool", True, "When true, reject jobs at or above the maximum proposal count."),
        ("require_project_length", "Require Preferred Project Length", "false", "bool", True, "When true, only accept jobs with preferred project lengths."),
        ("require_budget_range", "Enforce Fixed Budget Range", "false", "bool", True, "When true, reject fixed-price jobs outside the budget range."),
        ("require_hourly_range", "Enforce Hourly Rate Range", "false", "bool", True, "When true, reject hourly jobs outside the hourly rate range."),
        ("minimum_client_spent", "Minimum Client Spend", "100", "int", True, "Minimum client spend required when client spend filtering is enabled."),
        ("maximum_proposals", "Maximum Proposals", "20", "int", True, "Maximum proposal count allowed when proposal limit filtering is enabled."),
        ("minimum_fixed_budget", "Minimum Fixed Budget", "1000", "int", True, "Minimum fixed-price budget allowed when budget filtering is enabled."),
        ("maximum_fixed_budget", "Maximum Fixed Budget", "100000", "int", True, "Maximum fixed-price budget allowed when budget filtering is enabled."),
        ("minimum_hourly_rate", "Minimum Hourly Rate", "10", "int", True, "Minimum hourly rate allowed when hourly filtering is enabled."),
        ("maximum_hourly_rate", "Maximum Hourly Rate", "50", "int", True, "Maximum hourly rate allowed when hourly filtering is enabled."),
        ("default_prompt_template", "Default Prompt Template", "default-proposal-template", "string", True, "Prompt template key used when a job has no specific template."),
        ("proposal_prompt_mode", "Proposal Prompt Mode", "lean", "string", True, "Proposal prompt mode. Use lean for shorter prompts or full for full-template prompts."),
        ("proposal_max_description_chars", "Max Job Description Chars", "3500", "int", True, "Maximum job description characters sent to the AI model."),
        ("proposal_max_template_chars", "Max Template Chars", "2200", "int", True, "Maximum template characters sent to the AI model in full mode."),
    ]

    rows = []
    for key, display_name, value, value_type, enabled, description in defaults:
        rows.append(
            {
                "properties": {
                    "Setting": title_property(display_name),
                    "Setting Key": rich_text_property(key),
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
            item.get("plain_text")
            or item.get("text", {}).get("content", "")
            for item in row["properties"][title_property_name].get("title", [])
        ).strip()
        if title in existing_titles:
            continue
        create_page(database_id, row["properties"], row.get("children"))


def get_text_from_property_payload(property_payload: dict, property_type: str) -> str:
    return "".join(
        item.get("plain_text")
        or item.get("text", {}).get("content", "")
        for item in property_payload.get(property_type, [])
    ).strip()


def sync_default_settings_rows(database_id: str):
    defaults = get_default_settings_rows()
    pages = query_database(database_id)
    pages_by_title = {get_page_title(page): page for page in pages}
    pages_by_key = {
        get_plain_text_property(page, "Setting Key"): page
        for page in pages
        if get_plain_text_property(page, "Setting Key")
    }

    for row in defaults:
        properties = row["properties"]
        display_name = get_text_from_property_payload(properties["Setting"], "title")
        setting_key = get_text_from_property_payload(properties["Setting Key"], "rich_text")

        existing = (
            pages_by_key.get(setting_key)
            or pages_by_title.get(display_name)
            or pages_by_title.get(setting_key)
        )

        if not existing:
            create_page(database_id, properties, row.get("children"))
            continue

        update_page(
            existing["id"],
            {
                "Setting": title_property(display_name),
                "Setting Key": rich_text_property(setting_key),
                "Type": properties["Type"],
                "Description": properties["Description"],
            },
        )


def sync_automation_control_row(database_id: str):
    defaults = get_default_automation_control_rows()
    existing = find_page_by_title(database_id, "Primary Control")

    if not existing:
        create_page(database_id, defaults[0]["properties"], defaults[0].get("children"))
        return

    properties = defaults[0]["properties"]
    updates = {
        "Fetch Status": properties["Fetch Status"],
        "Help": properties["Help"],
        "Run Scraper Link": properties["Run Scraper Link"],
        "Refresh Workspace Link": properties["Refresh Workspace Link"],
    }

    if not get_plain_text_property(existing, "Last Message"):
        updates["Last Message"] = properties["Last Message"]

    update_page(existing["id"], updates)


def sync_jobs_action_links(database_id: str):
    for page in query_database(database_id):
        update_page(
            page["id"],
            {
                "Generate Proposal Now": url_property(build_generate_proposal_action_url(page["id"])),
            },
        )


def sync_jobs_discovered_day(database_id: str):
    local_timezone = get_local_timezone()

    for page in query_database(database_id):
        discovered_at = get_plain_text_property(page, "Discovered At")
        if not discovered_at:
            continue

        try:
            discovered_dt = datetime.fromisoformat(discovered_at)
        except ValueError:
            continue

        if discovered_dt.tzinfo is None:
            discovered_dt = discovered_dt.replace(tzinfo=timezone.utc)

        local_day = discovered_dt.astimezone(local_timezone).date().isoformat()
        current_day = get_plain_text_property(page, "Discovered Day")

        if current_day != local_day:
            update_page(page["id"], {"Discovered Day": date_property(local_day)})


def build_persian_knowledge_base_blocks() -> list[dict]:
    blocks = [
        callout_block(
            "این صفحه راهنمای فارسیِ کل سیستم است. هدفش این است که مدیر دیجیتال مارکتینگ و هر عضو تیم بدون نیاز به باز کردن کد یا GitHub بداند هر بخش برای چیست و هر اقدام را از کجا باید انجام دهد.",
            "📘",
        ),
        paragraph_block(
            "این سیستم سه کار اصلی انجام می‌دهد: جاب‌های جدید Upwork را جمع می‌کند، آن‌ها را در Notion برای بررسی روزانه منظم می‌کند، و برای جاب‌های تاییدشده proposal می‌سازد."
        ),
        divider_block(),
        heading_block("نقشه کلی سیستم"),
        callout_block(
            "ورودی: Upwork + تنظیمات Notion\n"
            "پردازش: Python + GitHub Actions\n"
            "خروجی: دیتابیس Jobs + Proposal + Run History داخل Notion",
            "🧭",
        ),
        toggle_block(
            "جریان روزانه مدیر دیجیتال مارکتینگ",
            [
                paragraph_block("1. وارد دیتابیس Jobs می‌شود."),
                paragraph_block("2. از 01 Today شروع می‌کند، بعد 02 Yesterday و بعد 03 Older را می‌بیند."),
                paragraph_block("3. جاب خوب را بررسی می‌کند و اگر مناسب بود تیک Generate Proposal را می‌زند."),
                paragraph_block("4. اگر نیاز به جاب‌های جدید داشت، در دیتابیس Automation Control فقط تیک Fetch New Jobs را می‌زند."),
                paragraph_block("5. خروجی proposal را در همان صفحه جاب و نتایج اجرا را در Run History می‌بیند."),
            ],
        ),
        divider_block(),
        heading_block("دیتابیس‌ها و نقش هرکدام"),
        toggle_block(
            "Jobs",
            [
                paragraph_block("مرکز اصلی بررسی جاب‌ها است. هر ردیف یک job از Upwork است."),
                paragraph_block("مهم‌ترین propertyها:"),
                paragraph_block("Title: عنوان جاب"),
                paragraph_block("Generate Proposal: تریگر ساده و مستقیم برای ساخت proposal."),
                paragraph_block("Manager Review: وضعیت تایید یا رد توسط مدیر"),
                paragraph_block("Proposal Status: وضعیت ساخت proposal"),
                paragraph_block("Match Score: امتیاز کیفیت جاب برای اولویت‌بندی"),
                paragraph_block("Published At / Discovered Day: زمان انتشار و زمان کشف جاب"),
                paragraph_block("Budget / Job Type / Proposals / Gig Link: اطلاعات اصلی برای تصمیم‌گیری سریع"),
            ],
        ),
        toggle_block(
            "Automation Control",
            [
                paragraph_block("پنل کنترل روزانه برای کارهای اجرایی است."),
                paragraph_block("Fetch New Jobs: تنها کاری که مدیر برای دریافت لیست جدید باید انجام دهد. در حالت درست، Notion Automation همین تیک را به webhook عمومی وصل می‌کند."),
                paragraph_block("Fetch Status: وضعیت اجرا را با مقدارهایی مثل Idle, Running, Success, Failed نشان می‌دهد."),
                paragraph_block("Last Fetch At: آخرین زمان موفق دریافت جاب‌های جدید."),
                paragraph_block("Help: راهنمای خیلی کوتاه همان‌جا برای مدیر."),
            ],
        ),
        toggle_block(
            "Search Queries",
            [
                paragraph_block("تنظیم می‌کند scraper دقیقاً چه نوع جاب‌هایی را بگردد."),
                paragraph_block("هر ردیف یک query است. با Enabled می‌شود query را روشن یا خاموش کرد."),
                paragraph_block("Results Per Page, Min Budget, Max Budget و Max Age Days رفتار جست‌وجو را کنترل می‌کنند."),
            ],
        ),
        toggle_block(
            "Scraper Settings",
            [
                paragraph_block("تنظیمات کلی سیستم اینجا نگه‌داری می‌شود."),
                paragraph_block("Value مقدار هر تنظیم است، Type نوع آن را مشخص می‌کند و Description توضیح انسانی آن است."),
                paragraph_block("نمونه‌ها: OpenAI Model، Max Job Age (Days)، Maximum Proposals، Minimum Client Spend."),
            ],
        ),
        toggle_block(
            "Prompt Templates",
            [
                paragraph_block("قالب نوشتن proposal را نگه می‌دارد."),
                paragraph_block("اگر لحن یا ساختار proposal عوض شود، معمولاً از اینجا یا از فایل template اصلی مدیریت می‌شود."),
            ],
        ),
        toggle_block(
            "Run History",
            [
                paragraph_block("تاریخچه اجرای scraper، setup و proposal generation را نگه می‌دارد."),
                paragraph_block("اگر چیزی fail شود، اول اینجا چک می‌شود."),
            ],
        ),
        divider_block(),
        heading_block("معنای propertyهای مهم در Jobs"),
        toggle_block(
            "Propertyهای تصمیم‌گیری روزانه",
            [
                paragraph_block("Generate Proposal: اگر تیک بخورد و Notion Automation فعال باشد، webhook عمومی GitHub Action را فوراً اجرا می‌کند."),
                paragraph_block("Manager Review: New یعنی هنوز بررسی نشده، Approved یعنی تایید شده، Rejected یعنی رد شده."),
                paragraph_block("Proposal Status: Not Requested, Requested, Generating, Ready, Failed."),
                paragraph_block("Status: وضعیت کلی داخلی مثل Draft, Applied, Rejected, Skipped."),
                paragraph_block("Match Score: هر چه بالاتر باشد، احتمال مناسب بودن جاب بیشتر است."),
            ],
        ),
        toggle_block(
            "Propertyهای اطلاعات جاب",
            [
                paragraph_block("Job Type: Hourly یا Fixed."),
                paragraph_block("Budget و Hourly Rate: محدوده مالی پروژه."),
                paragraph_block("Client Hires و Client Spent: کیفیت و سابقه کارفرما."),
                paragraph_block("Proposals: میزان رقابت روی جاب."),
                paragraph_block("Gig Link: لینک اصلی Upwork."),
                paragraph_block("Source Query: مشخص می‌کند این جاب از کدام query پیدا شده است."),
            ],
        ),
        toggle_block(
            "Propertyهایی که عمداً در جدول پنهان هستند",
            [
                paragraph_block("AI Model"),
                paragraph_block("AI Notes"),
                paragraph_block("Job ID"),
                paragraph_block("Job Summary"),
                paragraph_block("Prompt Template"),
                paragraph_block("Proposal Error"),
                paragraph_block("Proposal Preview"),
                paragraph_block("Proposal Requested At"),
            ],
        ),
        divider_block(),
        heading_block("ویوهای مهم برای کار روزانه"),
        toggle_block(
            "Review Inbox",
            [
                paragraph_block("01 Today: جاب‌های امروز که هنوز بررسی نشده‌اند."),
                paragraph_block("02 Yesterday: جاب‌های دیروز که هنوز بررسی نشده‌اند."),
                paragraph_block("03 Older: جاب‌های قبل از دیروز در هفته اخیر."),
                paragraph_block("04 Review: همه جاب‌های تصمیم‌نگرفته به عنوان backlog کامل."),
                paragraph_block("05 Week: مرور هفتگی تصمیم‌نگرفته‌ها بر اساس روز و امتیاز."),
            ],
        ),
        toggle_block(
            "Proposal و آرشیو",
            [
                paragraph_block("06 Proposal: جاب‌های تاییدشده که هنوز proposal نگرفته‌اند."),
                paragraph_block("07 Ready: proposal ساخته شده و آماده استفاده است."),
                paragraph_block("08 Applied: جاب‌هایی که اقدام نهایی روی آن‌ها انجام شده است."),
                paragraph_block("09 Archive: موارد آرشیوی که نباید جدول اصلی را شلوغ کنند."),
                paragraph_block("10 All: آرشیو کامل به ترتیب روز."),
            ],
        ),
        divider_block(),
        heading_block("چطور از داخل Notion کارها را اجرا کنیم"),
        toggle_block(
            "آپدیت لیست جاب‌ها",
            [
                paragraph_block("1. وارد دیتابیس Automation Control شو."),
                paragraph_block("2. ردیف Primary Control را باز کن."),
                paragraph_block("3. فقط تیک Fetch New Jobs را بزن."),
                paragraph_block("4. اگر Notion Automation به webhook وصل باشد، GitHub Action فوراً dispatch می‌شود."),
                paragraph_block("5. اگر Success شد، Last Fetch At زمان آخرین دریافت را نشان می‌دهد."),
            ],
        ),
        toggle_block(
            "ساخت proposal برای یک جاب",
            [
                paragraph_block("1. جاب را در Jobs باز کن یا در همان جدول پیدا کن."),
                paragraph_block("2. تیک Generate Proposal را فعال کن."),
                paragraph_block("3. Notion Automation باید webhook /notion/generate-proposal را صدا بزند؛ بعد سیستم خودش Manager Review و Proposal Status را مدیریت می‌کند."),
                paragraph_block("4. خروجی در همان صفحه زیر AI Proposal می‌آید."),
            ],
        ),
        divider_block(),
        heading_block("عیب‌یابی سریع"),
        toggle_block(
            "اگر proposal ساخته نشد",
            [
                paragraph_block("Proposal Status را چک کن: اگر Failed شد، Run History و Last Message را ببین."),
                paragraph_block("مطمئن شو OPENAI_API_KEY و تنظیمات prompt درست هستند."),
            ],
        ),
        toggle_block(
            "اگر جاب جدید نیامد",
            [
                paragraph_block("در Automation Control ستون Fetch Status را ببین."),
                paragraph_block("اگر Success نشد، Last Message یا Run History را چک کن."),
                paragraph_block("Search Queries و Scraper Settings را چک کن."),
                paragraph_block("Run History را برای خطاهای scrape یا setup نگاه کن."),
            ],
        ),
        callout_block(
            "قاعده ساده برای تیم: همه چیز از داخل Notion انجام می‌شود. GitHub و کد برای مدیر روزانه ابزار عملیاتی نیستند.",
            "✅",
        ),
    ]
    return blocks


def ensure_persian_knowledge_base_page(parent_page_id: str) -> str:
    children = build_persian_knowledge_base_blocks()
    existing = find_page_under_parent(parent_page_id, KNOWLEDGE_BASE_PAGE_TITLE)

    if existing:
        replace_page_children(existing["id"], children)
        return existing["id"]

    created = create_child_page(parent_page_id, KNOWLEDGE_BASE_PAGE_TITLE, children)
    return created["id"]


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
    job_url: str = "",
    job_links: str = "",
    error_message: str = "",
):
    try:
        run_history_database_id = require_database_id("run_history")
    except Exception:
        return

    try:
        existing_properties = get_database(run_history_database_id).get("properties", {})
        missing_properties = {
            name: schema
            for name, schema in build_run_history_schema().items()
            if name not in existing_properties
        }
        if missing_properties:
            patch_database_properties(run_history_database_id, missing_properties)
    except Exception:
        pass

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
        "Job URL": url_property(job_url),
        "Job Links": rich_text_property(job_links),
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

        key = get_plain_text_property(row, "Setting Key") or get_page_title(row)
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
