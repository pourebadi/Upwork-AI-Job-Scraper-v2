"""
Generate proposals only for manager-approved, explicitly requested jobs.
"""

import logging
import os
import time

import notion_workspace as nw
import setup_notion_workspace as setup_workspace
import upwork_scraper as scraper


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("proposal_generator.log", encoding="utf-8"), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


def get_trigger_source() -> str:
    return os.getenv("RUN_TRIGGER_SOURCE", "schedule").strip().lower() or "schedule"


def has_required_proposal_databases() -> bool:
    ids = nw.get_database_ids()
    required_keys = {
        "jobs",
        "scraper_settings",
        "run_history",
        "prompt_templates",
    }
    return required_keys.issubset({key for key, value in ids.items() if value})


def bootstrap_workspace_if_needed():
    if has_required_proposal_databases():
        return

    logger.info("Missing Notion database IDs; running workspace setup before proposal generation.")
    setup_workspace.main()


def find_description_toggle(page_id: str) -> str:
    for block in nw.list_block_children(page_id):
        if block.get("type") != "toggle":
            continue

        title = nw.extract_plain_text_from_block(block)
        if title == "Full Job Description":
            return nw.collect_block_text(block["id"]).strip()

    return nw.collect_block_text(page_id).strip()


def find_proposal_insert_anchor(page_id: str) -> str:
    blocks = nw.list_block_children(page_id)

    for index, block in enumerate(blocks):
        title = nw.extract_plain_text_from_block(block)
        if title != "Proposal Workflow":
            continue

        if index + 1 < len(blocks):
            return blocks[index + 1]["id"]
        return block["id"]

    return ""


def find_template_by_name(template_name: str):
    return nw.find_prompt_template_page(template_name)


def build_job_payload(page: dict, override_template_name: str = "") -> dict:
    page_id = page["id"]
    description = find_description_toggle(page_id)
    prompt_template = override_template_name or nw.get_plain_text_property(page, "Prompt Template")

    return {
        "id": nw.get_plain_text_property(page, "Job ID"),
        "title": nw.get_page_title(page),
        "description": description,
        "summary": "",
        "type": nw.get_plain_text_property(page, "Job Type"),
        "budget": nw.get_plain_text_property(page, "Budget"),
        "hourlyRate": nw.get_plain_text_property(page, "Hourly Rate"),
        "projectLength": nw.get_plain_text_property(page, "Project Length"),
        "proposals": int(nw.get_number_property(page, "Proposals", -1) or -1),
        "clientSpent": nw.get_plain_text_property(page, "Client Spent"),
        "clientHires": int(nw.get_number_property(page, "Client Hires", 0) or 0),
        "clientPaymentVerified": nw.get_plain_text_property(page, "Payment Status") == "Verified",
        "lastSeen": nw.get_plain_text_property(page, "Last Seen"),
        "publishedAt": nw.get_plain_text_property(page, "Published At"),
        "skills": [item.strip() for item in nw.get_plain_text_property(page, "Skills").split(",") if item.strip()],
        "category": {"name": nw.get_plain_text_property(page, "Category")},
        "categoryGroup": {"name": nw.get_plain_text_property(page, "Category Group")},
        "_source_query": nw.get_plain_text_property(page, "Source Query"),
        "_prompt_template_name": prompt_template,
    }


def set_generating(page_id: str):
    nw.update_page(
        page_id,
        {
            "Generate Proposal": nw.checkbox_property(True),
            "Manager Review": nw.status_property("Approved"),
            "Proposal Status": nw.status_property("Generating"),
            "Proposal Requested At": nw.date_property(nw.now_iso()),
            "Proposal Error": nw.rich_text_property(""),
        },
    )


def set_failed(page_id: str, error_message: str):
    nw.update_page(
        page_id,
        {
            "Generate Proposal": nw.checkbox_property(False),
            "Proposal Status": nw.status_property("Failed"),
            "Proposal Error": nw.rich_text_property(error_message),
            "AI Notes": nw.rich_text_property(""),
            "Proposal Preview": nw.rich_text_property(""),
            "Job Summary": nw.rich_text_property(""),
        },
    )


def set_ready(page: dict, proposal: str, ai_notes: str, model_name: str, template_name: str):
    page_id = page["id"]
    blocks = [
        nw.divider_block(),
        nw.heading_block("AI Proposal"),
    ]
    for chunk in nw.chunk_text(proposal):
        if chunk.strip():
            blocks.append(nw.callout_block(chunk, "✍️"))

    notes = f"Template: {template_name or 'Default Proposal Template'}\nModel: {model_name}"
    blocks.append(nw.toggle_block("Proposal Metadata", nw.blocks_from_text(notes)))

    insert_after = find_proposal_insert_anchor(page_id)
    if insert_after:
        nw.insert_block_children_after(page_id, insert_after, blocks)
    else:
        nw.append_block_children(page_id, blocks)

    nw.update_page(
        page_id,
        {
            "Generate Proposal": nw.checkbox_property(True),
            "Manager Review": nw.status_property("Approved"),
            "Proposal Status": nw.status_property("Ready"),
            "Proposal Generated At": nw.date_property(nw.now_iso()),
            "Proposal Preview": nw.rich_text_property(""),
            "AI Model": nw.rich_text_property(model_name),
            "AI Notes": nw.rich_text_property(""),
            "Job Summary": nw.rich_text_property(""),
            "Proposal Error": nw.rich_text_property(""),
        },
    )


def get_requested_jobs() -> list[dict]:
    database_id = nw.get_jobs_database_id()
    pages = nw.query_database(database_id)
    requested = []
    target_page_id = os.getenv("NOTION_TARGET_PAGE_ID", "").strip().replace("-", "")

    for page in pages:
        normalized_page_id = page["id"].replace("-", "")

        manager_review = nw.get_plain_text_property(page, "Manager Review")
        proposal_status = nw.get_plain_text_property(page, "Proposal Status")
        proposal_checkbox = nw.get_checkbox_property(page, "Generate Proposal", False)

        if target_page_id:
            if normalized_page_id == target_page_id and proposal_status not in {"Generating", "Ready"}:
                requested.append(page)
            continue

        if proposal_status in {"Generating", "Ready"}:
            continue

        if proposal_checkbox or (manager_review == "Approved" and proposal_status == "Requested"):
            requested.append(page)

    return requested


def main():
    started_at = nw.now_iso()
    proposals_generated = 0
    first_job_url = ""
    processed_job_links = []
    job_errors = []

    try:
        requested_jobs = get_requested_jobs()
        logger.info("Requested jobs found: %s", len(requested_jobs))

        if not requested_jobs:
            trigger_source = get_trigger_source()
            target_page_id = os.getenv("NOTION_TARGET_PAGE_ID", "").strip()
            if trigger_source == "schedule" and not target_page_id:
                logger.info("Scheduled proposal check found no requested jobs; skipping Run History record.")
                return

            nw.record_run_history(
                run_type="Proposal Generator",
                status="Success",
                started_at=started_at,
                finished_at=nw.now_iso(),
                proposals_generated=0,
                error_message="No checked jobs found. No proposal was generated.",
            )
            return

        for page in requested_jobs:
            page_id = page["id"]
            title = nw.get_page_title(page)

            try:
                logger.info("Generating proposal for: %s", title[:80])
                set_generating(page_id)

                template_page = find_template_by_name(nw.get_plain_text_property(page, "Prompt Template"))
                resolved_template_name = ""
                if template_page:
                    resolved_template_name = nw.get_page_title(template_page)
                    nw.update_page(page_id, {"Prompt Template": nw.rich_text_property(resolved_template_name)})

                job_payload = build_job_payload(page, override_template_name=resolved_template_name)
                proposal, ai_notes = scraper.generate_proposal(job_payload)

                if not proposal.strip():
                    error_message = ai_notes or "Proposal generation returned empty output"
                    set_failed(page_id, error_message)
                    job_errors.append(f"{title}: {error_message}")
                    continue

                set_ready(
                    page,
                    proposal,
                    ai_notes,
                    model_name=scraper.OPENAI_MODEL,
                    template_name=resolved_template_name or nw.get_plain_text_property(page, "Prompt Template"),
                )
                proposals_generated += 1
                if page.get("url"):
                    if not first_job_url:
                        first_job_url = page["url"]
                    processed_job_links.append(f"{title}: {page['url']}")
                time.sleep(0.5)
            except Exception as error:
                logger.exception("Proposal generation failed for job: %s", title[:80])
                error_message = str(error)
                job_errors.append(f"{title}: {error_message}")
                try:
                    set_failed(page_id, error_message)
                except Exception:
                    logger.exception("Could not mark failed proposal job: %s", title[:80])

        nw.record_run_history(
            run_type="Proposal Generator",
            status="Failed" if job_errors else "Success",
            started_at=started_at,
            finished_at=nw.now_iso(),
            proposals_generated=proposals_generated,
            job_url=first_job_url,
            job_links="\n".join(processed_job_links),
            error_message="\n".join(job_errors),
        )

    except Exception as error:
        logger.exception("Proposal generation run failed")
        nw.record_run_history(
            run_type="Proposal Generator",
            status="Failed",
            started_at=started_at,
            finished_at=nw.now_iso(),
            proposals_generated=proposals_generated,
            job_url=first_job_url,
            job_links="\n".join(processed_job_links),
            error_message=str(error),
        )
        raise


if __name__ == "__main__":
    bootstrap_workspace_if_needed()
    scraper.apply_workspace_settings()
    main()
