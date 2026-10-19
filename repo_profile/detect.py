"""Offline facts about a repository, mapped to named handlers by profile.json.

Detectors only look at files and PATH. A fact with a known handler is
proposed; a fact without one is reported as unhandled and never enabled.
"""
import copy
import json
import os
import shutil
import tempfile
from pathlib import Path

from . import config


def _file(rel):
    return lambda repo, profile, which: (repo / rel(profile)).is_file()


def _glob(*patterns):
    return lambda repo, profile, which: any(any(repo.glob(p)) for p in patterns)


def _tool(name):
    return lambda repo, profile, which: which(name) is not None


# fact -> (default handler or None, probe(repo, profile, which))
DETECTORS = {
    "profile-json": ("profile.config", _file(lambda p: config.PROFILE_REL)),
    "policy-file": ("runtime.policyBinding", _file(lambda p: p["policy"])),
    "skill-registry": ("routing.skillRegistry", _file(lambda p: p["skillRegistry"])),
    "eval-policy": ("eval.gate", _file(lambda p: p["eval"]["policy"])),
    "ci:github-actions": (None, _glob(".github/workflows/*.yml", ".github/workflows/*.yaml")),
    "harness:claude": ("hooks.claude", lambda repo, p, which: (repo / ".claude").is_dir() or which("claude") is not None),
    "harness:kimi": ("hooks.kimi", _tool("kimi")),
    "harness:codex": ("hooks.codex", lambda repo, p, which: (repo / ".codex").is_dir() or which("codex") is not None),
    "cli:gh": ("integrations.github", _tool("gh")),
    "cli:op": ("secrets.op", _tool("op")),
    "package-manager:npm": (None, _glob("package.json")),
    "package-manager:pip": (None, _glob("requirements*.txt", "pyproject.toml", "setup.py")),
    "package-manager:go": (None, _glob("go.mod")),
    "package-manager:cargo": (None, _glob("Cargo.toml")),
}


def detect(repo, which=shutil.which, profile=None):
    repo = Path(repo).resolve()
    profile = profile or config.load(repo)
    return sorted(fact for fact, (_, probe) in DETECTORS.items() if probe(repo, profile, which))


def report(repo, which=shutil.which):
    """Facts with their status, the proposed profile and the unhandled facts."""
    raw = config.read_raw(repo) or {}
    profile = config.validate(raw)
    facts = detect(repo, which, profile)
    configured = profile["handlers"]
    rows, proposed = [], copy.deepcopy(raw)
    for fact in facts:
        default = DETECTORS[fact][0]
        entry = configured.get(fact)
        if entry is not None:
            status = "handled" if entry["enabled"] else "acknowledged"
            handler = entry.get("handler")
        elif default:
            status, handler = "unconfigured", default
            proposed.setdefault("handlers", {})[fact] = {"handler": default, "enabled": True}
        else:
            status, handler = "unhandled", None
        rows.append({"fact": fact, "status": status, "handler": handler})
    for fact in sorted(set(configured) - set(facts)):
        rows.append({"fact": fact, "status": "not-detected", "handler": configured[fact].get("handler")})
    proposed.setdefault("schemaVersion", 1)
    config.validate(proposed)
    return {"facts": rows, "proposed": proposed,
            "unhandled": [r["fact"] for r in rows if r["status"] == "unhandled"]}


def write(repo, which=shutil.which):
    """Write the proposed profile (known handlers only); returns the report."""
    result = report(repo, which)
    path = Path(repo) / config.PROFILE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".profile-")
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(json.dumps(result["proposed"], indent=2) + "\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return result
