"""
Setup Notion Workspace
======================

Creates and syncs the Notion-first workspace under a single parent page.
"""

from notion_workspace import (
    NOTION_API_KEY,
    NOTION_PARENT_PAGE_ID,
    build_automation_control_schema,
    build_jobs_schema,
    configure_automation_control_table_view,
    configure_jobs_table_view,
    configure_scraper_settings_table_view,
    build_prompt_templates_schema,
    build_run_history_schema,
    build_scraper_settings_schema,
    build_search_queries_schema,
    ensure_database,
    ensure_persian_knowledge_base_page,
    ensure_seed_rows,
    get_database_ids,
    get_default_automation_control_rows,
    get_default_prompt_templates,
    get_default_search_rows,
    record_run_history,
    save_workspace_state,
    sync_default_settings_rows,
)


def main():
    if not NOTION_API_KEY:
        raise RuntimeError("NOTION_API_KEY is missing")

    if not NOTION_PARENT_PAGE_ID:
        raise RuntimeError("NOTION_PARENT_PAGE_ID is missing")

    started_at = None

    try:
        from notion_workspace import now_iso

        started_at = now_iso()

        ids = {
            "jobs": ensure_database(NOTION_PARENT_PAGE_ID, "jobs", build_jobs_schema()),
            "automation_control": ensure_database(
                NOTION_PARENT_PAGE_ID,
                "automation_control",
                build_automation_control_schema(),
            ),
            "search_queries": ensure_database(
                NOTION_PARENT_PAGE_ID,
                "search_queries",
                build_search_queries_schema(),
            ),
            "scraper_settings": ensure_database(
                NOTION_PARENT_PAGE_ID,
                "scraper_settings",
                build_scraper_settings_schema(),
            ),
            "run_history": ensure_database(
                NOTION_PARENT_PAGE_ID,
                "run_history",
                build_run_history_schema(),
            ),
            "prompt_templates": ensure_database(
                NOTION_PARENT_PAGE_ID,
                "prompt_templates",
                build_prompt_templates_schema(),
            ),
        }

        save_workspace_state(ids)

        try:
            configure_jobs_table_view(ids["jobs"])
            print("Configured Jobs management views.")
        except Exception as error:
            print(f"Warning: could not configure Jobs table view automatically: {error}")

        try:
            configure_automation_control_table_view(ids["automation_control"])
            print("Configured Automation Control view.")
        except Exception as error:
            print(f"Warning: could not configure Automation Control view automatically: {error}")

        try:
            configure_scraper_settings_table_view(ids["scraper_settings"])
            print("Configured Scraper Settings view.")
        except Exception as error:
            print(f"Warning: could not configure Scraper Settings table view automatically: {error}")

        ensure_seed_rows(ids["automation_control"], get_default_automation_control_rows(), "Control")
        ensure_seed_rows(ids["search_queries"], get_default_search_rows(), "Query")
        sync_default_settings_rows(ids["scraper_settings"])
        ensure_seed_rows(ids["prompt_templates"], get_default_prompt_templates(), "Template Name")
        ensure_persian_knowledge_base_page(NOTION_PARENT_PAGE_ID)

        ids = get_database_ids(refresh=True)

        print("Notion workspace is ready.")
        print("")
        print("Resolved database IDs:")
        for key, value in ids.items():
            print(f"- {key}: {value}")

        finished_at = now_iso()
        record_run_history(
            run_type="Setup",
            status="Success",
            started_at=started_at,
            finished_at=finished_at,
        )

    except Exception as error:
        from notion_workspace import now_iso

        finished_at = now_iso()
        if started_at:
            record_run_history(
                run_type="Setup",
                status="Failed",
                started_at=started_at,
                finished_at=finished_at,
                error_message=str(error),
            )
        raise


if __name__ == "__main__":
    main()
