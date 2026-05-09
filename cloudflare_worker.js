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

function notionHeaders(env) {
  return {
    authorization: `Bearer ${env.NOTION_API_KEY}`,
    "content-type": "application/json",
    "notion-version": env.NOTION_VERSION || "2022-06-28",
  };
}

function getRichTextText(items = []) {
  return items.map((item) => item.plain_text || item.text?.content || "").join("").trim();
}

function getPropertyText(page, name) {
  const property = page.properties?.[name];
  if (!property) return "";

  if (property.type === "title") return getRichTextText(property.title);
  if (property.type === "rich_text") return getRichTextText(property.rich_text);
  if (property.type === "select") return property.select?.name || "";
  if (property.type === "status") return property.status?.name || "";
  if (property.type === "url") return property.url || "";
  if (property.type === "date") return property.date?.start || "";
  if (property.type === "number") return property.number == null ? "" : String(property.number);
  if (property.type === "checkbox") return property.checkbox ? "true" : "false";

  return "";
}

function titleProperty(text) {
  return { title: [{ text: { content: String(text || "").slice(0, 1900) } }] };
}

function richTextProperty(text) {
  const content = String(text || "").slice(0, 1900);
  return content ? { rich_text: [{ text: { content } }] } : { rich_text: [] };
}

function checkboxProperty(value) {
  return { checkbox: Boolean(value) };
}

function statusProperty(value) {
  return value ? { status: { name: String(value).slice(0, 100) } } : { status: null };
}

function dateProperty(value) {
  return value ? { date: { start: value } } : { date: null };
}

function dividerBlock() {
  return { object: "block", type: "divider", divider: {} };
}

function headingBlock(text) {
  return {
    object: "block",
    type: "heading_2",
    heading_2: { rich_text: [{ type: "text", text: { content: String(text || "").slice(0, 1900) } }] },
  };
}

function paragraphBlock(text) {
  return {
    object: "block",
    type: "paragraph",
    paragraph: { rich_text: [{ type: "text", text: { content: String(text || "").slice(0, 1900) } }] },
  };
}

function calloutBlock(text, emoji = "✍️") {
  return {
    object: "block",
    type: "callout",
    callout: {
      rich_text: [{ type: "text", text: { content: String(text || "").slice(0, 1900) } }],
      icon: { emoji },
    },
  };
}

function toggleBlock(title, children) {
  return {
    object: "block",
    type: "toggle",
    toggle: {
      rich_text: [{ type: "text", text: { content: String(title || "").slice(0, 1900) } }],
      children,
    },
  };
}

function chunkText(text, chunkSize = 1800) {
  const value = String(text || "");
  if (!value) return [""];

  const chunks = [];
  for (let index = 0; index < value.length; index += chunkSize) {
    chunks.push(value.slice(index, index + chunkSize));
  }
  return chunks;
}

function blockText(block) {
  const type = block.type || "";
  return getRichTextText(block[type]?.rich_text || []);
}

function normalizeWhitespace(text) {
  return String(text || "").replace(/\s+/g, " ").trim();
}

function truncateText(text, limit) {
  const normalized = normalizeWhitespace(text);
  if (normalized.length <= limit) return normalized;

  const sliced = normalized.slice(0, limit);
  const boundary = Math.max(sliced.lastIndexOf(". "), sliced.lastIndexOf("! "), sliced.lastIndexOf("? "));
  if (boundary >= limit * 0.6) return sliced.slice(0, boundary + 1).trim();

  const space = sliced.lastIndexOf(" ");
  if (space >= limit * 0.8) return sliced.slice(0, space).trim();
  return sliced.trim();
}

function extractKeyJobPoints(description, maxChars = 3500) {
  const lines = String(description || "")
    .split(/\r?\n/)
    .map((line) => normalizeWhitespace(line.replace(/^[-*\s]+/, "")))
    .filter(Boolean);
  const keywords = [
    "need",
    "looking for",
    "must",
    "required",
    "deliver",
    "scope",
    "goal",
    "timeline",
    "budget",
    "experience",
    "task",
    "project",
    "design",
    "figma",
    "webflow",
    "framer",
    "landing page",
    "dashboard",
    "saas",
    "brand",
    "wordpress",
  ];
  const selected = [];
  const seen = new Set();

  for (const line of lines) {
    const lowered = line.toLowerCase();
    if (!keywords.some((keyword) => lowered.includes(keyword))) continue;

    const compact = truncateText(line, 220);
    if (compact && !seen.has(compact)) {
      selected.push(`- ${compact}`);
      seen.add(compact);
    }
    if (selected.join("\n").length >= maxChars) break;
  }

  return selected.length ? truncateText(selected.join("\n"), maxChars) : truncateText(description, maxChars);
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
    payload.entity?.id,
    payload.object?.id,
    payload.data?.id,
    payload.data?.page_id,
    payload.data?.pageId,
    payload.data?.entity?.id,
    payload.data?.object?.id,
  ];

  for (const candidate of candidates) {
    const normalized = normalizePageId(candidate);
    if (normalized) return normalized;
  }

  return "";
}

async function notionRequest(env, path, options = {}) {
  const response = await fetch(`https://api.notion.com/v1${path}`, {
    ...options,
    headers: {
      ...notionHeaders(env),
      ...(options.headers || {}),
    },
  });
  const text = await response.text();
  const body = text ? JSON.parse(text) : {};

  if (!response.ok) {
    throw new Error(`Notion request failed (${response.status}): ${text.slice(0, 1000)}`);
  }

  return body;
}

async function updateNotionPage(env, pageId, properties) {
  return notionRequest(env, `/pages/${pageId}`, {
    method: "PATCH",
    body: JSON.stringify({ properties }),
  });
}

async function listBlockChildren(env, blockId) {
  const results = [];
  let cursor = "";

  do {
    const suffix = cursor ? `?page_size=100&start_cursor=${encodeURIComponent(cursor)}` : "?page_size=100";
    const data = await notionRequest(env, `/blocks/${blockId}/children${suffix}`);
    results.push(...(data.results || []));
    cursor = data.has_more ? data.next_cursor : "";
  } while (cursor);

  return results;
}

async function collectBlockText(env, blockId) {
  const parts = [];
  const children = await listBlockChildren(env, blockId);

  for (const child of children) {
    const text = blockText(child);
    if (text) parts.push(text);
    if (child.has_children) {
      const nested = await collectBlockText(env, child.id);
      if (nested) parts.push(nested);
    }
  }

  return parts.join("\n").trim();
}

async function findDescription(env, pageId) {
  const children = await listBlockChildren(env, pageId);

  for (const child of children) {
    if (child.type === "toggle" && blockText(child) === "Full Job Description") {
      return collectBlockText(env, child.id);
    }
  }

  return collectBlockText(env, pageId);
}

async function findProposalInsertAnchor(env, pageId) {
  const children = await listBlockChildren(env, pageId);

  for (let index = 0; index < children.length; index += 1) {
    if (blockText(children[index]) !== "Proposal Workflow") continue;
    return children[index + 1]?.id || children[index].id;
  }

  return "";
}

function buildProposalPrompt(page, description) {
  const context = {
    title: getPropertyText(page, "Title"),
    budget: getPropertyText(page, "Budget"),
    job_type: getPropertyText(page, "Job Type"),
    hourly_rate: getPropertyText(page, "Hourly Rate"),
    project_length: getPropertyText(page, "Project Length"),
    proposals: getPropertyText(page, "Proposals"),
    client_spent: getPropertyText(page, "Client Spent"),
    client_hires: getPropertyText(page, "Client Hires"),
    payment_status: getPropertyText(page, "Payment Status"),
    skills: getPropertyText(page, "Skills"),
    category: getPropertyText(page, "Category"),
    category_group: getPropertyText(page, "Category Group"),
    source_query: getPropertyText(page, "Source Query"),
    service_line: getPropertyText(page, "Service Line"),
  };

  return `
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
- Target 2 short paragraphs, usually 80-140 words.

JOB DATA:
${JSON.stringify(context)}

FOCUSED JOB BRIEF:
${extractKeyJobPoints(description, Number.parseInt(context.PROPOSAL_MAX_DESCRIPTION_CHARS || "3500", 10))}

Return only the final proposal text.
`.trim();
}

async function generateProposalWithOpenAI(env, page, description) {
  const model = env.OPENAI_MODEL || "gpt-5.1";
  const response = await fetch("https://api.openai.com/v1/responses", {
    method: "POST",
    headers: {
      authorization: `Bearer ${env.OPENAI_API_KEY}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model,
      input: buildProposalPrompt(page, description),
      max_output_tokens: Number.parseInt(env.PROPOSAL_MAX_OUTPUT_TOKENS || "900", 10),
    }),
  });
  const data = await response.json();

  if (!response.ok) {
    throw new Error(`OpenAI request failed (${response.status}): ${JSON.stringify(data).slice(0, 1000)}`);
  }

  let proposal = data.output_text || "";
  if (!proposal && Array.isArray(data.output)) {
    const parts = [];
    for (const item of data.output) {
      for (const content of item.content || []) {
        if (content.text) parts.push(content.text);
      }
    }
    proposal = parts.join("\n").trim();
  }

  proposal = proposal.replace(/```(?:text|md)?/g, "").trim();
  if (!proposal) throw new Error("OpenAI response did not include proposal text");

  return { proposal, model };
}

async function appendProposalBlocks(env, pageId, proposal, model) {
  const blocks = [dividerBlock(), headingBlock("AI Proposal")];
  for (const chunk of chunkText(proposal)) {
    if (chunk.trim()) blocks.push(calloutBlock(chunk, "✍️"));
  }
  blocks.push(toggleBlock("Proposal Metadata", [paragraphBlock(`Model: ${model}\nGenerated by: Cloudflare Worker`)]));

  const after = await findProposalInsertAnchor(env, pageId);
  const payload = after ? { after, children: blocks } : { children: blocks };
  return notionRequest(env, `/blocks/${pageId}/children`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

async function generateProposalDirect(pageId, payload, env) {
  if (!pageId) {
    return dispatchWorkflow("generate_proposal", "", payload, env);
  }
  if (!env.NOTION_API_KEY || !env.OPENAI_API_KEY) {
    return dispatchWorkflow("generate_proposal", pageId, payload, env);
  }

  await updateNotionPage(env, pageId, {
    "Generate Proposal": checkboxProperty(true),
    "Manager Review": statusProperty("Approved"),
    "Proposal Status": statusProperty("Generating"),
    "Proposal Requested At": dateProperty(new Date().toISOString()),
    "Proposal Error": richTextProperty(""),
  });

  try {
    const page = await notionRequest(env, `/pages/${pageId}`);
    const description = await findDescription(env, pageId);
    const { proposal, model } = await generateProposalWithOpenAI(env, page, description);

    await appendProposalBlocks(env, pageId, proposal, model);
    await updateNotionPage(env, pageId, {
      "Generate Proposal": checkboxProperty(true),
      "Manager Review": statusProperty("Approved"),
      "Proposal Status": statusProperty("Ready"),
      "Proposal Generated At": dateProperty(new Date().toISOString()),
      "Proposal Preview": richTextProperty(""),
      "AI Model": richTextProperty(model),
      "AI Notes": richTextProperty(""),
      "Job Summary": richTextProperty(""),
      "Proposal Error": richTextProperty(""),
    });

    return {
      ok: true,
      action: "generate_proposal",
      mode: "direct_worker",
      page_id: pageId,
      model,
    };
  } catch (error) {
    await updateNotionPage(env, pageId, {
      "Generate Proposal": checkboxProperty(false),
      "Proposal Status": statusProperty("Failed"),
      "Proposal Error": richTextProperty(error.message || String(error)),
      "AI Notes": richTextProperty(""),
      "Proposal Preview": richTextProperty(""),
      "Job Summary": richTextProperty(""),
    });
    throw error;
  }
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
      const missingDirectProposalSecrets = [];
      if (!env.NOTION_API_KEY) missingDirectProposalSecrets.push("NOTION_API_KEY");
      if (!env.OPENAI_API_KEY) missingDirectProposalSecrets.push("OPENAI_API_KEY");

      return jsonResponse({
        ok: true,
        service: "notion-github-action-router",
        proposal_mode: missingDirectProposalSecrets.length ? "github_actions_fallback" : "direct_worker",
        direct_proposal_ready: missingDirectProposalSecrets.length === 0,
        missing_direct_proposal_secrets: missingDirectProposalSecrets,
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

      const result =
        action === "generate_proposal"
          ? await generateProposalDirect(pageId, payload, env)
          : await dispatchWorkflow(action, pageId, payload, env);
      return jsonResponse(result);
    } catch (error) {
      if (error instanceof Response) return error;
      return jsonResponse({ ok: false, error: error.message || String(error) }, 500);
    }
  },
};
