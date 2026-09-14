"""Unit tests for the Kimi config.toml surgery helper.

Kimi's config.toml is user-owned, and Kimi itself re-serializes it on provider
edits and token refresh (which destroys comments). So osEngineer must:

  * identify its own entries STRUCTURALLY ("osEngineer-" in the command), never
    by marker comments, which do not survive Kimi's own writer;
  * leave every other key and every foreign hook byte-identical;
  * never leave a malformed file behind — validate before replacing.

Python has tomllib for reading but no stdlib TOML writer, and this package has
zero dependencies by design. Since the only blocks emitted are [[hooks]] with
four scalar keys, they are hand-emitted as text and old ones removed by
text-level surgery, with a tomllib parse as the gate before replacing.
"""
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "hooks" / "lib"
MODULE = LIB / "kimi_config.py"

sys.path.insert(0, str(LIB))

BASE_CONFIG = textwrap.dedent("""\
    default_model = "kimi-for-coding/kimi-k2-thinking"

    [providers.kimi-for-coding]
    type = "anthropic"
    api_key = "sk-secret-value"
    base_url = "https://api.kimi.com/coding"

    [models."kimi-for-coding/k2p7"]
    provider = "kimi-for-coding"
    max_context_size = 262144

    [[hooks]]
    event = "PreToolUse"
    matcher = "Bash"
    command = "python3 /opt/other/unrelated-guard.py"
    timeout = 30
    """)

SAMPLE_ENTRIES = [
    {"event": "UserPromptSubmit",
     "command": 'OSENGINEER_HOME=/skill python3 "/skill/hooks/osEngineer-prompt-guard.py"',
     "timeout": 30},
    {"event": "PreToolUse", "matcher": "Write|Edit",
     "command": 'OSENGINEER_HOME=/skill python3 "/skill/hooks/osEngineer-pre-edit-guard.py"',
     "timeout": 30},
    {"event": "PreToolUse", "matcher": "Bash",
     "command": 'OSENGINEER_HOME=/skill python3 "/skill/hooks/osEngineer-pre-bash-guard.py"',
     "timeout": 30},
]


def load():
    import importlib
    if not MODULE.exists():
        raise unittest.SkipTest("hooks/lib/kimi_config.py does not exist yet")
    import kimi_config
    importlib.reload(kimi_config)
    return kimi_config


def parse(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


class KimiConfigBase(unittest.TestCase):
    def setUp(self):
        if tomllib is None:
            self.skipTest("tomllib unavailable")
        self.mod = load()
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Path(self.tmp.name) / "config.toml"
        self.cfg.write_text(BASE_CONFIG)

    def tearDown(self):
        self.tmp.cleanup()


class TestModuleExists(unittest.TestCase):
    def test_module_present_with_api(self):
        self.assertTrue(
            MODULE.exists(),
            "hooks/lib/kimi_config.py must exist: the TOML surgery needs to be "
            "unit-testable on its own, not buried in a heredoc inside install.sh",
        )
        src = MODULE.read_text()
        for fn in ("def apply_hooks", "def remove_hooks"):
            self.assertIn(fn, src, f"kimi_config.py must expose {fn}(...)")

    def test_no_third_party_imports(self):
        if not MODULE.exists():
            self.skipTest("module not written yet")
        src = MODULE.read_text()
        for banned in ("import toml\n", "import tomli_w", "import yaml", "import requests"):
            self.assertNotIn(banned, src, f"zero-dependency policy: {banned.strip()}")


class TestApplyHooks(KimiConfigBase):
    def test_appends_entries(self):
        self.mod.apply_hooks(self.cfg, SAMPLE_ENTRIES)
        hooks = parse(self.cfg)["hooks"]
        ose = [h for h in hooks if "osEngineer-" in h["command"]]
        self.assertEqual(len(ose), len(SAMPLE_ENTRIES))

    def test_preserves_every_other_key(self):
        self.mod.apply_hooks(self.cfg, SAMPLE_ENTRIES)
        data = parse(self.cfg)
        self.assertEqual(data["default_model"], "kimi-for-coding/kimi-k2-thinking")
        self.assertEqual(data["providers"]["kimi-for-coding"]["api_key"], "sk-secret-value")
        self.assertEqual(
            data["models"]["kimi-for-coding/k2p7"]["max_context_size"], 262144
        )

    def test_preserves_foreign_hooks(self):
        self.mod.apply_hooks(self.cfg, SAMPLE_ENTRIES)
        hooks = parse(self.cfg)["hooks"]
        foreign = [h for h in hooks if "unrelated-guard" in h["command"]]
        self.assertEqual(len(foreign), 1, f"foreign hook lost or duplicated: {hooks}")
        self.assertEqual(foreign[0]["matcher"], "Bash")
        self.assertEqual(foreign[0]["timeout"], 30)

    def test_only_strict_schema_keys_emitted(self):
        self.mod.apply_hooks(self.cfg, SAMPLE_ENTRIES)
        allowed = {"event", "matcher", "command", "timeout"}
        for h in parse(self.cfg)["hooks"]:
            self.assertEqual(set(h) - allowed, set(), f"HookDefSchema is .strict(): {h}")

    def test_is_idempotent(self):
        self.mod.apply_hooks(self.cfg, SAMPLE_ENTRIES)
        first = parse(self.cfg)["hooks"]
        self.mod.apply_hooks(self.cfg, SAMPLE_ENTRIES)
        self.mod.apply_hooks(self.cfg, SAMPLE_ENTRIES)
        third = parse(self.cfg)["hooks"]
        self.assertEqual(len(first), len(third), "re-apply duplicated entries")

    def test_creates_file_when_absent(self):
        missing = Path(self.tmp.name) / "sub" / "config.toml"
        self.mod.apply_hooks(missing, SAMPLE_ENTRIES)
        self.assertTrue(missing.exists())
        self.assertEqual(len(parse(missing)["hooks"]), len(SAMPLE_ENTRIES))

    def test_command_with_quotes_round_trips(self):
        tricky = [{
            "event": "PreToolUse", "matcher": "Bash",
            "command": 'OSENGINEER_HOME=/a b/skill python3 "/a b/skill/hooks/osEngineer-x.py"',
            "timeout": 30,
        }]
        self.mod.apply_hooks(self.cfg, tricky)
        got = [h for h in parse(self.cfg)["hooks"] if "osEngineer-" in h["command"]]
        self.assertEqual(got[0]["command"], tricky[0]["command"],
                         "command string did not survive TOML round-trip")

    def test_backup_is_written(self):
        self.mod.apply_hooks(self.cfg, SAMPLE_ENTRIES)
        backup = self.cfg.with_suffix(".toml.ose-bak")
        alt = Path(str(self.cfg) + ".ose-bak")
        self.assertTrue(
            backup.exists() or alt.exists(),
            "no backup of the user's config was taken before rewriting it",
        )


class TestRemoveHooks(KimiConfigBase):
    def test_removes_only_osengineer_entries(self):
        self.mod.apply_hooks(self.cfg, SAMPLE_ENTRIES)
        self.mod.remove_hooks(self.cfg)
        hooks = parse(self.cfg).get("hooks", [])
        self.assertEqual([h for h in hooks if "osEngineer-" in h["command"]], [])
        self.assertEqual(len([h for h in hooks if "unrelated-guard" in h["command"]]), 1)

    def test_remove_preserves_other_config(self):
        self.mod.apply_hooks(self.cfg, SAMPLE_ENTRIES)
        self.mod.remove_hooks(self.cfg)
        data = parse(self.cfg)
        self.assertEqual(data["default_model"], "kimi-for-coding/kimi-k2-thinking")
        self.assertEqual(data["providers"]["kimi-for-coding"]["api_key"], "sk-secret-value")

    def test_remove_on_missing_file_is_a_noop(self):
        missing = Path(self.tmp.name) / "nope.toml"
        self.mod.remove_hooks(missing)  # must not raise

    def test_remove_when_no_osengineer_entries(self):
        before = self.cfg.read_text()
        self.mod.remove_hooks(self.cfg)
        self.assertEqual(len(parse(self.cfg)["hooks"]), 1)
        self.assertIn("unrelated-guard", self.cfg.read_text())
        del before


class TestMalformedInputIsRefused(KimiConfigBase):
    def test_invalid_toml_is_left_untouched(self):
        self.cfg.write_text("this is [ not valid toml\n")
        original = self.cfg.read_text()
        with self.assertRaises(Exception):
            self.mod.apply_hooks(self.cfg, SAMPLE_ENTRIES)
        self.assertEqual(
            self.cfg.read_text(), original,
            "a malformed pre-existing config must be left exactly as found",
        )


if __name__ == "__main__":
    unittest.main()
