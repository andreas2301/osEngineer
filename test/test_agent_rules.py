"""The agent rules have one source, templates/agent-rules.md.

install.sh used to carry two inline copies, the prompt guard a third and
agents/developer a fourth, so a rule change reached only some of them.
Everything that states the rules now reads them from the source file.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "templates" / "agent-rules.md"
INSTALL = ROOT / "install.sh"
PROMPT_GUARD = ROOT / "hooks" / "osEngineer-prompt-guard.py"
# A phrase that exists only in the rules text; any other file holding it
# is a stale copy.
RULE_PHRASE = "Think Before Coding"


def rules():
    return RULES.read_text().strip()


class RulesContent(unittest.TestCase):
    """The karpathy-skills gaps and the closing report convention."""

    def test_rules_cover_the_confirmed_gaps(self):
        text = rules().lower()
        for phrase in (
            "push back",                  # simpler approach when warranted
            "interpretations",            # don't pick one silently
            "your own change made unused",
            "match the existing style",
            "trace to the request",
            "trivial",                    # rules scale with task size
            "impossible",                 # no defensive code for impossible states
            "skipped / risks",            # closing footer for agent reports
        ):
            self.assertIn(phrase, text)

    def test_reviewer_checks_line_traceability(self):
        checklist = (ROOT / "agents" / "reviewer" / "references" / "review-checklist.md").read_text()
        self.assertIn("traces to the request", checklist)

    def test_rules_carry_the_ponytail_pieces(self):
        text = rules().lower()
        for phrase in (
            "need to exist", "already in the codebase", "stdlib",
            "installed dependency", "one line", "minimal new code",   # reuse ladder
            "never cut", "input validation", "data loss", "security",
            "accessibility", "risk-exception",                          # never-cut list
            "shortcut: <limit> — revisit when <trigger>", "osengineer debt",  # ledger
        ):
            self.assertIn(phrase, text)
        # The ladder runs in this order.
        order = [text.index(p) for p in ("need to exist", "already in the codebase", "stdlib",
                                         "installed dependency", "one line", "minimal new code")]
        self.assertEqual(order, sorted(order))

    def test_rules_stay_compact(self):
        # Injected into every session and subagent; growth must stay small.
        self.assertLess(len(rules().encode()), 2700)

    def test_reviewer_uses_the_fixed_order_and_finding_format(self):
        ref = ROOT / "agents" / "reviewer"
        for text in ((ref / "AGENT.md").read_text(),
                     (ref / "references" / "review-checklist.md").read_text()):
            self.assertIn("correct → safe → holds under load → tested → fast → lean", text)
        checklist = (ref / "references" / "review-checklist.md").read_text()
        for phrase in ("failing case", "where", "what fails", "fix", "20", "Not checked",
                       "already in the codebase"):
            self.assertIn(phrase, checklist)
        self.assertIn("Not checked", (ref / "references" / "review-output.md").read_text())
        self.assertIn("correct → safe → holds under load", (ROOT / "agents" / "judge" / "AGENT.md").read_text())


class RulesHaveOneSource(unittest.TestCase):
    def test_no_inline_copies(self):
        for path in (INSTALL, PROMPT_GUARD, ROOT / "agents" / "developer" / "AGENT.md",
                     ROOT / "templates" / "CLAUDE.md.tmpl"):
            self.assertNotIn(RULE_PHRASE, path.read_text(), f"inline rule copy in {path}")

    def test_repo_claude_md_matches_the_source(self):
        self.assertIn(rules(), (ROOT / "CLAUDE.md").read_text())


class InstalledClaudeMd(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ose-rules-"))
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.repo = self.tmp / "repo"
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def install(self):
        env = dict(os.environ, OSE_NONINTERACTIVE="1", HOME=str(self.home), RUNTIMES="claude")
        env.pop("CI", None)
        proc = subprocess.run(["bash", str(INSTALL), str(self.repo)], capture_output=True,
                              text=True, timeout=300, env=env, stdin=subprocess.DEVNULL)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return (self.repo / "CLAUDE.md").read_text()

    def test_fresh_claude_md_carries_the_rules(self):
        self.assertIn(rules(), self.install())

    def test_appended_section_carries_the_rules(self):
        (self.repo / "CLAUDE.md").write_text("# mine\n\nOwn notes.\n")
        text = self.install()
        self.assertTrue(text.startswith("# mine\n"))
        self.assertIn(rules(), text)


class PromptGuardReinjection(unittest.TestCase):
    """The amnesia-guard re-injection restates the rules from the source."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".osengineer").mkdir()
        (self.root / ".osengineer/state.yml").write_text("phase: execute\n")
        self.session = "ose-test-" + uuid.uuid4().hex
        (Path(tempfile.gettempdir()) / f"claude-ctx-{self.session}.json").write_text(json.dumps({
            "session_id": self.session, "remaining_percentage": 20,
            "used_pct": 80, "timestamp": int(time.time())}))

    def tearDown(self):
        for path in Path(tempfile.gettempdir()).glob(f"claude-*{self.session}*"):
            path.unlink(missing_ok=True)
        self.tmp.cleanup()

    def test_reinjection_contains_the_rules(self):
        env = dict(os.environ)
        env.pop("OSE_BYPASS", None)
        env.pop("OSENGINEER_HOME", None)
        payload = {"cwd": str(self.root), "session_id": self.session, "prompt": "hi"}
        proc = subprocess.run([sys.executable, str(PROMPT_GUARD)], input=json.dumps(payload),
                              text=True, capture_output=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        ctx = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("DEGRADATION", ctx)
        self.assertIn(rules(), ctx)


if __name__ == "__main__":
    unittest.main()
