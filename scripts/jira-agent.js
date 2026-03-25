#!/usr/bin/env node
/**
 * jira-agent.js — Unified Jira automation agent for Claude Code hooks
 *
 * Commands:
 *   session-start          Read UserPromptSubmit JSON from stdin → update ticket
 *   session-end            Read Stop JSON from stdin → add summary comment
 *   add-comment <key> <msg>  Add a comment to a ticket
 *   set-status  <key> <name> Transition ticket to a named status
 *   branch-ticket [dir]    Print ticket key derived from current git branch
 *   smart-create <prompt> [type]  Create ticket from natural language (type: Task|Bug|Story)
 *   add-progress <key> <msg>     Alias for add-comment with [Progress] prefix
 *
 * Always exits 0 — never blocks Claude Code.
 */

"use strict";

const https   = require("https");
const { execSync } = require("child_process");
const fs      = require("fs");
const path    = require("path");

// ─────────────────────────────────────────────────────────────
// 1. Load .env
// ─────────────────────────────────────────────────────────────

const REPO_ROOT = path.resolve(__dirname, "..");

function loadEnv(p) {
  if (!fs.existsSync(p)) return {};
  const out = {};
  for (const line of fs.readFileSync(p, "utf8").split("\n")) {
    const t = line.trim();
    if (!t || t.startsWith("#")) continue;
    const eq = t.indexOf("=");
    if (eq === -1) continue;
    const key = t.slice(0, eq).trim();
    let val = t.slice(eq + 1).trim();
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    }
    out[key] = val;
  }
  return out;
}

const env = loadEnv(path.join(REPO_ROOT, ".env"));

const JIRA_EMAIL   = env.JIRA_EMAIL   || process.env.JIRA_EMAIL   || "";
const JIRA_TOKEN   = env.JIRA_API_TOKEN || process.env.JIRA_API_TOKEN || "";
const JIRA_DOMAIN  = (env.JIRA_BASE_URL || env.JIRA_DOMAIN || "https://ameer1996112.atlassian.net").replace(/\/$/, "");
const JIRA_PROJECT = env.JIRA_PROJECT_KEY || process.env.JIRA_PROJECT_KEY || "DEV";
const JIRA_TYPE_ID = env.JIRA_TASK_TYPE_ID || "10003";
const AMEER_ACCOUNT_ID = "5e77682c79f5ad0c34f09c9c";

if (!JIRA_EMAIL || !JIRA_TOKEN) {
  // Silent — hooks must never fail loudly
  process.exit(0);
}

const AUTH = Buffer.from(`${JIRA_EMAIL}:${JIRA_TOKEN}`).toString("base64");

// ─────────────────────────────────────────────────────────────
// 2. HTTP helpers
// ─────────────────────────────────────────────────────────────

function jiraRequest(method, urlPath, body) {
  return new Promise((resolve) => {
    const url  = new URL(JIRA_DOMAIN + urlPath);
    const data = body ? JSON.stringify(body) : null;
    const opts = {
      hostname: url.hostname,
      path:     url.pathname + url.search,
      method,
      headers: {
        "Authorization": `Basic ${AUTH}`,
        "Content-Type":  "application/json",
        "Accept":        "application/json",
        ...(data ? { "Content-Length": Buffer.byteLength(data) } : {}),
      },
    };
    const req = https.request(opts, res => {
      let raw = "";
      res.on("data", c => raw += c);
      res.on("end", () => {
        try { resolve({ ok: res.statusCode < 400, status: res.statusCode, body: raw ? JSON.parse(raw) : {} }); }
        catch { resolve({ ok: false, status: res.statusCode, body: {} }); }
      });
    });
    req.on("error", () => resolve({ ok: false, status: 0, body: {} }));
    if (data) req.write(data);
    req.end();
  });
}

const jiraGet  = (p)    => jiraRequest("GET",  p, null);
const jiraPost = (p, b) => jiraRequest("POST", p, b);
const jiraPut  = (p, b) => jiraRequest("PUT",  p, b);

// ─────────────────────────────────────────────────────────────
// 3. Git branch → ticket key
// ─────────────────────────────────────────────────────────────

function detectTicketFromBranch(cwd = REPO_ROOT) {
  try {
    const branch = execSync("git branch --show-current", { cwd, timeout: 5000 }).toString().trim();
    const m = branch.match(/([A-Z]+-\d+)/);
    return m ? m[1] : null;
  } catch {
    return null;
  }
}

// ─────────────────────────────────────────────────────────────
// 4. Jira operations
// ─────────────────────────────────────────────────────────────

async function addComment(issueKey, text) {
  const safe = text.length > 32000 ? text.slice(0, 31997) + "..." : text;
  return jiraPost(`/rest/api/3/issue/${issueKey}/comment`, {
    body: {
      type: "doc", version: 1,
      content: [{ type: "paragraph", content: [{ type: "text", text: safe }] }],
    },
  });
}

async function getTransitions(issueKey) {
  const r = await jiraGet(`/rest/api/3/issue/${issueKey}/transitions`);
  return r.ok ? (r.body.transitions || []) : [];
}

async function setStatus(issueKey, statusName) {
  const transitions = await getTransitions(issueKey);
  const target = transitions.find(t =>
    t.name.toLowerCase() === statusName.toLowerCase() ||
    t.to?.name?.toLowerCase() === statusName.toLowerCase()
  );
  if (!target) {
    // Try fuzzy match
    const fuzzy = transitions.find(t =>
      t.name.toLowerCase().includes(statusName.toLowerCase()) ||
      t.to?.name?.toLowerCase()?.includes(statusName.toLowerCase())
    );
    if (!fuzzy) return false;
    await jiraPost(`/rest/api/3/issue/${issueKey}/transitions`, { transition: { id: fuzzy.id } });
    return true;
  }
  await jiraPost(`/rest/api/3/issue/${issueKey}/transitions`, { transition: { id: target.id } });
  return true;
}

async function getIssue(issueKey) {
  const r = await jiraGet(`/rest/api/3/issue/${issueKey}?fields=summary,status,assignee`);
  return r.ok ? r.body : null;
}

async function createIssue(summary, descriptionText, type = "Task") {
  const description = {
    type: "doc", version: 1,
    content: [{ type: "paragraph", content: [{ type: "text", text: descriptionText }] }],
  };

  // Try to get active sprint
  let sprintId = null;
  try {
    const boards = await jiraGet(`/rest/agile/1.0/board?projectKeyOrId=${JIRA_PROJECT}&type=scrum`);
    const boardList = boards.ok ? (boards.body.values || []) : [];
    if (boardList.length) {
      const sprints = await jiraGet(`/rest/agile/1.0/board/${boardList[0].id}/sprint?state=active`);
      const list = sprints.ok ? (sprints.body.values || []) : [];
      if (list.length) sprintId = list[0].id;
    }
  } catch { /* ignore */ }

  const fields = {
    project: { key: JIRA_PROJECT },
    summary: summary.slice(0, 255),
    issuetype: { id: JIRA_TYPE_ID },
    description,
    assignee: { accountId: AMEER_ACCOUNT_ID },
    priority: { name: type === "Bug" ? "High" : "Medium" },
    labels: [type === "Bug" ? "type:bug" : "type:task"],
    ...(sprintId ? { customfield_10020: sprintId } : {}),
  };

  let r = await jiraPost("/rest/api/3/issue", { fields });

  // Retry without sprint field if it failed
  if (!r.ok && (JSON.stringify(r.body).includes("customfield_10020") || JSON.stringify(r.body).includes("sprint"))) {
    const { customfield_10020: _, ...fieldsNoSprint } = fields;
    r = await jiraPost("/rest/api/3/issue", { fields: fieldsNoSprint });
    if (r.ok && sprintId) {
      await jiraPost(`/rest/agile/1.0/sprint/${sprintId}/issue`, { issues: [r.body.key] });
    }
  }

  return r.ok ? r.body.key : null;
}

// ─────────────────────────────────────────────────────────────
// 5. ADF description helpers
// ─────────────────────────────────────────────────────────────

function buildSessionComment(prompt, sessionId) {
  const ts = new Date().toISOString();
  const lines = [
    `🤖 Claude Code — Session Started`,
    ``,
    `📅 Time: ${ts}`,
    `🔑 Session: ${sessionId || 'unknown'}`,
    ``,
    `📋 Task:`,
    prompt.slice(0, 2000),
  ];
  return lines.join('\n');
}

function buildCompletionComment(summary, sessionId) {
  const ts = new Date().toISOString();
  return [
    `✅ Claude Code Session Completed`,
    `Time: ${ts}`,
    `Session: ${sessionId || "unknown"}`,
    ``,
    `📝 What was done:`,
    summary.slice(0, 3000),
  ].join("\n");
}

// ─────────────────────────────────────────────────────────────
// 6. Read stdin as JSON (for Claude hooks)
// ─────────────────────────────────────────────────────────────

function readStdin() {
  return new Promise((resolve) => {
    let data = "";
    if (process.stdin.isTTY) return resolve(null);
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", chunk => data += chunk);
    process.stdin.on("end", () => {
      try { resolve(JSON.parse(data)); }
      catch { resolve(null); }
    });
    process.stdin.on("error", () => resolve(null));
    // Timeout fallback
    setTimeout(() => resolve(null), 5000);
  });
}

// Extract last assistant message from transcript
function extractLastAssistantMessage(transcript) {
  if (!Array.isArray(transcript)) return "";
  const assistantMsgs = transcript.filter(m => m.role === "assistant");
  if (!assistantMsgs.length) return "";
  const last = assistantMsgs[assistantMsgs.length - 1];
  if (typeof last.content === "string") return last.content.slice(0, 3000);
  if (Array.isArray(last.content)) {
    return last.content
      .filter(b => b.type === "text")
      .map(b => b.text)
      .join("\n")
      .slice(0, 3000);
  }
  return "";
}

function extractUserPrompt(transcript) {
  if (!Array.isArray(transcript)) return "";
  const userMsgs = transcript.filter(m => m.role === "user");
  if (!userMsgs.length) return "";
  const last = userMsgs[userMsgs.length - 1];
  if (typeof last.content === "string") return last.content.slice(0, 2000);
  if (Array.isArray(last.content)) {
    return last.content
      .filter(b => b.type === "text")
      .map(b => b.text)
      .join("\n")
      .slice(0, 2000);
  }
  return "";
}

// ─────────────────────────────────────────────────────────────
// 7. Main command routing
// ─────────────────────────────────────────────────────────────

const [,, command, ...rest] = process.argv;

(async () => {
  try {
    switch (command) {

      // ── session-start: called from UserPromptSubmit hook ──
      case "session-start": {
        const hook = await readStdin();
        if (!hook) process.exit(0);

        const prompt = hook.prompt || extractUserPrompt(hook.transcript) || "";
        const sessionId = hook.session_id || "";

        const ticket = detectTicketFromBranch();
        if (!ticket) process.exit(0); // No ticket on branch, skip silently

        // Set to in_progress
        await setStatus(ticket, "In Progress");

        // Add comment with what was requested
        const comment = buildSessionComment(prompt, sessionId);
        await addComment(ticket, comment);

        console.log(`[jira-agent] Session started on ${ticket}`);
        break;
      }

      // ── session-end: called from Stop hook ──
      case "session-end": {
        const hook = await readStdin();
        if (!hook) process.exit(0);

        const sessionId = hook.session_id || "";
        const summary = extractLastAssistantMessage(hook.transcript);

        const ticket = detectTicketFromBranch();
        if (!ticket || !summary) process.exit(0);

        const comment = buildCompletionComment(summary, sessionId);
        await addComment(ticket, comment);

        console.log(`[jira-agent] Session end comment added to ${ticket}`);
        break;
      }

      // ── add-comment <key> <message> ──
      case "add-comment": {
        const [key, ...msgParts] = rest;
        if (!key) { console.error("Usage: jira-agent.js add-comment <key> <message>"); break; }
        const msg = msgParts.join(" ");
        const r = await addComment(key, msg);
        console.log(r.ok ? `✅ Comment added to ${key}` : `❌ Failed: ${JSON.stringify(r.body)}`);
        break;
      }

      // ── add-progress <key> <message> ──
      case "add-progress": {
        const [key, ...msgParts] = rest;
        if (!key) { console.error("Usage: jira-agent.js add-progress <key> <message>"); break; }
        const msg = `[Progress] ${msgParts.join(" ")}`;
        const r = await addComment(key, msg);
        console.log(r.ok ? `✅ Progress added to ${key}` : `❌ Failed`);
        break;
      }

      // ── set-status <key> <status-name> ──
      case "set-status": {
        const [key, ...nameParts] = rest;
        const statusName = nameParts.join(" ");
        if (!key || !statusName) { console.error("Usage: jira-agent.js set-status <key> <status-name>"); break; }
        const ok = await setStatus(key, statusName);
        console.log(ok ? `✅ ${key} → ${statusName}` : `❌ No matching transition for "${statusName}"`);
        break;
      }

      // ── branch-ticket ──
      case "branch-ticket": {
        const ticket = detectTicketFromBranch(rest[0] || REPO_ROOT);
        if (ticket) { console.log(ticket); }
        else { console.error("No ticket key found in current branch"); process.exit(1); }
        break;
      }

      // ── get-transitions <key> ──
      case "get-transitions": {
        const [key] = rest;
        if (!key) { console.error("Usage: jira-agent.js get-transitions <key>"); break; }
        const transitions = await getTransitions(key);
        transitions.forEach(t => console.log(`  [${t.id}] ${t.name} → ${t.to?.name || "?"}`));
        break;
      }

      // ── smart-create <prompt> [type] ──
      case "smart-create": {
        const [type, ...promptParts] = rest[rest.length - 1]?.match(/^(Bug|Task|Story|Epic)$/i)
          ? [rest[rest.length - 1], ...rest.slice(0, -1)]
          : ["Task", ...rest];
        const prompt = promptParts.join(" ");
        if (!prompt) { console.error("Usage: jira-agent.js smart-create <prompt> [type]"); break; }
        const capitalType = type.charAt(0).toUpperCase() + type.slice(1).toLowerCase();
        const isBug = capitalType === "Bug";
        const prefix = isBug ? "🐛 " : "";
        const title = (prefix + prompt.charAt(0).toUpperCase() + prompt.slice(1)).slice(0, 255);
        const key = await createIssue(title, prompt, capitalType);
        if (key) {
          console.log(`✅ Created ${capitalType}: ${key}`);
          console.log(`🔗 ${JIRA_DOMAIN}/browse/${key}`);
          const slug = prompt.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '').slice(0, 50);
          const branchName = `feature/${key}-${slug}`;
          try {
            execSync(`git checkout -b ${branchName}`, { cwd: REPO_ROOT, stdio: 'pipe' });
            console.log(`🌿 Branch: ${branchName}`);
          } catch {
            // Branch may already exist or git not available — skip silently
          }
        } else {
          console.error("❌ Failed to create issue");
        }
        break;
      }

      // ── mark-done <key> [summary] ──
      case "mark-done": {
        const [key, ...summaryParts] = rest;
        if (!key) { console.error("Usage: jira-agent.js mark-done <key> [summary]"); break; }
        if (summaryParts.length) {
          await addComment(key, `✅ Done: ${summaryParts.join(" ")}`);
        }
        const ok = await setStatus(key, "Done");
        console.log(ok ? `✅ ${key} marked Done` : `⚠️  Could not find Done transition`);
        break;
      }

      // ── get-ticket <key> ──
      case "get-ticket": {
        const [key] = rest;
        if (!key) { console.error("Usage: jira-agent.js get-ticket <key>"); break; }
        const issue = await getIssue(key);
        if (issue) {
          console.log(`${issue.key}: ${issue.fields?.summary}`);
          console.log(`Status: ${issue.fields?.status?.name}`);
          console.log(`🔗 ${JIRA_DOMAIN}/browse/${issue.key}`);
        } else {
          console.error(`❌ Ticket ${key} not found`);
        }
        break;
      }

      default: {
        console.log(`Usage: node scripts/jira-agent.js <command> [args]

Commands:
  session-start              Hook: UserPromptSubmit → set in_progress + add prompt comment
  session-end                Hook: Stop → add completion summary comment
  add-comment <key> <msg>    Add a comment to a ticket
  add-progress <key> <msg>   Add a [Progress] comment to a ticket
  set-status <key> <name>    Transition ticket to a named status (e.g. "In Progress", "Done")
  mark-done <key> [summary]  Mark ticket Done with optional summary
  branch-ticket [dir]        Print ticket key from current git branch
  get-ticket <key>           Show ticket summary and status
  get-transitions <key>      List available transitions for a ticket
  smart-create <prompt> [type]  Create ticket from description (type: Task|Bug|Story)
`);
      }
    }
  } catch (err) {
    // Never crash — hooks must be silent on error
    console.error(`[jira-agent] Error: ${err.message}`);
  }
  process.exit(0);
})();
