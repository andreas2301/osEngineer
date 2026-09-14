"""osEngineer must have a CI surface, and it must not be a green gate that
validated nothing.

The package is currently architected to turn itself OFF in CI: post-commit.sh
hard-exits under CI and install.sh skips its wizard there. No workflow file
exists or is generated, despite the design doc claiming
.github/workflows/osengineer-gate.yml is created at repo init.

Two traps this locks out:

  * validate-commit.sh does `[ -f .osengineer/state.yml ] || exit 0` against a
    RELATIVE path. In a CI checkout without .osengineer/, every commit
    "passes" — a green gate that checked nothing. The workflow must assert the
    file exists before trusting the loop.

  * pre-commit.sh pipes its validator into `while read`, so the pipeline's
    status is the loop's and is always 0; a real failure cannot surface.

The gate lands on THIS repo first, before becoming a required check anywhere.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
SELF_CI = WORKFLOWS / "osengineer.yml"
PRECOMMIT = ROOT / "hooks" / "osEngineer-pre-commit.sh"
VALIDATE = ROOT / "hooks" / "osEngineer-validate-commit.sh"


def read(p):
    return p.read_text() if p.exists() else ""


class TestSelfCiExists(unittest.TestCase):
    def test_workflow_file_present(self):
        self.assertTrue(
            SELF_CI.exists(),
            "osEngineer has never run its own test suite in CI; add "
            ".github/workflows/osengineer.yml before making any check required "
            "on other repos",
        )

    def test_runs_the_test_suite(self):
        body = read(SELF_CI)
        self.assertIn(
            "unittest", body,
            "the self-CI workflow does not run the Python test suite",
        )

    def test_runs_shell_syntax_checks(self):
        body = read(SELF_CI)
        self.assertTrue(
            "bash -n" in body or "shellcheck" in body,
            "install.sh and uninstall.sh are 1300+ lines of bash with no "
            "syntax gate in CI",
        )

    def test_pins_bypass_off(self):
        body = read(SELF_CI)
        self.assertIn(
            "OSE_BYPASS", body,
            "CI must pin OSE_BYPASS=0 so a run cannot inherit a bypass from the "
            "environment",
        )


class TestGateTemplateIsGenerated(unittest.TestCase):
    """install.sh must be able to drop a gate workflow into a target repo."""

    def test_installer_can_write_a_gate_workflow(self):
        body = read(ROOT / "install.sh")
        self.assertIn(
            ".github/workflows", body,
            "install.sh never generates a CI gate, so the deterministic "
            "validators only ever run where a developer chose to install hooks",
        )


class TestValidateCommitIsSafeInCi(unittest.TestCase):
    def test_state_file_check_is_documented_as_a_precondition(self):
        body = read(VALIDATE)
        self.assertIn(
            ".osengineer/state.yml", body, "test premise stale"
        )
        gate = read(SELF_CI) + read(ROOT / "install.sh")
        self.assertIn(
            "state.yml", gate,
            "validate-commit.sh exits 0 when .osengineer/state.yml is absent, "
            "so a CI checkout without it produces a green gate that validated "
            "nothing. The workflow must assert the file exists first.",
        )


class TestPreCommitReportsFailures(unittest.TestCase):
    def test_validator_status_is_not_swallowed_by_a_pipe(self):
        body = read(PRECOMMIT)
        offenders = []
        for i, line in enumerate(body.splitlines(), 1):
            if "|" in line and "while" in line and "read" in line:
                offenders.append(f"{i}: {line.strip()}")
        self.assertEqual(
            offenders, [],
            "a validator is piped into `while read`, so the pipeline status is "
            "the loop's and is always 0 — real failures cannot surface:\n"
            + "\n".join(offenders),
        )


class TestWorkflowIsWellFormed(unittest.TestCase):
    def test_yaml_parses(self):
        body = read(SELF_CI)
        if not body:
            self.skipTest("workflow not written yet")
        try:
            import yaml  # noqa: F401
        except ModuleNotFoundError:
            # No PyYAML (zero-dependency policy) — do structural checks instead.
            self.assertIn("jobs:", body)
            self.assertIn("runs-on:", body)
            self.assertIn("steps:", body)
            self.assertTrue(
                re.search(r"^on:", body, re.MULTILINE),
                "workflow has no trigger",
            )
            return
        import yaml
        data = yaml.safe_load(body)
        self.assertIn("jobs", data)

    def test_commit_range_computed_once(self):
        """Each `run:` block is a separate shell: a range computed in one step
        is unset in the next unless it goes through $GITHUB_OUTPUT."""
        body = read(SELF_CI)
        if "git log" not in body and "rev-list" not in body:
            self.skipTest("workflow does not walk a commit range")
        self.assertIn(
            "GITHUB_OUTPUT", body,
            "a commit range is computed in one step and used in another; it "
            "must be passed through $GITHUB_OUTPUT or it will be empty",
        )


if __name__ == "__main__":
    unittest.main()
