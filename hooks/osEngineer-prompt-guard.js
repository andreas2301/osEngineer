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

const ROUTING_STOPWORDS = new Set([
  'the', 'a', 'an', 'is', 'are', 'in', 'on', 'of', 'for', 'to', 'with',
  'when', 'this', 'that', 'and', 'or'
]);

function tokenize(text) {
  if (!text) return [];
  return text
    .toLowerCase()
    .split(/[\s\.,;:!\?\(\)\[\]\{\}'"`<>\/\\\-_=+*&^%$#@~|]+/)
    .filter(t => t && !ROUTING_STOPWORDS.has(t));
}

function extractFrontmatter(raw) {
  // Frontmatter: starts with --- on first line, ends with --- on its own line.
  if (!raw.startsWith('---')) return null;
  const lines = raw.split('\n');
  if (lines[0].trim() !== '---') return null;
  let endIdx = -1;
  for (let i = 1; i < lines.length; i++) {
    if (lines[i].trim() === '---') { endIdx = i; break; }
  }
  if (endIdx === -1) return null;
  return lines.slice(1, endIdx);
}

function parseFrontmatter(raw) {
  const fmLines = extractFrontmatter(raw);
  if (!fmLines) return null;
  const result = {};
  let i = 0;
  while (i < fmLines.length) {
    const line = fmLines[i];
    // Match top-level "key:" or "key: value" — keys are letter/digit/underscore/hyphen
    const m = line.match(/^([A-Za-z_][\w-]*):\s*(.*)$/);
    if (!m) { i++; continue; }
    const key = m[1];
    let value = m[2];
    // Multi-line block-scalar: "key: >-" or "key: >" or "key: |" or "key: |-"
    if (/^[>|][-+]?\s*$/.test(value.trim())) {
      const buf = [];
      i++;
      while (i < fmLines.length) {
        const next = fmLines[i];
        // Continuation lines are indented; a new top-level key (unindented and matching the key pattern) ends the block.
        if (/^[A-Za-z_][\w-]*:/.test(next)) break;
        if (next.trim() === '') { buf.push(''); i++; continue; }
        buf.push(next.replace(/^\s+/, ''));
        i++;
      }
      // Folded scalar (>) joins lines with spaces; literal (|) keeps newlines.
      // Both >-/>+/|-/|+ variants are folded the same for our purposes.
      result[key] = buf.join(' ').replace(/\s+/g, ' ').trim();
      continue;
    }
    // Single-line value (strip optional quotes)
    result[key] = value.trim().replace(/^["']|["']$/g, '');
    i++;
  }
  return result;
}

// Sentence boundary that tolerates dotted identifiers like PHASE_PLAN.md or .osengineer/state.yml.
// Stops at a period followed by whitespace+capital or end-of-string, but not at periods inside
// lowercase-suffixed identifiers (file extensions).
function sentenceUntilTerminator(text) {
  if (!text) return '';
  // Walk char-by-char: if we see "." followed by whitespace+[A-Z] or end-of-string,
  // that's a sentence boundary. A "." followed by a lowercase letter is part of an identifier.
  let i = 0;
  while (i < text.length) {
    if (text[i] === '.') {
      // Check what comes after
      let j = i + 1;
      if (j >= text.length) return text.slice(0, i + 1).trim();
      // Skip whitespace
      while (j < text.length && /\s/.test(text[j])) j++;
      if (j >= text.length) return text.slice(0, i + 1).trim();
      // Boundary if next non-space is uppercase or punctuation marking new clause
      if (/[A-Z]/.test(text[j])) return text.slice(0, i + 1).trim();
    }
    // Semicolons also separate clauses in Don't-use sentences
    if (text[i] === ';') return text.slice(0, i).trim() + '.';
    i++;
  }
  return text.trim();
}

function extractUseSignal(description) {
  if (!description) return '';
  const m = description.match(/Use when\s+(.+)$/i);
  if (!m) return '';
  return sentenceUntilTerminator(m[1]);
}

function extractDontUseSignal(description) {
  if (!description) return '';
  const m = description.match(/Don'?t use(?:\s+when)?\s+(.+)$/i)
    || description.match(/Do not use(?:\s+when)?\s+(.+)$/i);
  if (!m) return '';
  return sentenceUntilTerminator(m[1]);
}

function firstSentence(description) {
  if (!description) return '';
  return sentenceUntilTerminator(description);
}

function loadSkillEntries(oseHome) {
  const entries = [];
  // Agents: <oseHome>/agents/*/AGENT.md
  const agentsDir = path.join(oseHome, 'agents');
  if (fs.existsSync(agentsDir)) {
    let agentDirs = [];
    try { agentDirs = fs.readdirSync(agentsDir); } catch { agentDirs = []; }
    for (const dirname of agentDirs) {
      const agentPath = path.join(agentsDir, dirname, 'AGENT.md');
      if (!fs.existsSync(agentPath)) continue;
      try {
        const raw = fs.readFileSync(agentPath, 'utf8');
        const fm = parseFrontmatter(raw);
        if (!fm || !fm.name || !fm.description) continue;
        entries.push({ name: fm.name, description: fm.description, type: 'agent' });
      } catch {}
    }
  }
  // Commands: <oseHome>/commands/osEngineer-*.md
  const cmdDir = path.join(oseHome, 'commands');
  if (fs.existsSync(cmdDir)) {
    let cmdFiles = [];
    try { cmdFiles = fs.readdirSync(cmdDir); } catch { cmdFiles = []; }
    for (const fname of cmdFiles) {
      if (!/^osEngineer-.*\.md$/.test(fname)) continue;
      const filePath = path.join(cmdDir, fname);
      try {
        const raw = fs.readFileSync(filePath, 'utf8');
        const fm = parseFrontmatter(raw);
        if (!fm || !fm.name || !fm.description) continue;
        entries.push({ name: fm.name, description: fm.description, type: 'command' });
      } catch {}
    }
  }
  return entries;
}

function findMatchingSkills(prompt, oseHome, maxMatches = 3) {
  if (!oseHome) return [];
  try {
    if (!fs.existsSync(oseHome)) return [];
  } catch { return []; }
  const promptTokens = tokenize(prompt);
  if (promptTokens.length === 0) return [];
  const promptSet = new Set(promptTokens);

  let entries;
  try { entries = loadSkillEntries(oseHome); } catch { return []; }

  const scored = [];
  for (const e of entries) {
    const useSignal = extractUseSignal(e.description);
    const signalTokens = tokenize(useSignal);
    if (signalTokens.length === 0) continue;
    const signalSet = new Set(signalTokens);

    let overlap = 0;
    for (const t of promptSet) {
      if (signalSet.has(t)) overlap++;
    }
    const denom = Math.max(promptTokens.length, signalTokens.length);
    let score = denom > 0 ? overlap / denom : 0;

    // Name bonus: any prompt token appears as a substring of the name
    const nameLower = (e.name || '').toLowerCase();
    if (nameLower) {
      for (const t of promptSet) {
        if (t.length >= 3 && nameLower.includes(t)) { score += 0.1; break; }
      }
    }

    // Exclusion penalty: prompt tokens overlap the "Don't use when" zone
    const dontSignal = extractDontUseSignal(e.description);
    if (dontSignal) {
      const dontTokens = new Set(tokenize(dontSignal));
      for (const t of promptSet) {
        if (dontTokens.has(t)) { score -= 0.5; break; }
      }
    }

    if (score > 0.15) {
      scored.push({
        name: e.name,
        description: e.description,
        score: score,
        type: e.type,
      });
    }
  }

  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, maxMatches);
}

function formatRoutingHints(matches) {
  if (!matches || matches.length === 0) return '';
  const lines = ['osEngineer routing hints (high-confidence matches for this prompt):'];
  for (const m of matches) {
    let excerpt = firstSentence(m.description);
    if (excerpt.length > 200) excerpt = excerpt.slice(0, 197) + '...';
    lines.push(`- ${m.name} (score: ${m.score.toFixed(2)}) — ${excerpt}`);
  }
  return lines.join('\n');
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
          `5. Owns Paths: Edits to a path outside the active team's owns_paths list are blocked.`,
          `6. Think Before Coding: State assumptions explicitly; ask if ambiguous.`,
          `7. Simplicity First: Write minimum code; no speculative abstractions.`,
          `8. Surgical Changes: Touch only what task requires.`,
          `9. Goal-Driven Execution: Create tests first to reproduce issue, then loop until pass.`,
          `10. Set Hard Token Budgets: Stop runaway iterations.`,
          `11. Expose Conflicts: Don't average contradictory patterns.`,
          `12. Read Before Writing: Scan existing code before making edits.`,
          `13. Test Real Logic: Validate actual logic, not just running to pass.`,
          `14. Use Checkpoints: For long-running, multi-step tasks.`,
          `15. Fail Explicitly: Avoid silent failures; fail immediately and clearly.`
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

    // Frontmatter-driven skill routing: append high-confidence matches as routing hints
    try {
      const oseHome = process.env.OSENGINEER_HOME;
      if (oseHome && prompt) {
        const matches = findMatchingSkills(prompt, oseHome);
        if (matches.length > 0) {
          const hintBlock = formatRoutingHints(matches);
          if (hintBlock) {
            additionalContext = additionalContext
              ? `${additionalContext}\n\n${hintBlock}`
              : hintBlock;
          }
        }
      }
    } catch {}

    // Inject state into context
    process.stdout.write(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'UserPromptSubmit',
        additionalContext: additionalContext,
      },
    }));
  } catch { process.exit(0); }
});
