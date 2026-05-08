"""
Minimal webhook receiver for Notion button clicks.

Receives a POST from Notion and triggers the proposal worker workflow in GitHub Actions.
"""

import json
import logging
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

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
GITHUB_WORKFLOW_ID = os.getenv("GITHUB_WORKFLOW_ID", "proposal-worker.yml")


def normalize_page_id(value: str) -> str:
    return str(value or "").strip().replace("-", "")


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


def dispatch_workflow(page_id: str, raw_payload: dict) -> dict:
    if not GITHUB_DISPATCH_TOKEN:
        raise RuntimeError("GITHUB_DISPATCH_TOKEN is missing")

    if not GITHUB_REPOSITORY:
        raise RuntimeError("GITHUB_REPOSITORY is missing")

    owner, repo = GITHUB_REPOSITORY.split("/", 1)
    api_url = (
        f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/"
        f"{GITHUB_WORKFLOW_ID}/dispatches"
    )

    inputs = {}
    if page_id:
        inputs["notion_page_id"] = page_id

    payload = {
        "ref": GITHUB_REF,
        "inputs": inputs,
    }

    response = requests.post(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {GITHUB_DISPATCH_TOKEN}",
            "X-GitHub-Api-Version": "2026-03-10",
        },
        json=payload,
        timeout=30,
    )
    response.raise_for_status()

    result = response.json() if response.content else {}
    logger.info(
        "Triggered workflow %s for page %s",
        GITHUB_WORKFLOW_ID,
        page_id or "all requested pages",
    )
    return {
        "ok": True,
        "page_id": page_id,
        "dispatch_result": result,
        "received_keys": sorted(raw_payload.keys()),
    }


class WebhookHandler(BaseHTTPRequestHandler):
    server_version = "NotionProposalWebhook/1.0"

    def _write_json(self, status_code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "notion-proposal-webhook",
                    "path": WEBHOOK_PATH,
                },
            )
            return

        self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != WEBHOOK_PATH:
            self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Invalid path"})
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
            page_id = extract_page_id(payload)
            result = dispatch_workflow(page_id, payload)
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
    logger.info("Webhook server listening on http://%s:%s%s", HOST, PORT, WEBHOOK_PATH)
    server.serve_forever()


if __name__ == "__main__":
    main()
