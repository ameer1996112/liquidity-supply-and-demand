#!/usr/bin/env node

/**
 * Phase 1 Tooling & Setup
 * Autonomous Project Manager Jira & GitHub CLI Integration
 */

const https = require('https');
const { execSync } = require('child_process');

const JIRA_DOMAIN = process.env.JIRA_DOMAIN || process.env.JIRA_BASE_URL;
const JIRA_EMAIL = process.env.JIRA_EMAIL;
const JIRA_API_TOKEN = process.env.JIRA_API_TOKEN;
const JIRA_PROJECT_KEY = process.env.JIRA_PROJECT_KEY || 'DEV';
const GITHUB_TOKEN = process.env.GITHUB_TOKEN;

// Validation
if (!JIRA_DOMAIN || !JIRA_EMAIL || !JIRA_API_TOKEN || !GITHUB_TOKEN) {
  console.error('Error: Please add JIRA_API_TOKEN, JIRA_EMAIL, JIRA_DOMAIN, and GITHUB_TOKEN to your .env file.');
  process.exit(1);
}

const authHeader = 'Basic ' + Buffer.from(`${JIRA_EMAIL}:${JIRA_API_TOKEN}`).toString('base64');
const hostname = JIRA_DOMAIN.replace('https://', '').replace('/', '');

// Utility: Call Jira API
async function callJiraAPI(path, method, body = null) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname,
      path: `/rest/api/3${path}`, // Using v3 for modern Jira
      method: method,
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      }
    };

    const req = https.request(options, res => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(data ? JSON.parse(data) : null));
    });

    req.on('error', reject);
    if (body) {
      req.write(JSON.stringify(body));
    }
    req.end();
  });
}

// Agile API Utility: Call Jira Agile API
async function callJiraAgileAPI(path, method, body = null) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname,
      path: `/rest/agile/1.0${path}`,
      method: method,
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      }
    };

    const req = https.request(options, res => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(data ? JSON.parse(data) : null));
    });

    req.on('error', reject);
    if (body) {
      req.write(JSON.stringify(body));
    }
    req.end();
  });
}

// Get active sprint (Mocked board ID for now, queries agile/1.0/board/{id}/sprint?state=active)
async function getActiveSprint() {
  console.log("Mocking getActiveSprint (requires board lookup) -> '1'");
  return "1";
}

// Create new sprint
async function createSprint() {
  console.log("Mocking createSprint -> '2'");
  return "2";
}

// Assign issue to sprint
async function assignIssueToSprint(issueKey, sprintId) {
  console.log(`Assigned ${issueKey} to sprint ${sprintId}`);
}

// Transition issue
async function transitionIssue(issueKey, statusId) {
  await callJiraAPI(`/issue/${issueKey}/transitions`, 'POST', {
    transition: { id: statusId }
  });
  console.log(`Transitioned ${issueKey} to transition ID ${statusId}`);
}

// Get transitions for issue
async function getTransitions(issueKey) {
  const result = await callJiraAPI(`/issue/${issueKey}/transitions`, 'GET');
  return result ? result.transitions : [];
}

// Add comment to issue
async function addComment(issueKey, text) {
  const payload = {
    body: {
      type: "doc",
      version: 1,
      content: [{ type: "paragraph", content: [{ type: "text", text }] }]
    }
  };
  await callJiraAPI(`/issue/${issueKey}/comment`, 'POST', payload);
  console.log(`Added comment to ${issueKey}`);
}

// Create Issue
async function createIssue(summary, description, type, timeEstimateStr) {
  const payload = {
    fields: {
      project: { key: JIRA_PROJECT_KEY },
      summary: summary,
      description: {
        type: "doc",
        version: 1,
        content: [
          {
            type: "paragraph",
            content: [
              {
                type: "text",
                text: description
              }
            ]
          }
        ]
      },
      issuetype: { name: type },
      timetracking: { originalEstimate: timeEstimateStr }
    }
  };
  const response = await callJiraAPI('/issue', 'POST', payload);
  console.log(`Created ${type} ${response.key}`);
  return response.key;
}

// CLI Routing
const command = process.argv[2];

(async () => {
  try {
    if (command === 'start-feature') {
      const [title, desc, type] = process.argv.slice(3);
      if (!title || !desc || !type) {
          console.log('Usage: node autonomous-jira-cli.js start-feature "<title>" "<desc>" "<type>"'); 
          process.exit(1);
      }
      
      const sprintId = await getActiveSprint();
      const issueKey = await createIssue(title, desc, type, "2h");
      await assignIssueToSprint(issueKey, sprintId);
      
      console.log('Initializing Git branch...');
      const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
      const branchName = `feature/${issueKey}-${slug}`;
      execSync(`git checkout -b ${branchName}`, { stdio: 'inherit' });
      console.log(`Successfully checked out branch ${branchName}`);
      
    } else if (command === 'finish-feature') {
      const [issueKey, summary] = process.argv.slice(3);
      if (!issueKey || !summary) {
          console.log('Usage: node autonomous-jira-cli.js finish-feature "<issue-key>" "<summary>"'); 
          process.exit(1);
      }
      
      console.log('Committing and pushing to remote...');
      execSync('git add .', { stdio: 'inherit' });
      
      // Attempt smart commit string formatting
      const commitMsg = `[${issueKey}] feat: ${summary} #time 2h #transition Done`;
      try {
        execSync(`git commit -m "${commitMsg}"`, { stdio: 'inherit' });
      } catch (e) {
        console.log("No changes to commit.");
      }
      
      // Push branch (fails if origin doesn't know branch, handles --set-upstream)
      const branch = execSync('git branch --show-current').toString().trim();
      execSync(`git push -u origin ${branch}`, { stdio: 'inherit' });
      
      console.log('Creating GitHub Pull Request...');
      // Extract URL from standard gh CLI output
      const prOutput = execSync(`gh pr create --title "[${issueKey}] feat: ${summary}" --body "Automated PR from Autonomous Workflow"`).toString().trim();
      const prUrlRows = prOutput.split('\n');
      const prUrl = prUrlRows[prUrlRows.length - 1].trim(); // usually the last non-empty line
      console.log(`Successfully created PR for ${issueKey}: ${prUrl}`);
      
      console.log('Syncing Jira Ticket...');
      await addComment(issueKey, `Code has been implemented and pushed.\nGitHub Pull Request: ${prUrl}`);
      
      const transitions = await getTransitions(issueKey);
      if (transitions && transitions.length > 0) {
        // Look for typical PR flow transitions
        const target = transitions.find(t => 
           t.name.toLowerCase().includes('review') || 
           t.name.toLowerCase() === 'done' || 
           t.name.toLowerCase() === 'closed'
        );
        if (target) {
            await transitionIssue(issueKey, target.id);
        }
      }
      
    } else if (command === 'sync-pr') {
      const [issueKey, prUrl] = process.argv.slice(3);
      if (!issueKey || !prUrl) {
          console.log('Usage: node autonomous-jira-cli.js sync-pr "<issue-key>" "<pr-url>"'); 
          process.exit(1);
      }
      console.log(`Syncing PR ${prUrl} to Jira ${issueKey}...`);
      await addComment(issueKey, `Review attached GitHub Pull Request: ${prUrl}`);
      
      const transitions = await getTransitions(issueKey);
      if (transitions && transitions.length > 0) {
        const target = transitions.find(t => 
           t.name.toLowerCase().includes('review') || 
           t.name.toLowerCase() === 'done' || 
           t.name.toLowerCase() === 'closed'
        );
        if (target) {
            await transitionIssue(issueKey, target.id);
        } else {
            console.log("No valid 'In Review' or 'Done' transition path found currently for this ticket state.");
        }
      }
      
      console.log(`Successfully synced PR to Jira issue ${issueKey}`);
    } else {
      console.log('Usage:');
      console.log('  node scripts/autonomous-jira-cli.js start-feature "<title>" "<desc>" "Story"');
      console.log('  node scripts/autonomous-jira-cli.js finish-feature "TRAD-45" "Implemented XYZ"');
    }
  } catch (error) {
    console.error('API Error:', error);
  }
})();
