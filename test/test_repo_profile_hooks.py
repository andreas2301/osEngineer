"""Payload-level regression checks: no services, credentials or model calls."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

HOOKS = Path(__file__).resolve().parents[1] / 'hooks'


class RepoProfileHooks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / '.osengineer').mkdir()
        (self.root / 'src' / 'nested').mkdir(parents=True)
        self.session = 'ose-test-' + uuid.uuid4().hex
        self.state('execute')

    def tearDown(self):
        for pattern in (f'claude-*{self.session}*',):
            for path in Path(tempfile.gettempdir()).glob(pattern):
                path.unlink(missing_ok=True)
        self.tmp.cleanup()

    def state(self, phase):
        (self.root / '.osengineer/state.yml').write_text(f'phase: {phase}\n')

    def repo_profile(self, workbench=False):
        if workbench:
            (self.root / '.osengineer/workbench-config.yml').write_text('validation_profile: repo\n')
        else:
            (self.root / '.osengineer/profile.json').write_text('{"profile":"repo"}')

    def run_hook(self, name, payload=None, raw=None, bypass=False):
        env = dict(os.environ)
        env.pop('OSE_BYPASS', None)
        if bypass:
            env['OSE_BYPASS'] = '1'
        result = subprocess.run([sys.executable, str(HOOKS / f'osEngineer-{name}.py')],
            input=raw if raw is not None else json.dumps(payload or {}), text=True, capture_output=True,
            cwd=self.root / 'src/nested', env=env)
        return result

    def edit(self, phase, path='file.py', bypass=False):
        self.state(phase)
        return self.run_hook('pre-edit-guard', {'cwd': str(self.root / 'src/nested'),
            'tool_name': 'Edit', 'tool_input': {'file_path': path}}, bypass=bypass)

    def metrics(self, remaining):
        (Path(tempfile.gettempdir()) / f'claude-ctx-{self.session}.json').write_text(json.dumps({
            'session_id': self.session, 'remaining_percentage': remaining,
            'used_pct': 100-remaining, 'timestamp': int(time.time())}))

    def prompt(self, text='implementiere die Änderung'):
        return self.run_hook('prompt-guard', {'cwd': str(self.root / 'src/nested'),
            'session_id': self.session, 'prompt': text})

    def test_nested_destructive_command_denied(self):
        for cwd in (self.root, self.root / 'src/nested'):
            out = self.run_hook('pre-bash-guard', {'cwd': str(cwd), 'tool_name': 'Bash', 'tool_input': {'command': 'git reset --hard'}})
            self.assertEqual(json.loads(out.stdout)['decision'], 'block')

    def test_blocked_and_suspended_edits_denied(self):
        for phase in ('blocked', 'suspended'):
            self.assertEqual(json.loads(self.edit(phase).stdout)['decision'], 'block')

    def test_execute_relative_path_allowed(self):
        self.assertEqual(self.edit('execute').stdout, '')

    def test_repo_profile_planning_namespace(self):
        self.repo_profile()
        self.assertEqual(self.edit('plan', str(self.root / '.plans/task.md')).stdout, '')
        self.assertEqual(json.loads(self.edit('plan', str(self.root / 'planning/task.md')).stdout)['decision'], 'block')
        self.assertFalse((self.root / 'planning').exists())

    def test_repo_profile_configurable_plan_directory(self):
        (self.root / '.osengineer/profile.json').write_text('{"profile":"repo","planDirectory":"work-plans"}')
        self.assertEqual(self.edit('plan', str(self.root / 'work-plans/task.md')).stdout, '')
        self.assertEqual(json.loads(self.edit('plan', str(self.root / '.plans/task.md')).stdout)['decision'], 'block')

    def test_generic_planning_namespace(self):
        self.assertEqual(self.edit('plan', str(self.root / 'planning/task.md')).stdout, '')

    def test_edit_bypass_audited(self):
        self.assertEqual(self.edit('blocked', bypass=True).stdout, '')
        entry = json.loads((self.root / '.osengineer/bypass-log.jsonl').read_text())
        self.assertEqual(entry['hook'], 'pre-edit-guard')

    def test_bash_bypass_audited_from_nested(self):
        self.run_hook('pre-bash-guard', {'cwd': str(self.root / 'src/nested'), 'tool_name': 'Bash', 'tool_input': {'command': 'rm -rf data'}}, bypass=True)
        self.assertEqual(json.loads((self.root / '.osengineer/bypass-log.jsonl').read_text())['hook'], 'pre-bash-guard')

    def test_invalid_payload_observable(self):
        for hook in ('pre-edit-guard', 'pre-bash-guard', 'read-guard', 'post-tool', 'statusline',
                     'prompt-guard', 'session-start'):
            result = self.run_hook(hook, raw='{')
            # Strict: exit 2 blocks (see test_hooks_smoke.TestHooksAreStrictOnMalformedPayloads).
            self.assertEqual(result.returncode, 2, hook)
            self.assertIn('invalid hook input', result.stderr)
            self.assertNotIn('Traceback', result.stderr)

    def test_statusline_real_session_telemetry(self):
        result = self.run_hook('statusline', {'session_id': self.session, 'workspace': {'current_dir': str(self.root)}, 'context_window': {'remaining_percentage': 33}})
        self.assertEqual(result.returncode, 0, result.stderr)
        bridge = json.loads((Path(tempfile.gettempdir()) / f'claude-ctx-{self.session}.json').read_text())
        self.assertEqual(bridge['used_pct'], 67)
        self.assertIn('67%', result.stdout)

    def test_statusline_does_not_guess_compaction_window(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {'CLAUDE_CODE_AUTO_COMPACT_WINDOW': '1000000'}):
            result = self.run_hook('statusline', {'context_window': {'remaining_percentage': 33}})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('67%', result.stdout)

    def test_statusline_invalid_occupancy_is_visible(self):
        for remaining in (True, -1, 101, '33'):
            result = self.run_hook('statusline', {'context_window': {'remaining_percentage': remaining}})
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, '')
            self.assertIn('ValueError', result.stderr)

    def test_occupancy_not_task_spend(self):
        self.metrics(30)
        out = self.run_hook('post-tool', {'session_id': self.session, 'cwd': str(self.root)})
        self.assertEqual(out.returncode, 0, out.stderr)
        # Volatile telemetry lives in the gitignored runtime.yml, never state.yml.
        state = (self.root / '.osengineer/state.yml').read_text()
        runtime = (self.root / '.osengineer/runtime.yml').read_text()
        self.assertIn('context_used_pct: 70', runtime)
        self.assertNotIn('context_used_pct:', state)
        self.assertNotIn('budget_used:', state + runtime)

    def test_context_warning_events(self):
        payload = {'session_id': self.session, 'cwd': str(self.root)}
        self.metrics(30)
        self.assertIn('WARNING', self.run_hook('post-tool', payload).stdout)
        for _ in range(8):
            self.assertEqual(self.run_hook('post-tool', payload).stdout, '')
        self.metrics(20)
        self.assertIn('CRITICAL', self.run_hook('post-tool', payload).stdout)
        self.metrics(90)
        self.run_hook('post-tool', payload)
        self.metrics(30)
        self.assertIn('WARNING', self.run_hook('post-tool', payload).stdout)

    def test_repo_profile_route_and_debounce(self):
        self.repo_profile()
        (self.root / '.osengineer').mkdir(exist_ok=True)
        (self.root / '.osengineer/skill-registry.json').write_text(json.dumps({'skills': [
            {'name': 'dispatch', 'canonical': '.claude/skills/dispatch', 'projections': {'codex': '.agents/skills/dispatch'}},
            {'name': 'judge', 'canonical': '.agents/skills/judge'}]}))
        self.metrics(30)
        out = self.prompt('check the dispatch workflow and judge')
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn('dispatch', out.stdout)
        self.assertNotIn('- judge', out.stdout)
        self.assertNotIn('TDD', out.stdout)
        self.assertLess(len(out.stdout), 650)
        self.assertEqual(self.prompt('check the dispatch workflow and judge').stdout, '')
        self.state('blocked')
        self.assertIn('Edits are denied', self.prompt('check the dispatch workflow and judge').stdout)

    def test_workbench_profile_detected(self):
        self.repo_profile(workbench=True)
        self.assertIn('Repo profile', self.prompt().stdout)

    def test_repo_profile_uses_repository_scope_not_legacy_team(self):
        (self.root / '.osengineer/teams').mkdir()
        (self.root / '.osengineer/teams/coding.json').write_text('{"owns_paths":["src/**"]}')
        for repo_profile in (False, True):
            if repo_profile:
                self.repo_profile()
            self.state('execute')
            with (self.root / '.osengineer/state.yml').open('a') as handle:
                handle.write('current_team: coding\n')
            result = self.run_hook('pre-edit-guard', {'cwd': str(self.root), 'tool_name': 'Edit',
                'tool_input': {'file_path': 'apps/web/app.ts'}})
            if repo_profile:
                self.assertEqual(result.stdout, '')
            else:
                self.assertEqual(json.loads(result.stdout)['decision'], 'block')

    def test_generic_missing_or_invalid_team_cache_denied(self):
        (self.root / '.osengineer/teams').mkdir()
        for content in (None, '{', '{"owns_paths": []}', '{"owns_paths": "src/**"}'):
            path = self.root / '.osengineer/teams/coding.json'
            if content is not None:
                path.write_text(content)
            self.state('execute')
            with (self.root / '.osengineer/state.yml').open('a') as handle:
                handle.write('current_team: coding\n')
            result = self.run_hook('pre-edit-guard', {'cwd': str(self.root), 'tool_name': 'Edit',
                'tool_input': {'file_path': 'src/app.py'}})
            self.assertIn('configuration fault', result.stdout)
            self.assertEqual(json.loads(result.stdout)['decision'], 'block')

    def test_repo_profile_telemetry_creates_no_execution_state(self):
        self.repo_profile()
        (self.root / '.osengineer/state.yml').unlink()
        self.metrics(30)
        result = self.run_hook('post-tool', {'session_id': self.session, 'cwd': str(self.root)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / '.osengineer/state.yml').exists())
        telemetry = json.loads((self.root / '.plans/osengineer/context.json').read_text())
        self.assertEqual(telemetry['context_used_pct'], 70)
        self.assertNotIn('phase', telemetry)

    def test_invalid_profile_observable(self):
        (self.root / '.osengineer/profile.json').write_text('{')
        result = self.prompt()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['decision'], 'block')
        self.assertIn('JSONDecodeError', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

if __name__ == '__main__':
    unittest.main()
