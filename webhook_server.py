"""
Notion action router.

Receives button/webhook requests from Notion and dispatches the matching GitHub
Actions workflow. Notion remains the manager-facing UI; GitHub remains the
execution engine.
"""

import json
import logging
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
PORT = int(os.getenv("WEBHOOK_PORT", "8787"))
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/notion/proposal-request")
WEBHOOK_SHARED_SECRET = os.getenv("WEBHOOK_SHARED_SECRET", "")
GITHUB_DISPATCH_TOKEN = os.getenv("GITHUB_DISPATCH_TOKEN", "")
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "")
GITHUB_REF = os.getenv("GITHUB_REF", "main")
GITHUB_API_VERSION = os.getenv("GITHUB_API_VERSION", "2022-11-28")
GITHUB_PROPOSAL_WORKFLOW_ID = os.getenv(
    "GITHUB_PROPOSAL_WORKFLOW_ID",
    os.getenv("GITHUB_WORKFLOW_ID", "proposal-worker.yml"),
)
GITHUB_SCRAPER_WORKFLOW_ID = os.getenv("GITHUB_SCRAPER_WORKFLOW_ID", "scraper.yml")

ACTION_ROUTES = {
    "/notion/proposal-request": "generate_proposal",
    "/notion/generate-proposal": "generate_proposal",
    "/notion/run-scraper": "run_scraper",
    "/notion/refresh-workspace": "refresh_workspace",
    "/notion/setup-workspace": "refresh_workspace",
}

ACTION_ALIASES = {
    "proposal": "generate_proposal",
    "proposal-request": "generate_proposal",
    "generate-proposal": "generate_proposal",
    "generate_proposal": "generate_proposal",
    "run-scraper": "run_scraper",
    "run_scraper": "run_scraper",
    "scraper": "run_scraper",
    "refresh-workspace": "refresh_workspace",
    "refresh_workspace": "refresh_workspace",
    "setup-workspace": "refresh_workspace",
    "setup_workspace": "refresh_workspace",
}

ACTION_CONFIG = {
    "generate_proposal": {
        "workflow_id": GITHUB_PROPOSAL_WORKFLOW_ID,
        "inputs": lambda page_id, payload: build_proposal_inputs(page_id),
    },
    "run_scraper": {
        "workflow_id": GITHUB_SCRAPER_WORKFLOW_ID,
        "inputs": lambda page_id, payload: {
            "trigger_source": "notion",
            "setup_only": "false",
        },
    },
    "refresh_workspace": {
        "workflow_id": GITHUB_SCRAPER_WORKFLOW_ID,
        "inputs": lambda page_id, payload: {
            "trigger_source": "notion",
            "setup_only": "true",
        },
    },
}


def normalize_page_id(value: str) -> str:
    return str(value or "").strip().replace("-", "")


def normalize_action(value: str) -> str:
    return ACTION_ALIASES.get(str(value or "").strip().lower(), "")


def extract_page_id(payload: dict) -> str:
    candidates = [
        payload.get("page_id"),
        payload.get("pageId"),
        payload.get("id"),
        payload.get("notion_page_id"),
    ]

    page = payload.get("page")
    if isinstance(page, dict):
        candidates.extend(
            [
                page.get("id"),
                page.get("page_id"),
                page.get("pageId"),
            ]
        )

    data = payload.get("data")
    if isinstance(data, dict):
        candidates.extend(
            [
                data.get("id"),
                data.get("page_id"),
                data.get("pageId"),
            ]
        )

    for candidate in candidates:
        normalized = normalize_page_id(candidate)
        if normalized:
            return normalized

    return ""


def extract_action(payload: dict, path: str, query: dict) -> str:
    if path == WEBHOOK_PATH:
        return "generate_proposal"

    path_action = ACTION_ROUTES.get(path)
    if path_action:
        return path_action

    candidates = [
        payload.get("action"),
        payload.get("type"),
        payload.get("event"),
        query.get("action", [""])[0],
    ]

    data = payload.get("data")
    if isinstance(data, dict):
        candidates.extend([data.get("action"), data.get("type"), data.get("event")])

    for candidate in candidates:
        action = normalize_action(candidate)
        if action:
            return action

    return ""


def build_proposal_inputs(page_id: str) -> dict:
    inputs = {"trigger_source": "notion"}
    if page_id:
        inputs["notion_page_id"] = page_id
    return inputs


def dispatch_workflow(action: str, page_id: str, raw_payload: dict) -> dict:
    if not GITHUB_DISPATCH_TOKEN:
        raise RuntimeError("GITHUB_DISPATCH_TOKEN is missing")

    if not GITHUB_REPOSITORY:
        raise RuntimeError("GITHUB_REPOSITORY is missing")

    action_config = ACTION_CONFIG.get(action)
    if not action_config:
        raise RuntimeError(f"Unsupported action: {action}")

    owner, repo = GITHUB_REPOSITORY.split("/", 1)
    workflow_id = action_config["workflow_id"]
    api_url = (
        f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/"
        f"{workflow_id}/dispatches"
    )

    inputs = action_config["inputs"](page_id, raw_payload)

    payload = {
        "ref": GITHUB_REF,
        "inputs": inputs,
    }

    response = requests.post(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {GITHUB_DISPATCH_TOKEN}",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        },
        json=payload,
        timeout=30,
    )
    response.raise_for_status()

    result = response.json() if response.content else {}
    logger.info(
        "Triggered action %s via workflow %s for page %s",
        action,
        workflow_id,
        page_id or "all requested pages",
    )
    return {
        "ok": True,
        "action": action,
        "workflow_id": workflow_id,
        "ref": GITHUB_REF,
        "inputs": inputs,
        "page_id": page_id,
        "dispatch_result": result,
        "received_keys": sorted(raw_payload.keys()),
    }


class WebhookHandler(BaseHTTPRequestHandler):
    server_version = "NotionActionRouter/2.0"

    def _write_json(self, status_code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/health":
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "notion-action-router",
                    "routes": sorted(ACTION_ROUTES.keys()),
                    "legacy_path": WEBHOOK_PATH,
                },
            )
            return

        if parsed.path in ACTION_ROUTES:
            if WEBHOOK_SHARED_SECRET:
                provided_secret = (
                    self.headers.get("X-Webhook-Secret")
                    or self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
                    or query.get("secret", [""])[0]
                    or query.get("token", [""])[0]
                )
                if provided_secret != WEBHOOK_SHARED_SECRET:
                    self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "Unauthorized"})
                    return

            payload = {
                "page_id": query.get("page_id", [""])[0] or query.get("notion_page_id", [""])[0],
                "action": ACTION_ROUTES[parsed.path],
            }

            try:
                page_id = extract_page_id(payload)
                result = dispatch_workflow(ACTION_ROUTES[parsed.path], page_id, payload)
                self._write_json(HTTPStatus.OK, result)
            except Exception as error:
                logger.exception("Webhook dispatch failed")
                self._write_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": str(error)},
                )
            return

        self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path != WEBHOOK_PATH and parsed.path not in ACTION_ROUTES:
            self._write_json(
                HTTPStatus.NOT_FOUND,
                {
                    "ok": False,
                    "error": "Invalid path",
                    "valid_paths": sorted(ACTION_ROUTES.keys()),
                },
            )
            return

        if WEBHOOK_SHARED_SECRET:
            provided_secret = (
                self.headers.get("X-Webhook-Secret")
                or self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            )
            if provided_secret != WEBHOOK_SHARED_SECRET:
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "Unauthorized"})
                return

        content_length = int(self.headers.get("Content-Length", "0") or 0)
        raw_body = self.rfile.read(content_length) if content_length else b"{}"

        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {}

        try:
            action = extract_action(payload, parsed.path, query)
            if not action:
                self._write_json(
                    HTTPStatus.BAD_REQUEST,
                    {
                        "ok": False,
                        "error": "Missing or unsupported action",
                        "valid_actions": sorted(ACTION_CONFIG.keys()),
                    },
                )
                return

            page_id = extract_page_id(payload)
            result = dispatch_workflow(action, page_id, payload)
            self._write_json(HTTPStatus.OK, result)
        except Exception as error:
            logger.exception("Webhook dispatch failed")
            self._write_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": str(error)},
            )

    def log_message(self, format, *args):
        logger.info("%s - %s", self.address_string(), format % args)


def main():
    server = ThreadingHTTPServer((HOST, PORT), WebhookHandler)
    logger.info(
        "Webhook server listening on http://%s:%s with routes: %s",
        HOST,
        PORT,
        ", ".join(sorted(ACTION_ROUTES.keys())),
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
