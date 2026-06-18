#!/usr/bin/env node
// checkpoint.js - PostToolUse hook
// After each Edit/Write/Bash tool call, appends a checkpoint entry to
// .claude/checkpoint.md so sessions can be resumed after quota failures.
//
// Checkpoint format:
//   ## [timestamp] Tool: <tool> | File: <file>
//   <2-sentence context summary from env>
//
// Reads from env:
//   CLAUDE_TOOL_NAME        — tool that just ran
//   CLAUDE_TOOL_INPUT_FILE_PATH — file touched (Edit/Write)
//   CLAUDE_SESSION_ID       — session identifier

const fs = require('fs');
const path = require('path');

const CHECKPOINT_FILE = path.join(process.cwd(), '.claude', 'checkpoint.md');

let input = '';
const stdinTimeout = setTimeout(() => process.exit(0), 10000);
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
  clearTimeout(stdinTimeout);
  try {
    const data = JSON.parse(input || '{}');
    const toolName = data.tool_name || process.env.CLAUDE_TOOL_NAME || 'unknown';

    // Only checkpoint meaningful tools
    const trackedTools = ['Edit', 'Write', 'MultiEdit', 'Bash'];
    if (!trackedTools.includes(toolName)) {
      process.exit(0);
    }

    const ts = new Date().toISOString().replace('T', ' ').slice(0, 19);
    const sessionId = process.env.CLAUDE_SESSION_ID || 'unknown-session';

    // Extract file path from input
    let filePath = '';
    try {
      const toolInput = data.tool_input || {};
      filePath = toolInput.file_path || toolInput.command || '';
      if (filePath.length > 80) filePath = filePath.slice(0, 80) + '...';
    } catch {}

    // Extract output summary (first 200 chars)
    let outputSummary = '';
    try {
      const output = data.tool_result || data.output || '';
      const text = typeof output === 'string' ? output : JSON.stringify(output);
      outputSummary = text.slice(0, 200).replace(/\n/g, ' ');
    } catch {}

    const entry = [
      `\n## [${ts}] Tool: ${toolName}${filePath ? ` | File: ${filePath}` : ''}`,
      `- Session: ${sessionId}`,
      outputSummary ? `- Result: ${outputSummary}` : '',
    ].filter(Boolean).join('\n') + '\n';

    // Ensure file exists with header
    if (!fs.existsSync(CHECKPOINT_FILE)) {
      fs.writeFileSync(CHECKPOINT_FILE,
        '# Session Checkpoint Log\n' +
        '> Auto-generated. Use /handoff to generate a resumption prompt from this file.\n\n'
      );
    }

    // Keep file from growing unbounded — trim to last 100 entries
    let existing = fs.readFileSync(CHECKPOINT_FILE, 'utf8');
    const entries = existing.split('\n## ');
    if (entries.length > 102) { // header + 100 entries + buffer
      const header = entries[0];
      const trimmed = entries.slice(entries.length - 100);
      existing = header + '\n## ' + trimmed.join('\n## ');
      fs.writeFileSync(CHECKPOINT_FILE, existing);
    }

    fs.appendFileSync(CHECKPOINT_FILE, entry);
    process.exit(0);
  } catch {
    process.exit(0);
  }
});
