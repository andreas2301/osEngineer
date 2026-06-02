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
// Honors OSE_BYPASS=1. Always exits 0 on parse failure (never breaks the user).

'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');

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

    // Debounced and Incremental State Injection
    const sessionId = data.session_id || 'default';
    let additionalContext = '';
    const stateStr = buildContext(state, openHandoffs);
    
    if (sessionId && !/[/\\]|\.\./.test(sessionId)) {
      // 1. Read token remaining capacity to assess risk of compaction amnesia
      let remainingPercent = 100;
      const metricsPath = path.join(os.tmpdir(), `claude-ctx-${sessionId}.json`);
      if (fs.existsSync(metricsPath)) {
        try {
          const metrics = JSON.parse(fs.readFileSync(metricsPath, 'utf8'));
          if (metrics.remaining_percentage != null) {
            remainingPercent = metrics.remaining_percentage;
          }
        } catch {}
      }

      const bridgePath = path.join(os.tmpdir(), `claude-ose-prompt-${sessionId}.json`);
      let sessionData = { lastStateString: '', turnCounter: 0 };
      if (fs.existsSync(bridgePath)) {
        try { sessionData = JSON.parse(fs.readFileSync(bridgePath, 'utf8')); } catch {}
      }
      
      if (remainingPercent <= 40) {
        // Enforce Amnesia Guard to keep critical guidelines and active plans in active memory
        const activePhases = fs.existsSync(path.join(cwd, 'planning', 'active'))
          ? fs.readdirSync(path.join(cwd, 'planning', 'active'))
              .filter(d => fs.statSync(path.join(cwd, 'planning', 'active', d)).isDirectory())
          : [];
        let planSummary = 'No active PHASE_PLAN.md found.';
        for (const phaseDir of activePhases) {
          const planPath = path.join(cwd, 'planning', 'active', phaseDir, 'PHASE_PLAN.md');
          if (fs.existsSync(planPath)) {
            try {
              // Read first 15 lines of the active plan to preserve high-level goals without wasting tokens
              const planLines = fs.readFileSync(planPath, 'utf8').split('\n').slice(0, 15).join('\n');
              planSummary = `Active Phase Plan (${phaseDir}):\n${planLines}`;
              break;
            } catch {}
          }
        }

        additionalContext = [
          `⚠️ osEngineer CONTEXT DEGRADATION WARNING: Claude context remaining: ${remainingPercent}%.`,
          `High-frequency turns have triggered auto-compaction. Core instructions and targets have been injected into active memory to prevent cognitive drift.`,
          `Current State: ${stateStr}`,
          planSummary,
          `CRITICAL WORKER CONSTRAINTS:`,
          `1. Commit format: type(scope): subject (Conventional Commits).`,
          `2. Enforce TDD: Write the failing test FIRST in a 'red' commit, then implementation in a 'green' commit.`,
          `3. Non-interactive Git: All git commands must run with '--no-edit' or 'git -c core.editor=true' to bypass text editor prompts.`,
          `4. Phase Gate: Editing outside 'planning/' or '.osengineer/' is strictly read-only during 'discuss' or 'plan' phases.`,
          `5. Owns Paths: Edits to a path outside the active team's owns_paths list are blocked.`
        ].join('\n');
        
        // Reset turn counter when forcing Amnesia Guard
        sessionData.turnCounter = 0;
      } else if (sessionData.lastStateString === stateStr && sessionData.turnCounter < 5) {
        sessionData.turnCounter += 1;
        additionalContext = 'osEngineer state: active (unchanged)';
      } else {
        sessionData.lastStateString = stateStr;
        sessionData.turnCounter = 0;
        additionalContext = stateStr;
      }
      
      try { fs.writeFileSync(bridgePath, JSON.stringify(sessionData)); } catch {}
    } else {
      additionalContext = stateStr;
    }

    // Inject state into context
    process.stdout.write(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'UserPromptSubmit',
        additionalContext: additionalContext,
      },
    }));
  } catch { process.exit(0); }
});
