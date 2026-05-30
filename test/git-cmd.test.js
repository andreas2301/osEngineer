'use strict';

const { describe, it } = require('node:test');
const assert = require('node:assert');
const { isGitSubcommand, tokenize } = require('../hooks/lib/osengineer-git-cmd.js');

describe('tokenize', () => {
  it('splits on whitespace', () => {
    assert.deepStrictEqual(tokenize('git commit'), ['git', 'commit']);
  });

  it('handles single quotes', () => {
    assert.deepStrictEqual(tokenize("git commit -m 'hello world'"), ['git', 'commit', '-m', 'hello world']);
  });

  it('handles double quotes', () => {
    assert.deepStrictEqual(tokenize('git commit -m "hello world"'), ['git', 'commit', '-m', 'hello world']);
  });

  it('handles env prefix', () => {
    assert.deepStrictEqual(tokenize('GIT_PAGER=cat git log'), ['GIT_PAGER=cat', 'git', 'log']);
  });
});

describe('isGitSubcommand', () => {
  it('detects bare git commit', () => {
    assert.strictEqual(isGitSubcommand('git commit', 'commit'), true);
  });

  it('detects git -C path commit', () => {
    assert.strictEqual(isGitSubcommand('git -C /foo/bar commit', 'commit'), true);
  });

  it('detects env-prefixed git commit', () => {
    assert.strictEqual(isGitSubcommand('GIT_PAGER=cat git commit', 'commit'), true);
  });

  it('detects full-path git commit', () => {
    assert.strictEqual(isGitSubcommand('/usr/bin/git commit', 'commit'), true);
  });

  it('rejects git log when looking for commit', () => {
    assert.strictEqual(isGitSubcommand('git log', 'commit'), false);
  });

  it('rejects non-git command', () => {
    assert.strictEqual(isGitSubcommand('ls -la', 'commit'), false);
  });

  it('handles --no-pager flag', () => {
    assert.strictEqual(isGitSubcommand('git --no-pager commit', 'commit'), true);
  });
});
