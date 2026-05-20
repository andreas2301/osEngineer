#!/usr/bin/env node
// osEngineer-pre-edit-guard.js — Claude PreToolUse hook on Write/Edit.
//
// Blocks edits during `discuss`/`plan` phases (planning is read-only by design).
// Blocks edits to `/opt/sovereign-shield/` live system at all times.
// Blocks edits to paths outside the current team's owns_paths (P3+; no-op until
// team contracts ship in P3).
//
// Honours OSE_BYPASS=1.

'use strict';

const fs = require('fs');
const path = require('path');

const STDIN_TIMEOUT_MS = 3000;

function readState(cwd) {
  const statePath = path.join(cwd, '.osengineer', 'state.yml');
  if (!fs.existsSync(statePath)) return null;
  try {
    const raw = fs.readFileSync(statePath, 'utf8');
    const state = {};
    for (const line of raw.split('\n')) {
      const m = line.match(/^(\w+):\s*(.*)$/);
      if (!m) continue;
      const [, k, v] = m;
      state[k] = v.trim().replace(/^["']|["']$/g, '') || null;
    }
    return state;
  } catch { return null; }
}

let input = '';
const t = setTimeout(() => process.exit(0), STDIN_TIMEOUT_MS);
process.stdin.setEncoding('utf8');
process.stdin.on('data', c => input += c);
process.stdin.on('end', () => {
  clearTimeout(t);
  try {
    if (process.env.OSE_BYPASS === '1') process.exit(0);

    const data = JSON.parse(input);
    const tool = data.tool_name;
    if (tool !== 'Write' && tool !== 'Edit' && tool !== 'NotebookEdit') process.exit(0);

    const cwd = data.cwd || process.cwd();
    const filePath = data.tool_input?.file_path || data.tool_input?.path || '';

    // Always block live-system edits
    if (filePath.includes('/opt/sovereign-shield/') || filePath.startsWith('/opt/sovereign-shield')) {
      process.stdout.write(JSON.stringify({
        decision: 'block',
        reason: 'osEngineer: edits to /opt/sovereign-shield/ are forbidden — that path is the live system. Edit in workbench and deploy via install-guide. Bypass with OSE_BYPASS=1 if absolutely necessary.',
      }));
      process.exit(0);
    }

    const state = readState(cwd);
    if (!state) process.exit(0); // not an osEngineer repo

    // Block edits during discuss/plan phases
    if (state.phase === 'discuss' || state.phase === 'plan') {
      // Allow edits inside planning/ and .osengineer/ — those ARE the planning artifacts
      const rel = path.relative(cwd, filePath);
      const allowed = /^(planning|\.osengineer)[/\\]/.test(rel);
      if (!allowed) {
        process.stdout.write(JSON.stringify({
          decision: 'block',
          reason: `osEngineer: cannot edit ${path.basename(filePath)} during ${state.phase} phase — only planning/ and .osengineer/ artifacts are editable. Transition to execute phase first.`,
        }));
        process.exit(0);
      }
    }

    // owns_paths enforcement is P3+; no-op until team contracts exist.
    process.exit(0);
  } catch { process.exit(0); }
});
