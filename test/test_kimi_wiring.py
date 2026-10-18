"""osEngineer must wire Kimi where Kimi actually looks.

Verified against Kimi Code 0.36.1:

  * `resolveConfigPath(input) = input.configPath ?? join(resolveKimiHome(...),
    "config.toml")` and `resolveKimiHome(homeDir) = homeDir ?? KIMI_CODE_HOME ??
    join(homedir(), ".kimi-code")`. Config is resolved ONLY from Kimi home —
    there is no project-level config.toml. So hook wiring is machine-global and
    repo membership must be decided inside the hook from the payload cwd.

  * `HookDefSchema = object({event, matcher, command, timeout}).strict()`.
    `.strict()` means Claude's `type: "command"` and `description` keys are
    REJECTED outright.

  * The string "settings.json" does not appear in the Kimi binary at all, so
    install.sh's `$repo/.$runtime/settings.json` is written into a void.

  * Project-level `.kimi-code/` does hold AGENTS.md and skills/, so per-repo
    team context is expressible there even though hooks are not.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - py<3.11
    tomllib = None

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install.sh"
UNINSTALL = ROOT / "uninstall.sh"

KIMI_BIN = Path("/root/.kimi-code/bin/kimi")

# Hooks that make sense on Kimi. SessionStart output is discarded and
# PostToolUse early-returns on a statusline bridge file Kimi cannot produce.
EXPECTED_HOOK_SCRIPTS = {
    "osEngineer-prompt-guard.py",
    "osEngineer-pre-edit-guard.py",
    "osEngineer-pre-bash-guard.py",
    "osEngineer-read-guard.py",
}

ALLOWED_HOOK_KEYS = {"event", "matcher", "command", "timeout"}


def run_install(repo, home, kimi_home, runtimes="claude kimi", extra=None):
    env = dict(os.environ)
    env.update({
        "OSE_NONINTERACTIVE": "1",
        "HOME": str(home),
        "KIMI_CODE_HOME": str(kimi_home),
        "RUNTIMES": runtimes,
    })
    env.pop("CI", None)
    if extra:
        env.update(extra)
    return subprocess.run(
        ["bash", str(INSTALL), str(repo)],
        capture_output=True, text=True, timeout=300, env=env,
    )


def run_uninstall(repo, home, kimi_home):
    env = dict(os.environ)
    env.update({
        "OSE_NONINTERACTIVE": "1",
        "HOME": str(home),
        "KIMI_CODE_HOME": str(kimi_home),
    })
    env.pop("CI", None)
    return subprocess.run(
        ["bash", str(UNINSTALL), str(repo)],
        capture_output=True, text=True, timeout=300, env=env,
    )


def make_git_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True)
    (path / "README.md").write_text("# test\n")
    (path / "main.py").write_text("print('x')\n")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=path, check=True)
    return path


def read_hooks(kimi_home):
    cfg = Path(kimi_home) / "config.toml"
    if not cfg.exists():
        return None
    if tomllib is None:
        return []
    with open(cfg, "rb") as f:
        return tomllib.load(f).get("hooks", [])


def ose_hooks(kimi_home):
    hooks = read_hooks(kimi_home) or []
    return [h for h in hooks if "osEngineer-" in (h.get("command") or "")]


class KimiWiringBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = Path(self.tmp) / "home"
        self.kimi_home = Path(self.tmp) / "kimihome"
        self.home.mkdir()
        self.kimi_home.mkdir()
        # A pre-existing config with a foreign hook that must survive untouched.
        (self.kimi_home / "config.toml").write_text(
            'default_model = "kimi-for-coding/kimi-k2-thinking"\n'
            "\n"
            "[[hooks]]\n"
            'event = "PreToolUse"\n'
            'matcher = "Bash"\n'
            'command = "python3 /opt/other/unrelated-guard.py"\n'
            "timeout = 30\n"
        )
        self.repo = make_git_repo(Path(self.tmp) / "repo")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestKimiConfigIsWrittenWhereKimiLooks(KimiWiringBase):
    def test_hooks_land_in_kimi_home_config_toml(self):
        proc = run_install(self.repo, self.home, self.kimi_home)
        self.assertEqual(proc.returncode, 0, f"install failed:\n{proc.stdout}\n{proc.stderr}")
        entries = ose_hooks(self.kimi_home)
        self.assertTrue(
            entries,
            "no osEngineer [[hooks]] entries in $KIMI_CODE_HOME/config.toml — "
            "Kimi resolves config only from Kimi home and reads no settings.json",
        )

    def test_no_inert_kimi_settings_json(self):
        run_install(self.repo, self.home, self.kimi_home)
        stray = self.repo / ".kimi" / "settings.json"
        self.assertFalse(
            stray.exists(),
            "install wrote .kimi/settings.json, a file Kimi never reads "
            '("settings.json" has zero occurrences in the Kimi binary)',
        )

    def test_config_remains_valid_toml(self):
        run_install(self.repo, self.home, self.kimi_home)
        if tomllib is None:
            self.skipTest("tomllib unavailable")
        with open(self.kimi_home / "config.toml", "rb") as f:
            tomllib.load(f)  # raises on malformed output

    def test_foreign_hooks_and_settings_survive(self):
        run_install(self.repo, self.home, self.kimi_home)
        hooks = read_hooks(self.kimi_home) or []
        foreign = [h for h in hooks if "unrelated-guard" in (h.get("command") or "")]
        self.assertEqual(len(foreign), 1, f"foreign hook clobbered: {hooks}")
        raw = (self.kimi_home / "config.toml").read_text()
        self.assertIn("kimi-for-coding/kimi-k2-thinking", raw, "user config lost")


class TestKimiHookEntryShape(KimiWiringBase):
    def test_entries_use_only_the_strict_schema_keys(self):
        run_install(self.repo, self.home, self.kimi_home)
        for h in ose_hooks(self.kimi_home):
            extra = set(h) - ALLOWED_HOOK_KEYS
            self.assertEqual(
                extra, set(),
                f"HookDefSchema is .strict(); these keys are rejected: {extra} in {h}",
            )

    def test_expected_guards_are_wired(self):
        run_install(self.repo, self.home, self.kimi_home)
        wired = {
            Path(h["command"].split()[-1].strip('"')).name
            for h in ose_hooks(self.kimi_home)
        }
        missing = EXPECTED_HOOK_SCRIPTS - wired
        self.assertEqual(missing, set(), f"guards not wired on Kimi: {missing}")

    def test_command_bakes_osengineer_home(self):
        """Kimi's config schema has no env block and it does not set
        CLAUDE_PROJECT_DIR, so OSENGINEER_HOME must ride in the command."""
        run_install(self.repo, self.home, self.kimi_home)
        for h in ose_hooks(self.kimi_home):
            self.assertIn(
                "OSENGINEER_HOME=", h["command"],
                f"no OSENGINEER_HOME in command; Kimi cannot supply it: {h}",
            )

    def test_events_are_valid_kimi_events(self):
        valid = {
            "PreToolUse", "PostToolUse", "PostToolUseFailure", "PermissionRequest",
            "PermissionResult", "UserPromptSubmit", "Stop", "StopFailure",
            "Interrupt", "SessionStart", "SessionEnd", "SubagentStart",
            "SubagentStop", "PreCompact", "PostCompact", "Notification",
        }
        run_install(self.repo, self.home, self.kimi_home)
        for h in ose_hooks(self.kimi_home):
            self.assertIn(h.get("event"), valid, f"not a Kimi hook event: {h}")


class TestKimiWiringIsIdempotent(KimiWiringBase):
    def test_second_install_does_not_duplicate(self):
        run_install(self.repo, self.home, self.kimi_home)
        first = ose_hooks(self.kimi_home)
        run_install(self.repo, self.home, self.kimi_home)
        second = ose_hooks(self.kimi_home)
        self.assertEqual(
            len(first), len(second),
            f"re-install duplicated hook entries: {len(first)} -> {len(second)}",
        )


class TestKimiUnwiring(KimiWiringBase):
    def test_uninstall_removes_osengineer_hooks_only(self):
        run_install(self.repo, self.home, self.kimi_home)
        self.assertTrue(ose_hooks(self.kimi_home), "precondition: hooks installed")
        proc = run_uninstall(self.repo, self.home, self.kimi_home)
        self.assertEqual(proc.returncode, 0, f"uninstall failed:\n{proc.stderr}")
        self.assertEqual(
            ose_hooks(self.kimi_home), [],
            "uninstall left osEngineer hooks in the global Kimi config",
        )
        hooks = read_hooks(self.kimi_home) or []
        self.assertEqual(
            len([h for h in hooks if "unrelated-guard" in (h.get("command") or "")]), 1,
            "uninstall removed a foreign hook",
        )


class TestRepoLedger(KimiWiringBase):
    def test_ledger_records_wired_repos(self):
        """Kimi config is global, so uninstall must know when the last repo is
        gone before touching the machine-wide file."""
        run_install(self.repo, self.home, self.kimi_home)
        ledger = self.home / ".osengineer" / "repos.json"
        self.assertTrue(ledger.exists(), "no ~/.osengineer/repos.json ledger written")
        data = json.loads(ledger.read_text())
        blob = json.dumps(data)
        self.assertIn(
            str(self.repo.resolve()), blob,
            f"ledger does not record the wired repo: {data}",
        )

    def test_uninstall_prunes_ledger(self):
        run_install(self.repo, self.home, self.kimi_home)
        run_uninstall(self.repo, self.home, self.kimi_home)
        ledger = self.home / ".osengineer" / "repos.json"
        if not ledger.exists():
            return
        self.assertNotIn(
            str(self.repo.resolve()), json.dumps(json.loads(ledger.read_text())),
            "uninstall left the repo in the ledger",
        )


class TestPerRepoKimiTeamContext(KimiWiringBase):
    def test_project_kimi_agents_md_is_written(self):
        """Teams live in each repo. Kimi reads <project root>/.kimi-code/AGENTS.md,
        which is the per-repo seam Kimi does support."""
        run_install(self.repo, self.home, self.kimi_home)
        agents = self.repo / ".kimi-code" / "AGENTS.md"
        self.assertTrue(
            agents.exists(),
            "no .kimi-code/AGENTS.md — Kimi gets no per-repo team context",
        )


@unittest.skipUnless(KIMI_BIN.exists(), "kimi not installed")
class TestKimiAcceptsGeneratedConfig(KimiWiringBase):
    def test_kimi_doctor_validates(self):
        run_install(self.repo, self.home, self.kimi_home)
        env = dict(os.environ)
        env["KIMI_CODE_HOME"] = str(self.kimi_home)
        proc = subprocess.run(
            [str(KIMI_BIN), "doctor"],
            capture_output=True, text=True, timeout=120, env=env,
        )
        self.assertIn(
            "valid", (proc.stdout + proc.stderr).lower(),
            f"kimi doctor rejected the generated config:\n{proc.stdout}\n{proc.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
