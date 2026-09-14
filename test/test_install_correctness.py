"""install.sh must install what it documents, and must not leak credentials.

Six defects, each verified against the current tree:

  * MANDATORY_AGENTS (install.sh:33-43) is a hardcoded 17-name array while 22
    agent directories exist. budget-tracker, dba, qa, sync-agent and
    ui-ux-designer are documented in SKILL.md and agents/INDEX.md but never
    reach a target repo.
  * install.sh never creates planning/, though the phase gate, the PHASE_PLAN
    precondition and planning/PROTOCOL.md all reference planning/active/.
  * The Vault token is written as a literal value into .claude/settings.json,
    and the gitignore block only covers .osengineer/secrets.env — and that block
    is itself wrapped in `if [ -f "$gitignore" ]`, so it no-ops entirely in any
    repo that has no .gitignore yet.
  * The agent upgrade path freezes permanently: the first upgrade appends
    "## osEngineer Additions", and every later upgrade sees that marker via
    `grep -q '## osEngineer'` and skips, so the repo silently stops receiving
    agent updates forever.
  * install.sh unconditionally clones a specific personal GitHub repo into every
    new workbench, which contradicts SKILL.md's "Project-Agnostic: Yes".
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install.sh"
AGENTS_DIR = ROOT / "agents"


def mandatory_agents():
    src = INSTALL.read_text()
    m = re.search(r"MANDATORY_AGENTS=\((.*?)\)", src, re.DOTALL)
    if not m:
        return set()
    return {n[:-3] for n in re.findall(r"([a-z0-9-]+\.md)", m.group(1))}


def agent_dirs():
    return {p.name for p in AGENTS_DIR.iterdir() if p.is_dir() and (p / "AGENT.md").exists()}


def make_git_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True)
    (path / "main.py").write_text("print(1)\n")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=path, check=True)
    return path


def run_install(repo, home, extra=None):
    env = dict(os.environ)
    env.update({"OSE_NONINTERACTIVE": "1", "HOME": str(home), "RUNTIMES": "claude"})
    env.pop("CI", None)
    if extra:
        env.update(extra)
    return subprocess.run(
        ["bash", str(INSTALL), str(repo)],
        capture_output=True, text=True, timeout=300, env=env,
    )


class InstallBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = Path(self.tmp) / "home"
        self.home.mkdir()
        self.repo = make_git_repo(Path(self.tmp) / "repo")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestAllAgentsAreInstalled(unittest.TestCase):
    def test_mandatory_list_covers_every_agent(self):
        missing = agent_dirs() - mandatory_agents()
        self.assertEqual(
            missing, set(),
            f"these agents exist on disk and are documented but are never "
            f"installed into a target repo: {sorted(missing)}",
        )

    def test_no_phantom_agents_listed(self):
        phantom = mandatory_agents() - agent_dirs()
        self.assertEqual(phantom, set(), f"listed but no AGENT.md on disk: {sorted(phantom)}")


class TestAgentsLandInRepo(InstallBase):
    def test_every_agent_file_is_written(self):
        proc = run_install(self.repo, self.home)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        installed = {p.stem for p in (self.repo / ".claude" / "agents").glob("*.md")}
        missing = agent_dirs() - installed
        self.assertEqual(missing, set(), f"agents not written: {sorted(missing)}")


class TestUpgradeDoesNotFreeze(InstallBase):
    def test_agent_updates_still_apply_after_an_append(self):
        run_install(self.repo, self.home)
        target = self.repo / ".claude" / "agents" / "developer.md"
        self.assertTrue(target.exists(), "precondition: developer.md installed")

        # Simulate a user edit so the next install takes the non-identical path.
        target.write_text(target.read_text() + "\n<!-- user tweak -->\n")
        run_install(self.repo, self.home)
        after_first = target.read_text()

        # Now the upstream agent changes. A third install must reflect it.
        sentinel = "SENTINEL-UPSTREAM-CHANGE-12345"
        src = AGENTS_DIR / "developer" / "AGENT.md"
        original = src.read_text()
        try:
            src.write_text(original + f"\n{sentinel}\n")
            run_install(self.repo, self.home)
            self.assertIn(
                sentinel, target.read_text(),
                "after one append the installer matches its own "
                "'## osEngineer' marker and skips forever, so the repo never "
                "receives another agent update",
            )
        finally:
            src.write_text(original)
        del after_first


class TestPlanningDirsExist(InstallBase):
    def test_planning_active_is_created(self):
        run_install(self.repo, self.home)
        self.assertTrue(
            (self.repo / "planning" / "active").is_dir(),
            "planning/active/ is referenced by the phase gate, the PHASE_PLAN "
            "precondition and planning/PROTOCOL.md, but never created",
        )


class TestSecretsAreNotLeaked(InstallBase):
    def test_vault_token_is_not_written_literally(self):
        token = "hvs.SUPERSECRETTOKENVALUE"
        run_install(self.repo, self.home, extra={
            "VAULT_ADDR": "http://127.0.0.1:8200",
            "VAULT_TOKEN": token,
        })
        leaked = []
        for p in self.repo.rglob("*"):
            if not p.is_file() or ".git/" in str(p):
                continue
            try:
                if token in p.read_text():
                    leaked.append(str(p.relative_to(self.repo)))
            except (UnicodeDecodeError, OSError):
                continue
        self.assertEqual(
            leaked, [],
            f"the Vault token was written in plaintext to {leaked}; write an "
            f"env reference instead so the value never lands on disk",
        )

    def test_osengineer_dir_has_its_own_gitignore(self):
        """The root-gitignore append is wrapped in `if [ -f "$gitignore" ]`, so
        it no-ops entirely in a repo with no .gitignore — as here."""
        run_install(self.repo, self.home)
        self.assertFalse(
            (self.repo / ".gitignore").exists(),
            "test premise: this repo starts without a .gitignore",
        )
        nested = self.repo / ".osengineer" / ".gitignore"
        self.assertTrue(
            nested.exists(),
            ".osengineer/.gitignore was not written, and the root .gitignore "
            "path is skipped when no .gitignore exists — so nothing protects "
            ".osengineer/secrets.env in a fresh repo",
        )
        body = nested.read_text()
        self.assertIn("secrets.env", body)


class TestNoHardcodedThirdPartyClone(unittest.TestCase):
    def test_openspace_clone_is_opt_in(self):
        src = INSTALL.read_text()
        offenders = []
        for i, line in enumerate(src.splitlines(), 1):
            if "git clone" not in line:
                continue
            if "OpenSpace" in line or "openspace" in line:
                offenders.append(f"{i}: {line.strip()}")
        if not offenders:
            return
        # Present is fine only if gated behind an explicit opt-in.
        window = "\n".join(src.splitlines())
        for off in offenders:
            ln = int(off.split(":")[0])
            context = "\n".join(src.splitlines()[max(0, ln - 12):ln])
            self.assertTrue(
                re.search(r"OSE_(INSTALL_)?OPENSPACE|prompt_yn|if \[", context),
                "install.sh clones a specific personal GitHub repo into every "
                "workbench unconditionally, which contradicts SKILL.md's "
                f"'Project-Agnostic: Yes':\n{off}",
            )
        del window


if __name__ == "__main__":
    unittest.main()
