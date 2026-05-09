const ACTION_ROUTES = {
  "/health": "health",
  "/notion/proposal-request": "generate_proposal",
  "/notion/generate-proposal": "generate_proposal",
  "/notion/run-scraper": "run_scraper",
  "/notion/refresh-workspace": "refresh_workspace",
  "/notion/setup-workspace": "refresh_workspace",
};

const ACTION_ALIASES = {
  proposal: "generate_proposal",
  "proposal-request": "generate_proposal",
  "generate-proposal": "generate_proposal",
  generate_proposal: "generate_proposal",
  "run-scraper": "run_scraper",
  run_scraper: "run_scraper",
  scraper: "run_scraper",
  "refresh-workspace": "refresh_workspace",
  refresh_workspace: "refresh_workspace",
  "setup-workspace": "refresh_workspace",
  setup_workspace: "refresh_workspace",
};

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload, null, 2), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
    },
  });
}

function normalizeAction(value) {
  return ACTION_ALIASES[String(value || "").trim().toLowerCase()] || "";
}

function normalizePageId(value) {
  return String(value || "").trim().replaceAll("-", "");
}

function extractPageId(payload, url) {
  const candidates = [
    url.searchParams.get("page_id"),
    url.searchParams.get("notion_page_id"),
    payload.page_id,
    payload.pageId,
    payload.id,
    payload.notion_page_id,
    payload.page?.id,
    payload.page?.page_id,
    payload.page?.pageId,
    payload.data?.id,
    payload.data?.page_id,
    payload.data?.pageId,
  ];

  for (const candidate of candidates) {
    const normalized = normalizePageId(candidate);
    if (normalized) return normalized;
  }

  return "";
}

function extractAction(payload, url) {
  const pathAction = ACTION_ROUTES[url.pathname];
  if (pathAction && pathAction !== "health") return pathAction;

  const candidates = [
    url.searchParams.get("action"),
    payload.action,
    payload.type,
    payload.event,
    payload.data?.action,
    payload.data?.type,
    payload.data?.event,
  ];

  for (const candidate of candidates) {
    const action = normalizeAction(candidate);
    if (action) return action;
  }

  return "";
}

function buildWorkflowConfig(action, pageId, env) {
  const proposalWorkflow = env.GITHUB_PROPOSAL_WORKFLOW_ID || "proposal-worker.yml";
  const scraperWorkflow = env.GITHUB_SCRAPER_WORKFLOW_ID || "scraper.yml";

  if (action === "generate_proposal") {
    const inputs = { trigger_source: "notion" };
    if (pageId) inputs.notion_page_id = pageId;
    return { workflowId: proposalWorkflow, inputs };
  }

  if (action === "run_scraper") {
    return {
      workflowId: scraperWorkflow,
      inputs: { trigger_source: "notion", setup_only: "false" },
    };
  }

  if (action === "refresh_workspace") {
    return {
      workflowId: scraperWorkflow,
      inputs: { trigger_source: "notion", setup_only: "true" },
    };
  }

  throw new Error(`Unsupported action: ${action}`);
}

async function readJson(request) {
  if (request.method === "GET") return {};
  const text = await request.text();
  if (!text.trim()) return {};

  try {
    return JSON.parse(text);
  } catch {
    return {};
  }
}

function assertAuthorized(request, url, env) {
  const expected = env.WEBHOOK_SHARED_SECRET || "";
  if (!expected) return;

  const provided =
    request.headers.get("x-webhook-secret") ||
    request.headers.get("authorization")?.replace(/^Bearer\s+/i, "").trim() ||
    url.searchParams.get("secret") ||
    url.searchParams.get("token") ||
    "";

  if (provided !== expected) {
    throw new Response(JSON.stringify({ ok: false, error: "Unauthorized" }), {
      status: 401,
      headers: { "content-type": "application/json; charset=utf-8" },
    });
  }
}

async function dispatchWorkflow(action, pageId, payload, env) {
  if (!env.GITHUB_DISPATCH_TOKEN) {
    throw new Error("GITHUB_DISPATCH_TOKEN is missing");
  }

  if (!env.GITHUB_REPOSITORY) {
    throw new Error("GITHUB_REPOSITORY is missing");
  }

  const [owner, repo] = env.GITHUB_REPOSITORY.split("/");
  if (!owner || !repo) {
    throw new Error("GITHUB_REPOSITORY must look like owner/repo");
  }

  const { workflowId, inputs } = buildWorkflowConfig(action, pageId, env);
  const githubUrl = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflowId}/dispatches`;

  const response = await fetch(githubUrl, {
    method: "POST",
    headers: {
      accept: "application/vnd.github+json",
      authorization: `Bearer ${env.GITHUB_DISPATCH_TOKEN}`,
      "content-type": "application/json",
      "user-agent": "notion-github-action-router",
      "x-github-api-version": env.GITHUB_API_VERSION || "2022-11-28",
    },
    body: JSON.stringify({
      ref: env.GITHUB_REF || "main",
      inputs,
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`GitHub dispatch failed (${response.status}): ${body}`);
  }

  return {
    ok: true,
    action,
    workflow_id: workflowId,
    ref: env.GITHUB_REF || "main",
    inputs,
    page_id: pageId,
    received_keys: Object.keys(payload).sort(),
  };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return jsonResponse({
        ok: true,
        service: "notion-github-action-router",
        routes: Object.keys(ACTION_ROUTES).filter((route) => route !== "/health"),
      });
    }

    if (!ACTION_ROUTES[url.pathname]) {
      return jsonResponse(
        {
          ok: false,
          error: "Not found",
          routes: Object.keys(ACTION_ROUTES).filter((route) => route !== "/health"),
        },
        404,
      );
    }

    if (!["GET", "POST"].includes(request.method)) {
      return jsonResponse({ ok: false, error: "Method not allowed" }, 405);
    }

    try {
      assertAuthorized(request, url, env);
      const payload = await readJson(request);
      const action = extractAction(payload, url);
      const pageId = extractPageId(payload, url);

      if (!action) {
        return jsonResponse({ ok: false, error: "Missing or unsupported action" }, 400);
      }

      const result = await dispatchWorkflow(action, pageId, payload, env);
      return jsonResponse(result);
    } catch (error) {
      if (error instanceof Response) return error;
      return jsonResponse({ ok: false, error: error.message || String(error) }, 500);
    }
  },
};
