"""
Generate proposals only for manager-approved, explicitly requested jobs.
"""

import logging
import os
import time

import notion_workspace as nw
import upwork_scraper as scraper


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("proposal_generator.log", encoding="utf-8"), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


def find_description_toggle(page_id: str) -> str:
    for block in nw.list_block_children(page_id):
        if block.get("type") != "toggle":
            continue

        title = nw.extract_plain_text_from_block(block)
        if title == "Full Job Description":
            return nw.collect_block_text(block["id"]).strip()

    return nw.collect_block_text(page_id).strip()


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
            "Generate Proposal": nw.checkbox_property(False),
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
    nw.update_page(
        page_id,
        {
            "Generate Proposal": nw.checkbox_property(False),
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

    blocks = [
        nw.divider_block(),
        nw.heading_block("AI Proposal"),
    ]
    for chunk in nw.chunk_text(proposal):
        if chunk.strip():
            blocks.append(nw.callout_block(chunk, "✍️"))

    notes = f"Template: {template_name or 'Default Proposal Template'}\nModel: {model_name}"
    blocks.append(nw.toggle_block("Proposal Metadata", nw.blocks_from_text(notes)))
    nw.append_block_children(page_id, blocks)


def get_requested_jobs() -> list[dict]:
    database_id = nw.get_jobs_database_id()
    pages = nw.query_database(database_id)
    requested = []
    target_page_id = os.getenv("NOTION_TARGET_PAGE_ID", "").strip().replace("-", "")

    for page in pages:
        normalized_page_id = page["id"].replace("-", "")

        if target_page_id and normalized_page_id != target_page_id:
            continue

        manager_review = nw.get_plain_text_property(page, "Manager Review")
        proposal_status = nw.get_plain_text_property(page, "Proposal Status")
        proposal_checkbox = nw.get_checkbox_property(page, "Generate Proposal", False)

        if proposal_status == "Generating":
            continue

        if proposal_checkbox or (manager_review == "Approved" and proposal_status == "Requested"):
            requested.append(page)

    return requested


def main():
    started_at = nw.now_iso()
    proposals_generated = 0

    try:
        requested_jobs = get_requested_jobs()
        logger.info("Requested jobs found: %s", len(requested_jobs))

        if not requested_jobs:
            nw.record_run_history(
                run_type="Proposal Generator",
                status="Success",
                started_at=started_at,
                finished_at=nw.now_iso(),
                proposals_generated=0,
            )
            return

        for page in requested_jobs:
            page_id = page["id"]
            title = nw.get_page_title(page)

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
                set_failed(page_id, ai_notes or "Proposal generation returned empty output")
                continue

            set_ready(
                page,
                proposal,
                ai_notes,
                model_name=scraper.OPENAI_MODEL,
                template_name=resolved_template_name or nw.get_plain_text_property(page, "Prompt Template"),
            )
            proposals_generated += 1
            time.sleep(0.5)

        nw.record_run_history(
            run_type="Proposal Generator",
            status="Success",
            started_at=started_at,
            finished_at=nw.now_iso(),
            proposals_generated=proposals_generated,
        )

    except Exception as error:
        logger.exception("Proposal generation run failed")
        nw.record_run_history(
            run_type="Proposal Generator",
            status="Failed",
            started_at=started_at,
            finished_at=nw.now_iso(),
            proposals_generated=proposals_generated,
            error_message=str(error),
        )
        raise


if __name__ == "__main__":
    scraper.apply_workspace_settings()
    main()
