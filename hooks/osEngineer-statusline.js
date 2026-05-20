#!/usr/bin/env node
// osEngineer-statusline.js — Claude statusline hook.
// Shows: model · phase · team · budget% · open-handoffs · cwd-name · context-meter
//
// Also writes context metrics to /tmp/claude-ctx-{session_id}.json which the
// osEngineer-post-tool hook reads for warning injection.
//
// Origin: adapted from get-shit-done/hooks/gsd-statusline.js per ADR-001.

'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');

const STDIN_TIMEOUT_MS = 3000;

function readState(cwd) {
  let current = cwd;
  const home = os.homedir();
  for (let i = 0; i < 6; i++) {
    const p = path.join(current, '.osengineer', 'state.yml');
    if (fs.existsSync(p)) {
      try {
        const raw = fs.readFileSync(p, 'utf8');
        const s = {};
        for (const line of raw.split('\n')) {
          const m = line.match(/^(\w+):\s*(.*)$/);
          if (!m) continue;
          s[m[1]] = m[2].trim().replace(/^["']|["']$/g, '') || null;
        }
        return { state: s, repoRoot: current };
      } catch { return null; }
    }
    const parent = path.dirname(current);
    if (parent === current || current === home) break;
    current = parent;
  }
  return null;
}

function countHandoffs(repoRoot) {
  const d = path.join(repoRoot, '.osengineer', 'handoffs');
  if (!fs.existsSync(d)) return 0;
  try {
    return fs.readdirSync(d).filter(f => f.endsWith('.md') && f !== '.gitkeep').length;
  } catch { return 0; }
}

function formatStateSegment(state, handoffs) {
  const parts = [];
  parts.push(`phase:${state.phase || 'idle'}`);
  if (state.current_team) parts.push(`team:${state.current_team}`);
  if (state.budget_used != null) parts.push(`b:${state.budget_used}%`);
  if (handoffs > 0) parts.push(`HO:${handoffs}`);
  return parts.join(' · ');
}

function buildContextMeter(remaining, session) {
  if (remaining == null) return '';
  const totalCtx = 1_000_000;
  const acw = parseInt(process.env.CLAUDE_CODE_AUTO_COMPACT_WINDOW || '0', 10);
  const buf = acw > 0 ? Math.min(100, (acw / totalCtx) * 100) : 16.5;
  const usableRem = Math.max(0, ((remaining - buf) / (100 - buf)) * 100);
  const used = Math.max(0, Math.min(100, Math.round(100 - usableRem)));

  if (session && !/[/\\]|\.\./.test(session)) {
    try {
      const bridgePath = path.join(os.tmpdir(), `claude-ctx-${session}.json`);
      fs.writeFileSync(bridgePath, JSON.stringify({
        session_id: session,
        remaining_percentage: remaining,
        used_pct: Math.round(100 - remaining),
        timestamp: Math.floor(Date.now() / 1000),
      }));
    } catch {}
  }

  const filled = Math.floor(used / 10);
  const bar = '█'.repeat(filled) + '░'.repeat(10 - filled);
  let color;
  if (used < 50) color = '\x1b[32m';
  else if (used < 65) color = '\x1b[33m';
  else if (used < 80) color = '\x1b[38;5;208m';
  else color = '\x1b[5;31m💀 ';
  return ` ${color}${bar} ${used}%\x1b[0m`;
}

let input = '';
const t = setTimeout(() => process.exit(0), STDIN_TIMEOUT_MS);
process.stdin.setEncoding('utf8');
process.stdin.on('data', c => input += c);
process.stdin.on('end', () => {
  clearTimeout(t);
  try {
    const data = JSON.parse(input);
    const model = data.model?.display_name || 'Claude';
    const dir = data.workspace?.current_dir || process.cwd();
    const session = data.session_id || '';
    const remaining = data.context_window?.remaining_percentage;

    const modelSeg = `\x1b[2m${model}\x1b[0m`;
    const dirSeg = `\x1b[2m${path.basename(dir)}\x1b[0m`;
    const ctx = buildContextMeter(remaining, session);

    const found = readState(dir);
    let stateSeg = '';
    if (found) {
      const handoffs = countHandoffs(found.repoRoot);
      stateSeg = ` │ \x1b[2m${formatStateSegment(found.state, handoffs)}\x1b[0m`;
    }

    process.stdout.write(`${modelSeg}${stateSeg} │ ${dirSeg}${ctx}`);
  } catch {}
});
