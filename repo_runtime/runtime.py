"""Task receipts are evidence, not a security boundary. See README.md."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import time
import uuid

from repo_profile import config as profile_config


class ContractError(ValueError):
    pass


# Volatile state the local hooks rewrite on every tool call (context
# telemetry and its lock). It is not task output, and a repo need not
# gitignore it.
HOOK_VOLATILE_PATHS = {".osengineer/runtime.yml", ".osengineer/.state.lock"}
# Runner basename that selects the `codex exec` protocol; profile.json key codexRunner.
DEFAULT_CODEX_RUNNER = profile_config.DEFAULTS["codexRunner"]


def profile_settings(repo):
    """Policy file, plan directory and codexRunner from .osengineer/profile.json; invalid fails closed."""
    try:
        profile = profile_config.load(repo)
    except profile_config.ProfileError as e:
        raise ContractError(str(e)) from None
    return {key: profile[key] for key in ("policy", "planDirectory", "codexRunner")}


def policy_file(repo):
    return profile_settings(repo)["policy"]


def state_dir(repo):
    return profile_settings(repo)["planDirectory"] + "/osengineer"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def git(repo, *args):
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if p.returncode:
        raise ContractError("Git operation failed: " + p.stderr.decode(errors="replace").strip())
    return p.stdout


def head(repo):
    return git(repo, "rev-parse", "HEAD").decode().strip()


def path_inside(repo, name):
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise ContractError("Paths must be nonempty POSIX repository-relative paths")
    trimmed = name.removesuffix("/")
    p = PurePosixPath(trimmed)
    if p.is_absolute() or any(x in (".", "..", "") for x in trimmed.split("/")) or trimmed == ".git" or trimmed.startswith(".git/"):
        raise ContractError("Unsafe repository path: " + name)
    candidate = (repo / trimmed).resolve()
    if not candidate.is_relative_to(repo):
        raise ContractError("Path escapes repository through a symlink: " + name)
    # Even inward symlinks make declared scopes ambiguous; reject symlink ancestors.
    cursor = repo
    for part in p.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ContractError("Symlinks are not permitted in task scopes: " + name)
    return candidate


def load_contract(path, repo):
    repo = Path(repo).resolve()
    root = Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if root != repo:
        raise ContractError("--repo must name the repository root")
    profile_settings(repo)
    try:
        c = json.loads(Path(path).read_text())
    except (OSError, ValueError) as e:
        raise ContractError("Cannot read contract: " + str(e)) from e
    if not isinstance(c, dict):
        raise ContractError("Contract must be an object")
    allowed = {"schemaVersion", "issue", "goal", "outcome", "baseSha", "allowedPaths", "acceptanceCommands", "authorizedEffects", "attempts", "wallLimitSeconds", "repoPolicy", "repoPolicyDigest", "policyFileDigest", "planDigest", "planPath"}
    if set(c) - allowed:
        raise ContractError("Unknown contract fields: " + ", ".join(sorted(set(c) - allowed)))
    if type(c.get("schemaVersion")) is not int or c["schemaVersion"] != 1:
        raise ContractError("schemaVersion must be integer 1")
    for key in ("goal", "baseSha"):
        if not isinstance(c.get(key), str) or not c[key].strip():
            raise ContractError(key + " must be a nonempty string")
    if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", c["baseSha"]):
        raise ContractError("baseSha must be a full commit SHA")
    actual = git(repo, "rev-parse", "--verify", c["baseSha"] + "^{commit}").decode().strip()
    c["baseSha"] = actual
    for key in ("issue", "outcome", "planDigest"):
        if key in c and (not isinstance(c[key], str) or not c[key].strip()):
            raise ContractError(key + " must be a nonempty string")
    if "planDigest" in c and not re.fullmatch(r"[0-9a-f]{64}", c["planDigest"]):
        raise ContractError("planDigest must be a SHA-256 digest")
    scopes = c.get("allowedPaths")
    if not isinstance(scopes, list) or not scopes:
        raise ContractError("allowedPaths must be a nonempty array")
    for name in scopes:
        path_inside(repo, name)
        if name.rstrip("/") == state_dir(repo) or name.startswith(state_dir(repo) + "/"):
            raise ContractError("Execution artifacts cannot be an authorized coding scope")
        if (repo / name).is_dir() and not name.endswith("/"):
            raise ContractError("Directory scopes must end in /: " + name)
    commands = c.get("acceptanceCommands")
    if not isinstance(commands, list):
        raise ContractError("acceptanceCommands must be an array of argv arrays")
    for argv in commands:
        if not isinstance(argv, list) or not argv or any(not isinstance(x, str) or not x or "\x00" in x for x in argv):
            raise ContractError("Every acceptance command must be a nonempty argv array")
    for key, default, maximum in (("attempts", 1, 20), ("wallLimitSeconds", 300, 86400)):
        c.setdefault(key, default)
        if type(c[key]) is not int or not 1 <= c[key] <= maximum:
            raise ContractError(key + " must be a positive bounded integer")
    c.setdefault("authorizedEffects", ["local"])
    if not isinstance(c["authorizedEffects"], list) or not c["authorizedEffects"] or any(x not in ("local", "draft-pr", "issue-update") for x in c["authorizedEffects"]):
        raise ContractError("authorizedEffects contains unsupported capabilities")
    for key in ('repoPolicyDigest', 'policyFileDigest'):
        if key in c and (not isinstance(c[key], str) or not re.fullmatch(r'[0-9a-f]{64}', c[key])):
            raise ContractError(key + ' must be a SHA-256 digest')
    policy = policy_file(repo)
    if (repo / policy).is_file():
        authority = path_inside(repo, policy)
        authority_digest = hashlib.sha256(authority.read_bytes()).hexdigest()
        if 'policyFileDigest' in c and c['policyFileDigest'] != authority_digest:
            raise ContractError('Policy file digest is stale')
        c['policyFileDigest'] = authority_digest
        c.setdefault("repoPolicy", policy)
    elif 'policyFileDigest' in c:
        raise ContractError('Bound policy file is missing')
    if "repoPolicyDigest" in c and "repoPolicy" not in c:
        raise ContractError("repoPolicyDigest requires repoPolicy")
    if "repoPolicy" in c:
        policy = path_inside(repo, c["repoPolicy"])
        if not policy.is_file():
            raise ContractError("repoPolicy must reference an existing repository file")
        policy_digest = hashlib.sha256(policy.read_bytes()).hexdigest()
        if "repoPolicyDigest" in c and c["repoPolicyDigest"] != policy_digest:
            raise ContractError("Repository policy digest is stale")
        c["repoPolicyDigest"] = policy_digest
    if "planPath" in c:
        plan = path_inside(repo, c["planPath"])
        if not plan.is_file() or "planDigest" not in c:
            raise ContractError("planPath requires an existing file and planDigest")
        if hashlib.sha256(plan.read_bytes()).hexdigest() != c["planDigest"]:
            raise ContractError("Plan digest is stale")
    elif "planDigest" in c:
        raise ContractError("planDigest requires planPath to bind actual evidence")
    return c, repo


def allowed_path(name, scopes):
    return any(name.startswith(s) if s.endswith("/") else name == s for s in scopes)


def changed_paths(repo, base):
    # --no-renames returns both old and new names; includes staged, unstaged and deleted paths.
    tracked = git(repo, "diff", "--no-renames", "--name-only", "-z", base, "--").split(b"\0")
    untracked = git(repo, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
    return sorted({os.fsdecode(x) for x in tracked + untracked if x} - HOOK_VOLATILE_PATHS)


def registered_artifacts(repo):
    """Exclude only inventoried runtime files; changed or extra files remain visible."""
    manifest = repo / state_dir(repo) / "runtime-manifest.json"
    if not manifest.exists():
        return set()
    path_inside(repo, str(manifest.relative_to(repo)))
    try:
        entries = json.loads(manifest.read_text())
        if not isinstance(entries, dict) or entries.get("schemaVersion") != 1 or not isinstance(entries.get("files"), dict):
            raise ContractError("Invalid runtime artifact manifest")
        paths = set()
        for name, expected in entries["files"].items():
            p = path_inside(repo, name)
            if not name.startswith(state_dir(repo) + "/") or name == state_dir(repo) + "/runtime-manifest.json":
                raise ContractError("Invalid artifact manifest scope")
            if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
                raise ContractError("Prior runtime artifact changed: " + name)
            paths.add(name)
        paths.add(str(manifest.relative_to(repo)))
        return paths
    except (OSError, ValueError) as e:
        raise ContractError("Cannot validate prior runtime artifacts: " + str(e)) from e


def register_artifacts(repo, out):
    if not out.is_relative_to(repo / state_dir(repo)):
        return
    manifest = repo / state_dir(repo) / "runtime-manifest.json"
    registered_artifacts(repo)
    entries = json.loads(manifest.read_text()) if manifest.exists() else {"schemaVersion": 1, "files": {}}
    for p in out.rglob("*"):
        if p.is_symlink():
            raise ContractError("Runner created a symlink in artifacts")
        if p.is_file():
            entries["files"][str(p.relative_to(repo))] = hashlib.sha256(p.read_bytes()).hexdigest()
    write_json(manifest, entries)


def scope_violations(repo, c, artifact_dir=None):
    violations = []
    registered = registered_artifacts(repo)
    for name in changed_paths(repo, c["baseSha"]):
        if name in registered:
            continue
        if artifact_dir and (repo / name).is_relative_to(artifact_dir):
            continue
        try:
            path_inside(repo, name)
        except ContractError:
            violations.append(name)
            continue
        if not allowed_path(name, c["allowedPaths"]):
            violations.append(name)
    return violations


def worktree_digest(repo, c, artifact_dir=None):
    """Bind evidence to dirty tree contents as well as the commit SHA."""
    state = []
    registered = registered_artifacts(repo)
    for name in changed_paths(repo, c["baseSha"]):
        if name in registered:
            continue
        if artifact_dir and (repo / name).is_relative_to(artifact_dir):
            continue
        path = repo / name
        if path.is_symlink():
            content = "symlink:" + os.readlink(path)
        elif path.is_file():
            content = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            content = "deleted-or-directory"
        state.append([name, content, path.stat().st_mode if path.exists() else None])
    return digest(state)


def evidence_freshness(c, repo):
    """Check the actual bound files even with cached contracts or ignored plans."""
    reasons = []
    policy = policy_file(repo)
    authority = repo / policy
    if authority.exists() and 'policyFileDigest' not in c:
        reasons.append('Policy file appeared after contract preparation')
    bindings = [(policy, c.get('policyFileDigest'), 'Policy file'),
                (c.get('repoPolicy'), c.get('repoPolicyDigest'), 'Repository policy'),
                (c.get('planPath'), c.get('planDigest'), 'Plan')]
    for name, expected, label in bindings:
        if expected is None:
            continue
        try:
            path = path_inside(repo, name)
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                reasons.append(label + ' changed after contract preparation')
        except (ContractError, OSError):
            reasons.append(label + ' is missing or no longer safely readable')
    return reasons


def preflight(c, repo, mode="local", artifact_dir=None):
    reasons = evidence_freshness(c, repo)
    if head(repo) != c["baseSha"]:
        reasons.append("HEAD differs from contract baseSha; prepare a fresh contract")
    violations = scope_violations(repo, c, artifact_dir)
    if violations:
        reasons.append("Changes outside allowedPaths: " + ", ".join(violations))
    if mode == "shadow" and c["authorizedEffects"] != ["local"]:
        reasons.append("Shadow mode permits only local effects")
    return {"status": "needs-human" if reasons else "passed", "reasons": reasons, "baseSha": c["baseSha"], "contractDigest": digest(c), "scopeViolations": violations}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def execute(argv, repo, seconds, out, name, env=None, stdin=None):
    stdout, stderr = out / (name + ".stdout"), out / (name + ".stderr")
    started = time.monotonic()
    timed_out = False
    with stdout.open("wb") as so, stderr.open("wb") as se:
        p = subprocess.Popen(argv, cwd=repo, stdout=so, stderr=se, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL, env=env, start_new_session=(os.name == "posix"))
        try:
            p.communicate(input=stdin.encode() if stdin is not None else None, timeout=max(0.01, seconds))
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name == "posix":
                os.killpg(p.pid, signal.SIGKILL)
            else:
                p.kill()
            p.communicate()
    return {"argv": argv, "exitCode": p.returncode, "timedOut": timed_out, "elapsedSeconds": round(time.monotonic() - started, 3), "stdout": str(stdout), "stderr": str(stderr), "stdoutSha256": hashlib.sha256(stdout.read_bytes()).hexdigest(), "stderrSha256": hashlib.sha256(stderr.read_bytes()).hexdigest()}


def run(c, repo, mode="local", runner=None, out=None):
    out = Path(out).resolve() if out else repo / state_dir(repo) / ("run-" + uuid.uuid4().hex)
    if out.is_relative_to(repo):
        parent = repo / state_dir(repo)
        if not out.is_relative_to(parent) or out == parent:
            raise ContractError("In-repository --out must be a new directory beneath " + state_dir(repo) + "/")
        path_inside(repo, str(out.relative_to(repo)))
    # Do not reuse artifacts: prior receipts must remain immutable by this runner.
    if out.exists():
        raise ContractError("Output directory already exists")
    before = preflight(c, repo, mode)
    out.mkdir(parents=True)
    prepared = out / "contract.json"
    write_json(prepared, c)
    prepared.chmod(0o444)
    result = {"schemaVersion": 1, "mode": mode, "status": before["status"], "contractDigest": digest(c), "baseSha": c["baseSha"], "completedSha": head(repo), "reasons": before["reasons"], "scopeViolations": before["scopeViolations"], "runner": None, "checks": [], "artifactDirectory": str(out)}
    def finish():
        result["completedSha"] = head(repo)
        result["worktreeDigest"] = worktree_digest(repo, c, out)
        write_json(out / "result.json", result)
        register_artifacts(repo, out)
        return result
    if before["status"] != "passed":
        return finish()
    if not runner:
        result.update(status="not-run", reasons=["No explicit runner supplied"])
        return finish()
    executable = shutil.which(runner)
    if executable is None:
        result.update(status="needs-human", reasons=["Runner executable is unavailable"])
        return finish()
    final_path = out / "runner-final.json"
    prompt = "Execute this Repo profile contract within the repository policy and allowed paths. Do not request interactive input; report needs-human when blocked. No remote effects without an explicit capability and external sandbox authorization. Contract:\n" + json.dumps(c, ensure_ascii=False)
    argv = [executable]
    if Path(runner).name == profile_settings(repo)["codexRunner"]:
        schema = out / "runner-output-schema.json"
        write_json(schema, {"type": "object", "properties": {"status": {"type": "string", "enum": ["passed", "failed", "needs-human"]}, "summary": {"type": "string"}}, "required": ["status", "summary"], "additionalProperties": False})
        argv += ["exec", "--json", "--output-schema", str(schema), "--output-last-message", str(final_path), "-"]
    env = os.environ.copy()
    env.update(OSE_PROFILE_CONTRACT_PATH=str(prepared), OSE_PROFILE_REPO=str(repo), OSE_PROFILE_RESULT_PATH=str(final_path), OSE_PROFILE_MODE=mode)
    deadline = time.monotonic() + c["wallLimitSeconds"]
    try:
        result["runner"] = execute(argv, repo, deadline - time.monotonic(), out, "runner", env, prompt)
    except OSError as e:
        result.update(status="needs-human", reasons=["Runner could not start: " + str(e)])
        return finish()
    try:
        prepared_matches = digest(json.loads(prepared.read_text())) == digest(c)
    except (OSError, ValueError):
        prepared_matches = False
    if not prepared_matches:
        result.update(status="failed", reasons=["Prepared contract changed during execution"])
        return finish()
    stale = evidence_freshness(c, repo)
    if stale:
        result.update(status='failed', reasons=stale)
        return finish()
    violations = scope_violations(repo, c, out)
    result["scopeViolations"] = violations
    result_sha = head(repo)
    descendant = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", c["baseSha"], result_sha], capture_output=True).returncode == 0
    if violations or not descendant:
        result.update(status="failed", reasons=["Runner rewrote task base history or changed files outside allowedPaths"])
        return finish()
    receipt = result["runner"]
    if receipt["timedOut"] or receipt["exitCode"] != 0:
        result.update(status="failed", reasons=["Runner timed out or exited unsuccessfully"])
        return finish()
    try:
        final = json.loads(final_path.read_text())
    except (OSError, ValueError):
        result.update(status="needs-human", reasons=["Runner did not produce a structured final result"])
        return finish()
    if not isinstance(final, dict) or final.get("status") not in ("passed", "failed", "needs-human") or not isinstance(final.get("summary"), str):
        result.update(status="needs-human", reasons=["Runner final result has invalid shape"])
        return finish()
    result["runnerSummary"] = final["summary"]
    if final["status"] != "passed":
        result.update(status=final["status"], reasons=["Runner reported " + final["status"]])
        return finish()
    if not c["acceptanceCommands"]:
        result.update(status="not-run", reasons=["No acceptance commands; success is unverified"])
        return finish()
    for index, command in enumerate(c["acceptanceCommands"]):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            result.update(status="failed", reasons=["Run wall-time budget exhausted"])
            return finish()
        try:
            checked_tree = worktree_digest(repo, c, out)
            checked_sha = head(repo)
            receipt = execute(command, repo, remaining, out, "check-" + str(index))
        except OSError as e:
            result.update(status="failed", reasons=["Acceptance command could not start: " + str(e)])
            return finish()
        receipt.update(contractDigest=digest(c), baseSha=c["baseSha"], checkedSha=checked_sha, worktreeDigest=checked_tree)
        result["checks"].append(receipt)
        if receipt["timedOut"] or receipt["exitCode"] != 0:
            result.update(status="failed", reasons=["Acceptance command failed or timed out"])
            return finish()
        stale = evidence_freshness(c, repo)
        if stale:
            result.update(status='failed', reasons=stale)
            return finish()
        if checked_tree != worktree_digest(repo, c, out) or checked_sha != head(repo):
            result.update(status="failed", reasons=["Acceptance command changed task inputs; rerun verification on final contents"])
            return finish()
    result["scopeViolations"] = scope_violations(repo, c, out)
    stale = evidence_freshness(c, repo)
    if stale:
        result.update(status='failed', reasons=stale)
    elif result["scopeViolations"] or head(repo) != result_sha:
        result.update(status="failed", reasons=["Acceptance checks changed revision or files outside allowedPaths"])
    else:
        result.update(status="passed", reasons=[])
    return finish()


def verify(c, repo, result_path):
    try:
        r = json.loads(Path(result_path).read_text())
    except (OSError, ValueError) as e:
        raise ContractError("Cannot read receipt: " + str(e)) from e
    reasons = evidence_freshness(c, repo)
    if not isinstance(r, dict):
        raise ContractError("Receipt must be an object")
    artifact_dir = Path(result_path).resolve().parent
    if artifact_dir.is_relative_to(repo) and not artifact_dir.is_relative_to(repo / state_dir(repo)):
        raise ContractError("In-repository receipt must be beneath " + state_dir(repo))
    tree = worktree_digest(repo, c, artifact_dir)
    try:
        if digest(json.loads((artifact_dir / "contract.json").read_text())) != digest(c):
            reasons.append("Prepared contract no longer matches")
    except (OSError, ValueError):
        reasons.append("Prepared contract is missing or invalid")
    if r.get("status") != "passed":
        reasons.append("Run did not pass")
    if r.get("contractDigest") != digest(c) or r.get("baseSha") != c["baseSha"] or r.get("completedSha") != head(repo):
        reasons.append("Receipt contract or revision is stale")
    if r.get("worktreeDigest") != tree:
        reasons.append("Working tree changed after verification")
    checks = r.get("checks", [])
    if not isinstance(checks, list) or any(not isinstance(check, dict) for check in checks):
        raise ContractError("Receipt checks must be objects")
    if not c["acceptanceCommands"] or len(checks) != len(c["acceptanceCommands"]):
        reasons.append("Acceptance evidence is incomplete")
    runner = r.get("runner")
    if not isinstance(runner, dict) or type(runner.get("exitCode")) is not int or runner["exitCode"] != 0 or runner.get("timedOut") is not False:
        reasons.append("Runner evidence is incomplete or unsuccessful")
    else:
        for kind in ("stdout", "stderr"):
            try:
                log = Path(runner[kind])
                if not log.resolve().is_relative_to(artifact_dir) or hashlib.sha256(log.read_bytes()).hexdigest() != runner[kind + "Sha256"]:
                    reasons.append("Runner evidence changed")
            except (KeyError, OSError, TypeError):
                reasons.append("Runner evidence is missing")
    for index, check in enumerate(checks):
        if index >= len(c["acceptanceCommands"]) or check.get("argv") != c["acceptanceCommands"][index] or type(check.get("exitCode")) is not int or check.get("exitCode") != 0 or check.get("timedOut") is not False or check.get("contractDigest") != digest(c) or check.get("checkedSha") != head(repo) or check.get("baseSha") != c["baseSha"] or check.get("worktreeDigest") != tree:
            reasons.append("Acceptance receipt is invalid")
        for kind in ("stdout", "stderr"):
            try:
                log = Path(check[kind])
                if not log.resolve().is_relative_to(Path(result_path).resolve().parent) or hashlib.sha256(log.read_bytes()).hexdigest() != check[kind + "Sha256"]:
                    reasons.append("Evidence log changed or escaped run directory")
            except (KeyError, OSError, TypeError):
                reasons.append("Evidence log is missing")
    if scope_violations(repo, c, Path(result_path).resolve().parent):
        reasons.append("Repository has changes outside task scope")
    return {"status": "failed" if reasons else "passed", "reasons": reasons, "contractDigest": digest(c), "baseSha": c["baseSha"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "preflight", "run", "verify", "handoff"):
        p = sub.add_parser(name)
        p.add_argument("--contract", required=True)
        p.add_argument("--repo", required=True)
        if name in ("preflight", "run"):
            p.add_argument("--mode", choices=("local", "headless", "shadow"), default="local")
        if name == "run":
            p.add_argument("--runner")
            p.add_argument("--out")
        if name == "verify":
            p.add_argument("--result", required=True)
    a = parser.parse_args(argv)
    try:
        c, repo = load_contract(a.contract, a.repo)
        if a.command == "validate":
            r = {"status": "passed", "contractDigest": digest(c), "contract": c}
        elif a.command == "preflight":
            r = preflight(c, repo, a.mode)
        elif a.command == "run":
            r = run(c, repo, a.mode, a.runner, a.out)
        elif a.command == "verify":
            r = verify(c, repo, a.result)
        else:
            r = {"status": "not-run", "contractDigest": digest(c), "issue": c.get("issue"), "goal": c["goal"], "baseSha": c["baseSha"], "allowedPaths": c["allowedPaths"], "acceptanceCommands": c["acceptanceCommands"], "repoPolicy": c.get("repoPolicy"), "nextAction": "Run preflight, then execute with an explicitly selected runner"}
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["status"] == "passed" else 2
    except (ContractError, OSError, ValueError) as e:
        print(json.dumps({"status": "needs-human", "reasons": [str(e)]}))
        return 2
