#!/usr/bin/env node
// osEngineer-pre-bash-guard.js — Claude PreToolUse hook on Bash.
//
// Blocks destructive bash commands without an active 4-part plan
// (.osengineer/current-plan.md). The 4-part plan must contain Touch/Change/
// Impact/Rollback sections. Forbidden ops:
//   - rm -rf
//   - git push --force / -f
//   - docker rm / docker volume rm
//   - kubectl delete
//
// Honours OSE_BYPASS=1.

'use strict';

const fs = require('fs');
const path = require('path');

const STDIN_TIMEOUT_MS = 3000;

const DESTRUCTIVE_PATTERNS = [
  { name: 'rm -rf',           re: /\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)/ },
  { name: 'git push --force', re: /\bgit\s+(?:\S+\s+)*push\s+(?:[^|;&]*\s)?(?:--force\b|-f\b)/ },
  { name: 'docker rm',        re: /\bdocker\s+(rm|volume\s+rm|system\s+prune)/ },
  { name: 'kubectl delete',   re: /\bkubectl\s+(?:\S+\s+)*delete\b/ },
  { name: 'git reset --hard', re: /\bgit\s+(?:\S+\s+)*reset\s+--hard/ },
];

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

let input = '';
const t = setTimeout(() => process.exit(0), STDIN_TIMEOUT_MS);
process.stdin.setEncoding('utf8');
process.stdin.on('data', c => input += c);
process.stdin.on('end', () => {
  clearTimeout(t);
  try {
    if (process.env.OSE_BYPASS === '1') process.exit(0);

    const data = JSON.parse(input);
    if (data.tool_name !== 'Bash') process.exit(0);

    const cwd = data.cwd || process.cwd();
    const stateExists = fs.existsSync(path.join(cwd, '.osengineer', 'state.yml'));
    if (!stateExists) process.exit(0); // not an osEngineer repo

    const cmd = data.tool_input?.command || '';
    if (!cmd) process.exit(0);

    const matched = DESTRUCTIVE_PATTERNS.find(p => p.re.test(cmd));
    if (!matched) process.exit(0);

    if (hasFourPartPlan(cwd)) process.exit(0); // plan present — allow

    process.stdout.write(JSON.stringify({
      decision: 'block',
      reason: `osEngineer: command matches destructive pattern "${matched.name}" and no 4-part plan is active. Write .osengineer/current-plan.md with Touch / Change / Impact / Rollback sections first, OR set OSE_BYPASS=1 if absolutely necessary.`,
    }));
  } catch { process.exit(0); }
});
