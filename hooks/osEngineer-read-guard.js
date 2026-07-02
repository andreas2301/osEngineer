#!/usr/bin/env node
// osEngineer-read-guard.js — Claude PreToolUse hook on Read/Glob/Grep.
//
// Advisory: when an edit is attempted on an existing file inside an osEngineer
// repo, remind the agent to Read first (defends against non-Claude harnesses
// that don't natively enforce read-before-edit).
//
// Claude Code itself enforces read-before-edit natively, so this hook detects
// the Claude Code session and silently exits in that environment.
//
// Origin: adapted from get-shit-done/hooks/gsd-read-guard.js per ADR-001.

'use strict';

const fs = require('fs');
const path = require('path');

const STDIN_TIMEOUT_MS = 3000;

let input = '';
const t = setTimeout(() => process.exit(0), STDIN_TIMEOUT_MS);
process.stdin.setEncoding('utf8');
process.stdin.on('data', c => input += c);
process.stdin.on('end', () => {
  clearTimeout(t);
  try {
    const data = JSON.parse(input);
    const tool = (data.tool_name || '').toLowerCase();
    const isEditTool = tool.includes('write') || tool.includes('edit') || tool.includes('replace');
    if (!isEditTool) process.exit(0);

    // Claude Code enforces read-before-edit natively — skip on CC
    const isClaudeCode =
      (typeof data.session_id === 'string' && data.session_id.length > 0) ||
      process.env.CLAUDE_CODE_ENTRYPOINT ||
      process.env.CLAUDE_CODE_SSE_PORT ||
      process.env.CLAUDE_SESSION_ID ||
      process.env.CLAUDECODE;
    if (isClaudeCode) process.exit(0);

    const filePath = data.tool_input?.file_path || data.tool_input?.path || data.tool_input?.TargetFile || data.tool_input?.AbsolutePath || '';
    if (!filePath) process.exit(0);

    let exists = false;
    try { fs.accessSync(filePath, fs.constants.F_OK); exists = true; } catch {}
    if (!exists) process.exit(0);

    process.stdout.write(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'PreToolUse',
        additionalContext:
          `READ-BEFORE-EDIT REMINDER: ${path.basename(filePath)} exists on disk. ` +
          'If you have not Read it in this session, do so first — the runtime ' +
          'will otherwise reject the edit.',
      },
    }));
  } catch { process.exit(0); }
});
