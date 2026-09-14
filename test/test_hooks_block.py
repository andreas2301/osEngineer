"""Every block a guard emits must actually block on BOTH supported harnesses.

Verified behaviourally against Kimi Code 0.36.1 on 2026-09-14:

  * Emitting the legacy shape `{"decision": "block", "reason": R}` — which is
    what every osEngineer guard shipped until now — Kimi ALLOWED a destructive
    Bash command. Its HookJsonOutputSchema is
    `looseObject({message, permissionDecision, permissionDecisionReason})`
    nested under `hookSpecificOutput`, with no top-level `decision` field, so
    the payload parsed as a loose object with `hookSpecificOutput` undefined
    and fell through to allowResult(). Silent fail-open, no error anywhere.

  * Emitting the union of both dialects, Kimi blocked the same command and
    surfaced the reason string verbatim. Claude honours the same object through
    its legacy top-level branch. Neither harness rejects the other's keys.

So the contract is: every block payload carries BOTH dialects. These tests run
the real guards and assert on what they actually print.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "hooks"


def make_repo(tmp, phase="execute", **state):
    repo = Path(tmp)
    (repo / ".osengineer").mkdir(parents=True, exist_ok=True)
    lines = [f"phase: {phase}"]
    for k, v in state.items():
        lines.append(f"{k}: {v}")
    (repo / ".osengineer" / "state.yml").write_text("\n".join(lines) + "\n")
    return repo


def run_hook(name, payload, cwd=None):
    proc = subprocess.run(
        [sys.executable, str(HOOKS / name)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(cwd) if cwd else None,
    )
    return proc


def parse_emissions(stdout):
    """A hook prints one JSON object when it has something to say."""
    out = stdout.strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


class BlockDialectMixin:
    def assertBlocksBothHarnesses(self, emitted, context=""):
        self.assertIsNotNone(emitted, f"{context}: guard emitted nothing at all")

        # Claude dialect (legacy top-level branch).
        self.assertEqual(
            emitted.get("decision"), "block",
            f"{context}: missing Claude dialect `decision: block` -> "
            f"Claude will not block. Got: {emitted}",
        )
        self.assertTrue(
            emitted.get("reason"),
            f"{context}: `decision: block` with no `reason`",
        )

        # Kimi dialect — the ONLY path Kimi honours.
        hso = emitted.get("hookSpecificOutput")
        self.assertIsInstance(
            hso, dict,
            f"{context}: no `hookSpecificOutput` object -> Kimi FAILS OPEN and "
            f"allows the action. Got: {emitted}",
        )
        self.assertEqual(
            hso.get("permissionDecision"), "deny",
            f"{context}: hookSpecificOutput.permissionDecision must be 'deny'; "
            f"Kimi blocks on nothing else. Got: {hso}",
        )
        self.assertTrue(
            hso.get("permissionDecisionReason"),
            f"{context}: Kimi surfaces permissionDecisionReason to the model; "
            f"an empty reason gives the agent nothing to act on",
        )
        self.assertTrue(
            hso.get("hookEventName"),
            f"{context}: hookSpecificOutput.hookEventName is required",
        )


class TestDestructiveBashIsBlockedOnBothHarnesses(unittest.TestCase, BlockDialectMixin):
    def test_denylisted_command_emits_both_dialects(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            proc = run_hook(
                "osEngineer-pre-bash-guard.py",
                {
                    "session_id": "block-1",
                    "cwd": str(repo),
                    "tool_name": "Bash",
                    "tool_input": {"command": "rm -rf /"},
                },
                cwd=repo,
            )
            self.assertNotIn("Traceback", proc.stderr)
            emitted = parse_emissions(proc.stdout)
            self.assertBlocksBothHarnesses(emitted, "pre-bash-guard / rm -rf /")


class TestEditGuardBlocksOnBothHarnesses(unittest.TestCase, BlockDialectMixin):
    def test_live_system_path_block_emits_both_dialects(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            live = Path(tmp) / "live"
            live.mkdir()
            (repo / ".osengineer" / "workbench-config.yml").write_text(
                f'live_system_path: "{live}"\n'
            )
            proc = run_hook(
                "osEngineer-pre-edit-guard.py",
                {
                    "session_id": "block-2",
                    "cwd": str(repo),
                    "tool_name": "Write",
                    "tool_input": {"file_path": str(live / "prod.conf")},
                },
                cwd=repo,
            )
            self.assertNotIn("Traceback", proc.stderr)
            emitted = parse_emissions(proc.stdout)
            self.assertBlocksBothHarnesses(emitted, "pre-edit-guard / live system path")


class TestNoGuardEmitsLegacyOnlyBlock(unittest.TestCase):
    """Static backstop: no source line may construct a block without the Kimi key.

    Catches a future guard that copies the old pattern, including on code paths
    these tests do not exercise.
    """

    def test_no_bare_decision_block_in_sources(self):
        offenders = []
        for hook in sorted(HOOKS.glob("osEngineer-*.py")):
            src = hook.read_text()
            if '"decision": "block"' not in src and "'decision': 'block'" not in src:
                continue
            if "permissionDecision" not in src:
                offenders.append(
                    f"{hook.name}: builds a `decision: block` payload but never "
                    f"mentions permissionDecision -> fails open on Kimi"
                )
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_shared_emit_helper_exists(self):
        """One helper, not six hand-rolled dicts that can drift apart."""
        common = HOOKS / "lib" / "osengineer_common.py"
        src = common.read_text()
        self.assertIn(
            "def emit_block", src,
            "hooks/lib/osengineer_common.py must expose emit_block(event, reason) "
            "so the dual-dialect payload is built in exactly one place",
        )
        self.assertIn(
            "permissionDecision", src,
            "emit_block must emit the Kimi dialect",
        )


if __name__ == "__main__":
    unittest.main()
