import copy
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from repo_profile.install import install, uninstall, SKILL_REL, LINK_REL, PROFILE_REL
from repo_profile.learning import validate, compare, summarize, read

ROOT = Path(__file__).resolve().parent.parent


def receipt(**updates):
    row = {'schemaVersion': 1, 'taskId': 'domain-change', 'model': 'fixture', 'repetition': 1,
           'condition': 'baseline', 'profileVersion': '0.1.0', 'status': 'passed',
           'inputTokens': 100, 'outputTokens': 20, 'wallSeconds': 2.5, 'corrections': 0,
           'checks': [{'name': 'domain-parity', 'status': 'passed'}], 'evidence': ['tests/parity.py:12']}
    row.update(updates)
    return row


class ProfileInstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        (self.repo / 'POLICY.md').write_text('Canonical existing policy\n')
        (self.repo / 'CLAUDE.md').symlink_to('POLICY.md')
        settings = self.repo / '.claude/settings.json'
        settings.parent.mkdir(parents=True)
        settings.write_text('{"hooks":{"Stop":[{"foreign":"keep"}]}}\n')
        registry = self.repo / '.osengineer/skill-registry.json'
        registry.parent.mkdir()
        registry.write_text(json.dumps({'policy': 'POLICY.md', 'skills': [
            {'name': 'dispatch', 'canonical': '.claude/skills/dispatch', 'projections': {'codex': '.agents/skills/dispatch'}}], 'foreign': True}))
        self.original = {p: (self.repo / p).read_bytes() for p in ('POLICY.md', 'CLAUDE.md', '.claude/settings.json')}

    def tearDown(self):
        self.tmp.cleanup()

    def assert_preserved(self):
        for path, content in self.original.items():
            self.assertEqual((self.repo / path).read_bytes(), content)
        self.assertTrue((self.repo / 'CLAUDE.md').is_symlink())

    def test_install_reinstall_uninstall_preserves_policy_and_foreign_settings(self):
        install(self.repo)
        self.assert_preserved()
        self.assertTrue((self.repo / LINK_REL).is_symlink())
        self.assertTrue((self.repo / SKILL_REL / 'scripts/repo_runtime/__main__.py').is_file())
        self.assertFalse((self.repo / 'planning').exists())
        self.assertFalse((self.repo / '.osengineer/state.yml').exists())
        install(self.repo)
        registry = json.loads((self.repo / '.osengineer/skill-registry.json').read_text())
        self.assertEqual(sum(r['name'] == 'osengineer-repo-profile' for r in registry['skills']), 1)
        # Preserve a concurrent foreign registry update on removal.
        registry['skills'].append({'name': 'foreign', 'canonical': 'foreign'})
        (self.repo / '.osengineer/skill-registry.json').write_text(json.dumps(registry))
        uninstall(self.repo)
        self.assert_preserved()
        self.assertFalse((self.repo / SKILL_REL).exists())
        registry = json.loads((self.repo / '.osengineer/skill-registry.json').read_text())
        self.assertEqual([r['name'] for r in registry['skills']], ['dispatch', 'foreign'])

    def test_install_refuses_foreign_skill(self):
        path = self.repo / SKILL_REL
        path.mkdir(parents=True)
        (path / 'SKILL.md').write_text('foreign skill')
        with self.assertRaises(ValueError):
            install(self.repo)
        self.assertEqual((path / 'SKILL.md').read_text(), 'foreign skill')
        self.assert_preserved()

    def test_changed_owned_file_prevents_reinstall_and_uninstall(self):
        install(self.repo)
        path = self.repo / SKILL_REL / 'SKILL.md'
        path.write_text('local customisation')
        for operation in (install, uninstall):
            with self.assertRaises(ValueError):
                operation(self.repo)
        self.assertEqual(path.read_text(), 'local customisation')

    def test_projection_parent_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as external:
            path = self.repo / '.agents/skills'
            path.parent.mkdir()
            path.symlink_to(external, target_is_directory=True)
            with self.assertRaises(ValueError):
                install(self.repo)
            self.assertEqual(list(Path(external).iterdir()), [])

    def test_installed_entrypoint_is_portable_and_no_global_path_required(self):
        install(self.repo)
        entry = self.repo / SKILL_REL / 'scripts/repo_profile.py'
        result = subprocess.run(['python3', str(entry), 'runtime', '--help'], capture_output=True, text=True, cwd='/tmp')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('run', result.stdout)
        # Normal Python execution may create disposable bytecode in the skill.
        cache = entry.parent / 'repo_runtime/__pycache__'
        cache.mkdir(exist_ok=True)
        (cache / 'runtime.fixture.pyc').write_bytes(b'generated bytecode')
        install(self.repo)
        uninstall(self.repo)
        self.assert_preserved()

    def test_installed_runtime_runs_and_verifies_from_other_directory(self):
        import sys
        install(self.repo)
        subprocess.run(['git', '-C', str(self.repo), 'config', 'user.name', 'Test'], check=True)
        subprocess.run(['git', '-C', str(self.repo), 'config', 'user.email', 'test@example.invalid'], check=True)
        (self.repo / 'src').mkdir()
        (self.repo / 'src/value.txt').write_text('before')
        subprocess.run(['git', '-C', str(self.repo), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.repo), 'commit', '-qm', 'fixture'], check=True)
        base = subprocess.check_output(['git', '-C', str(self.repo), 'rev-parse', 'HEAD'], text=True).strip()
        with tempfile.TemporaryDirectory() as external:
            root = Path(external)
            contract = root / 'contract.json'
            contract.write_text(json.dumps({'schemaVersion': 1, 'goal': 'Update value', 'baseSha': base,
                'allowedPaths': ['src/'], 'acceptanceCommands': [[sys.executable, '-c',
                "from pathlib import Path; assert Path('src/value.txt').read_text() == 'after'"]]}))
            runner = root / 'runner'
            runner.write_text('#!' + sys.executable + "\nimport json,os\nfrom pathlib import Path\n"
                "Path('src/value.txt').write_text('after')\n"
                "Path(os.environ['OSE_PROFILE_RESULT_PATH']).write_text(json.dumps({'status':'passed','summary':'updated'}))\n")
            runner.chmod(0o755)
            entry = self.repo / SKILL_REL / 'scripts/repo_profile.py'
            common = [sys.executable, str(entry), 'runtime']
            args = ['--repo', str(self.repo), '--contract', str(contract)]
            result = subprocess.run(common + ['run'] + args + ['--mode', 'headless', '--runner',
                str(runner), '--out', str(root / 'run')], cwd=external, text=True, capture_output=True,
                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads((root / 'run/result.json').read_text())['status'], 'passed')
            result = subprocess.run(common + ['verify'] + args + ['--result', str(root / 'run/result.json')],
                cwd=external, text=True, capture_output=True,
                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_package_failure_preserves_existing_repository(self):
        with tempfile.TemporaryDirectory() as missing:
            with self.assertRaises((ValueError, OSError)):
                install(self.repo, source=missing)
        self.assert_preserved()
        self.assertFalse((self.repo / SKILL_REL).exists())


class Learning(unittest.TestCase):
    def test_schema_version_is_strict_integer(self):
        for value in (True, 1.0, '1'):
            with self.assertRaises(ValueError):
                validate(receipt(schemaVersion=value))

    def test_mixed_learning_cohorts_are_rejected(self):
        for mixed in (receipt(taskId='second', profileVersion='0.2.0'),
                      receipt(taskId='second', condition='candidate')):
            rows = [receipt(), mixed]
            with self.assertRaises(ValueError):
                summarize(rows)
            with self.assertRaises(ValueError):
                compare(rows, [receipt(condition='candidate'), receipt(taskId='second', condition='candidate')])

    def test_homogeneous_different_versions_can_be_compared(self):
        result = compare([receipt()], [receipt(condition='candidate', profileVersion='0.2.0')])
        self.assertTrue(result['comparable'])

    def test_passed_requires_observed_checks(self):
        with self.assertRaises(ValueError):
            validate(receipt(checks=[]))
        with self.assertRaises(ValueError):
            validate(receipt(checks=[{'name': 'check', 'status': 'not-run'}]))

    def test_raw_transcript_and_nonfinite_metrics_are_rejected(self):
        for row in (receipt(prompt='raw'), receipt(inputTokens=True), receipt(wallSeconds=float('nan')),
                    receipt(evidence=['Bearer synthetically-secret'])):
            with self.assertRaises(ValueError):
                validate(row)

    def test_comparison_requires_same_case_model_repetitions(self):
        with self.assertRaises(ValueError):
            compare([receipt()], [receipt(taskId='different')])
        with self.assertRaises(ValueError):
            compare([receipt()], [receipt(repetition=2)])
        result = compare([receipt()], [receipt(condition='candidate', inputTokens=60)])
        self.assertEqual(result['tokensDelta'], -40)
        self.assertFalse(result['improvementProven'])

    def test_reports_observed_failure_without_inventing_success(self):
        result = summarize([receipt(), receipt(repetition=2, status='failed', inputTokens=150)])
        self.assertEqual(result['passAt1'], 1)
        self.assertEqual(result['allObservedRepetitionsPassRate'], 0)
        self.assertEqual(result['passed'], 1)
        self.assertEqual(result['tokensPerSuccessfulTask'], 290)

    def test_duplicate_receipts_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'usage.jsonl'
            path.write_text('\n'.join([json.dumps(receipt())] * 2))
            with self.assertRaises(ValueError):
                read(path)

    def test_record_does_not_modify_skill_or_write_remote(self):
        with tempfile.TemporaryDirectory() as temp:
            path, out = Path(temp) / 'input.json', Path(temp) / 'usage.jsonl'
            path.write_text(json.dumps(receipt()))
            result = subprocess.run(['python3', '-m', 'repo_profile.learning', 'record',
                                     '--input', str(path), '--out', str(out)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(read(out), [receipt()])
            again = subprocess.run(['python3', '-m', 'repo_profile.learning', 'record',
                                    '--input', str(path), '--out', str(out)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(again.returncode, 1)
            self.assertEqual(len(read(out)), 1)


if __name__ == '__main__':
    unittest.main()
