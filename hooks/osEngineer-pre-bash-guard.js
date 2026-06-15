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
// Per-team overrides (P7): repo and team-level JSON files can `disabled`,
// `downgraded_to_warning`, or `added` patterns relative to the global
// denylist. See trust/denylist.md for the schema and resolution rules.
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

function logOverride(cwd, entry) {
  try {
    const p = path.join(cwd, '.osengineer', 'override-log.jsonl');
    fs.appendFileSync(p, JSON.stringify(Object.assign({
      ts: new Date().toISOString(),
      hook: 'pre-bash-guard',
    }, entry)) + '\n');
  } catch {}
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
      const [, k, v] = m;
      state[k] = v.trim().replace(/^["']|["']$/g, '') || null;
    }
    return state;
  } catch { return null; }
}

// Parse a single override file. Returns:
//   { disabled: [name], downgraded_to_warning: [name], added: [{name, regex, category}] }
// or null if the file is missing, unreadable, or malformed.
// Malformed files are logged as a parse-failure entry to override-log.jsonl.
function loadOverrideFile(cwd, filePath, source) {
  if (!fs.existsSync(filePath)) return null;
  let raw;
  try { raw = fs.readFileSync(filePath, 'utf8'); }
  catch (e) {
    logOverride(cwd, { event: 'override_parse_failure', source, file: filePath, error: 'read_error' });
    return null;
  }
  let parsed;
  try { parsed = JSON.parse(raw); }
  catch (e) {
    logOverride(cwd, { event: 'override_parse_failure', source, file: filePath, error: 'json_parse_error' });
    return null;
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    logOverride(cwd, { event: 'override_parse_failure', source, file: filePath, error: 'not_an_object' });
    return null;
  }
  const out = { disabled: [], downgraded_to_warning: [], added: [] };
  if (Array.isArray(parsed.disabled)) {
    out.disabled = parsed.disabled.filter(s => typeof s === 'string');
  }
  if (Array.isArray(parsed.downgraded_to_warning)) {
    out.downgraded_to_warning = parsed.downgraded_to_warning.filter(s => typeof s === 'string');
  }
  if (Array.isArray(parsed.added)) {
    for (const entry of parsed.added) {
      if (!entry || typeof entry.name !== 'string' || typeof entry.regex !== 'string') continue;
      let compiled;
      try { compiled = new RegExp(entry.regex); }
      catch {
        logOverride(cwd, {
          event: 'override_parse_failure', source, file: filePath,
          error: 'invalid_regex', name: entry.name,
        });
        continue;
      }
      out.added.push({
        name: entry.name,
        regex: compiled,
        category: entry.category || 'team-override',
      });
    }
  }
  return out;
}

// Compose effective denylist from globals + override layers.
// Repo-level merges first, then team-level on top. Team-level disabled/added
// extends the repo-level lists. Team disabled of a name added by repo-level
// removes that addition. Returns:
//   { patterns: [{name,regex,category}], downgraded: Set<name>, disabled: Set<name>,
//     overridesApplied: { repoLoaded, teamLoaded, addedFromRepo, addedFromTeam } }
function buildEffectiveDenylist(globals, repoOv, teamOv) {
  const downgraded = new Set();
  const disabledSet = new Set();
  let added = [];

  if (repoOv) {
    for (const n of repoOv.disabled) disabledSet.add(n);
    for (const n of repoOv.downgraded_to_warning) downgraded.add(n);
    for (const a of repoOv.added) added.push(Object.assign({ _source: 'repo' }, a));
  }
  if (teamOv) {
    for (const n of teamOv.disabled) disabledSet.add(n);
    for (const n of teamOv.downgraded_to_warning) downgraded.add(n);
    for (const a of teamOv.added) added.push(Object.assign({ _source: 'team' }, a));
  }
  // A team-level `disabled` may remove a name added at repo-level.
  added = added.filter(a => !disabledSet.has(a.name));

  // Filter globals through disabled set.
  const effectiveGlobals = globals.filter(p => !disabledSet.has(p.name));

  return {
    patterns: effectiveGlobals.concat(added),
    downgraded,
    disabled: disabledSet,
    addedNames: new Set(added.map(a => a.name)),
  };
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

    const globals = loadPatterns();

    // Load override layers (repo first, team on top).
    const repoOvPath = path.join(cwd, '.osengineer', 'denylist-overrides.json');
    const repoOv = loadOverrideFile(cwd, repoOvPath, 'repo');

    let teamOv = null;
    const state = readStateMap(cwd);
    const currentTeam = state && state.current_team;
    if (currentTeam) {
      const teamOvPath = path.join(
        cwd, '.osengineer', 'teams', currentTeam, 'denylist-overrides.json'
      );
      teamOv = loadOverrideFile(cwd, teamOvPath, 'team:' + currentTeam);
    }

    const effective = buildEffectiveDenylist(globals, repoOv, teamOv);

    // Check the command against the effective denylist.
    const matched = effective.patterns.find(p => p.regex.test(cmd));

    // Even when there is no match, log that disabled globals were skipped so
    // the audit trail captures "team turned off X, command ran clean". Only
    // log disabled entries that the command would have hit, to keep noise low.
    if (effective.disabled.size > 0) {
      for (const name of effective.disabled) {
        const global = globals.find(g => g.name === name);
        if (global && global.regex.test(cmd)) {
          logOverride(cwd, {
            event: 'disabled_applied',
            pattern: name,
            team: currentTeam || null,
            cmd: cmd.slice(0, 200),
          });
        }
      }
    }

    if (!matched) process.exit(0);

    // Pattern matched. Decide: block / warn-downgrade / allow-as-added.
    const isDowngraded = effective.downgraded.has(matched.name);
    const isAdded = effective.addedNames.has(matched.name);

    if (isAdded) {
      logOverride(cwd, {
        event: 'added_pattern_matched',
        pattern: matched.name,
        team: currentTeam || null,
        cmd: cmd.slice(0, 200),
      });
    }

    if (hasFourPartPlan(cwd)) process.exit(0); // plan present — allow

    if (isDowngraded) {
      logOverride(cwd, {
        event: 'downgraded_to_warning',
        pattern: matched.name,
        team: currentTeam || null,
        cmd: cmd.slice(0, 200),
      });
      process.stdout.write(JSON.stringify({
        hookSpecificOutput: {
          hookEventName: 'PreToolUse',
          additionalContext:
            `osEngineer warning: command matches denylist pattern "${matched.name}"` +
            (matched.category ? ` (category: ${matched.category})` : '') +
            `. This pattern is downgraded-to-warning by a per-team override; ` +
            `the command will run but the match was logged to override-log.jsonl.`,
        },
      }));
      process.exit(0);
    }

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
