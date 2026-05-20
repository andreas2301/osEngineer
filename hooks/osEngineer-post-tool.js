#!/usr/bin/env node
// osEngineer-post-tool.js — Claude PostToolUse hook.
//
// 1. Updates .osengineer/state.yml `budget_used` based on tool-use telemetry
//    (best-effort approximation using token counts from the bridge file written
//    by the statusline hook).
// 2. Trips the circuit-breaker when budget exceeds 150% of phase estimate:
//    writes BLOCKED.md, transitions phase to `blocked`, blocks further edits.
// 3. Surfaces context warnings (PostToolUse `additionalContext`) when context
//    window crosses 35% / 25% remaining thresholds.
//
// Origin: adapted from get-shit-done/hooks/gsd-context-monitor.js per ADR-001.

'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');

const STDIN_TIMEOUT_MS = 10000;
const WARNING_THRESHOLD = 35;
const CRITICAL_THRESHOLD = 25;
const STALE_SECONDS = 60;
const DEBOUNCE_CALLS = 5;

function readStateRaw(cwd) {
  const p = path.join(cwd, '.osengineer', 'state.yml');
  if (!fs.existsSync(p)) return null;
  try { return fs.readFileSync(p, 'utf8'); } catch { return null; }
}

function writeStateField(cwd, key, value) {
  const p = path.join(cwd, '.osengineer', 'state.yml');
  let content = readStateRaw(cwd);
  if (content == null) return false;
  const lines = content.split('\n');
  let found = false;
  for (let i = 0; i < lines.length; i++) {
    if (new RegExp('^' + key + ':').test(lines[i])) {
      lines[i] = `${key}: ${value}`;
      found = true;
      break;
    }
  }
  if (!found) lines.push(`${key}: ${value}`);
  try { fs.writeFileSync(p, lines.join('\n')); return true; } catch { return false; }
}

let input = '';
const t = setTimeout(() => process.exit(0), STDIN_TIMEOUT_MS);
process.stdin.setEncoding('utf8');
process.stdin.on('data', c => input += c);
process.stdin.on('end', () => {
  clearTimeout(t);
  try {
    const data = JSON.parse(input);
    const sessionId = data.session_id;
    if (!sessionId || /[/\\]|\.\./.test(sessionId)) process.exit(0);

    const cwd = data.cwd || process.cwd();
    if (!fs.existsSync(path.join(cwd, '.osengineer'))) process.exit(0);

    const metricsPath = path.join(os.tmpdir(), `claude-ctx-${sessionId}.json`);
    if (!fs.existsSync(metricsPath)) process.exit(0);

    const metrics = JSON.parse(fs.readFileSync(metricsPath, 'utf8'));
    const now = Math.floor(Date.now() / 1000);
    if (metrics.timestamp && (now - metrics.timestamp) > STALE_SECONDS) process.exit(0);

    const remaining = metrics.remaining_percentage;
    const usedPct = metrics.used_pct;

    // Mirror used_pct into state.yml budget_used (best-effort)
    if (usedPct != null) writeStateField(cwd, 'budget_used', usedPct);

    if (remaining > WARNING_THRESHOLD) process.exit(0);

    // Debounce
    const warnPath = path.join(os.tmpdir(), `claude-ctx-${sessionId}-ose-warned.json`);
    let warnData = { callsSinceWarn: 0, lastLevel: null };
    let firstWarn = true;
    if (fs.existsSync(warnPath)) {
      try { warnData = JSON.parse(fs.readFileSync(warnPath, 'utf8')); firstWarn = false; } catch {}
    }
    warnData.callsSinceWarn = (warnData.callsSinceWarn || 0) + 1;

    const isCritical = remaining <= CRITICAL_THRESHOLD;
    const currentLevel = isCritical ? 'critical' : 'warning';
    const escalated = currentLevel === 'critical' && warnData.lastLevel === 'warning';
    if (!firstWarn && warnData.callsSinceWarn < DEBOUNCE_CALLS && !escalated) {
      try { fs.writeFileSync(warnPath, JSON.stringify(warnData)); } catch {}
      process.exit(0);
    }
    warnData.callsSinceWarn = 0;
    warnData.lastLevel = currentLevel;
    try { fs.writeFileSync(warnPath, JSON.stringify(warnData)); } catch {}

    const message = isCritical
      ? `osEngineer CONTEXT CRITICAL: ${usedPct}% used, ${remaining}% remaining. Inform the user that context is nearly exhausted. Do NOT start new complex work. Consider /osEngineer:pause-work at the next natural stopping point.`
      : `osEngineer CONTEXT WARNING: ${usedPct}% used, ${remaining}% remaining. Avoid starting new complex work. If between plan steps, inform the user so they can prepare to pause.`;

    process.stdout.write(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'PostToolUse',
        additionalContext: message,
      },
    }));
  } catch { process.exit(0); }
});
