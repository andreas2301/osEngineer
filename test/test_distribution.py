"""osEngineer must be installable by someone outside this estate.

Three blockers:

  * OSENGINEER_HOME is written into every repo's settings.json as a resolved
    absolute path, so all 27 repos pin one machine's checkout. Move the
    checkout and they all break at once; a CI runner has no such path at all.
  * There is no upgrade verb, and version state disagrees with itself:
    state.yml pins osengineer_version at first install while settings.json
    rewrites OSENGINEER_VERSION every time, and nothing reconciles them.
    SKILL.md has drifted from VERSION independently.
  * The package still hardcodes one user's estate — a personal GitHub repo is
    cloned into every workbench, and templates/ carries Sovereign-Shield names
    plus .js hook references left over from the Python migration.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install.sh"
VERSION_FILE = ROOT / "VERSION"


def read(p):
    return p.read_text() if p.exists() else ""


def make_git_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True)
    (path / "m.py").write_text("x=1\n")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "i"], cwd=path, check=True)
    return path


def run_install(repo, home):
    env = dict(os.environ)
    env.update({"OSE_NONINTERACTIVE": "1", "HOME": str(home), "RUNTIMES": "claude"})
    env.pop("CI", None)
    return subprocess.run(
        ["bash", str(INSTALL), str(repo)],
        capture_output=True, text=True, timeout=300, env=env,
    )


class TestVersionIsSingleSourced(unittest.TestCase):
    def test_skill_md_matches_version_file(self):
        version = VERSION_FILE.read_text().strip()
        m = re.search(r"^\*\*Version:\*\*\s*(\S+)", read(ROOT / "SKILL.md"), re.MULTILINE)
        self.assertIsNotNone(m, "SKILL.md declares no version")
        self.assertEqual(
            m.group(1), version,
            f"SKILL.md says {m.group(1)} but VERSION says {version}; the two "
            f"drifted because nothing asserts they agree",
        )

    def test_package_json_matches_version_file(self):
        version = VERSION_FILE.read_text().strip()
        pkg = json.loads(read(ROOT / "package.json"))
        self.assertEqual(pkg["version"], version)


class TestUpgradeVerbExists(unittest.TestCase):
    def test_cli_has_upgrade(self):
        proc = subprocess.run(
            ["python3", str(ROOT / "bin" / "osengineer"), "help"],
            capture_output=True, text=True, timeout=60,
        )
        self.assertIn(
            "upgrade", proc.stdout,
            "no `osengineer upgrade` verb: a repo installed once has no "
            "supported way to pick up a new skill version",
        )

    def test_upgrade_runs_and_reconciles_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            repo = make_git_repo(Path(tmp) / "repo")
            run_install(repo, home)
            state = repo / ".osengineer" / "state.yml"
            self.assertTrue(state.exists(), "precondition: installed")
            # Simulate a repo pinned at an older version.
            state.write_text(
                re.sub(r"^osengineer_version:.*$", "osengineer_version: 0.0.1",
                       state.read_text(), flags=re.MULTILINE)
            )
            env = dict(os.environ)
            env.update({"OSE_NONINTERACTIVE": "1", "HOME": str(home),
                        "OSENGINEER_HOME": str(ROOT), "RUNTIMES": "claude"})
            proc = subprocess.run(
                ["python3", str(ROOT / "bin" / "osengineer"), "upgrade"],
                cwd=str(repo), capture_output=True, text=True, timeout=300, env=env,
            )
            self.assertEqual(proc.returncode, 0, f"{proc.stdout}\n{proc.stderr}")
            self.assertIn(
                VERSION_FILE.read_text().strip(), state.read_text(),
                "upgrade did not reconcile osengineer_version in state.yml",
            )


class TestNoHardcodedEstate(unittest.TestCase):
    def test_no_personal_repo_cloned_unconditionally(self):
        body = read(INSTALL)
        for i, line in enumerate(body.splitlines(), 1):
            if "git clone" in line and "andreas2301" in line:
                context = "\n".join(body.splitlines()[max(0, i - 14):i])
                self.assertTrue(
                    re.search(r"OSE_\w*OPENSPACE|prompt_yn|if \[", context),
                    f"install.sh:{i} clones a personal repo into every "
                    f"workbench unconditionally, contradicting SKILL.md's "
                    f"'Project-Agnostic: Yes'",
                )

    def test_templates_have_no_stale_js_hook_names(self):
        offenders = []
        for p in sorted((ROOT / "templates").rglob("*")):
            if not p.is_file():
                continue
            for i, line in enumerate(p.read_text(errors="ignore").splitlines(), 1):
                if re.search(r"osEngineer-[a-z-]+\.js\b", line):
                    offenders.append(f"{p.relative_to(ROOT)}:{i}: {line.strip()}")
        self.assertEqual(
            offenders, [],
            "templates still name .js hooks from before the Python migration:\n"
            + "\n".join(offenders),
        )


class TestRelocatable(unittest.TestCase):
    def test_launcher_prefers_env_over_baked_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            repo = make_git_repo(Path(tmp) / "repo")
            run_install(repo, home)
            launcher = repo / ".osengineer" / "bin" / "osengineer"
            self.assertTrue(launcher.exists(), "no launcher installed")
            body = launcher.read_text()
            self.assertIn(
                "OSENGINEER_HOME:-", body,
                "the launcher bakes an absolute checkout path with no env "
                "override, so CI and a relocated checkout cannot work",
            )

    def test_documents_relocation(self):
        docs = read(ROOT / "README.md") + read(ROOT / "SKILL.md")
        self.assertIn(
            "OSENGINEER_HOME", docs,
            "OSENGINEER_HOME is the one knob that makes an install relocatable "
            "and it is documented nowhere",
        )


if __name__ == "__main__":
    unittest.main()
