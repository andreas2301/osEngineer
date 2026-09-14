"""Smoke tests that actually EXECUTE every hook.

Before this file, 0 of 28 tests ran a single line of hook code — which is how
two `NameError`s (missing `import re` in osEngineer-post-tool.py and
osEngineer-statusline.py) shipped through a full Node->Python migration and a
tagged release. Every hook ends in a bare `except Exception: pass`, so a crash
is indistinguishable from a clean no-op unless something asserts on it.

These tests deliberately bypass that swallow: each hook is imported as a module
and its `main()` called directly, so an exception propagates instead of being
silently discarded.
"""
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "hooks"
PY_HOOKS = sorted(HOOKS.glob("osEngineer-*.py"))


def load_hook(path):
    """Import a hook by path without executing its __main__ guard."""
    sys.path.insert(0, str(HOOKS / "lib"))
    try:
        spec = importlib.util.spec_from_file_location(
            "ose_hook_" + path.stem.replace("-", "_"), path
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.pop(0)


def make_repo(tmp):
    """Minimal on-disk shape a hook recognises as an osEngineer repo."""
    repo = Path(tmp)
    (repo / ".osengineer").mkdir(parents=True, exist_ok=True)
    (repo / ".osengineer" / "state.yml").write_text(
        "phase: idle\ncurrent_team: null\nbudget_used: 0\n"
    )
    return repo


class TestHooksAreDiscovered(unittest.TestCase):
    def test_python_hooks_exist(self):
        self.assertGreaterEqual(
            len(PY_HOOKS), 5, f"expected >=5 python hooks, found {PY_HOOKS}"
        )


class TestHooksImportCleanly(unittest.TestCase):
    """Every name a hook references at runtime must be imported.

    This is the direct regression for the missing `import re`. A hook that
    compiles fine can still raise NameError the moment the guarded branch is
    reached, and the bare except hides it.
    """

    def test_every_referenced_module_is_imported(self):
        import ast

        failures = []
        for hook in PY_HOOKS:
            src = hook.read_text()
            tree = ast.parse(src)
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        imported.add((a.asname or a.name).split(".")[0])
                elif isinstance(node, ast.ImportFrom):
                    for a in node.names:
                        imported.add(a.asname or a.name)
            # Module-style attribute access: `re.search(...)`, `os.environ`, ...
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id in {
                        "re", "os", "sys", "json", "time", "tempfile",
                        "subprocess", "shutil", "hashlib",
                    }
                    and node.value.id not in imported
                ):
                    failures.append(f"{hook.name}: uses `{node.value.id}.` but never imports it")
        self.assertEqual(failures, [], "\n".join(sorted(set(failures))))


class TestHooksSurviveHostilePayloads(unittest.TestCase):
    """A hook must never crash the harness, whatever arrives on stdin."""

    PAYLOADS = {
        "empty": "",
        "not-json": "definitely not json",
        "empty-object": "{}",
        "null-fields": json.dumps({"session_id": None, "cwd": None}),
        "unexpected-types": json.dumps({"session_id": 42, "cwd": [], "tool_name": {}}),
    }

    def test_no_traceback_on_any_payload(self):
        failures = []
        for hook in PY_HOOKS:
            for name, payload in self.PAYLOADS.items():
                proc = subprocess.run(
                    [sys.executable, str(hook)],
                    input=payload,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if proc.returncode != 0:
                    failures.append(f"{hook.name}/{name}: exit {proc.returncode}")
                if "Traceback" in proc.stderr:
                    failures.append(f"{hook.name}/{name}: traceback\n{proc.stderr}")
        self.assertEqual(failures, [], "\n".join(failures))


class TestHooksRunOnValidPayload(unittest.TestCase):
    """Call main() directly so exceptions are NOT swallowed by the bare except.

    A hook whose body raises NameError still exits 0 via `except Exception:
    pass`, so subprocess-level checks alone cannot catch the import bugs.
    """

    def _payload(self, repo, **over):
        data = {
            "session_id": "smoke-session-1",
            "cwd": str(repo),
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "prompt": "hello",
        }
        data.update(over)
        return data

    def test_main_does_not_raise(self):
        failures = []
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            for hook in PY_HOOKS:
                mod = load_hook(hook)
                main = getattr(mod, "main", None)
                if main is None:
                    continue
                payload = json.dumps(self._payload(repo))
                stdin = sys.stdin
                sys.stdin = io.StringIO(payload)
                try:
                    with redirect_stdout(io.StringIO()):
                        main()
                except SystemExit:
                    pass
                except Exception as exc:  # noqa: BLE001 - that is the point
                    failures.append(f"{hook.name}: {type(exc).__name__}: {exc}")
                finally:
                    sys.stdin = stdin
        self.assertEqual(failures, [], "\n".join(failures))


class TestStatuslineWritesBridgeFile(unittest.TestCase):
    """The statusline hook is the sole producer of the context bridge file.

    post-tool.py reads /tmp/claude-ctx-<session>.json for budget tracking and
    prompt-guard.py reads it for context-percentage re-injection. When the
    statusline crashes, all three features die together and nothing reports it.
    """

    def test_bridge_file_is_written(self):
        statusline = HOOKS / "osEngineer-statusline.py"
        if not statusline.exists():
            self.skipTest("statusline hook not present")
        session = "smoke-bridge-1"
        bridge = Path(tempfile.gettempdir()) / f"claude-ctx-{session}.json"
        if bridge.exists():
            bridge.unlink()
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            payload = json.dumps({
                "session_id": session,
                "cwd": str(repo),
                "workspace": {"current_dir": str(repo)},
                "model": {"display_name": "Test"},
                # The hook reads remaining_percentage specifically; without it
                # build_context_meter returns early and writes no bridge file.
                "context_window": {"remaining_percentage": 72},
            })
            proc = subprocess.run(
                [sys.executable, str(statusline)],
                input=payload, capture_output=True, text=True, timeout=30,
            )
        self.assertNotIn("Traceback", proc.stderr)
        self.assertTrue(
            bridge.exists(),
            "statusline produced no context bridge file; post-tool budget "
            "tracking and prompt-guard context re-injection both depend on it",
        )
        if bridge.exists():
            bridge.unlink()


if __name__ == "__main__":
    unittest.main()
