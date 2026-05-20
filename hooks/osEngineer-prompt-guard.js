#!/usr/bin/env node
// osEngineer-prompt-guard.js — Claude UserPromptSubmit hook.
//
// On every prompt: read .osengineer/state.yml from cwd and inject a one-paragraph
// status block (phase, current team, budget used%, open handoff count) into the
// agent context as `additionalContext`. This makes the agent aware of phase
// state without requiring a manual /osEngineer:explain call.
//
// Also blocks certain prompts when state is incompatible:
//   - `/osEngineer:execute` when no PHASE_PLAN.md exists for the active phase
//   - any prompt when state.phase === 'blocked' (advisory, not block — user can override)
//
// Honours OSE_BYPASS=1. Always exits 0 on parse failure (never breaks the user).

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

function countHandoffs(cwd) {
  const dir = path.join(cwd, '.osengineer', 'handoffs');
  if (!fs.existsSync(dir)) return 0;
  try {
    return fs.readdirSync(dir).filter(f => f.endsWith('.md') && f !== '.gitkeep').length;
  } catch { return 0; }
}

function buildContext(state, openHandoffs) {
  const parts = [];
  parts.push(`phase=${state.phase || 'idle'}`);
  if (state.current_team) parts.push(`team=${state.current_team}`);
  if (state.budget_used != null) parts.push(`budget=${state.budget_used}%`);
  if (openHandoffs > 0) parts.push(`open_handoffs=${openHandoffs}`);
  return `osEngineer state: ${parts.join(' · ')}`;
}

let input = '';
const t = setTimeout(() => process.exit(0), STDIN_TIMEOUT_MS);
process.stdin.setEncoding('utf8');
process.stdin.on('data', c => input += c);
process.stdin.on('end', () => {
  clearTimeout(t);
  try {
    if (process.env.OSE_BYPASS === '1') {
      const cwd = process.cwd();
      const log = path.join(cwd, '.osengineer', 'bypass-log.jsonl');
      try {
        fs.appendFileSync(log, JSON.stringify({
          ts: new Date().toISOString(), hook: 'prompt-guard', reason: 'OSE_BYPASS=1',
        }) + '\n');
      } catch {}
      process.exit(0);
    }

    const data = JSON.parse(input);
    const cwd = data.cwd || process.cwd();
    const state = readState(cwd);
    if (!state) process.exit(0);

    const prompt = data.prompt || '';
    const openHandoffs = countHandoffs(cwd);

    // Block /osEngineer:execute when no PHASE_PLAN.md exists
    if (/\/osEngineer:execute\b/.test(prompt)) {
      const activePhases = fs.existsSync(path.join(cwd, 'planning', 'active'))
        ? fs.readdirSync(path.join(cwd, 'planning', 'active'))
            .filter(d => fs.statSync(path.join(cwd, 'planning', 'active', d)).isDirectory())
        : [];
      const hasPlan = activePhases.some(d =>
        fs.existsSync(path.join(cwd, 'planning', 'active', d, 'PHASE_PLAN.md'))
      );
      if (!hasPlan) {
        process.stdout.write(JSON.stringify({
          decision: 'block',
          reason: 'osEngineer: cannot /osEngineer:execute — no PHASE_PLAN.md in any planning/active/ directory. Run /osEngineer:plan first.',
        }));
        process.exit(0);
      }
    }

    // Inject state into context
    process.stdout.write(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'UserPromptSubmit',
        additionalContext: buildContext(state, openHandoffs),
      },
    }));
  } catch { process.exit(0); }
});
