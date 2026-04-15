#!/usr/bin/env node
/**
 * jira-sync.js — Jira CLI for the trading project
 *
 * Usage:
 *   node scripts/jira/jira-sync.js "Add 5-minute timeframe liquidity check"
 *   node scripts/jira/jira-sync.js --bug "Fix order execution delay"
 *   node scripts/jira/jira-sync.js "Some task" --no-branch
 *   npm run task "Add 5-minute timeframe liquidity check"
 *   npm run bug  "Fix order execution delay"
 *
 * What it does:
 *   1. Reads Jira credentials from .env (no external deps needed)
 *   2. Fetches your active sprint ID
 *   3. Creates a Jira issue (Task or Bug) with rich description + AC
 *   4. Assigns it to your account and places it in the active sprint
 *   5. Prints the issue key (e.g. DEV-42)
 *   6. Creates and checks out a git branch: feature/DEV-42-short-slug
 */

"use strict";

const https  = require("https");
const { execSync } = require("child_process");
const fs     = require("fs");
const path   = require("path");

// ── 0. Parse CLI args ─────────────────────────────────────────────────────────

const args = process.argv.slice(2);

const isBug      = args.includes("--bug");
const noBranch   = args.includes("--no-branch");
const prompt     = args.filter(a => !a.startsWith("--")).join(" ").trim();

if (!prompt) {
  console.error("❌  Usage: node scripts/jira-sync.js [--bug] [--no-branch] \"<task description>\"");
  process.exit(1);
}

// ── 1. Load .env ──────────────────────────────────────────────────────────────

function loadEnv(envPath) {
  if (!fs.existsSync(envPath)) return {};
  const out = {};
  for (const line of fs.readFileSync(envPath, "utf8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    let val = trimmed.slice(eq + 1).trim();
    // Strip surrounding quotes
    if ((val.startsWith('"') && val.endsWith('"')) ||
        (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    }
    out[key] = val;
  }
  return out;
}

// scripts/jira/* lives two levels below the repo root
const repoRoot   = path.resolve(__dirname, "..", "..");
const env        = loadEnv(path.join(repoRoot, ".env"));

const JIRA_EMAIL   = env.JIRA_EMAIL   || process.env.JIRA_EMAIL   || "";
const JIRA_TOKEN   = env.JIRA_API_TOKEN || process.env.JIRA_API_TOKEN || "";
const JIRA_DOMAIN  = (env.JIRA_BASE_URL || env.JIRA_DOMAIN || "https://ameer1996112.atlassian.net").replace(/\/$/, "");
const JIRA_PROJECT = env.JIRA_PROJECT_KEY || process.env.JIRA_PROJECT_KEY || "DEV";
const JIRA_TYPE_ID = env.JIRA_TASK_TYPE_ID || "10003";
const AMEER_ACCOUNT_ID = "5e77682c79f5ad0c34f09c9c"; // fetched once, stable

if (!JIRA_EMAIL || !JIRA_TOKEN) {
  console.error("❌  JIRA_EMAIL and JIRA_API_TOKEN must be set in .env");
  process.exit(1);
}

const AUTH = Buffer.from(`${JIRA_EMAIL}:${JIRA_TOKEN}`).toString("base64");

// ── 2. HTTP helpers ───────────────────────────────────────────────────────────

function jiraRequest(method, path, body) {
  return new Promise((resolve, reject) => {
    const url   = new URL(JIRA_DOMAIN + path);
    const data  = body ? JSON.stringify(body) : null;
    const opts  = {
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
        try {
          const parsed = raw ? JSON.parse(raw) : {};
          if (res.statusCode >= 400) {
            reject(new Error(`Jira ${res.statusCode}: ${JSON.stringify(parsed?.errors || parsed?.errorMessages || parsed)}`));
          } else {
            resolve(parsed);
          }
        } catch {
          reject(new Error(`Could not parse Jira response: ${raw}`));
        }
      });
    });
    req.on("error", reject);
    if (data) req.write(data);
    req.end();
  });
}

function jiraGet(path, params = {}) {
  const qs = new URLSearchParams(params).toString();
  return jiraRequest("GET", path + (qs ? "?" + qs : ""), null);
}

function jiraPost(path, body) {
  return jiraRequest("POST", path, body);
}

// ── 3. Get active sprint ──────────────────────────────────────────────────────

async function getActiveSprintId() {
  try {
    const boards = await jiraGet("/rest/agile/1.0/board", { projectKeyOrId: JIRA_PROJECT, type: "scrum" });
    let boardList = boards.values || [];
    if (!boardList.length) {
      const all = await jiraGet("/rest/agile/1.0/board", { projectKeyOrId: JIRA_PROJECT });
      boardList = all.values || [];
    }
    if (!boardList.length) return null;
    const boardId = boardList[0].id;
    const sprints = await jiraGet(`/rest/agile/1.0/board/${boardId}/sprint`, { state: "active" });
    const list = sprints.values || [];
    return list.length ? { id: list[0].id, name: list[0].name } : null;
  } catch (e) {
    console.warn("⚠️  Could not fetch active sprint:", e.message);
    return null;
  }
}

// ── 4. Build ADF description ──────────────────────────────────────────────────

function adfHeading(text, level = 2) {
  return { type: "heading", attrs: { level }, content: [{ type: "text", text }] };
}

function adfParagraph(text) {
  return { type: "paragraph", content: [{ type: "text", text }] };
}

function adfBulletList(items) {
  return {
    type: "bulletList",
    content: items.map(item => ({
      type: "listItem",
      content: [{ type: "paragraph", content: [{ type: "text", text: item }] }],
    })),
  };
}

function buildTaskDescription(prompt) {
  return {
    type: "doc", version: 1,
    content: [
      adfHeading("🔍 Problem / Context", 2),
      adfParagraph(prompt),
      adfHeading("✅ Acceptance Criteria", 2),
      adfBulletList([
        "Feature is implemented and manually verified",
        "No regression in related functionality",
        "Code is reviewed and committed with Jira Smart Commit",
        "Tests pass (unit + integration where applicable)",
      ]),
      adfHeading("💡 Implementation Notes", 2),
      adfParagraph("See branch for implementation details. Follow existing code conventions."),
    ],
  };
}

function buildBugDescription(prompt) {
  return {
    type: "doc", version: 1,
    content: [
      adfHeading("🐛 Bug Report", 2),
      adfParagraph(prompt),
      adfHeading("✅ Expected Behavior", 2),
      adfParagraph("(Describe what should happen)"),
      adfHeading("❌ Actual Behavior", 2),
      adfParagraph("(Describe what is actually happening)"),
      adfHeading("🔁 Steps to Reproduce", 2),
      adfBulletList([
        "Step 1: ...",
        "Step 2: ...",
        "Step 3: ...",
      ]),
      adfHeading("✅ Acceptance Criteria", 2),
      adfBulletList([
        "Bug is fixed and verified in the affected flow",
        "Root cause is identified and documented",
        "Regression test added (if applicable)",
        "PR merged with Jira Smart Commit referencing this ticket",
      ]),
    ],
  };
}

// ── 5. Generate a professional title from raw prompt ─────────────────────────

function toTitle(raw) {
  // Capitalise first letter, ensure it ends without trailing period
  const cleaned = raw.trim().replace(/\.$/, "");
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}

// ── 6. Create issue + assign sprint ──────────────────────────────────────────

async function createIssue(title, description, sprintId, isBug) {
  const labels = isBug ? ["type:bug"] : ["type:task"];
  const fields = {
    project: { key: JIRA_PROJECT },
    summary: title,
    issuetype: { id: JIRA_TYPE_ID },
    description,
    labels,
    priority: { name: isBug ? "High" : "Medium" },
    assignee: { accountId: AMEER_ACCOUNT_ID },
    ...(sprintId ? { customfield_10020: sprintId } : {}),
  };

  try {
    const resp = await jiraPost("/rest/api/3/issue", { fields });
    return resp.key;
  } catch (e) {
    // Sprint field might not be on screen — retry without it then move via agile API
    if (e.message.includes("customfield_10020") || e.message.includes("Field 'sprint'")) {
      const { customfield_10020: _, ...fieldsNoSprint } = fields; // eslint-disable-line
      const resp = await jiraPost("/rest/api/3/issue", { fields: fieldsNoSprint });
      const key = resp.key;
      if (sprintId) {
        try {
          await jiraPost(`/rest/agile/1.0/sprint/${sprintId}/issue`, { issues: [key] });
        } catch (e2) {
          console.warn("⚠️  Could not add ticket to sprint via agile API:", e2.message);
        }
      }
      return key;
    }
    throw e;
  }
}

// ── 7. Git branch helper ──────────────────────────────────────────────────────

function createBranch(issueKey, title) {
  const slug = title
    .toLowerCase()
    .replace(/[^a-z0-9 ]/g, "")
    .trim()
    .split(/\s+/)
    .slice(0, 6)
    .join("-");
  const branch = `feature/${issueKey}-${slug}`;

  try {
    // Check if branch already exists
    execSync(`git rev-parse --verify ${branch} 2>/dev/null`, { cwd: repoRoot });
    // Branch exists — just switch
    execSync(`git checkout ${branch}`, { cwd: repoRoot, stdio: "inherit" });
    console.log(`🔀  Switched to existing branch: ${branch}`);
  } catch {
    // Branch doesn't exist — create it
    try {
      execSync(`git checkout -b ${branch}`, { cwd: repoRoot, stdio: "inherit" });
      console.log(`🌿  Created and switched to branch: ${branch}`);
    } catch (err) {
      console.warn("⚠️  Could not create branch (dirty tree?):", err.message.split("\n")[0]);
    }
  }
  return branch;
}

// ── 8. Main ───────────────────────────────────────────────────────────────────

async function main() {
  console.log(`\n🔄  ${isBug ? "🐛 Bug" : "📋 Task"}: ${prompt}\n`);

  const title       = toTitle(prompt);
  const description = isBug ? buildBugDescription(prompt) : buildTaskDescription(prompt);

  // Fetch active sprint
  process.stdout.write("⏳  Fetching active sprint... ");
  const sprint = await getActiveSprintId();
  if (sprint) {
    console.log(`✅  Sprint: ${sprint.name} (ID: ${sprint.id})`);
  } else {
    console.log("⚠️  No active sprint — ticket will be in backlog");
  }

  // Create issue
  process.stdout.write(`⏳  Creating Jira ${isBug ? "bug" : "task"}... `);
  let issueKey;
  try {
    issueKey = await createIssue(title, description, sprint?.id ?? null, isBug);
    console.log(`✅  Created: ${issueKey}`);
  } catch (e) {
    console.error("\n❌  Failed to create Jira issue:", e.message);
    process.exit(1);
  }

  const issueUrl = `${JIRA_DOMAIN}/browse/${issueKey}`;
  console.log(`\n🎫  ${issueKey}: ${title}`);
  console.log(`🔗  ${issueUrl}`);
  console.log(`👤  Assigned to: Ameer Amer`);
  console.log(`🏷   Type: ${isBug ? "Bug" : "Task"} | Priority: ${isBug ? "High" : "Medium"}`);
  if (sprint) console.log(`🏃  Sprint: ${sprint.name}`);

  // Git branch
  if (!noBranch) {
    const branch = createBranch(issueKey, title);
    console.log(`\n✅  Ready to code on branch: ${branch}`);
    console.log(`💡  Smart commit format: feat: [${issueKey}] your message`);
  }

  // Print the key last so scripts can easily capture it
  console.log(`\n${issueKey}`);
}

main().catch(e => {
  console.error("❌  Unexpected error:", e.message);
  process.exit(1);
});
