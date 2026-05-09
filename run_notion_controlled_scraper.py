"""
Run Notion-controlled scraper actions.

Managers should only need one visible action in Notion:
- check "Fetch New Jobs" in Automation Control

The workflow wakes up regularly from GitHub Actions. It checks requested
proposals on every scheduled wake-up and runs the scraper only when its
3-hour interval is due. It can also run immediately when Notion sends a
webhook or when an admin starts it manually.
"""

from datetime import datetime, timezone
import logging
import os

import generate_requested_proposals as proposal_runner
import notion_workspace as nw
import setup_notion_workspace as setup_workspace
import upwork_scraper as scraper


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)
SCHEDULED_SCRAPER_INTERVAL_HOURS = int(os.getenv("SCHEDULED_SCRAPER_INTERVAL_HOURS", "3"))


def is_true(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def update_control_row(page_id: str, properties: dict):
    if not page_id:
        return
    nw.update_page(page_id, properties)


def parse_iso_datetime(value: str):
    if not value:
        return None

    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def is_scheduled_scraper_due(control_row: dict) -> bool:
    if not control_row:
        return True

    last_run = (
        parse_iso_datetime(nw.get_plain_text_property(control_row, "Last Scraper Run At"))
        or parse_iso_datetime(nw.get_plain_text_property(control_row, "Last Fetch At"))
    )
    if not last_run:
        return True

    elapsed_seconds = (nw.now_utc() - last_run).total_seconds()
    return elapsed_seconds >= SCHEDULED_SCRAPER_INTERVAL_HOURS * 3600


def has_required_scraper_databases() -> bool:
    ids = nw.get_database_ids()
    required_keys = {
        "jobs",
        "automation_control",
        "search_queries",
        "scraper_settings",
        "run_history",
        "prompt_templates",
    }
    return required_keys.issubset({key for key, value in ids.items() if value})


def main():
    trigger_source = os.getenv("RUN_TRIGGER_SOURCE", "schedule").strip().lower() or "schedule"
    setup_only = is_true(os.getenv("SETUP_ONLY", "false"))
    control_row = nw.get_primary_automation_control_row()
    control_row_id = control_row["id"] if control_row else ""

    fetch_new_jobs = nw.get_checkbox_property(control_row, "Fetch New Jobs", False) if control_row else False
    run_scraper_now = nw.get_checkbox_property(control_row, "Run Scraper Now", False) if control_row else False
    refresh_workspace_now = (
        nw.get_checkbox_property(control_row, "Refresh Workspace Now", False) if control_row else False
    )
    scheduled_trigger = trigger_source == "schedule"
    scheduled_scrape_due = scheduled_trigger and is_scheduled_scraper_due(control_row)

    should_refresh_workspace = setup_only or refresh_workspace_now
    should_run_scraper = (
        (trigger_source in {"manual", "notion"} and not setup_only)
        or fetch_new_jobs
        or run_scraper_now
        or scheduled_scrape_due
    )
    should_check_proposals = scheduled_trigger or (trigger_source in {"manual", "notion"} and not setup_only)

    if not should_refresh_workspace and not should_run_scraper and not should_check_proposals:
        logger.info("No Notion-controlled scraper action requested.")
        return

    action_parts = []
    if should_refresh_workspace:
        action_parts.append("Refresh Workspace")
    if should_run_scraper:
        if scheduled_scrape_due:
            action_parts.append("Scheduled Scraper")
        elif trigger_source == "notion":
            action_parts.append("Notion Scraper")
        else:
            action_parts.append("Manual Scraper")
    if should_check_proposals:
        action_parts.append("Proposal Check")
    action_label = " + ".join(action_parts)

    if should_run_scraper:
        start_message = "Fetching new jobs and checking requested proposals..."
    elif should_refresh_workspace:
        start_message = "Refreshing workspace..."
    else:
        start_message = "Checking requested proposals..."
    update_control_row(
        control_row_id,
        {
            "Fetch Status": nw.status_property("Running" if should_run_scraper else "Idle"),
            "Last Action": nw.rich_text_property(action_label),
            "Last Result": nw.status_property("Running"),
            "Last Message": nw.rich_text_property(start_message),
        },
    )

    try:
        should_bootstrap_workspace = (should_run_scraper or should_check_proposals) and not has_required_scraper_databases()

        if should_refresh_workspace or should_bootstrap_workspace:
            if should_bootstrap_workspace:
                logger.info("Missing Notion database IDs; running workspace setup before automation.")
            setup_workspace.main()

        updates = {
            "Fetch Status": nw.status_property("Success" if should_run_scraper else "Idle"),
            "Last Action": nw.rich_text_property(action_label),
            "Last Result": nw.status_property("Success"),
            "Last Message": nw.rich_text_property("Done. Jobs/proposals checked."),
        }
        settings_applied = False

        if should_refresh_workspace:
            updates["Refresh Workspace Now"] = nw.checkbox_property(False)
            updates["Last Workspace Refresh At"] = nw.date_property(nw.now_iso())

        if should_run_scraper:
            scraper.apply_workspace_settings()
            settings_applied = True
            scraper.run_scraper()
            finished_at = nw.now_iso()
            updates["Fetch New Jobs"] = nw.checkbox_property(False)
            updates["Last Completed At"] = nw.date_property(finished_at)
            updates["Last Fetch At"] = nw.date_property(finished_at)
            updates["Last Scraper Run At"] = nw.date_property(finished_at)
            if run_scraper_now:
                updates["Run Scraper Now"] = nw.checkbox_property(False)
        elif fetch_new_jobs:
            updates["Fetch New Jobs"] = nw.checkbox_property(False)

        if should_check_proposals:
            if not settings_applied:
                scraper.apply_workspace_settings()
            proposal_runner.main()

        if "Last Completed At" not in updates:
            updates["Last Completed At"] = nw.date_property(nw.now_iso())

        update_control_row(control_row_id, updates)

    except Exception as error:
        logger.exception("Notion-controlled scraper run failed")
        failed_at = nw.now_iso()
        update_control_row(
            control_row_id,
            {
                "Fetch Status": nw.status_property("Failed"),
                "Last Action": nw.rich_text_property(action_label),
                "Last Result": nw.status_property("Failed"),
                "Last Completed At": nw.date_property(failed_at),
                "Last Message": nw.rich_text_property(str(error)),
            },
        )
        raise


if __name__ == "__main__":
    main()
