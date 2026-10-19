"""Cheap guards against docs drifting away from the tree.

Each one caught a live defect: SKILL.md listed flat agents/<name>.md paths
after the move to agents/<name>/AGENT.md, live docs named the .js hooks of
the Node era, the post-tool hook pointed at a command that never existed,
and the judge declared two different verdict sets.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Released changelog entries, ADRs and dated design specs are history.
HISTORICAL = ("CHANGELOG.md", "docs/adr/", "docs/superpowers/")


def live_docs():
    for p in ROOT.rglob("*.md"):
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith(".git/") or rel.startswith(HISTORICAL):
            continue
        yield rel, p.read_text()


class DocsDrift(unittest.TestCase):
    def test_skill_md_paths_exist(self):
        text = (ROOT / "SKILL.md").read_text()
        paths = re.findall(r"`((?:agents|planning|discovery|trust|integrations|docs|commands|examples)/[^`\s]*)`", text)
        self.assertTrue(paths, "no paths found in SKILL.md")
        missing = [p for p in paths if not (ROOT / p).exists()]
        self.assertEqual(missing, [], "SKILL.md references missing paths")

    def test_live_docs_name_existing_hooks(self):
        stale = []
        for rel, text in live_docs():
            for name in set(re.findall(r"osEngineer-[a-z-]+\.(?:js|py|sh)\b", text)):
                if not (ROOT / "hooks" / name).exists():
                    stale.append(f"{rel}: {name}")
        self.assertEqual(stale, [], "docs name hooks that do not exist")

    def test_hooks_point_to_existing_commands(self):
        missing = []
        for hook in (ROOT / "hooks").glob("osEngineer-*.py"):
            for verb in set(re.findall(r"/osEngineer:([a-z][a-z-]*)", hook.read_text())):
                if not (ROOT / "commands" / f"osEngineer-{verb}.md").exists():
                    missing.append(f"{hook.name}: /osEngineer:{verb}")
        self.assertEqual(missing, [], "hooks suggest commands that do not exist")

    def test_judge_has_one_verdict_set(self):
        text = (ROOT / "agents" / "judge" / "AGENT.md").read_text()
        self.assertIn("MERGE / BLOCK", text)
        self.assertNotRegex(text, r"\bFLAG\b|\bPASS\b")


if __name__ == "__main__":
    unittest.main()
