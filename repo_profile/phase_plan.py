"""PHASE_PLAN.md frontmatter: the one parser and validator, shared by hooks and CLI.

Stdlib only. The frontmatter between the leading --- lines is a JSON object
(JSON is YAML 1.2 flow syntax), so validation is exact without a YAML parser.
specs/SCHEMAS/phase-plan.schema.json documents the same rules; a test keeps the
two in step. Anything invalid fails closed with the file and offending key.
"""
import json
import re
from pathlib import Path

PLAN_NAME = "PHASE_PLAN.md"

TOP_KEYS = ("phase_id", "goal", "classification", "owner_team", "rollback_path",
            "risk_flags", "tasks", "acceptance_criteria")
TOP_REQUIRED = ("phase_id", "goal", "tasks")
TASK_KEYS = ("id", "description", "depends_on", "acceptance", "budget", "status")
TASK_REQUIRED = ("id", "description", "acceptance", "budget")
# Measured per attempt by the post-tool hook and the headless runner (tool
# calls, wall time); tokens are recorded when the harness exposes them.
BUDGET_MINIMUMS = {"tool_calls": 1, "wall_minutes": 1, "tokens": 100}
BUDGET_REQUIRED = ("tool_calls", "wall_minutes")
CLASSIFICATIONS = ("feature", "fix", "refactor", "adr", "hotfix")
STATUSES = ("pending", "in_progress", "completed", "blocked")
LEVELS = ("low", "medium", "high")
PHASE_ID = re.compile(r"^phase-\d{3}(\.\d+)?-[a-z0-9-]+$")
TASK_ID = re.compile(r"^T\d+$")


class PlanError(ValueError):
    """An invalid PHASE_PLAN.md; the message names the file and the offending key."""


def _fail(where, key, problem):
    raise PlanError(f"{where}: {key} {problem}")


def _obj(value, allowed, required, where, key):
    if not isinstance(value, dict):
        _fail(where, key, "must be an object")
    extra = set(value) - set(allowed)
    if extra:
        _fail(where, key, "has unknown keys: " + ", ".join(sorted(extra)))
    for name in required:
        if name not in value:
            _fail(where, f"{key}.{name}" if key != "frontmatter" else name, "is required")


def _str(value, where, key, min_len=0):
    if not isinstance(value, str) or len(value) < min_len:
        _fail(where, key, f"must be a string of at least {min_len} characters" if min_len else "must be a string")


def _enum(value, allowed, where, key):
    if value not in allowed:
        _fail(where, key, "must be one of: " + ", ".join(allowed))


def _str_list(value, where, key):
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        _fail(where, key, "must be a list of strings")


def validate(data, where):
    """Return data when it is a valid PHASE_PLAN frontmatter object, else raise PlanError."""
    _obj(data, TOP_KEYS, TOP_REQUIRED, where, "frontmatter")
    if not isinstance(data["phase_id"], str) or not PHASE_ID.fullmatch(data["phase_id"]):
        _fail(where, "phase_id", "must match phase-NNN[.N]-slug")
    _str(data["goal"], where, "goal", 10)
    if "classification" in data:
        _enum(data["classification"], CLASSIFICATIONS, where, "classification")
    for key in ("owner_team", "rollback_path"):
        if key in data:
            _str(data[key], where, key)
    if "acceptance_criteria" in data:
        _str_list(data["acceptance_criteria"], where, "acceptance_criteria")
    if "risk_flags" in data:
        if not isinstance(data["risk_flags"], list):
            _fail(where, "risk_flags", "must be a list")
        for i, flag in enumerate(data["risk_flags"]):
            key = f"risk_flags[{i}]"
            _obj(flag, ("risk", "likelihood", "impact", "mitigation"), ("risk", "likelihood", "impact"), where, key)
            _str(flag["risk"], where, f"{key}.risk")
            _enum(flag["likelihood"], LEVELS, where, f"{key}.likelihood")
            _enum(flag["impact"], LEVELS, where, f"{key}.impact")
            if "mitigation" in flag:
                _str(flag["mitigation"], where, f"{key}.mitigation")

    tasks = data["tasks"]
    if not isinstance(tasks, list) or not tasks:
        _fail(where, "tasks", "must be a nonempty list")
    ids = []
    for i, task in enumerate(tasks):
        key = f"tasks[{i}]"
        _obj(task, TASK_KEYS, TASK_REQUIRED, where, key)
        if not isinstance(task["id"], str) or not TASK_ID.fullmatch(task["id"]):
            _fail(where, f"{key}.id", "must match TN")
        if task["id"] in ids:
            _fail(where, f"{key}.id", f"is a duplicate of an earlier task: {task['id']}")
        ids.append(task["id"])
        _str(task["description"], where, f"{key}.description")
        _str(task["acceptance"], where, f"{key}.acceptance")
        if "status" in task:
            _enum(task["status"], STATUSES, where, f"{key}.status")
        budget = task["budget"]
        _obj(budget, BUDGET_MINIMUMS, BUDGET_REQUIRED, where, f"{key}.budget")
        for name, value in budget.items():
            low = BUDGET_MINIMUMS[name]
            if type(value) is not int or value < low:
                _fail(where, f"{key}.budget.{name}", f"must be an integer >= {low}")
    for i, task in enumerate(tasks):
        if "depends_on" in task:
            deps = task["depends_on"]
            if (not isinstance(deps, list) or any(not isinstance(d, str) or d not in ids or d == task["id"]
                                                  for d in deps)):
                _fail(where, f"tasks[{i}].depends_on", "must list ids of other tasks in this plan")
    return data


def parse(text, where):
    """Parse and validate the frontmatter of PHASE_PLAN.md text."""
    lines = text.splitlines()
    end = None
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        _fail(where, "frontmatter", "is missing: the file must start with a --- delimited JSON object")
    try:
        data = json.loads("\n".join(lines[1:end]))
    except ValueError as exc:
        _fail(where, "frontmatter", f"is not valid JSON ({exc})")
    if not isinstance(data, dict):
        _fail(where, "frontmatter", "must be an object")
    return validate(data, where)


def load(path):
    path = Path(path)
    try:
        text = path.read_text()
    except OSError as exc:
        raise PlanError(f"{path}: unreadable ({exc})") from None
    return parse(text, str(path))


def load_active(planning_root):
    """(path, plan) for the single <planning>/active/*/PHASE_PLAN.md, or None if there is none."""
    plans = sorted(Path(planning_root).glob(f"active/*/{PLAN_NAME}"))
    if not plans:
        return None
    if len(plans) > 1:
        raise PlanError(f"{Path(planning_root) / 'active'}: more than one active {PLAN_NAME} "
                        f"({', '.join(p.parent.name for p in plans)}); archive all but one")
    return plans[0], load(plans[0])


def estimate(plan):
    """The phase budget: per-task budgets summed. tokens is None when no task gives it."""
    budgets = [task["budget"] for task in plan["tasks"]]
    tokens = [b["tokens"] for b in budgets if "tokens" in b]
    return {"tool_calls": sum(b["tool_calls"] for b in budgets),
            "wall_minutes": sum(b["wall_minutes"] for b in budgets),
            "tokens": sum(tokens) if tokens else None}
