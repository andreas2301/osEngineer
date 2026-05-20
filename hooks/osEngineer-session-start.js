#!/usr/bin/env node
// osEngineer-session-start.js — Claude SessionStart hook.
//
// Loads .osengineer/state.yml on session start and emits a banner showing
// phase / team / budget / open handoffs / auto-nudge (if 5+ phases since
// last evolution).

'use strict';

const fs = require('fs');
const path = require('path');

function readStateMap(cwd) {
  const p = path.join(cwd, '.osengineer', 'state.yml');
  if (!fs.existsSync(p)) return null;
  try {
    const raw = fs.readFileSync(p, 'utf8');
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

function readEvolutionCounter(cwd) {
  const p = path.join(cwd, '.osengineer', 'evolution-counter.yml');
  if (!fs.existsSync(p)) return null;
  try {
    const raw = fs.readFileSync(p, 'utf8');
    const m = raw.match(/^phases_since_last_evolution:\s*(\d+)/m);
    return m ? parseInt(m[1], 10) : null;
  } catch { return null; }
}

function countHandoffs(cwd) {
  const d = path.join(cwd, '.osengineer', 'handoffs');
  if (!fs.existsSync(d)) return 0;
  try {
    return fs.readdirSync(d).filter(f => f.endsWith('.md') && f !== '.gitkeep').length;
  } catch { return 0; }
}

function main() {
  const cwd = process.cwd();
  const state = readStateMap(cwd);
  if (!state) process.exit(0); // not an osEngineer repo

  const handoffs = countHandoffs(cwd);
  const counter = readEvolutionCounter(cwd);

  const lines = ['## osEngineer state'];
  lines.push(`- phase: ${state.phase || 'idle'}`);
  if (state.current_team) lines.push(`- team: ${state.current_team}`);
  if (state.budget_used != null) lines.push(`- budget used: ${state.budget_used}%`);
  if (handoffs > 0) lines.push(`- open handoffs: ${handoffs}`);
  if (counter != null && counter >= 5) {
    lines.push(`- ⚙ ${counter} phases since last /osEngineer:evolve — consider running it to surface improvement proposals.`);
  }
  if (state.phase === 'blocked') {
    lines.push(`- ⚠ phase is BLOCKED. See .osengineer/BLOCKED.md for resume instructions.`);
  }

  process.stdout.write(JSON.stringify({
    hookSpecificOutput: {
      hookEventName: 'SessionStart',
      additionalContext: lines.join('\n'),
    },
  }));
}

if (require.main === module) main();
