#!/usr/bin/env node
// osEngineer-pre-bash-guard.js — Claude PreToolUse hook on Bash.
//
// Blocks destructive bash commands without an active 4-part plan
// (.osengineer/current-plan.md). The 4-part plan must contain Touch/Change/
// Impact/Rollback sections.
//
// Patterns are loaded at runtime from trust/denylist.md (the readable
// contract). If the file is missing or malformed, the hook falls back to a
// hardcoded baseline so enforcement is never silently disabled.
//
// Honours OSE_BYPASS=1 (logged to .osengineer/bypass-log.jsonl).

'use strict';

const fs = require('fs');
const path = require('path');

const STDIN_TIMEOUT_MS = 3000;

// Hardcoded fallback — used only when trust/denylist.md cannot be loaded.
// Keep in sync with the JSON block in trust/denylist.md.
const FALLBACK_PATTERNS = [
  { name: 'rm -rf',           regex: /\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)/ },
  { name: 'git push --force', regex: /\bgit\s+(?:\S+\s+)*push\s+(?:[^|;&]*\s)?(?:--force\b|-f\b)/ },
  { name: 'git reset --hard', regex: /\bgit\s+(?:\S+\s+)*reset\s+--hard/ },
  { name: 'docker rm',        regex: /\bdocker\s+(rm|volume\s+rm|system\s+prune)/ },
  { name: 'kubectl delete',   regex: /\bkubectl\s+(?:\S+\s+)*delete\b/ },
];

function findDenylistFile() {
  // 1. OSENGINEER_HOME env var (set by install.sh in .claude/settings.json)
  const home = process.env.OSENGINEER_HOME;
  if (home) {
    const p = path.join(home, 'trust', 'denylist.md');
    if (fs.existsSync(p)) return p;
  }
  // 2. Walk up from this script's dirname — script lives at osEngineer/hooks/
  //    (or copied to .git/hooks/, but only Node hooks are referenced via
  //    absolute path from settings.json so __dirname always resolves to the
  //    osEngineer/hooks/ source location in practice).
  const sibling = path.resolve(__dirname, '..', 'trust', 'denylist.md');
  if (fs.existsSync(sibling)) return sibling;
  return null;
}

function loadPatterns() {
  const file = findDenylistFile();
  if (!file) return FALLBACK_PATTERNS;
  let content;
  try { content = fs.readFileSync(file, 'utf8'); } catch { return FALLBACK_PATTERNS; }
  // Extract the FIRST ```json ... ``` fenced block. Match across newlines.
  const m = content.match(/```json\s*\n([\s\S]*?)\n```/);
  if (!m) return FALLBACK_PATTERNS;
  let parsed;
  try { parsed = JSON.parse(m[1]); } catch { return FALLBACK_PATTERNS; }
  if (!Array.isArray(parsed)) return FALLBACK_PATTERNS;
  const compiled = [];
  for (const entry of parsed) {
    if (!entry || typeof entry.name !== 'string' || typeof entry.regex !== 'string') continue;
    try {
      compiled.push({ name: entry.name, regex: new RegExp(entry.regex), category: entry.category || 'uncategorised' });
    } catch {
      // Skip malformed regex entries; do not fail the whole hook
    }
  }
  // If parsing yielded no usable entries, fall back rather than no-op
  return compiled.length > 0 ? compiled : FALLBACK_PATTERNS;
}

function hasFourPartPlan(cwd) {
  const planPath = path.join(cwd, '.osengineer', 'current-plan.md');
  if (!fs.existsSync(planPath)) return false;
  try {
    const content = fs.readFileSync(planPath, 'utf8');
    const required = ['touch', 'change', 'impact', 'rollback'];
    return required.every(section =>
      new RegExp('^#+\\s*' + section + '\\b', 'im').test(content)
    );
  } catch { return false; }
}

function logBypass(cwd, hook, reason, cmd) {
  try {
    const p = path.join(cwd, '.osengineer', 'bypass-log.jsonl');
    fs.appendFileSync(p, JSON.stringify({
      ts: new Date().toISOString(),
      hook,
      reason,
      cmd: cmd ? cmd.slice(0, 200) : null,
    }) + '\n');
  } catch {}
}

let input = '';
const t = setTimeout(() => process.exit(0), STDIN_TIMEOUT_MS);
process.stdin.setEncoding('utf8');
process.stdin.on('data', c => input += c);
process.stdin.on('end', () => {
  clearTimeout(t);
  try {
    const data = JSON.parse(input);
    if (data.tool_name !== 'Bash') process.exit(0);

    const cwd = data.cwd || process.cwd();
    const stateExists = fs.existsSync(path.join(cwd, '.osengineer', 'state.yml'));
    if (!stateExists) process.exit(0); // not an osEngineer repo

    const cmd = data.tool_input?.command || '';
    if (!cmd) process.exit(0);

    if (process.env.OSE_BYPASS === '1') {
      logBypass(cwd, 'pre-bash-guard', 'OSE_BYPASS=1', cmd);
      process.exit(0);
    }

    const patterns = loadPatterns();
    const matched = patterns.find(p => p.regex.test(cmd));
    if (!matched) process.exit(0);

    if (hasFourPartPlan(cwd)) process.exit(0); // plan present — allow

    process.stdout.write(JSON.stringify({
      decision: 'block',
      reason:
        `osEngineer: command matches denylist pattern "${matched.name}"` +
        (matched.category ? ` (category: ${matched.category})` : '') +
        ` and no 4-part plan is active.\n` +
        `Either:\n` +
        `  (a) write .osengineer/current-plan.md with sections Touch / Change / Impact / Rollback, or\n` +
        `  (b) set OSE_BYPASS=1 if absolutely necessary (logged to bypass-log.jsonl).\n` +
        `See trust/denylist.md for the full pattern contract and rationale.`,
    }));
  } catch { process.exit(0); }
});
