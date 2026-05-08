"""
Run Notion-controlled scraper actions.

This worker lets non-technical managers trigger automation fully from Notion:
- check "Run Scraper Now" in Automation Control
- check "Refresh Workspace Now" in Automation Control

The GitHub workflow polls Notion on a short schedule and runs only when a
manual request exists or when the normal 6-hour scraper window is due.
"""

import logging
import os

import notion_workspace as nw
import setup_notion_workspace as setup_workspace
import upwork_scraper as scraper


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


def is_true(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def is_scheduled_scraper_window() -> bool:
    now = nw.now_utc()
    return now.minute == 0 and now.hour % 6 == 0


def update_control_row(page_id: str, properties: dict):
    if not page_id:
        return
    nw.update_page(page_id, properties)


def main():
    trigger_source = os.getenv("RUN_TRIGGER_SOURCE", "schedule").strip().lower() or "schedule"
    setup_only = is_true(os.getenv("SETUP_ONLY", "false"))
    control_row = nw.get_primary_automation_control_row()
    control_row_id = control_row["id"] if control_row else ""

    run_scraper_now = nw.get_checkbox_property(control_row, "Run Scraper Now", False) if control_row else False
    refresh_workspace_now = (
        nw.get_checkbox_property(control_row, "Refresh Workspace Now", False) if control_row else False
    )
    scheduled_scrape_due = trigger_source == "schedule" and is_scheduled_scraper_window()

    should_refresh_workspace = setup_only or refresh_workspace_now
    should_run_scraper = (
        (trigger_source in {"manual", "notion"} and not setup_only)
        or run_scraper_now
        or scheduled_scrape_due
    )

    if not should_refresh_workspace and not should_run_scraper:
        logger.info("No Notion-controlled scraper action requested.")
        return

    action_parts = []
    if should_refresh_workspace:
        action_parts.append("Refresh Workspace")
    if should_run_scraper:
        action_parts.append("Run Scraper")
    action_label = " + ".join(action_parts)

    update_control_row(
        control_row_id,
        {
            "Last Action": nw.rich_text_property(action_label),
            "Last Result": nw.status_property("Running"),
            "Last Message": nw.rich_text_property(f"Started via {trigger_source}."),
        },
    )

    try:
        setup_workspace.main()

        updates = {
            "Last Action": nw.rich_text_property(action_label),
            "Last Result": nw.status_property("Success"),
            "Last Completed At": nw.date_property(nw.now_iso()),
            "Last Message": nw.rich_text_property(f"Completed via {trigger_source}."),
        }

        if should_refresh_workspace or should_run_scraper:
            updates["Refresh Workspace Now"] = nw.checkbox_property(False)
            updates["Last Workspace Refresh At"] = nw.date_property(nw.now_iso())

        if should_run_scraper:
            scraper.apply_workspace_settings()
            scraper.run_scraper()
            updates["Last Scraper Run At"] = nw.date_property(nw.now_iso())
            if run_scraper_now:
                updates["Run Scraper Now"] = nw.checkbox_property(False)

        update_control_row(control_row_id, updates)

    except Exception as error:
        logger.exception("Notion-controlled scraper run failed")
        update_control_row(
            control_row_id,
            {
                "Last Action": nw.rich_text_property(action_label),
                "Last Result": nw.status_property("Failed"),
                "Last Completed At": nw.date_property(nw.now_iso()),
                "Last Message": nw.rich_text_property(str(error)),
            },
        )
        raise


if __name__ == "__main__":
    main()
