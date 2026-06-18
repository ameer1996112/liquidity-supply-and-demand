#!/usr/bin/env node
// generate-handoff.js
// Reads .claude/checkpoint.md and generates a resumption prompt
// that can be pasted into a new Claude Code session.
//
// Usage: node .claude/hooks/generate-handoff.js
// Or via /handoff slash command in CLAUDE.md

const fs = require('fs');
const path = require('path');

const CHECKPOINT_FILE = path.join(process.cwd(), '.claude', 'checkpoint.md');
const HANDOFF_FILE = path.join(process.cwd(), '.claude', 'handoff.md');

if (!fs.existsSync(CHECKPOINT_FILE)) {
  console.log('No checkpoint file found. Nothing to hand off.');
  process.exit(0);
}

const content = fs.readFileSync(CHECKPOINT_FILE, 'utf8');
const entries = content.split('\n## ').slice(1); // skip header

if (entries.length === 0) {
  console.log('Checkpoint file is empty. Nothing to hand off.');
  process.exit(0);
}

// Get last 20 entries for context
const recent = entries.slice(-20);

// Extract unique files touched
const filestouched = new Set();
recent.forEach(entry => {
  const match = entry.match(/File: ([^\n|]+)/);
  if (match) filestouched.add(match[1].trim());
});

const lastEntry = recent[recent.length - 1];
const lastTimestamp = (lastEntry.match(/\[([^\]]+)\]/) || [])[1] || 'unknown';

const handoff = `# Session Resumption Prompt
Generated: ${new Date().toISOString()}
Last checkpoint: ${lastTimestamp}

## Paste this into your next Claude Code session:

---
I'm resuming a session that was interrupted. Here's what was in progress:

**Project:** Trading system (PineScript + Python backend + TypeScript/React frontend + Playwright optimizer)

**Files recently touched:**
${[...filestouched].map(f => `- ${f}`).join('\n') || '- (see checkpoint log)'}

**Last ${Math.min(5, recent.length)} actions:**
${recent.slice(-5).map(e => '- ' + e.split('\n')[0].trim()).join('\n')}

**To resume:** Check \`.claude/checkpoint.md\` for full action history, then continue from where I left off. If you're not sure what was in progress, read the most recent checkpoint entries and ask me what I want to do next.
---

## Full recent checkpoint log (last 20 entries):

${recent.map(e => '## ' + e).join('\n')}
`;

fs.writeFileSync(HANDOFF_FILE, handoff);
console.log(`\n✅ Handoff prompt written to .claude/handoff.md`);
console.log(`\nCopy the content between the --- markers and paste into your next session.\n`);
console.log('Preview:');
console.log('─'.repeat(60));
// Print the paste-able section
const start = handoff.indexOf('---');
const end = handoff.indexOf('---', start + 3);
console.log(handoff.slice(start + 3, end).trim());
console.log('─'.repeat(60));
