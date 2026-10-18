import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from repo_runtime.runtime import ContractError, load_contract, preflight, run, verify


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        (self.repo / "src").mkdir()
        (self.repo / "src/a.txt").write_text("initial\n")
        (self.repo / "policy.md").write_text("Observe repository policy\n")
        self.git("add", ".")
        self.git("commit", "-qm", "initial")
        self.contract = dict(schemaVersion=1, goal="Change src", baseSha=self.git("rev-parse", "HEAD").strip(), allowedPaths=["src/"], acceptanceCommands=[[sys.executable, "-c", "print('checked')"]], repoPolicy="policy.md", wallLimitSeconds=5)
        self.path = self.root / "contract.json"
        self.runner = self.root / "fake-runner"
        self.make_runner("pass")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True)

    def load(self):
        self.path.write_text(json.dumps(self.contract))
        return load_contract(self.path, self.repo)

    def make_runner(self, body):
        self.runner.write_text("#!" + sys.executable + "\nimport os,json,time\nfrom pathlib import Path\n" + body + "\nPath(os.environ['OSE_PROFILE_RESULT_PATH']).write_text(json.dumps({'status':'passed','summary':'done'}))\n")
        self.runner.chmod(0o755)

    def execute(self, **kwargs):
        c, repo = self.load()
        return run(c, repo, runner=str(self.runner), out=self.root / "out", **kwargs)

    def test_pass_and_verify(self):
        self.make_runner("Path('src/a.txt').write_text('changed')")
        result = self.execute()
        self.assertEqual(result["status"], "passed", result)
        c, repo = self.load()
        self.assertEqual(verify(c, repo, self.root / "out/result.json")["status"], "passed")
        (repo / "src/a.txt").write_text("later")
        self.assertEqual(verify(c, repo, self.root / "out/result.json")["status"], "failed")

    def test_runner_can_commit_authorized_changes_with_result_sha_receipts(self):
        self.make_runner("import subprocess; Path('src/a.txt').write_text('committed'); subprocess.run(['git','add','src/a.txt'],check=True); subprocess.run(['git','commit','-qm','authorized fix'],check=True)")
        result = self.execute()
        self.assertEqual(result['status'], 'passed', result)
        self.assertNotEqual(result['completedSha'], result['baseSha'])
        self.assertEqual(result['checks'][0]['checkedSha'], result['completedSha'])
        c, repo = self.load()
        self.assertEqual(verify(c, repo, self.root / 'out/result.json')['status'], 'passed')

    def test_acceptance_revision_change_is_rejected(self):
        self.contract['acceptanceCommands'] = [['git','commit','--allow-empty','-qm','unrelated check mutation']]
        self.assertEqual(self.execute()['status'], 'failed')

    def test_policy_digest_binds_later_policy_changes(self):
        result = self.execute()
        (self.repo / 'policy.md').write_text('changed rules')
        self.contract['allowedPaths'].append('policy.md')
        c, repo = self.load()
        self.assertEqual(verify(c, repo, self.root / 'out/result.json')['status'], 'failed')

    def test_plan_digest_requires_actual_matching_plan_file(self):
        import hashlib
        self.contract['planDigest'] = 'a' * 64
        with self.assertRaises(ContractError):
            self.load()
        self.contract['planPath'] = 'policy.md'
        with self.assertRaises(ContractError):
            self.load()
        self.contract['planDigest'] = hashlib.sha256((self.repo / 'policy.md').read_bytes()).hexdigest()
        self.assertEqual(self.load()[0]['planDigest'], self.contract['planDigest'])

    def test_stale_policy_preflight_prevents_runner_start(self):
        self.contract['allowedPaths'].append('policy.md')
        c, repo = self.load()
        (repo / 'policy.md').write_text('new policy')
        self.assertEqual(preflight(c, repo)['status'], 'needs-human')
        result = run(c, repo, runner=str(self.runner), out=self.root / 'out')
        self.assertEqual(result['status'], 'needs-human')
        self.assertIsNone(result['runner'])

    def test_runner_policy_mutation_fails_before_acceptance(self):
        self.contract['allowedPaths'].append('policy.md')
        self.make_runner("Path('policy.md').write_text('mutated')")
        result = self.execute()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['checks'], [])

    def test_policy_file_is_bound_even_with_auxiliary_policy(self):
        import hashlib
        (self.repo / 'POLICY.md').write_text('Canonical authority')
        self.git('add', 'POLICY.md'); self.git('commit', '-qm', 'policy')
        self.contract['baseSha'] = self.git('rev-parse', 'HEAD').strip()
        self.contract['allowedPaths'].append('POLICY.md')
        c, repo = self.load()
        self.assertEqual(c['policyFileDigest'], hashlib.sha256((repo / 'POLICY.md').read_bytes()).hexdigest())
        (repo / 'POLICY.md').write_text('new authority')
        self.assertEqual(preflight(c, repo)['status'], 'needs-human')

    def test_cached_contract_verify_detects_ignored_plan_changes(self):
        import hashlib
        (self.repo / '.git/info/exclude').write_text('plan.md\n')
        (self.repo / 'plan.md').write_text('approved plan')
        self.contract.update(planPath='plan.md', planDigest=hashlib.sha256((self.repo / 'plan.md').read_bytes()).hexdigest())
        c, repo = self.load()
        result = run(c, repo, runner=str(self.runner), out=self.root / 'out')
        self.assertEqual(result['status'], 'passed')
        (repo / 'plan.md').write_text('different plan')
        self.assertEqual(verify(c, repo, self.root / 'out/result.json')['status'], 'failed')
        self.assertEqual(preflight(c, repo)['status'], 'needs-human')

    def test_acceptance_mutation_of_ignored_plan_fails(self):
        import hashlib
        (self.repo / '.git/info/exclude').write_text('plan.md\n')
        (self.repo / 'plan.md').write_text('approved plan')
        self.contract.update(planPath='plan.md', planDigest=hashlib.sha256((self.repo / 'plan.md').read_bytes()).hexdigest(),
            acceptanceCommands=[[sys.executable, '-c', "from pathlib import Path; Path('plan.md').write_text('changed')"]])
        self.assertEqual(self.execute()['status'], 'failed')

    def test_no_runner_shadow(self):
        c, repo = self.load()
        result = run(c, repo, mode="shadow", out=self.root / "out")
        self.assertEqual(result["status"], "not-run")
        self.assertIsNone(result["runner"])

    def make_codex_like(self, name):
        """A runner that records its argv and answers like `codex exec`."""
        runner = self.root / "bin" / name
        runner.parent.mkdir(exist_ok=True)
        runner.write_text("#!" + sys.executable + "\nimport json,sys\nfrom pathlib import Path\n"
            "Path(%r).write_text(json.dumps(sys.argv[1:]))\n"
            "a=sys.argv\nfinal=a[a.index('--output-last-message')+1] if '--output-last-message' in a else __import__('os').environ['OSE_PROFILE_RESULT_PATH']\n"
            "Path(final).write_text(json.dumps({'status':'passed','summary':'done'}))\n" % str(self.root / "argv.json"))
        runner.chmod(0o755)
        return runner

    def set_profile(self, data):
        (self.repo / ".osengineer").mkdir(exist_ok=True)
        (self.repo / ".osengineer" / "profile.json").write_text(json.dumps(data))
        self.git("add", ".")
        self.git("commit", "-qm", "profile")
        self.contract["baseSha"] = self.git("rev-parse", "HEAD").strip()

    def runner_argv(self, runner):
        c, repo = self.load()
        out = self.root / "out"
        while out.exists():
            out = out.with_name(out.name + "-")
        result = run(c, repo, runner=str(runner), out=out)
        self.assertEqual(result["status"], "passed", result["reasons"])
        return json.loads((self.root / "argv.json").read_text())

    def test_runner_named_codex_uses_codex_exec_by_default(self):
        self.assertEqual(self.runner_argv(self.make_codex_like("codex"))[:2], ["exec", "--json"])

    def test_codex_runner_name_is_configurable(self):
        self.set_profile({"codexRunner": "codex-nightly"})
        self.assertEqual(self.runner_argv(self.make_codex_like("codex-nightly"))[:2], ["exec", "--json"])

    def test_configured_name_replaces_the_default(self):
        self.set_profile({"codexRunner": "codex-nightly"})
        self.assertEqual(self.runner_argv(self.make_codex_like("codex")), [],
                         "only the configured name selects the codex exec protocol")

    def test_invalid_codex_runner_falls_back_to_default(self):
        for bad in ("", "bin/codex", 7, None):
            self.set_profile({"codexRunner": bad, "n": str(bad)})
            self.assertEqual(self.runner_argv(self.make_codex_like("codex"))[:2], ["exec", "--json"], bad)

    def test_missing_runner(self):
        c, repo = self.load()
        result = run(c, repo, runner="missing-runner-123", out=self.root / "out")
        self.assertEqual(result["status"], "needs-human")

    def test_stale_base(self):
        self.git("commit", "--allow-empty", "-qm", "new")
        c, repo = self.load()
        self.assertEqual(preflight(c, repo)["status"], "needs-human")

    def test_unknown_sha(self):
        self.contract["baseSha"] = "1" * 40
        with self.assertRaises(ContractError):
            self.load()

    def test_numbers_bool_zero(self):
        for key in ("schemaVersion", "attempts", "wallLimitSeconds"):
            original = self.contract.get(key)
            for value in (True, 0, -1, "1"):
                self.contract[key] = value
                with self.assertRaises(ContractError, msg=(key, value)):
                    self.load()
            if original is None:
                del self.contract[key]
            else:
                self.contract[key] = original

    def test_path_escape_and_symlink(self):
        for value in ("../outside", "/tmp/anything", "src/../x", ".git/", "src//x"):
            self.contract["allowedPaths"] = [value]
            with self.assertRaises(ContractError):
                self.load()
        (self.repo / "escape").symlink_to(self.root)
        self.contract["allowedPaths"] = ["escape/file"]
        with self.assertRaises(ContractError):
            self.load()

    def test_untracked_out_of_scope_before(self):
        (self.repo / "outside.txt").write_text("x")
        result = self.execute()
        self.assertEqual(result["status"], "needs-human")
        self.assertIsNone(result["runner"])

    def test_untracked_out_of_scope_after(self):
        self.make_runner("Path('outside.txt').write_text('x')")
        self.assertEqual(self.execute()["status"], "failed")

    def test_deleted_out_of_scope(self):
        self.make_runner("Path('policy.md').unlink()")
        self.assertEqual(self.execute()["status"], "failed")

    def test_renamed_out_of_scope(self):
        self.make_runner("Path('src/a.txt').rename('outside.txt')")
        self.assertEqual(self.execute()["status"], "failed")

    def test_acceptance_failure(self):
        self.contract["acceptanceCommands"] = [[sys.executable, "-c", "raise SystemExit(7)"]]
        r = self.execute()
        self.assertEqual(r["status"], "failed")
        self.assertEqual(r["checks"][0]["exitCode"], 7)

    def test_acceptance_mutation(self):
        self.contract["acceptanceCommands"] = [[sys.executable, "-c", "from pathlib import Path; Path('src/a.txt').write_text('mutated')"]]
        self.assertEqual(self.execute()["status"], "failed")

    def test_timeout(self):
        self.contract["wallLimitSeconds"] = 1
        self.make_runner("time.sleep(10)")
        r = self.execute()
        self.assertEqual(r["status"], "failed")
        self.assertTrue(r["runner"]["timedOut"])

    def test_no_acceptance_is_not_green(self):
        self.contract["acceptanceCommands"] = []
        self.assertEqual(self.execute()["status"], "not-run")

    def test_shell_string_rejected(self):
        self.contract["acceptanceCommands"] = ["pytest && echo passed"]
        with self.assertRaises(ContractError):
            self.load()

    def test_shadow_remote_effects_rejected(self):
        self.contract["authorizedEffects"] = ["local", "draft-pr"]
        self.assertEqual(self.execute(mode="shadow")["status"], "needs-human")

    def test_log_tampering_fails_verify(self):
        r = self.execute()
        Path(r["checks"][0]["stdout"]).write_text("tampered")
        c, repo = self.load()
        self.assertEqual(verify(c, repo, self.root / "out/result.json")["status"], "failed")

    def test_receipt_directory_cannot_be_overwritten(self):
        self.execute()
        with self.assertRaises(ContractError):
            self.execute()

    def test_in_repo_artifact_default(self):
        c, repo = self.load()
        r = run(c, repo, runner=str(self.runner))
        self.assertEqual(r["status"], "passed", r)
        self.assertEqual(verify(c, repo, Path(r["artifactDirectory"]) / "result.json")["status"], "passed")

    def test_repeat_default_without_gitignore(self):
        c, repo = self.load()
        first = run(c, repo, runner=str(self.runner))
        second = run(c, repo, runner=str(self.runner))
        self.assertEqual(first["status"], "passed")
        self.assertEqual(second["status"], "passed", second)
        (repo / ".plans/osengineer/unrelated.txt").write_text("not an artifact")
        self.assertEqual(run(c, repo, runner=str(self.runner))["status"], "needs-human")

    def test_hook_context_telemetry_is_not_a_scope_change(self):
        """The PostToolUse hook fires on every tool call, also around runtime runs."""
        import time, uuid
        (self.repo / ".osengineer").mkdir()
        (self.repo / ".osengineer/profile.json").write_text('{"profile":"repo"}')
        self.git("add", ".")
        self.git("commit", "-qm", "repo profile")
        self.contract["baseSha"] = self.git("rev-parse", "HEAD").strip()
        session = "ose-test-" + uuid.uuid4().hex
        metrics = Path(tempfile.gettempdir()) / f"claude-ctx-{session}.json"
        self.addCleanup(metrics.unlink, missing_ok=True)
        hook = Path(__file__).resolve().parents[1] / "hooks/osEngineer-post-tool.py"

        def tool_call():
            metrics.write_text(json.dumps({"session_id": session, "remaining_percentage": 60,
                                           "used_pct": 40, "timestamp": int(time.time())}))
            p = subprocess.run([sys.executable, str(hook)], input=json.dumps({"session_id": session, "cwd": str(self.repo)}),
                               text=True, capture_output=True)
            self.assertEqual(p.returncode, 0, p.stderr)

        tool_call()
        c, repo = self.load()
        self.assertEqual(preflight(c, repo)["status"], "passed", preflight(c, repo))
        r = run(c, repo, runner=str(self.runner))
        self.assertEqual(r["status"], "passed", r)
        tool_call()
        self.assertEqual(verify(c, repo, Path(r["artifactDirectory"]) / "result.json")["status"], "passed")

    def test_registered_artifact_tampering_rejected(self):
        c, repo = self.load()
        first = run(c, repo, runner=str(self.runner))
        Path(first["checks"][0]["stdout"]).write_text("tampered")
        with self.assertRaises(ContractError):
            run(c, repo, runner=str(self.runner))

    def test_runner_without_structured_final(self):
        self.runner.write_text("#!" + sys.executable + "\nprint('success')\n")
        self.assertEqual(self.execute()["status"], "needs-human")

    def test_acceptance_timeout(self):
        self.contract["wallLimitSeconds"] = 1
        self.contract["acceptanceCommands"] = [[sys.executable, "-c", "import time; time.sleep(10)"]]
        r = self.execute()
        self.assertEqual(r["status"], "failed")
        self.assertTrue(r["checks"][0]["timedOut"])


if __name__ == "__main__":
    unittest.main()
