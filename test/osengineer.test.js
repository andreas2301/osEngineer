'use strict';

const { describe, it, before, after } = require('node:test');
const assert = require('node:assert');
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const BIN = path.resolve(__dirname, '..', 'bin', 'osengineer');

function run(args, cwd) {
  const result = spawnSync(process.execPath, [BIN, ...args], {
    cwd,
    encoding: 'utf8',
    env: { ...process.env, PATH: process.env.PATH },
  });
  return { stdout: result.stdout, stderr: result.stderr, status: result.status };
}

describe('osengineer CLI', () => {
  describe('version', () => {
    it('prints the version', () => {
      const { stdout, status } = run(['version']);
      assert.strictEqual(status, 0);
      assert.match(stdout, /^osengineer \d+\.\d+\.\d+/);
    });

    it('accepts --version', () => {
      const { stdout, status } = run(['--version']);
      assert.strictEqual(status, 0);
      assert.match(stdout, /^osengineer \d+\.\d+\.\d+/);
    });
  });

  describe('explain', () => {
    it('prints overview by default', () => {
      const { stdout, status } = run(['explain']);
      assert.strictEqual(status, 0);
      assert(stdout.includes('osEngineer'));
    });

    it('prints phases topic', () => {
      const { stdout, status } = run(['explain', 'phases']);
      assert.strictEqual(status, 0);
      assert(stdout.includes('Phase lifecycle'));
    });

    it('errors on unknown topic', () => {
      const { status } = run(['explain', 'nonexistent']);
      assert.strictEqual(status, 1);
    });
  });

  describe('detect-teams', () => {
    let tmpDir;

    before(() => {
      tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ose-test-'));
    });

    after(() => {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    });

    it('detects Go repo', () => {
      fs.writeFileSync(path.join(tmpDir, 'go.mod'), 'module example\n');
      fs.mkdirSync(path.join(tmpDir, 'internal'));
      fs.mkdirSync(path.join(tmpDir, '.osengineer'));

      const { stdout, status } = run(['detect-teams', tmpDir]);
      assert.strictEqual(status, 0);
      assert(stdout.includes('team_id: coding'));
      assert(stdout.includes('folder: internal/'));
      assert(stdout.includes('team_id: infra') === false); // no ansible, no compose
    });

    it('detects Python repo with docs', () => {
      // Clean tmpDir first
      for (const f of fs.readdirSync(tmpDir)) {
        fs.rmSync(path.join(tmpDir, f), { recursive: true, force: true });
      }
      fs.writeFileSync(path.join(tmpDir, 'pyproject.toml'), '[project]\n');
      fs.mkdirSync(path.join(tmpDir, 'docs'));
      fs.mkdirSync(path.join(tmpDir, '.osengineer'));

      const { stdout, status } = run(['detect-teams', tmpDir]);
      assert.strictEqual(status, 0);
      assert(stdout.includes('team_id: coding'));
      assert(stdout.includes('team_id: docs'));
      assert(stdout.includes('folder: src/') || stdout.includes('folder: null')); // no src dir
    });
  });

  describe('state', () => {
    let tmpDir;

    before(() => {
      tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ose-state-'));
      fs.mkdirSync(path.join(tmpDir, '.git'));
      fs.mkdirSync(path.join(tmpDir, '.osengineer'));
      fs.writeFileSync(path.join(tmpDir, '.osengineer', 'state.yml'), 'phase: idle\ncurrent_team: coding\n');
    });

    after(() => {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    });

    it('reads state', () => {
      const { stdout, status } = run(['state'], tmpDir);
      assert.strictEqual(status, 0);
      assert(stdout.includes('phase: idle'));
      assert(stdout.includes('current_team: coding'));
    });

    it('sets state field', () => {
      const { status } = run(['state', 'set', 'phase', 'execute'], tmpDir);
      assert.strictEqual(status, 0);
      const content = fs.readFileSync(path.join(tmpDir, '.osengineer', 'state.yml'), 'utf8');
      assert(content.includes('phase: execute'));
    });
  });

  describe('handoff', () => {
    let tmpDir;

    before(() => {
      tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ose-handoff-'));
      fs.mkdirSync(path.join(tmpDir, '.git'));
      fs.mkdirSync(path.join(tmpDir, '.osengineer'));
    });

    after(() => {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    });

    it('opens and closes a repo handoff', () => {
      const open = run(['handoff', 'open', '--from', 'coding', '--to', 'infra', '--slug', 'add-compose', '--closes-when', 'docker-compose.yml merged'], tmpDir);
      assert.strictEqual(open.status, 0, open.stderr);
      assert(open.stdout.includes('HO-001'));

      const list = run(['handoff', 'list'], tmpDir);
      assert.strictEqual(list.status, 0);
      assert(list.stdout.includes('HO-001'));

      const close = run(['handoff', 'close', 'HO-001', '--reason', 'Done'], tmpDir);
      assert.strictEqual(close.status, 0, close.stderr);

      const content = fs.readFileSync(path.join(tmpDir, '.osengineer', 'handoffs', 'HO-001-add-compose.md'), 'utf8');
      assert(content.includes('closed_at:'));
      assert(content.includes('close_reason:'));
      assert(content.includes('status:') === false); // should not invent a status field
    });
  });
});
