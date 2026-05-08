"""
Setup Notion Workspace
======================

Creates and syncs the Notion-first workspace under a single parent page.
"""

from notion_workspace import (
    NOTION_API_KEY,
    NOTION_PARENT_PAGE_ID,
    build_jobs_schema,
    configure_jobs_table_view,
    build_prompt_templates_schema,
    build_run_history_schema,
    build_scraper_settings_schema,
    build_search_queries_schema,
    ensure_database,
    ensure_seed_rows,
    get_database_ids,
    get_default_prompt_templates,
    get_default_search_rows,
    get_default_settings_rows,
    record_run_history,
    save_workspace_state,
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
            print("Configured Jobs views: Jobs Table, Today, Approved, Proposal Ready.")
        except Exception as error:
            print(f"Warning: could not configure Jobs table view automatically: {error}")

        ensure_seed_rows(ids["search_queries"], get_default_search_rows(), "Query")
        ensure_seed_rows(ids["scraper_settings"], get_default_settings_rows(), "Setting")
        ensure_seed_rows(ids["prompt_templates"], get_default_prompt_templates(), "Template Name")

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
