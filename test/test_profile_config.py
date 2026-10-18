"""The single .osengineer/profile.json loader: defaults, strict validation, schema parity."""
import json
import tempfile
import unittest
from pathlib import Path

from repo_profile import config

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "specs" / "SCHEMAS" / "repo-profile.schema.json"


class ProfileLoader(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo / ".osengineer").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, value):
        raw = value if isinstance(value, str) else json.dumps(value)
        (self.repo / ".osengineer/profile.json").write_text(raw)

    def test_missing_file_gives_current_defaults(self):
        profile = config.load(self.repo)
        self.assertIsNone(profile["profile"])
        self.assertEqual(profile["policy"], "POLICY.md")
        self.assertEqual(profile["planDirectory"], ".plans")
        self.assertEqual(profile["skillRegistry"], ".osengineer/skill-registry.json")
        self.assertEqual(profile["dispatchSkill"], "dispatch")
        self.assertEqual(profile["context"], {"warnPct": 35, "criticalPct": 25,
                                              "reinjectPct": 40, "staleSeconds": 60})
        self.assertEqual(profile["routing"], {"excludeNamePattern": "reviewer|verifier|judge",
                                              "dispatchWords": ["dispatch", "workflow"],
                                              "minSignalTerms": 2, "maxHints": 2,
                                              "projection": "codex"})
        self.assertEqual(profile["validationProfiles"]["infra"]["configDirs"],
                         ["planning", ".osengineer", "ansible", "docker", "scripts"])
        self.assertEqual(profile["eval"], {"policy": "EVAL_POLICY.json"})
        self.assertEqual(profile["runners"], {"codex": {"protocol": "codex-exec"}})
        self.assertEqual(profile["handlers"], {})

    def test_existing_flat_profile_still_loads(self):
        self.write({"schemaVersion": 1, "profile": "repo", "policy": "AGENTS.md",
                    "skillRegistry": ".osengineer/skill-registry.json", "planDirectory": "work/"})
        profile = config.load(self.repo)
        self.assertEqual(profile["profile"], "repo")
        self.assertEqual(profile["policy"], "AGENTS.md")
        self.assertEqual(profile["planDirectory"], "work")

    def test_nested_sections_merge_with_defaults(self):
        self.write({"context": {"warnPct": 50}, "routing": {"maxHints": 3}})
        profile = config.load(self.repo)
        self.assertEqual(profile["context"]["warnPct"], 50)
        self.assertEqual(profile["context"]["criticalPct"], 25)
        self.assertEqual(profile["routing"]["maxHints"], 3)
        self.assertEqual(profile["routing"]["minSignalTerms"], 2)

    def test_defaults_are_not_shared_between_loads(self):
        config.load(self.repo)["routing"]["dispatchWords"].append("mutated")
        self.assertEqual(config.load(self.repo)["routing"]["dispatchWords"], ["dispatch", "workflow"])

    def assert_rejected(self, value, fragment):
        self.write(value)
        with self.assertRaises(config.ProfileError) as caught:
            config.load(self.repo)
        self.assertIn("profile.json", str(caught.exception))
        self.assertIn(fragment, str(caught.exception))

    def test_invalid_profiles_fail_closed_with_the_offending_key(self):
        cases = [
            ("{", "invalid JSON"),
            ("[]", "must be an object"),
            ({"unknown": 1}, "unknown"),
            ({"schemaVersion": 2}, "schemaVersion"),
            ({"profile": "infra"}, "profile"),
            ({"planDirectory": "/abs"}, "planDirectory"),
            ({"policy": "../POLICY.md"}, "policy"),
            ({"skillRegistry": ""}, "skillRegistry"),
            ({"dispatchSkill": 3}, "dispatchSkill"),
            ({"context": {"warnPct": 101}}, "context.warnPct"),
            ({"context": {"warnPct": True}}, "context.warnPct"),
            ({"context": {"warnPct": 20, "criticalPct": 25}}, "criticalPct"),
            ({"context": {"other": 1}}, "context"),
            ({"routing": {"excludeNamePattern": "("}}, "routing.excludeNamePattern"),
            ({"routing": {"dispatchWords": [""]}}, "routing.dispatchWords"),
            ({"routing": {"minSignalTerms": 0}}, "routing.minSignalTerms"),
            ({"routing": {"projection": "a/b"}}, "routing.projection"),
            ({"validationProfiles": {"infra": {"configDirs": ["/etc"]}}}, "configDirs"),
            ({"validationProfiles": {"frontend": {}}}, "validationProfiles"),
            ({"eval": {"policy": "../x.json"}}, "eval.policy"),
            ({"runners": {"codex": {"protocol": "ssh"}}}, "runners.codex.protocol"),
            ({"runners": {"bad name": {"protocol": "env"}}}, "runners"),
            ({"handlers": {"eval-policy": {"handler": "no.such", "enabled": True}}}, "handlers.eval-policy.handler"),
            ({"handlers": {"eval-policy": {"handler": "eval.gate"}}}, "handlers.eval-policy.enabled"),
            ({"handlers": {"eval-policy": {"enabled": True}}}, "handlers.eval-policy.handler"),
            ({"handlers": {"Bad Fact": {"enabled": False}}}, "handlers"),
        ]
        for value, fragment in cases:
            with self.subTest(value=value):
                self.assert_rejected(value, fragment)

    def test_disabled_handler_entry_may_omit_the_handler(self):
        self.write({"handlers": {"package-manager:npm": {"enabled": False},
                                 "eval-policy": {"handler": "eval.gate", "enabled": True}}})
        self.assertEqual(config.load(self.repo)["handlers"]["eval-policy"]["handler"], "eval.gate")


class ProfileSchemaParity(unittest.TestCase):
    """The schema documents what the loader enforces; they must not drift."""

    def setUp(self):
        self.schema = json.loads(SCHEMA.read_text())

    def test_schema_is_2020_12_and_closed(self):
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertFalse(self.schema["additionalProperties"])

    def test_schema_keys_and_defaults_match_loader(self):
        props = self.schema["properties"]
        self.assertEqual(set(props), set(config.DEFAULTS) | {"schemaVersion"})
        for key, default in config.DEFAULTS.items():
            if key in ("validationProfiles", "runners", "handlers"):
                self.assertEqual(props[key]["default"], default, key)
            elif isinstance(default, dict):
                for sub, value in default.items():
                    self.assertEqual(props[key]["properties"][sub]["default"], value, f"{key}.{sub}")
            else:
                self.assertEqual(props[key].get("default"), default, key)

    def test_schema_enums_match_loader(self):
        defs = self.schema["$defs"]
        self.assertEqual(sorted(defs["handlerEntry"]["properties"]["handler"]["enum"]),
                         sorted(config.HANDLERS))
        self.assertEqual(sorted(defs["runner"]["properties"]["protocol"]["enum"]),
                         sorted(config.RUNNER_PROTOCOLS))


if __name__ == "__main__":
    unittest.main()
