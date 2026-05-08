"""
Upwork Job Scraper (Apify) -> OpenAI Proposal -> Notion Integration
===================================================================

Flow:
1. Runs Apify Upwork scraper actor
2. Fetches jobs
3. Deduplicates by Job ID and Gig Link
4. Filters by freshness and optional strict rules
5. Scores each job with Match Score
6. Generates a proposal with OpenAI API using proposal_template.md
7. Saves clean job properties into Notion
8. Saves AI Proposal, Job Summary, Snapshot, Skills, and Full Job Description inside the Notion page
"""

import os
import sys
import time
import re
import json
import logging
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

import notion_workspace as nw

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

# =========================================================
# Environment
# =========================================================

APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")
APIFY_ACTOR_ID = "gLI248Zq7Fja9xoMo"

NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")
NOTION_API_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.1")
OPENAI_API_URL = "https://api.openai.com/v1/responses"
PROPOSAL_PROMPT_MODE = os.getenv("PROPOSAL_PROMPT_MODE", "lean")
PROPOSAL_MAX_DESCRIPTION_CHARS = int(os.getenv("PROPOSAL_MAX_DESCRIPTION_CHARS", "3500"))
PROPOSAL_MAX_TEMPLATE_CHARS = int(os.getenv("PROPOSAL_MAX_TEMPLATE_CHARS", "2200"))

NOTIFICATION_WEBHOOK_URL = os.getenv("NOTIFICATION_WEBHOOK_URL", "")

# =========================================================
# Filter Settings
# =========================================================
# برای تست و زیر بار بردن، فعلاً False هستند.
# وقتی خواستی سخت‌گیرانه‌تر شود، یکی‌یکی True کن.

REQUIRE_PAYMENT_VERIFIED = False
REQUIRE_CLIENT_SPENT = False
REQUIRE_CLIENT_HIRES = False
REQUIRE_PROPOSALS_LIMIT = False
REQUIRE_PROJECT_LENGTH = False
REQUIRE_BUDGET_RANGE = False
REQUIRE_HOURLY_RANGE = False

MAX_JOB_AGE_DAYS_RAW = os.getenv("MAX_JOB_AGE_DAYS", "14").strip()
MAX_JOB_AGE_DAYS = int(MAX_JOB_AGE_DAYS_RAW) if MAX_JOB_AGE_DAYS_RAW else 14

MINIMUM_FIXED_BUDGET = 1000
MAXIMUM_FIXED_BUDGET = 100000
MINIMUM_CLIENT_SPENT = 100
MINIMUM_HOURLY_RATE = 10
MAXIMUM_HOURLY_RATE = 50
MAXIMUM_PROPOSALS = 20

# =========================================================
# Logging
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("scraper.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

_NOTION_DATABASE_CACHE = None

LEAN_PROPOSAL_TEMPLATE = """
Write a short, tailored Upwork proposal for Heli Studio.

Rules:
- Sound human, calm, and specific.
- Use "we" / "our".
- Do not invent facts, past work, numbers, or tools not supported by the job.
- Focus on the client's core need, likely deliverable, and the clearest strategic angle.
- Mention 1-2 relevant details from the job so it feels custom.
- Keep it concise and easy to paste into Upwork.
- Avoid generic intros, buzzwords, and long process breakdowns.
- End with a simple next step or invitation to continue.

Target shape:
- 2 short paragraphs.
- Usually 80-140 words.
- Client-facing language, not technical spec language.

Return only the final proposal text.
""".strip()


def get_jobs_database_id() -> str:
    global NOTION_DATABASE_ID

    if NOTION_DATABASE_ID:
        return NOTION_DATABASE_ID

    NOTION_DATABASE_ID = nw.get_jobs_database_id()
    return NOTION_DATABASE_ID


def apply_workspace_settings():
    global OPENAI_MODEL
    global PROPOSAL_PROMPT_MODE
    global PROPOSAL_MAX_DESCRIPTION_CHARS
    global PROPOSAL_MAX_TEMPLATE_CHARS
    global MAX_JOB_AGE_DAYS
    global MINIMUM_FIXED_BUDGET
    global MAXIMUM_FIXED_BUDGET
    global MINIMUM_CLIENT_SPENT
    global MINIMUM_HOURLY_RATE
    global MAXIMUM_HOURLY_RATE
    global MAXIMUM_PROPOSALS
    global REQUIRE_PAYMENT_VERIFIED
    global REQUIRE_CLIENT_SPENT
    global REQUIRE_CLIENT_HIRES
    global REQUIRE_PROPOSALS_LIMIT
    global REQUIRE_PROJECT_LENGTH
    global REQUIRE_BUDGET_RANGE
    global REQUIRE_HOURLY_RANGE

    settings = nw.load_scraper_settings()

    OPENAI_MODEL = settings.get("openai_model", OPENAI_MODEL)
    PROPOSAL_PROMPT_MODE = str(settings.get("proposal_prompt_mode", PROPOSAL_PROMPT_MODE) or "lean").strip().lower()
    PROPOSAL_MAX_DESCRIPTION_CHARS = int(settings.get("proposal_max_description_chars", PROPOSAL_MAX_DESCRIPTION_CHARS))
    PROPOSAL_MAX_TEMPLATE_CHARS = int(settings.get("proposal_max_template_chars", PROPOSAL_MAX_TEMPLATE_CHARS))
    MAX_JOB_AGE_DAYS = int(settings.get("max_job_age_days", MAX_JOB_AGE_DAYS))
    MINIMUM_FIXED_BUDGET = int(settings.get("minimum_fixed_budget", MINIMUM_FIXED_BUDGET))
    MAXIMUM_FIXED_BUDGET = int(settings.get("maximum_fixed_budget", MAXIMUM_FIXED_BUDGET))
    MINIMUM_CLIENT_SPENT = int(settings.get("minimum_client_spent", MINIMUM_CLIENT_SPENT))
    MINIMUM_HOURLY_RATE = int(settings.get("minimum_hourly_rate", MINIMUM_HOURLY_RATE))
    MAXIMUM_HOURLY_RATE = int(settings.get("maximum_hourly_rate", MAXIMUM_HOURLY_RATE))
    MAXIMUM_PROPOSALS = int(settings.get("maximum_proposals", MAXIMUM_PROPOSALS))
    REQUIRE_PAYMENT_VERIFIED = bool(settings.get("require_payment_verified", REQUIRE_PAYMENT_VERIFIED))
    REQUIRE_CLIENT_SPENT = bool(settings.get("require_client_spent", REQUIRE_CLIENT_SPENT))
    REQUIRE_CLIENT_HIRES = bool(settings.get("require_client_hires", REQUIRE_CLIENT_HIRES))
    REQUIRE_PROPOSALS_LIMIT = bool(settings.get("require_proposals_limit", REQUIRE_PROPOSALS_LIMIT))
    REQUIRE_PROJECT_LENGTH = bool(settings.get("require_project_length", REQUIRE_PROJECT_LENGTH))
    REQUIRE_BUDGET_RANGE = bool(settings.get("require_budget_range", REQUIRE_BUDGET_RANGE))
    REQUIRE_HOURLY_RANGE = bool(settings.get("require_hourly_range", REQUIRE_HOURLY_RANGE))


# =========================================================
# General Helpers
# =========================================================

def safe_text(value, limit=1900):
    if value is None:
        return ""
    return str(value)[:limit]


def get_nested(data: dict, path: list, default=""):
    current = data

    for key in path:
        if not isinstance(current, dict):
            return default

        current = current.get(key)

        if current in (None, "", [], {}):
            return default

    return current


def load_proposal_template(template_name: str = "") -> str:
    try:
        template_page = nw.find_prompt_template_page(template_name)

        if template_page:
            template_body = nw.get_template_body(template_page["id"])
            if template_body.strip():
                return template_body
    except Exception:
        pass

    path = "proposal_template.md"

    if not os.path.exists(path):
        return (
            "Write a short, calm, tailored Upwork proposal for Heli Studio. "
            "Use we and our. Do not invent facts. Keep it ready to paste into Upwork."
        )

    with open(path, "r", encoding="utf-8") as file:
        return file.read()


def parse_datetime(value):
    if not value:
        return None

    text = str(value).strip()

    try:
        if text.endswith("Z"):
            text = text.replace("Z", "+00:00")

        if "+0000" in text:
            text = text.replace("+0000", "+00:00")

        dt = datetime.fromisoformat(text)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except Exception:
        return None


def days_since(dt):
    if not dt:
        return None

    now = datetime.now(timezone.utc)
    delta = now - dt
    return max(0, int(delta.total_seconds() // 86400))


def format_datetime_human(value):
    if not value:
        return ""

    dt = parse_datetime(value)

    if not dt:
        return str(value)

    return dt.strftime("%Y-%m-%d %H:%M UTC")


def format_money_value(value, prefix="$", suffix=""):
    if value in (None, "", [], {}):
        return ""

    if isinstance(value, dict):
        amount = value.get("amount")
        currency = value.get("currencyCode") or value.get("currency") or "USD"

        if amount in (None, ""):
            return ""

        try:
            amount_float = float(amount)
            if currency == "USD":
                return f"${amount_float:,.0f}{suffix}"
            return f"{currency} {amount_float:,.0f}{suffix}"
        except Exception:
            return str(value)

    if isinstance(value, (int, float)):
        return f"{prefix}{float(value):,.0f}{suffix}"

    text = str(value)

    if text.startswith("{") and "amount" in text:
        numbers = re.findall(r"\d+(?:\.\d+)?", text)
        if numbers:
            try:
                amount_float = float(numbers[0])
                return f"${amount_float:,.0f}{suffix}"
            except Exception:
                pass

    return text


# =========================================================
# Apify
# =========================================================

def build_apify_input(search_config: dict) -> dict:
    query_value = search_config.get("query", "")

    if isinstance(query_value, list):
        query_array = query_value
    else:
        query_array = [query_value]

    requested_count = search_config.get("results_per_page", 10)

    actor_input = {
        "query": query_array,
        "sort": "newest",
        "page": search_config.get("start_page", 1),

        # چند اسم رایج برای limit می‌فرستیم چون Actorها همیشه آدم‌وار اسم‌گذاری نمی‌کنند.
        "resultsPerPage": requested_count,
        "maxItems": requested_count,
        "limit": requested_count,
        "maxResults": requested_count,
    }

    if search_config.get("fixed_budget_min") is not None:
        actor_input["fixedBudgetMin"] = search_config["fixed_budget_min"]

    if search_config.get("fixed_budget_max") is not None:
        actor_input["fixedBudgetMax"] = search_config["fixed_budget_max"]

    if search_config.get("max_job_age"):
        actor_input["maxJobAge"] = search_config["max_job_age"]

    if search_config.get("job_type"):
        actor_input["jobType"] = search_config["job_type"]

    if search_config.get("experience_level"):
        actor_input["experienceLevel"] = search_config["experience_level"]

    if search_config.get("locations"):
        actor_input["locations"] = search_config["locations"]

    logger.info(f"Apify input: {actor_input}")
    return actor_input


def run_apify_actor(actor_input: dict) -> str:
    url = f"https://api.apify.com/v2/acts/{APIFY_ACTOR_ID}/runs"
    params = {"token": APIFY_API_TOKEN}

    logger.info(f"Starting Apify actor run for query: {actor_input.get('query', 'N/A')}")

    try:
        response = requests.post(url, params=params, json=actor_input, timeout=30)
        response.raise_for_status()

        data = response.json()
        run_id = data["data"]["id"]

        logger.info(f"Actor run started: {run_id}")
        return run_id

    except requests.exceptions.RequestException as error:
        logger.error(f"Failed to start Apify actor: {error}")

        if hasattr(error, "response") and error.response is not None:
            logger.error(f"Response: {error.response.text[:1000]}")

        return ""


def wait_for_run(run_id: str, timeout_seconds: int = 300, poll_interval: int = 10) -> dict:
    url = f"https://api.apify.com/v2/actor-runs/{run_id}"
    params = {"token": APIFY_API_TOKEN}

    elapsed = 0

    while elapsed < timeout_seconds:
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()

            data = response.json()["data"]
            status = data.get("status", "UNKNOWN")

            if status == "SUCCEEDED":
                logger.info("Actor run completed successfully")
                return data

            if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                logger.error(f"Actor run ended with status: {status}")
                return data

            logger.info(f"Run status: {status} - waiting...")

        except requests.exceptions.RequestException as error:
            logger.warning(f"Error polling run status: {error}")

        time.sleep(poll_interval)
        elapsed += poll_interval

    logger.error(f"Timed out waiting for actor run after {timeout_seconds}s")
    return {}


def fetch_dataset_items(run_data: dict) -> list:
    dataset_id = run_data.get("defaultDatasetId", "")

    if not dataset_id:
        logger.error("No dataset ID found in run data")
        return []

    url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
    params = {
        "token": APIFY_API_TOKEN,
        "format": "json"
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        items = response.json()
        logger.info(f"Fetched {len(items)} jobs from Apify dataset")

        return items

    except requests.exceptions.RequestException as error:
        logger.error(f"Failed to fetch dataset: {error}")

        if hasattr(error, "response") and error.response is not None:
            logger.error(f"Response: {error.response.text[:1000]}")

        return []


# =========================================================
# Job Field Mapping
# =========================================================

def get_job_id(job: dict) -> str:
    return str(
        job.get("id")
        or job.get("jobId")
        or job.get("job_id")
        or job.get("recno")
        or ""
    ).strip()


def normalize_job_url(job: dict) -> str:
    url = (
        job.get("url")
        or job.get("jobUrl")
        or job.get("job_url")
        or job.get("link")
        or ""
    )

    return str(url).split("?")[0].rstrip("/")


def get_job_title(job: dict) -> str:
    return str(
        job.get("title")
        or job.get("jobTitle")
        or job.get("name")
        or "Untitled"
    )


def get_job_description(job: dict) -> str:
    return str(
        job.get("description")
        or job.get("jobDescription")
        or job.get("summary")
        or ""
    )


def get_job_summary(job: dict) -> str:
    description = get_job_description(job)
    return safe_text(description, 700)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def truncate_text_safely(text: str, limit: int) -> str:
    text = normalize_whitespace(text)
    if len(text) <= limit:
        return text

    truncated = text[:limit]
    last_boundary = max(truncated.rfind(". "), truncated.rfind("! "), truncated.rfind("? "), truncated.rfind("; "))
    if last_boundary >= int(limit * 0.6):
        return truncated[:last_boundary + 1].strip()

    last_space = truncated.rfind(" ")
    if last_space >= int(limit * 0.8):
        return truncated[:last_space].strip()

    return truncated.strip()


def extract_key_job_points(description: str, max_chars: int) -> str:
    if not description:
        return ""

    normalized_lines = []
    for raw_line in str(description).splitlines():
        line = normalize_whitespace(raw_line.strip(" -*\t"))
        if line:
            normalized_lines.append(line)

    keywords = [
        "need", "looking for", "must", "required", "deliver", "deliverable",
        "scope", "goal", "objective", "timeline", "deadline", "budget",
        "experience", "ideal", "responsib", "task", "project", "design",
        "figma", "webflow", "framer", "landing page", "dashboard", "saas",
    ]

    selected = []
    seen = set()

    for line in normalized_lines:
        lowered = line.lower()
        if any(keyword in lowered for keyword in keywords):
            compact = truncate_text_safely(line, 220)
            if compact and compact not in seen:
                selected.append(f"- {compact}")
                seen.add(compact)

        if sum(len(item) for item in selected) >= max_chars:
            break

    if not selected:
        compact = truncate_text_safely(description, max_chars)
        return compact

    joined = "\n".join(selected)
    return truncate_text_safely(joined, max_chars)


def build_compact_job_context(job: dict) -> dict:
    return {
        "title": get_job_title(job),
        "summary": get_job_summary(job),
        "budget": get_budget_display(job),
        "job_type": get_job_type(job),
        "hourly_rate": get_hourly_rate_text(job),
        "project_length": get_project_length(job),
        "proposals": get_proposals_count(job),
        "client_spent": get_client_spent_text(job),
        "client_hires": get_client_hires_count(job),
        "payment_status": get_payment_status_text(job),
        "published_at": get_published_iso(job),
        "freshness_days": get_freshness_days(job),
        "skills": get_skills_text(job),
        "category": get_nested(job, ["category", "name"], ""),
        "category_group": get_nested(job, ["categoryGroup", "name"], ""),
        "source_query": job.get("_source_query", ""),
    }


def build_proposal_prompt(job: dict) -> str:
    description = get_job_description(job)
    template = load_proposal_template(str(job.get("_prompt_template_name") or ""))
    compact_context = build_compact_job_context(job)

    if PROPOSAL_PROMPT_MODE == "full":
        template_section = truncate_text_safely(template, PROPOSAL_MAX_TEMPLATE_CHARS)
        description_section = truncate_text_safely(description, PROPOSAL_MAX_DESCRIPTION_CHARS)

        return f"""
Use the template and rules below to write a tailored Upwork proposal.

TEMPLATE AND RULES:
{template_section}

JOB DATA:
{json.dumps(compact_context, ensure_ascii=False, separators=(",", ":"))}

FULL JOB DESCRIPTION:
{description_section}

Return only the proposal text.
""".strip()

    focused_brief = extract_key_job_points(description, PROPOSAL_MAX_DESCRIPTION_CHARS)
    lean_template = LEAN_PROPOSAL_TEMPLATE

    return f"""
Write a short, tailored Upwork proposal using the rules below.

RULES:
{lean_template}

REFERENCE STYLE:
{truncate_text_safely(template, 900)}

JOB DATA:
{json.dumps(compact_context, ensure_ascii=False, separators=(",", ":"))}

FOCUSED JOB BRIEF:
{focused_brief}

Return only the proposal text.
""".strip()


def get_skills_text(job: dict) -> str:
    skills = job.get("skills") or job.get("tags") or []

    if isinstance(skills, list):
        names = []

        for skill in skills:
            if isinstance(skill, dict):
                name = skill.get("name")
                if name:
                    names.append(str(name))
            else:
                names.append(str(skill))

        return ", ".join(names)

    return str(skills)


def get_job_budget(job: dict):
    fixed_budget = get_nested(job, ["fixed", "budget"], "")

    if fixed_budget not in ("", None):
        return fixed_budget

    return (
        job.get("budget")
        or job.get("amount")
        or job.get("fixedPrice")
        or job.get("fixed_budget")
        or job.get("fixedBudget")
        or job.get("price")
        or ""
    )


def get_job_type(job: dict) -> str:
    job_type = job.get("type") or job.get("jobType") or job.get("contractType") or ""

    if job_type:
        job_type_text = str(job_type).lower()

        if job_type_text == "hourly":
            return "Hourly"

        if job_type_text == "fixed":
            return "Fixed"

        return str(job_type).title()

    if get_nested(job, ["hourly", "min"], "") or get_nested(job, ["hourly", "max"], ""):
        return "Hourly"

    if get_nested(job, ["fixed", "budget"], ""):
        return "Fixed"

    return "Unknown"


def get_hourly_rate_text(job: dict) -> str:
    hourly_min = get_nested(job, ["hourly", "min"], "")
    hourly_max = get_nested(job, ["hourly", "max"], "")

    if hourly_min != "" and hourly_max != "":
        try:
            return f"${float(hourly_min):,.0f}-${float(hourly_max):,.0f}/hr"
        except Exception:
            return f"${hourly_min}-${hourly_max}/hr"

    hourly_rate = (
        job.get("hourlyRate")
        or job.get("hourlyRateText")
        or job.get("hourlyBudget")
        or ""
    )

    return str(hourly_rate)


def get_project_length(job: dict) -> str:
    hourly_length = get_nested(job, ["hourly", "duration", "label"], "")
    fixed_length = get_nested(job, ["fixed", "duration", "label"], "")

    return str(
        hourly_length
        or fixed_length
        or job.get("projectLength")
        or job.get("duration")
        or job.get("durationText")
        or ""
    )


def normalize_project_length(value: str) -> str:
    text = str(value or "").lower()

    if "less than one month" in text or "less than 1 month" in text:
        return "Less than one month"

    if "1 to 3 months" in text or "1-3 months" in text:
        return "1 to 3 months"

    if "more than 6 months" in text:
        return "More than 6 months"

    return "Unknown"


def get_proposals_count(job: dict) -> int:
    value = get_nested(job, ["clientActivity", "totalApplicants"], None)

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return int(value)

    value = (
        job.get("proposals")
        or job.get("proposalsCount")
        or job.get("numberOfProposals")
        or job.get("proposalCount")
        or job.get("applicants")
        or ""
    )

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return int(value)

    text = str(value).lower()

    if "less than 5" in text:
        return 4

    numbers = re.findall(r"\d+", text)

    if numbers:
        return int(numbers[0])

    return -1


def get_client_spent_value(job: dict) -> float:
    value = get_nested(job, ["buyer", "stats", "totalCharges", "amount"], None)

    if isinstance(value, (int, float)):
        return float(value)

    value = (
        job.get("totalSpent")
        or job.get("clientTotalSpent")
        or job.get("clientSpent")
        or job.get("spent")
        or job.get("buyerTotalSpent")
        or ""
    )

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).lower().replace(",", "")

    numbers = re.findall(r"\d+(?:\.\d+)?", text)

    if not numbers:
        return 0.0

    amount = float(numbers[0])

    if "k" in text:
        amount *= 1000

    return amount


def get_client_spent_text(job: dict) -> str:
    value = get_nested(job, ["buyer", "stats", "totalCharges"], None)

    if isinstance(value, dict):
        return format_money_value(value)

    amount = get_nested(job, ["buyer", "stats", "totalCharges", "amount"], None)
    currency = get_nested(job, ["buyer", "stats", "totalCharges", "currencyCode"], "USD")

    if isinstance(amount, (int, float)):
        if currency == "USD":
            return f"${amount:,.0f}"
        return f"{currency} {amount:,.0f}"

    fallback = (
        job.get("totalSpent")
        or job.get("clientTotalSpent")
        or job.get("clientSpent")
        or job.get("spent")
        or ""
    )

    return format_money_value(fallback)


def get_client_hires_count(job: dict) -> int:
    value = get_nested(job, ["buyer", "stats", "totalJobsWithHires"], None)

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return int(value)

    value = get_nested(job, ["buyer", "stats", "totalAssignments"], None)

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return int(value)

    value = (
        job.get("hires")
        or job.get("clientHires")
        or job.get("hireCount")
        or job.get("totalHires")
        or ""
    )

    numbers = re.findall(r"\d+", str(value))

    if numbers:
        return int(numbers[0])

    return 0


def get_payment_verified(job: dict) -> bool:
    value = get_nested(job, ["buyer", "isPaymentMethodVerified"], None)

    if isinstance(value, bool):
        return value

    value = (
        job.get("paymentVerified")
        or job.get("isPaymentVerified")
        or job.get("clientPaymentVerified")
        or False
    )

    if isinstance(value, bool):
        return value

    return str(value).lower() in [
        "true",
        "yes",
        "verified",
        "payment verified"
    ]


def get_payment_status_text(job: dict) -> str:
    if get_payment_verified(job):
        return "Verified"
    return "Not verified"


def get_last_seen(job: dict) -> str:
    raw_value = (
        get_nested(job, ["clientActivity", "lastBuyerActivity"], "")
        or job.get("lastSeen")
        or job.get("clientLastSeen")
        or job.get("lastActivity")
        or job.get("clientLastActivity")
        or ""
    )

    return format_datetime_human(raw_value)


def get_hourly_min_max(job: dict) -> tuple:
    hourly_min = get_nested(job, ["hourly", "min"], None)
    hourly_max = get_nested(job, ["hourly", "max"], None)

    if isinstance(hourly_min, (int, float)) and isinstance(hourly_max, (int, float)):
        return float(hourly_min), float(hourly_max)

    hourly_text = get_hourly_rate_text(job).replace(",", "")
    numbers = re.findall(r"\d+(?:\.\d+)?", hourly_text)

    if len(numbers) >= 2:
        return float(numbers[0]), float(numbers[1])

    if len(numbers) == 1:
        value = float(numbers[0])
        return value, value

    return 0.0, 0.0


def get_published_datetime(job: dict):
    value = (
        job.get("ts_publish")
        or job.get("publishedDate")
        or job.get("publishedAt")
        or job.get("postedAt")
        or job.get("ts_create")
        or job.get("createdAt")
        or ""
    )

    return parse_datetime(value)


def get_published_iso(job: dict) -> str:
    dt = get_published_datetime(job)

    if not dt:
        return ""

    return dt.isoformat()


def get_freshness_days(job: dict):
    dt = get_published_datetime(job)
    return days_since(dt)


def extract_budget_value(job: dict) -> float:
    fixed_budget = get_nested(job, ["fixed", "budget"], None)

    if isinstance(fixed_budget, (int, float)) and fixed_budget > 0:
        return float(fixed_budget)

    budget = get_job_budget(job)

    if isinstance(budget, (int, float)) and budget > 0:
        return float(budget)

    if isinstance(budget, dict):
        amount = budget.get("amount")
        if amount:
            try:
                return float(amount)
            except Exception:
                pass

    budget_text = str(budget).replace(",", "")
    numbers = re.findall(r"\d+(?:\.\d+)?", budget_text)

    if numbers:
        try:
            values = [float(number) for number in numbers]
            return max(values)
        except ValueError:
            pass

    return 0.0


def get_budget_display(job: dict) -> str:
    raw_type = str(job.get("type") or "").upper()
    job_type = get_job_type(job).lower()

    is_hourly = raw_type == "HOURLY" or "hourly" in job_type
    is_fixed = raw_type == "FIXED" or "fixed" in job_type

    if is_hourly:
        hourly_min = get_nested(job, ["hourly", "min"], "")
        hourly_max = get_nested(job, ["hourly", "max"], "")

        if hourly_min != "" and hourly_max != "":
            try:
                return f"${float(hourly_min):,.0f}-${float(hourly_max):,.0f}/hr"
            except Exception:
                return f"${hourly_min}-${hourly_max}/hr"

        hourly_rate = get_job_budget(job)
        formatted = format_money_value(hourly_rate, suffix="/hr")
        return formatted or get_hourly_rate_text(job)

    if is_fixed:
        fixed_budget = get_nested(job, ["fixed", "budget"], "")
        formatted = format_money_value(fixed_budget)
        return formatted or format_money_value(get_job_budget(job))

    budget = get_job_budget(job)
    formatted = format_money_value(budget)

    return formatted or str(budget or "")


# =========================================================
# Matching / Freshness / Scoring
# =========================================================

REQUIRED_KEYWORDS = [
    "ui", "ux", "ui/ux",
    "user interface", "user experience",
    "product design", "product designer",
    "web design", "website design", "website redesign",
    "landing page", "homepage design",
    "figma", "webflow", "framer",
    "prototype", "prototyping", "wireframe", "wireframing",
    "mvp", "minimum viable product",
    "design system", "dashboard design", "saas design", "saas",
    "brand identity", "branding",
    "presentation", "pitch deck", "graphic design", "marketing design"
]

HIGH_VALUE_KEYWORDS = [
    "ui/ux",
    "ux",
    "product design",
    "figma",
    "webflow",
    "framer",
    "saas",
    "dashboard",
    "landing page",
    "website redesign",
    "mvp",
    "prototype",
    "design system",
    "pitch deck",
    "presentation",
    "brand identity"
]

NEGATIVE_KEYWORDS = [
    "data entry",
    "translation",
    "proofreader",
    "bookkeeper",
    "accounting",
    "crypto trading",
    "onlyfans",
    "adult",
    "casino",
    "betting",
    "logo only",
    "simple logo"
]


def searchable_text(job: dict) -> str:
    title = get_job_title(job).lower()
    description = get_job_description(job).lower()
    skills_text = get_skills_text(job).lower()
    category = str(get_nested(job, ["category", "name"], "")).lower()
    category_group = str(get_nested(job, ["categoryGroup", "name"], "")).lower()
    source_query = str(job.get("_source_query") or "").lower()

    return f"{title} {description} {skills_text} {category} {category_group} {source_query}"


def job_matches_keywords(job: dict) -> bool:
    text = searchable_text(job)

    for keyword in REQUIRED_KEYWORDS:
        if keyword.lower() in text:
            return True

    return False


def calculate_match_score(job: dict) -> int:
    score = 0
    text = searchable_text(job)

    for keyword in HIGH_VALUE_KEYWORDS:
        if keyword in text:
            score += 8

    if get_payment_verified(job):
        score += 10

    client_spent = get_client_spent_value(job)
    if client_spent >= 100:
        score += 8
    if client_spent >= 1000:
        score += 8
    if client_spent >= 10000:
        score += 8

    client_hires = get_client_hires_count(job)
    if client_hires > 0:
        score += 8
    if client_hires >= 3:
        score += 5

    proposals = get_proposals_count(job)
    if 0 <= proposals < 5:
        score += 12
    elif 5 <= proposals < 10:
        score += 8
    elif 10 <= proposals < 20:
        score += 4
    elif proposals >= 20:
        score -= 10

    budget_value = extract_budget_value(job)
    if 1000 <= budget_value <= 100000:
        score += 10

    hourly_min, hourly_max = get_hourly_min_max(job)
    if hourly_min >= MINIMUM_HOURLY_RATE and hourly_max <= MAXIMUM_HOURLY_RATE and hourly_max > 0:
        score += 8

    project_length = normalize_project_length(get_project_length(job))
    if project_length in ["Less than one month", "1 to 3 months"]:
        score += 8

    freshness = get_freshness_days(job)
    if freshness is not None:
        if freshness <= 1:
            score += 12
        elif freshness <= 3:
            score += 8
        elif freshness <= 7:
            score += 4
        elif freshness > MAX_JOB_AGE_DAYS:
            score -= 20

    for keyword in NEGATIVE_KEYWORDS:
        if keyword in text:
            score -= 25

    return max(0, score)


def passes_strict_filters(job: dict) -> tuple:
    if not job_matches_keywords(job):
        return False, f"no keyword match: {get_job_title(job)[:50]}"

    freshness = get_freshness_days(job)
    if freshness is not None and freshness > MAX_JOB_AGE_DAYS:
        return False, f"job is too old: {freshness} days"

    payment_verified = get_payment_verified(job)

    if REQUIRE_PAYMENT_VERIFIED and not payment_verified:
        return False, "payment not verified"

    if not payment_verified:
        logger.info("Payment is not verified, but REQUIRE_PAYMENT_VERIFIED is False, so job is allowed for testing.")

    client_spent = get_client_spent_value(job)

    if REQUIRE_CLIENT_SPENT and client_spent <= MINIMUM_CLIENT_SPENT:
        return False, f"client spent ${client_spent:.0f} is not above ${MINIMUM_CLIENT_SPENT}"

    if not REQUIRE_CLIENT_SPENT and client_spent <= MINIMUM_CLIENT_SPENT:
        logger.info("Client spent is below threshold or missing, but REQUIRE_CLIENT_SPENT is False, so job is allowed.")

    client_hires = get_client_hires_count(job)

    if REQUIRE_CLIENT_HIRES and client_hires <= 0:
        return False, f"client hires {client_hires} is not above 0"

    if not REQUIRE_CLIENT_HIRES and client_hires <= 0:
        logger.info("Client hires is missing or zero, but REQUIRE_CLIENT_HIRES is False, so job is allowed.")

    proposals = get_proposals_count(job)

    if REQUIRE_PROPOSALS_LIMIT and proposals >= MAXIMUM_PROPOSALS:
        return False, f"proposals {proposals} is not below {MAXIMUM_PROPOSALS}"

    if not REQUIRE_PROPOSALS_LIMIT and proposals >= MAXIMUM_PROPOSALS:
        logger.info("Proposals are above threshold, but REQUIRE_PROPOSALS_LIMIT is False, so job is allowed.")

    project_length_raw = get_project_length(job).lower()

    allowed_lengths = [
        "less than one month",
        "less than 1 month",
        "1 to 3 months",
        "1-3 months"
    ]

    if REQUIRE_PROJECT_LENGTH and project_length_raw:
        if not any(length in project_length_raw for length in allowed_lengths):
            return False, f"project length not allowed: {project_length_raw}"

    if not REQUIRE_PROJECT_LENGTH and project_length_raw:
        if not any(length in project_length_raw for length in allowed_lengths):
            logger.info("Project length is outside preferred range, but REQUIRE_PROJECT_LENGTH is False, so job is allowed.")

    raw_type = str(job.get("type") or "").upper()
    job_type = get_job_type(job).lower()
    budget_value = extract_budget_value(job)

    is_hourly = raw_type == "HOURLY" or "hourly" in job_type
    is_fixed = raw_type == "FIXED" or "fixed" in job_type

    if is_fixed:
        if REQUIRE_BUDGET_RANGE:
            if budget_value <= 0:
                return False, "fixed job has no budget"

            if not (MINIMUM_FIXED_BUDGET <= budget_value <= MAXIMUM_FIXED_BUDGET):
                return False, f"fixed budget ${budget_value:.0f} outside allowed range"

        if not REQUIRE_BUDGET_RANGE:
            if budget_value <= 0:
                logger.info("Fixed job has no budget, but REQUIRE_BUDGET_RANGE is False, so job is allowed.")
            elif not (MINIMUM_FIXED_BUDGET <= budget_value <= MAXIMUM_FIXED_BUDGET):
                logger.info("Fixed budget is outside preferred range, but REQUIRE_BUDGET_RANGE is False, so job is allowed.")

    if is_hourly:
        hourly_min, hourly_max = get_hourly_min_max(job)

        if REQUIRE_HOURLY_RANGE:
            if hourly_min <= 0 or hourly_max <= 0:
                return False, "hourly job has no hourly range"

            if hourly_min < MINIMUM_HOURLY_RATE or hourly_max > MAXIMUM_HOURLY_RATE:
                return False, f"hourly rate {hourly_min}-{hourly_max} outside allowed range"

        if not REQUIRE_HOURLY_RANGE:
            if hourly_min <= 0 or hourly_max <= 0:
                logger.info("Hourly range is missing, but REQUIRE_HOURLY_RANGE is False, so job is allowed.")
            elif hourly_min < MINIMUM_HOURLY_RATE or hourly_max > MAXIMUM_HOURLY_RATE:
                logger.info("Hourly range is outside preferred range, but REQUIRE_HOURLY_RANGE is False, so job is allowed.")

    return True, ""


# =========================================================
# OpenAI Proposal Generation
# =========================================================

def generate_proposal(job: dict) -> tuple:
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY missing. Proposal will be empty.")
        return "", "OPENAI_API_KEY missing"

    prompt = build_proposal_prompt(job)

    payload = {
        "model": OPENAI_MODEL,
        "input": prompt,
        "max_output_tokens": 900
    }

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    last_error = ""

    for attempt in range(1, 4):
        try:
            response = requests.post(
                OPENAI_API_URL,
                headers=headers,
                json=payload,
                timeout=60
            )

            response.raise_for_status()

            data = response.json()
            proposal = data.get("output_text", "")

            if not proposal:
                output = data.get("output", [])
                parts = []

                for item in output:
                    for content in item.get("content", []):
                        text = content.get("text")
                        if text:
                            parts.append(text)

                proposal = "\n".join(parts).strip()

            if not proposal:
                return "", "OpenAI response did not include output text"

            proposal = proposal.replace("```text", "").replace("```md", "").replace("```", "").strip()

            return proposal, f"OK | mode={PROPOSAL_PROMPT_MODE}"

        except requests.exceptions.RequestException as error:
            last_error = str(error)
            logger.error(f"OpenAI proposal generation failed on attempt {attempt}: {error}")

            if hasattr(error, "response") and error.response is not None:
                logger.error(f"OpenAI response: {error.response.text[:1000]}")
                last_error = error.response.text[:1000]

            time.sleep(2 * attempt)

    return "", last_error or "OpenAI request failed after retries"


# =========================================================
# Notion
# =========================================================

def notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION
    }


def get_notion_database() -> dict:
    global _NOTION_DATABASE_CACHE

    if _NOTION_DATABASE_CACHE is not None:
        return _NOTION_DATABASE_CACHE

    database_id = get_jobs_database_id()

    response = requests.get(
        f"{NOTION_API_URL}/databases/{database_id}",
        headers=notion_headers(),
        timeout=30
    )
    response.raise_for_status()

    _NOTION_DATABASE_CACHE = response.json()
    return _NOTION_DATABASE_CACHE


def get_notion_properties() -> dict:
    database = get_notion_database()
    return database.get("properties", {})


def get_title_property_name() -> str:
    properties = get_notion_properties()

    for property_name, property_schema in properties.items():
        if property_schema.get("type") == "title":
            return property_name

    return "Title"


def property_exists(property_name: str) -> bool:
    return property_name in get_notion_properties()


def add_property_if_exists(properties: dict, property_name: str, value: dict):
    if property_exists(property_name):
        properties[property_name] = value
    else:
        logger.warning(f"Skipping Notion property because it does not exist: {property_name}")


def get_existing_jobs() -> tuple:
    logger.info("Checking existing jobs in Notion database...")

    database_id = get_jobs_database_id()

    existing_links = set()
    existing_ids = set()

    has_more = True
    cursor = None

    while has_more:
        payload = {"page_size": 100}

        if cursor:
            payload["start_cursor"] = cursor

        try:
            response = requests.post(
                f"{NOTION_API_URL}/databases/{database_id}/query",
                headers=notion_headers(),
                json=payload,
                timeout=30
            )

            response.raise_for_status()
            data = response.json()

            for page in data.get("results", []):
                props = page.get("properties", {})

                link = props.get("Gig Link", {}).get("url")
                if link:
                    existing_links.add(link.split("?")[0].rstrip("/"))

                job_id_text = props.get("Job ID", {}).get("rich_text", [])
                if job_id_text:
                    plain_text = job_id_text[0].get("plain_text") or ""
                    if plain_text:
                        existing_ids.add(plain_text.strip())

            has_more = data.get("has_more", False)
            cursor = data.get("next_cursor")

        except requests.exceptions.RequestException as error:
            logger.error(f"Error querying Notion: {error}")

            if hasattr(error, "response") and error.response is not None:
                logger.error(f"Response: {error.response.text[:1000]}")

            break

    logger.info(f"Found {len(existing_links)} existing links and {len(existing_ids)} existing job IDs in database")
    return existing_links, existing_ids


def rich_text_property(text: str):
    return {
        "rich_text": [
            {
                "text": {
                    "content": safe_text(text, 1900)
                }
            }
        ]
    }


def select_property(value: str):
    value = safe_text(value, 100)

    if not value:
        value = "Unknown"

    return {
        "select": {
            "name": value
        }
    }


def date_property(iso_value: str):
    if not iso_value:
        return {
            "date": None
        }

    return {
        "date": {
            "start": iso_value
        }
    }


# =========================================================
# Notion Blocks
# =========================================================

def paragraph_block(text: str):
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


def heading_block(title: str):
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {
                        "content": title
                    }
                }
            ]
        }
    }


def callout_block(text: str, emoji: str = "💬"):
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
            "icon": {
                "emoji": emoji
            }
        }
    }


def divider_block():
    return {
        "object": "block",
        "type": "divider",
        "divider": {}
    }


def toggle_block(title: str, children: list):
    return {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {
                        "content": title
                    }
                }
            ],
            "children": children
        }
    }


def add_heading(blocks: list, title: str):
    blocks.append(heading_block(title))


def add_divider(blocks: list):
    blocks.append(divider_block())


def add_callout_chunks(blocks: list, text: str, emoji: str = "💬", chunk_size: int = 1800):
    text = text or ""

    if not text.strip():
        blocks.append(callout_block("No content available.", emoji))
        return

    for index in range(0, len(text), chunk_size):
        chunk = text[index:index + chunk_size]

        if chunk.strip():
            blocks.append(callout_block(chunk, emoji))


def make_paragraph_chunks(text: str, chunk_size: int = 1800):
    blocks = []
    text = text or ""

    for index in range(0, len(text), chunk_size):
        chunk = text[index:index + chunk_size]

        if chunk.strip():
            blocks.append(paragraph_block(chunk))

    if not blocks:
        blocks.append(paragraph_block("No description available."))

    return blocks


# =========================================================
# Add Job to Notion
# =========================================================

def add_job_to_notion(job: dict) -> bool:
    title_property_name = get_title_property_name()
    database_id = get_jobs_database_id()

    title = safe_text(get_job_title(job), 2000)
    description = get_job_description(job)
    job_url = normalize_job_url(job)
    job_id = get_job_id(job)

    budget_display = get_budget_display(job)
    summary = get_job_summary(job)
    job_type = get_job_type(job)
    hourly_rate = get_hourly_rate_text(job)
    project_length_raw = get_project_length(job)
    project_length = normalize_project_length(project_length_raw)
    proposals = get_proposals_count(job)
    client_spent_text = get_client_spent_text(job)
    client_hires = get_client_hires_count(job)
    payment_status = get_payment_status_text(job)
    last_seen = get_last_seen(job)
    skills_text = get_skills_text(job)
    published_iso = get_published_iso(job)
    freshness = get_freshness_days(job)
    match_score = calculate_match_score(job)
    source_query = str(job.get("_source_query") or "")
    category = str(get_nested(job, ["category", "name"], ""))
    category_group = str(get_nested(job, ["categoryGroup", "name"], ""))
    discovered_at = datetime.now(timezone.utc).isoformat()
    discovered_day = datetime.now(timezone.utc).date().isoformat()
    template_name = "Default Proposal Template"

    children = []

    add_heading(children, "Proposal Workflow")
    add_callout_chunks(
        children,
        (
            "After review, tick the Generate Proposal checkbox on this row or page. "
            "That one action is enough: the automation approves the job, requests the "
            "proposal, and starts generation. Do not change statuses manually."
        ),
        "🧠"
    )
    add_divider(children)

    add_heading(children, "Job Summary")
    add_callout_chunks(children, summary or "No summary available.", "🧭")
    add_divider(children)

    add_heading(children, "Job Snapshot")

    snapshot_lines = [
        f"Match Score: {match_score}",
        f"Source Query: {source_query}",
        f"Job Type: {job_type}",
        f"Budget: {budget_display or 'Unknown'}",
        f"Hourly Rate: {hourly_rate or 'Unknown'}",
        f"Project Length: {project_length_raw or 'Unknown'}",
        f"Proposals: {proposals if proposals >= 0 else 'Unknown'}",
        f"Client Spent: {client_spent_text or 'Unknown'}",
        f"Client Hires: {client_hires}",
        f"Payment Status: {payment_status}",
        f"Published At: {published_iso or 'Unknown'}",
        f"Freshness Days: {freshness if freshness is not None else 'Unknown'}",
        f"Last Seen: {last_seen or 'Unknown'}",
        f"Job ID: {job_id or 'Unknown'}",
        f"Category: {category or 'Unknown'}",
        f"Category Group: {category_group or 'Unknown'}",
    ]

    children.append(callout_block("\n".join(snapshot_lines), "📋"))

    if skills_text:
        children.append(callout_block(f"Skills:\n{skills_text}", "🎯"))

    if job_url:
        children.append({
            "object": "block",
            "type": "bookmark",
            "bookmark": {
                "url": job_url
            }
        })

    add_divider(children)

    description_children = make_paragraph_chunks(description[:20000])
    children.append(toggle_block("Full Job Description", description_children))

    properties = {
        title_property_name: {
            "title": [
                {
                    "text": {
                        "content": title
                    }
                }
            ]
        }
    }

    add_property_if_exists(properties, "Status", {"status": {"name": "Draft"}})
    add_property_if_exists(properties, "Generate Proposal", nw.checkbox_property(False))
    add_property_if_exists(properties, "Manager Review", {"status": {"name": "New"}})
    add_property_if_exists(properties, "Proposal Status", {"status": {"name": "Not Requested"}})
    add_property_if_exists(properties, "Match Score", {"number": match_score})
    add_property_if_exists(properties, "Freshness Days", {"number": freshness if freshness is not None else None})
    add_property_if_exists(properties, "Published At", date_property(published_iso))
    add_property_if_exists(properties, "Discovered At", date_property(discovered_at))
    add_property_if_exists(properties, "Discovered Day", date_property(discovered_day))
    add_property_if_exists(properties, "Source Query", rich_text_property(source_query))
    add_property_if_exists(properties, "Job Type", select_property(job_type))
    add_property_if_exists(properties, "Budget", rich_text_property(budget_display))
    add_property_if_exists(properties, "Hourly Rate", rich_text_property(hourly_rate))
    add_property_if_exists(properties, "Project Length", select_property(project_length))
    add_property_if_exists(properties, "Proposals", {"number": proposals if proposals >= 0 else None})
    add_property_if_exists(properties, "Client Spent", rich_text_property(client_spent_text))
    add_property_if_exists(properties, "Client Hires", {"number": client_hires})
    add_property_if_exists(properties, "Payment Status", select_property(payment_status))
    add_property_if_exists(properties, "Gig Link", {"url": job_url if job_url else None})
    add_property_if_exists(properties, "Job ID", rich_text_property(job_id))
    add_property_if_exists(properties, "Skills", rich_text_property(skills_text))
    add_property_if_exists(properties, "Category", rich_text_property(category))
    add_property_if_exists(properties, "Category Group", rich_text_property(category_group))
    add_property_if_exists(properties, "Prompt Template", rich_text_property(template_name))
    add_property_if_exists(properties, "AI Model", rich_text_property(""))
    add_property_if_exists(properties, "Proposal Error", rich_text_property(""))
    add_property_if_exists(properties, "Last Seen", rich_text_property(last_seen))

    payload = {
        "parent": {
            "database_id": database_id
        },
        "properties": properties,
        "children": children
    }

    try:
        response = requests.post(
            f"{NOTION_API_URL}/pages",
            headers=notion_headers(),
            json=payload,
            timeout=30
        )

        response.raise_for_status()

        logger.info(f"Added to Notion: {title[:60]}")
        return True

    except requests.exceptions.RequestException as error:
        logger.error(f"Failed to add '{title[:60]}': {error}")

        if hasattr(error, "response") and error.response is not None:
            logger.error(f"Response: {error.response.text[:1500]}")

        return False


# =========================================================
# Notification
# =========================================================

def send_notification(jobs_added: list, total_scraped: int, duplicates: int):
    if not NOTIFICATION_WEBHOOK_URL:
        return

    job_list = "\n".join([
        f"- {get_job_title(job)[:60]} | Score: {calculate_match_score(job)}"
        for job in jobs_added[:10]
    ])

    if len(jobs_added) > 10:
        job_list += f"\n... and {len(jobs_added) - 10} more"

    message = {
        "text": (
            f"*Upwork Job Scraper Report*\n"
            f"Jobs scraped: {total_scraped}\n"
            f"Duplicates skipped: {duplicates}\n"
            f"New jobs added: {len(jobs_added)}\n\n"
            f"*New Jobs:*\n{job_list}\n\n"
            f"Jobs are ready for review in Notion. Proposal generation now happens only on request."
        )
    }

    try:
        requests.post(NOTIFICATION_WEBHOOK_URL, json=message, timeout=10)
        logger.info("Notification sent")

    except Exception as error:
        logger.error(f"Failed to send notification: {error}")


# =========================================================
# Main
# =========================================================

def run_scraper():
    started_at = nw.now_iso()
    jobs_scraped = 0
    duplicates = 0
    rejected_count = 0
    jobs_added = []

    logger.info("=" * 60)
    logger.info("Starting Upwork Scraper")
    logger.info("=" * 60)

    try:
        if not APIFY_API_TOKEN:
            raise RuntimeError("APIFY_API_TOKEN missing")

        if not NOTION_API_KEY:
            raise RuntimeError("NOTION_API_KEY missing")

        get_jobs_database_id()
        apply_workspace_settings()

        search_configs = nw.load_search_queries()

        if not search_configs:
            raise RuntimeError("No enabled search queries found in Notion")

        all_jobs = []
        seen_keys = set()

        for config in search_configs:
            actor_input = build_apify_input(config)
            source_query = config.get("query", "")

            run_id = run_apify_actor(actor_input)

            if not run_id:
                continue

            run_data = wait_for_run(run_id)

            if run_data.get("status") != "SUCCEEDED":
                logger.warning(f"Skipping failed run for query: {source_query}")
                continue

            items = fetch_dataset_items(run_data)

            for job in items:
                job["_source_query"] = source_query

                job_id = get_job_id(job)
                url = normalize_job_url(job)

                dedupe_key = job_id or url or get_job_title(job)

                if dedupe_key and dedupe_key not in seen_keys:
                    seen_keys.add(dedupe_key)
                    all_jobs.append(job)

        jobs_scraped = len(all_jobs)
        logger.info(f"Total unique jobs scraped: {jobs_scraped}")

        if not all_jobs:
            logger.info("No jobs found. Check Apify quota, actor input, or search queries in Notion.")
            nw.record_run_history(
                run_type="Scraper",
                status="Success",
                started_at=started_at,
                finished_at=nw.now_iso(),
                jobs_scraped=0,
                jobs_added=0,
            )
            return

        filtered_jobs = []

        for job in all_jobs:
            passes, reason = passes_strict_filters(job)

            if passes:
                filtered_jobs.append(job)
            else:
                rejected_count += 1
                logger.info(f"REJECTED: {reason}")

        filtered_jobs.sort(key=calculate_match_score, reverse=True)

        logger.info(f"Jobs passing strict filters: {len(filtered_jobs)}")
        logger.info(f"Jobs rejected by filters: {rejected_count}")

        if not filtered_jobs:
            logger.info("No jobs passed the strict filters.")
            nw.record_run_history(
                run_type="Scraper",
                status="Success",
                started_at=started_at,
                finished_at=nw.now_iso(),
                jobs_scraped=jobs_scraped,
                jobs_added=0,
                rejected=rejected_count,
            )
            return

        existing_links, existing_ids = get_existing_jobs()

        new_jobs = []

        for job in filtered_jobs:
            job_id = get_job_id(job)
            url = normalize_job_url(job)

            if job_id and job_id in existing_ids:
                continue

            if url and url in existing_links:
                continue

            new_jobs.append(job)

        duplicates = len(filtered_jobs) - len(new_jobs)

        logger.info(f"New jobs to add: {len(new_jobs)}")
        logger.info(f"Duplicates skipped: {duplicates}")

        if not new_jobs:
            logger.info("All scraped jobs already exist in Notion.")
            nw.record_run_history(
                run_type="Scraper",
                status="Success",
                started_at=started_at,
                finished_at=nw.now_iso(),
                jobs_scraped=jobs_scraped,
                jobs_added=0,
                duplicates=duplicates,
                rejected=rejected_count,
            )
            return

        for job in new_jobs:
            if add_job_to_notion(job):
                jobs_added.append(job)

            time.sleep(0.4)

        logger.info(f"Summary: {len(jobs_added)}/{len(new_jobs)} jobs added to Notion")

        send_notification(jobs_added, len(all_jobs), duplicates)
        nw.record_run_history(
            run_type="Scraper",
            status="Success",
            started_at=started_at,
            finished_at=nw.now_iso(),
            jobs_scraped=jobs_scraped,
            jobs_added=len(jobs_added),
            duplicates=duplicates,
            rejected=rejected_count,
        )

        logger.info("=" * 60)
        logger.info("Scraper run complete")
        logger.info("=" * 60)

    except Exception as error:
        logger.exception("Scraper run failed")
        nw.record_run_history(
            run_type="Scraper",
            status="Failed",
            started_at=started_at,
            finished_at=nw.now_iso(),
            jobs_scraped=jobs_scraped,
            jobs_added=len(jobs_added),
            duplicates=duplicates,
            rejected=rejected_count,
            error_message=str(error),
        )
        raise


if __name__ == "__main__":
    run_scraper()
