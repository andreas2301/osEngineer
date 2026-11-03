"""HANDOFF.json: the sidecar a producer leaves next to a PHASE_PLAN.md (family-handoff/1).

Stdlib only. The producer owns the format (autoRoadmap's
specs/schemas/family-handoff.schema.json); this module pins the schema id and
reads only the keys below, so a producer can add others without a release here.
It is read at one place, the human gate into execute (hooks/lib/phase_gate.py):
a file contract, so no tool calls another. Anything unusable fails with the file
and the offending key.
"""
import hashlib
import json
import re
from pathlib import Path

NAME = "HANDOFF.json"
SCHEMA = "family-handoff/1"
CONSUMER = "osEngineer"
TRACE_ID = re.compile(r"[a-z0-9][a-z0-9-]*:(RM-[0-9]{3,})")
SHA256 = re.compile(r"[0-9a-f]{64}")


class HandoffError(ValueError):
    """An unusable HANDOFF.json; the message names the file and the offending key."""


def _field(data, key):
    """data[key] when data is an object holding a nonempty string there, else None."""
    value = data.get(key) if isinstance(data, dict) else None
    return value if isinstance(value, str) and value else None


def read(plan_path):
    """The approval record of the sidecar next to plan_path; None when it has none."""
    plan_path = Path(plan_path)
    path = plan_path.with_name(NAME)
    if not path.exists():
        return None

    def fail(key, problem):
        raise HandoffError(f"{path}: {key} {problem}")

    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise HandoffError(f"{path}: unreadable ({exc})") from None
    if not isinstance(data, dict):
        fail("document", "must be an object")
    if data.get("schema") != SCHEMA:
        fail("schema", f"must be {SCHEMA}")
    if _field(data.get("consumer"), "name") != CONSUMER:
        fail("consumer.name", f"must be {CONSUMER}")
    trace = TRACE_ID.fullmatch(_field(data, "trace_id") or "")
    if not trace or trace.group(1) != data.get("roadmap_id"):
        fail("trace_id", "must be <repo_id>:<roadmap_id>")
    producer, version = _field(data.get("producer"), "name"), _field(data.get("producer"), "version")
    if not producer or not version:
        fail("producer", "must give name and version")
    handed_off = _field(data, "artefact_sha256")
    if not handed_off or not SHA256.fullmatch(handed_off):
        fail("artefact_sha256", "must be a sha256 in hex")
    plan_sha = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    return {"trace_id": data["trace_id"], "producer": f"{producer} {version}",
            "artefact_sha256": handed_off, "plan_sha256": plan_sha,
            "plan_changed": plan_sha != handed_off}
