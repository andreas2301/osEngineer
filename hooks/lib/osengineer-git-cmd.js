'use strict';

// osengineer-git-cmd.js — token-walk git command classifier.
// Determines whether a shell command invokes a specific git subcommand.
// Handles: bare `git commit`, `git -C path commit`, `VAR=x git commit`,
// `/usr/bin/git commit`. The naive `^git\s+commit` regex misses 3 of 4.
//
// Origin: ported verbatim from get-shit-done/hooks/lib/git-cmd.js
// (SHA 40a442b21f8b7a0df252efdf4b6ac4defd9d3a1f) per ADR-001, renamed.

const path = require('path');

const ARGUMENT_TAKING_FLAGS = new Set([
  '-C', '--git-dir', '--work-tree', '--namespace', '--super-prefix',
  '--exec-path', '--html-path', '--man-path', '--info-path', '--list-cmds',
]);

const BOOLEAN_FLAGS = new Set([
  '-p', '--paginate', '--no-pager',
  '--no-replace-objects', '--bare',
  '--literal-pathspecs', '--glob-pathspecs', '--noglob-pathspecs',
  '--icase-pathspecs', '--no-optional-locks',
  '-P', '--no-lazy-fetch',
  '--version', '--help',
]);

function tokenize(cmd) {
  const tokens = [];
  let i = 0;
  const len = cmd.length;
  while (i < len) {
    while (i < len && /\s/.test(cmd[i])) i++;
    if (i >= len) break;
    let token = '';
    while (i < len && !/\s/.test(cmd[i])) {
      if (cmd[i] === "'") {
        i++;
        while (i < len && cmd[i] !== "'") token += cmd[i++];
        if (i < len) i++;
      } else if (cmd[i] === '"') {
        i++;
        while (i < len && cmd[i] !== '"') token += cmd[i++];
        if (i < len) i++;
      } else {
        token += cmd[i++];
      }
    }
    if (token) tokens.push(token);
  }
  return tokens;
}

function isGitSubcommand(cmd, sub) {
  if (!cmd || !sub) return false;
  const tokens = tokenize(cmd);
  let i = 0;
  while (i < tokens.length && /^[A-Za-z_][A-Za-z0-9_]*=/.test(tokens[i])) i++;
  if (i >= tokens.length) return false;
  const gitToken = tokens[i++];
  if (path.basename(gitToken) !== 'git') return false;
  while (i < tokens.length) {
    const t = tokens[i];
    const eqIdx = t.indexOf('=');
    const flagName = eqIdx !== -1 ? t.slice(0, eqIdx) : t;
    if (ARGUMENT_TAKING_FLAGS.has(flagName)) {
      i += (eqIdx !== -1) ? 1 : 2;
      continue;
    }
    if (BOOLEAN_FLAGS.has(t)) { i++; continue; }
    break;
  }
  if (i >= tokens.length) return false;
  return tokens[i] === sub;
}

module.exports = { isGitSubcommand, tokenize };
