#!/usr/bin/env node
// osEngineer-pre-edit-guard.js — Claude PreToolUse hook on Write/Edit.
//
// Blocks edits during `discuss`/`plan` phases (planning is read-only by design).
// Blocks edits to `/opt/sovereign-shield/` live system at all times.
// Blocks edits to paths outside the current team's owns_paths when in `execute`
// phase with a `current_team` set (P3+).
//
// Reads:
//   .osengineer/state.yml          — phase + current_team
//   .osengineer/teams/<id>.json    — current team's owns_paths globs
//
// Honours OSE_BYPASS=1.

'use strict';

const fs = require('fs');
const path = require('path');

const STDIN_TIMEOUT_MS = 3000;

function readLiveSystemPath(cwd) {
  let dir = cwd;
  while (dir) {
    const p = path.join(dir, '.osengineer', 'workbench-config.yml');
    if (fs.existsSync(p)) {
      try {
        const raw = fs.readFileSync(p, 'utf8');
        const m = raw.match(/live_system_path:\s*"(.*)"/) || raw.match(/live_system_path:\s*(.*)/);
        if (m) {
          const val = m[1].trim().replace(/^["']|["']$/g, '');
          if (val !== 'none' && val !== '') return val;
        }
      } catch {}
    }
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return null;
}

function readValidationProfile(cwd) {
  let dir = cwd;
  while (dir) {
    const p = path.join(dir, '.osengineer', 'workbench-config.yml');
    if (fs.existsSync(p)) {
      try {
        const raw = fs.readFileSync(p, 'utf8');
        const m = raw.match(/validation_profile:\s*"(.*)"/) || raw.match(/validation_profile:\s*(.*)/);
        if (m) return m[1].trim().replace(/^["']|["']$/g, '');
      } catch {}
    }
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return 'hybrid';
}

function readStateMap(cwd) {
  const p = path.join(cwd, '.osengineer', 'state.yml');
  if (!fs.existsSync(p)) return null;
  try {
    const raw = fs.readFileSync(p, 'utf8');
    const state = {};
    for (const line of raw.split('\n')) {
      const m = line.match(/^(\w+):\s*(.*)$/);
      if (!m) continue;
      state[m[1]] = m[2].trim().replace(/^["']|["']$/g, '') || null;
    }
    return state;
  } catch { return null; }
}

function readTeamCache(cwd, teamId) {
  const p = path.join(cwd, '.osengineer', 'teams', `${teamId}.json`);
  if (!fs.existsSync(p)) return null;
  try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch { return null; }
}

// Minimal glob → regex converter supporting **, *, ? against POSIX paths.
function globToRegex(g) {
  // Escape regex special chars first (except *, ?)
  let r = g.replace(/[.+^${}()|[\]\\]/g, '\\$&');
  // Order matters: handle ** before *
  r = r.replace(/\*\*\//g, '___DOUBLESLASH___');
  r = r.replace(/\*\*/g, '___DOUBLE___');
  r = r.replace(/\*/g, '[^/]*');
  r = r.replace(/\?/g, '[^/]');
  r = r.replace(/___DOUBLESLASH___/g, '(?:.*/)?');
  r = r.replace(/___DOUBLE___/g, '.*');
  return new RegExp('^' + r + '$');
}

function pathMatchesAny(filePath, globs) {
  // Normalise to forward slashes for matching
  const normalised = filePath.replace(/\\/g, '/').replace(/^\.\//, '');
  for (const g of globs || []) {
    if (globToRegex(g).test(normalised)) return true;
  }
  return false;
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
    const tool = (data.tool_name || '').toLowerCase();
    const isEditTool = tool.includes('write') || tool.includes('edit') || tool.includes('replace');
    if (!isEditTool) process.exit(0);

    const cwd = data.cwd || process.cwd();
    const filePath = data.tool_input?.file_path || data.tool_input?.path || data.tool_input?.TargetFile || data.tool_input?.AbsolutePath || '';

    // Always block live-system edits if configured
    const liveSystemPath = readLiveSystemPath(cwd);
    if (liveSystemPath && (filePath.includes(liveSystemPath) || filePath.startsWith(liveSystemPath))) {
      process.stdout.write(JSON.stringify({
        decision: 'block',
        reason: `osEngineer: edits to ${liveSystemPath} are forbidden — that path is the live system. Edit in workbench and deploy via normal project workflow. Bypass with OSE_BYPASS=1 if absolutely necessary.`,
      }));
      process.exit(0);
    }

    const state = readStateMap(cwd);
    if (!state) process.exit(0); // not an osEngineer repo

    // Profile-specific rules
    const profile = readValidationProfile(cwd);
    const relPath = path.relative(cwd, filePath).replace(/\\/g, '/');
    
    // If validation profile is infra, enforce strict constraints on system configs
    if (profile === 'infra' && !/^(planning|\.osengineer|ansible|docker|scripts)[/\\]/.test(relPath) && (relPath.endsWith('.yml') || relPath.endsWith('.yaml') || relPath.endsWith('.json'))) {
      if (state.phase === 'discuss' || state.phase === 'plan') {
        process.stdout.write(JSON.stringify({
          decision: 'block',
          reason: `osEngineer: [Infra Profile] Editing configuration file ${relPath} is forbidden during ${state.phase} phase to prevent configuration drift. Focus on playbooks/scripts in planning directories first.`,
        }));
        process.exit(0);
      }
    }

    // If validation profile is frontend, add visual asset warnings or guard against editing critical assets directly
    if (profile === 'frontend' && (relPath.includes('assets/') || relPath.endsWith('.png') || relPath.endsWith('.jpg') || relPath.endsWith('.svg'))) {
      if (state.phase === 'execute' && !state.current_team) {
        process.stdout.write(JSON.stringify({
          decision: 'block',
          reason: `osEngineer: [Frontend Profile] Editing visual asset ${relPath} requires an active team context (e.g., UI/UX designer) to ensure design system consistency. Set current team first.`,
        }));
        process.exit(0);
      }
    }

    // Block edits during discuss/plan phases
    if (state.phase === 'discuss' || state.phase === 'plan') {
      const rel = path.relative(cwd, filePath);
      const allowed = /^(planning|\.osengineer)[/\\]/.test(rel);
      if (!allowed) {
        process.stdout.write(JSON.stringify({
          decision: 'block',
          reason: `osEngineer: cannot edit ${path.basename(filePath)} during ${state.phase} phase — only planning/ and .osengineer/ artifacts are editable. Transition to execute phase first (\`osengineer state set phase execute\`).`,
        }));
        process.exit(0);
      }
    }

    // owns_paths enforcement during execute phase
    if (state.phase === 'execute' && state.current_team) {
      const team = readTeamCache(cwd, state.current_team);
      if (team && Array.isArray(team.owns_paths) && team.owns_paths.length > 0) {
        const rel = path.relative(cwd, filePath);
        // Always allow edits inside .osengineer/ and planning/ (state artifacts)
        const isStateArtifact = /^(planning|\.osengineer)[/\\]/.test(rel);
        if (!isStateArtifact && !pathMatchesAny(rel, team.owns_paths)) {
          const relDisplay = rel.replace(/\\/g, '/');
          process.stdout.write(JSON.stringify({
            decision: 'block',
            reason: `osEngineer: ${relDisplay} is outside team "${state.current_team}"'s owns_paths. Either (a) open a handoff to the right team — \`osengineer handoff open --from ${state.current_team} --to <team> --slug <s>\` — or (b) bypass with OSE_BYPASS=1 if absolutely necessary.`,
          }));
          process.exit(0);
        }
      }
    }

    process.exit(0);
  } catch { process.exit(0); }
});
