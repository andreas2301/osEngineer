"""The one loader for .osengineer/profile.json, shared by hooks, CLI and runtime.

Stdlib only and import-free of the hooks, so the installed skill can ship it.
specs/SCHEMAS/repo-profile.schema.json documents the same rules; a test keeps
the two in step. A missing file means defaults; anything invalid fails closed.
"""
import copy
import json
import re
from pathlib import Path, PurePosixPath

PROFILE_REL = ".osengineer/profile.json"

DEFAULTS = {
    "profile": None,
    "policy": "POLICY.md",
    "planDirectory": ".plans",
    "skillRegistry": ".osengineer/skill-registry.json",
    "dispatchSkill": "dispatch",
    "context": {"warnPct": 35, "criticalPct": 25, "reinjectPct": 40, "staleSeconds": 60},
    "routing": {"excludeNamePattern": "reviewer|verifier|judge",
                "dispatchWords": ["dispatch", "workflow"],
                "minSignalTerms": 2, "maxHints": 2, "projection": "codex"},
    "eval": {"policy": "EVAL_POLICY.json"},
    "runners": {"codex": {"protocol": "codex-exec"}},
    "handlers": {},
}

# Existing capabilities a detected fact can be mapped to (see repo_profile/detect.py).
HANDLERS = {
    "profile.config": ".osengineer/profile.json settings for hooks and runtime",
    "runtime.policyBinding": "task contracts bind the policy file digest",
    "routing.skillRegistry": "prompt-guard routing hints from the skill registry",
    "eval.gate": "bin/ose-eval-gate keep/revert decisions from the eval policy",
    "hooks.claude": "osEngineer hooks wired into Claude Code by install.sh",
    "hooks.kimi": "osEngineer hooks wired into Kimi Code by install.sh",
    "runtime.runner.codex": "codex exec runner protocol in the task runtime",
    "integrations.github": "read-only GitHub pull request reader via gh",
    "secrets.op": "1Password op:// secret references (metadata only)",
}
RUNNER_PROTOCOLS = ("codex-exec", "env")
FACT_NAME = re.compile(r"^[a-z][a-z0-9-]*(?::[a-z0-9.-]+)?$")
RUNNER_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


class ProfileError(ValueError):
    """An invalid profile; the message names the file and the offending key."""


def _fail(key, problem):
    raise ProfileError(f"{PROFILE_REL}: {key} {problem}")


def _keys(value, allowed, key):
    if not isinstance(value, dict):
        _fail(key, "must be an object")
    extra = set(value) - set(allowed)
    if extra:
        _fail(key, "has unknown keys: " + ", ".join(sorted(extra)))


def _rel_path(value, key):
    ok = (isinstance(value, str) and value and "\x00" not in value and "\\" not in value
          and not value.startswith("/") and ".." not in PurePosixPath(value).parts)
    if not ok:
        _fail(key, "must be a nonempty repository-relative path without ..")
    return value.rstrip("/")


def _int(value, key, low, high):
    if type(value) is not int or not low <= value <= high:
        _fail(key, f"must be an integer between {low} and {high}")
    return value


def _section(data, name, checks):
    """Merge one nested section over its defaults, checking every given key."""
    merged = copy.deepcopy(DEFAULTS[name])
    if name not in data:
        return merged
    _keys(data[name], merged, name)
    for sub, value in data[name].items():
        merged[sub] = checks[sub](value, f"{name}.{sub}")
    return merged


def validate(data):
    """Return the effective profile (defaults merged in) or raise ProfileError."""
    _keys(data, set(DEFAULTS) | {"schemaVersion"}, "profile")
    if "schemaVersion" in data and (type(data["schemaVersion"]) is not int or data["schemaVersion"] != 1):
        _fail("schemaVersion", "must be integer 1")
    out = copy.deepcopy(DEFAULTS)
    if "profile" in data and data["profile"] != "repo":
        _fail("profile", 'must be "repo" when present')
    out["profile"] = data.get("profile")
    for key in ("policy", "planDirectory", "skillRegistry"):
        if key in data:
            out[key] = _rel_path(data[key], key)
    if "dispatchSkill" in data:
        if not isinstance(data["dispatchSkill"], str) or not data["dispatchSkill"]:
            _fail("dispatchSkill", "must be a nonempty string")
        out["dispatchSkill"] = data["dispatchSkill"]

    pct = lambda v, k: _int(v, k, 0, 100)
    out["context"] = _section(data, "context", {
        "warnPct": pct, "criticalPct": pct, "reinjectPct": pct,
        "staleSeconds": lambda v, k: _int(v, k, 1, 86400)})
    if out["context"]["criticalPct"] > out["context"]["warnPct"]:
        _fail("context.criticalPct", "must not exceed context.warnPct")

    def pattern(value, key):
        try:
            re.compile(value)
        except (re.error, TypeError):
            _fail(key, "must be a valid regular expression string")
        return value

    def words(value, key):
        if not isinstance(value, list) or any(not isinstance(w, str) or not w for w in value):
            _fail(key, "must be a list of nonempty strings")
        return [w.lower() for w in value]

    def projection(value, key):
        if value is not None and (not isinstance(value, str) or not RUNNER_NAME.fullmatch(value)):
            _fail(key, "must be a harness name or null")
        return value

    out["routing"] = _section(data, "routing", {
        "excludeNamePattern": pattern, "dispatchWords": words,
        "minSignalTerms": lambda v, k: _int(v, k, 1, 20),
        "maxHints": lambda v, k: _int(v, k, 0, 20), "projection": projection})

    out["eval"] = _section(data, "eval", {"policy": _rel_path})

    if "runners" in data:
        _keys(data["runners"], data["runners"], "runners")
        for name, runner in data["runners"].items():
            if not RUNNER_NAME.fullmatch(name):
                _fail("runners", f"has an invalid runner name: {name!r}")
            _keys(runner, {"protocol"}, f"runners.{name}")
            if runner.get("protocol") not in RUNNER_PROTOCOLS:
                _fail(f"runners.{name}.protocol", "must be one of " + ", ".join(RUNNER_PROTOCOLS))
        out["runners"] = copy.deepcopy(data["runners"])

    if "handlers" in data:
        _keys(data["handlers"], data["handlers"], "handlers")
        for fact, entry in data["handlers"].items():
            if not FACT_NAME.fullmatch(fact):
                _fail("handlers", f"has an invalid fact name: {fact!r}")
            key = f"handlers.{fact}"
            _keys(entry, {"handler", "enabled"}, key)
            if type(entry.get("enabled")) is not bool:
                _fail(f"{key}.enabled", "must be boolean")
            if "handler" in entry and entry["handler"] not in HANDLERS:
                _fail(f"{key}.handler", "must name a known handler: " + ", ".join(sorted(HANDLERS)))
            if entry["enabled"] and "handler" not in entry:
                _fail(f"{key}.handler", "is required when enabled")
        out["handlers"] = copy.deepcopy(data["handlers"])
    return out


def read_raw(repo_root):
    """The profile file as written (None when absent); malformed JSON fails closed."""
    path = Path(repo_root) / PROFILE_REL
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise ProfileError(f"{PROFILE_REL}: invalid JSON or unreadable ({exc})") from None
    if not isinstance(data, dict):
        _fail("profile", "must be an object")
    return data


def load(repo_root):
    raw = read_raw(repo_root)
    return validate({} if raw is None else raw)
