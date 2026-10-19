"""Codex must get the same guard verdicts as Claude Code, in Codex's dialect.

Codex CLI hooks (learn.chatgpt.com/docs/hooks, checked 2026-10-18) differ from
Claude Code in three ways that make the unmodified guards fail open:

  * File edits arrive as `tool_name: "apply_patch"` with the whole patch in
    `tool_input.command` and no `file_path`. The edit guards only look for
    write/edit/replace tool names and a `file_path`, so every Codex edit would
    pass unchecked.
  * Codex marks a hook run failed on unsupported output fields and then lets
    the action continue. Exit code 2 with the reason on stderr is the block
    that every Codex event documents.
  * Context goes in `hookSpecificOutput.additionalContext` only.

hooks/lib/codex_hook.py runs the real guard and translates. These tests run the
adapter with the real guards and assert what Codex would see.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADAPTER = ROOT / "hooks" / "lib" / "codex_hook.py"


def make_repo(tmp, phase="execute"):
    repo = Path(tmp)
    (repo / ".osengineer").mkdir(parents=True, exist_ok=True)
    (repo / ".osengineer" / "state.yml").write_text(f"phase: {phase}\n")
    return repo


def run_adapter(script, payload, cwd):
    return subprocess.run(
        [sys.executable, str(ADAPTER), script],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(cwd),
    )


def assert_blocked(case, proc):
    case.assertEqual(proc.returncode, 2, f"Codex blocks only on exit 2:\n{proc.stdout}\n{proc.stderr}")
    case.assertIn("osEngineer", proc.stderr, "block reason must reach Codex on stderr")


def patch(*headers):
    body = ["*** Begin Patch"]
    for h in headers:
        body += [h, "@@", "-old", "+new"]
    body.append("*** End Patch")
    return "\n".join(body) + "\n"


def codex_payload(repo, tool_name, command, event="PreToolUse"):
    return {
        "session_id": "codex-1",
        "turn_id": "t1",
        "cwd": str(repo),
        "hook_event_name": event,
        "model": "gpt-5-codex",
        "tool_name": tool_name,
        "tool_use_id": "u1",
        "tool_input": {"command": command},
    }


class TestApplyPatchIsGuarded(unittest.TestCase):
    def test_protected_file_in_patch_blocks_with_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            proc = run_adapter(
                "osEngineer-pre-edit-guard.py",
                codex_payload(repo, "apply_patch",
                              patch("*** Update File: .osengineer/current-plan.md")),
                repo,
            )
            assert_blocked(self, proc)

    def test_any_protected_file_in_a_multi_file_patch_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            proc = run_adapter(
                "osEngineer-pre-edit-guard.py",
                codex_payload(repo, "apply_patch", patch(
                    "*** Add File: src/ok.py",
                    "*** Update File: .osengineer/current-plan.md",
                )),
                repo,
            )
            assert_blocked(self, proc)

    def test_relative_paths_resolve_against_the_payload_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            sub = repo / "pkg"
            sub.mkdir()
            proc = run_adapter(
                "osEngineer-pre-edit-guard.py",
                codex_payload(sub, "apply_patch",
                              patch("*** Update File: ../.osengineer/current-plan.md")),
                sub,
            )
            assert_blocked(self, proc)

    def test_unprotected_patch_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            proc = run_adapter(
                "osEngineer-pre-edit-guard.py",
                codex_payload(repo, "apply_patch", patch("*** Update File: src/app.py")),
                repo,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("deny", proc.stdout)

    def test_plan_phase_blocks_source_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, phase="plan")
            proc = run_adapter(
                "osEngineer-pre-edit-guard.py",
                codex_payload(repo, "apply_patch", patch("*** Update File: src/app.py")),
                repo,
            )
            assert_blocked(self, proc)


class TestShellIsGuarded(unittest.TestCase):
    def test_destructive_bash_blocks_with_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            proc = run_adapter("osEngineer-pre-bash-guard.py",
                               codex_payload(repo, "Bash", "rm -rf /"), repo)
            assert_blocked(self, proc)

    def test_shell_tool_aliases_and_argv_commands_are_guarded(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            payload = codex_payload(repo, "exec_command", ["rm", "-rf", "/"])
            proc = run_adapter("osEngineer-pre-bash-guard.py", payload, repo)
            assert_blocked(self, proc)

    def test_harmless_command_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            proc = run_adapter("osEngineer-pre-bash-guard.py",
                               codex_payload(repo, "Bash", "ls -la"), repo)
            self.assertEqual(proc.returncode, 0, proc.stderr)


class TestContextUsesOnlyCodexFields(unittest.TestCase):
    def test_session_start_context_is_hook_specific_output_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            payload = {"session_id": "s", "cwd": str(repo), "hook_event_name": "SessionStart",
                       "source": "startup", "model": "gpt-5-codex"}
            proc = run_adapter("osEngineer-session-start.py", payload, repo)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = json.loads(proc.stdout)
            self.assertEqual(set(out), {"hookSpecificOutput"}, f"unsupported keys reach Codex: {out}")
            hso = out["hookSpecificOutput"]
            self.assertEqual(hso["hookEventName"], "SessionStart")
            self.assertTrue(hso["additionalContext"])

    def test_subagent_start_context_reaches_the_subagent(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            payload = {"session_id": "s", "turn_id": "t", "cwd": str(repo),
                       "hook_event_name": "SubagentStart", "agent_id": "a", "agent_type": "worker"}
            proc = run_adapter("osEngineer-subagent-start.py", payload, repo)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = json.loads(proc.stdout)
            self.assertEqual(set(out), {"hookSpecificOutput"}, f"unsupported keys reach Codex: {out}")
            self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "SubagentStart")
            self.assertIn("Baseline", out["hookSpecificOutput"]["additionalContext"])


class TestAdapterRefusesArbitraryScripts(unittest.TestCase):
    def test_unknown_script_is_an_explicit_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run_adapter("../../etc/passwd", {"cwd": tmp}, tmp)
            self.assertNotEqual(proc.returncode, 0)
            self.assertNotEqual(proc.returncode, 2, "a config fault must not look like a guard verdict")
            self.assertIn("codex_hook", proc.stderr)


if __name__ == "__main__":
    unittest.main()
