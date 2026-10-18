# Portable Repo profile runtime

This standard-library Python module runs the same contract locally or headlessly. It complements the repository's dispatch workflow and policy; it does not replace their lifecycle, review, or merge gates. References to repository policy are required when that project has an applicable policy file. Read the existing policy file, dispatch workflow contract, and referenced `repoPolicy` before authoring a task.

```sh
python3 -m repo_runtime validate --repo /path/to/repo --contract task.json
python3 -m repo_runtime preflight --repo /path/to/repo --contract task.json
python3 -m repo_runtime run --repo /path/to/repo --contract task.json --mode local --runner codex
python3 -m repo_runtime run --repo /path/to/repo --contract task.json --mode shadow
python3 -m repo_runtime verify --repo /path/to/repo --contract task.json --result /path/to/run/result.json
python3 -m repo_runtime handoff --repo /path/to/repo --contract task.json
```

Exit code 0 means the requested operation passed; code 2 means failed, needs-human, or not-run. `validate` checks contract shape and resolvability, not readiness to execute. `preflight` checks the base revision and scope. `handoff` only emits a compact brief. A run with no explicitly chosen runner executes nothing, including in shadow mode. A run with no acceptance commands cannot report passed.

## Contract schema v1

```json
{
  "schemaVersion": 1,
  "issue": "TEST-123",
  "goal": "Correct the dispatch transition guard",
  "outcome": "Invalid transitions fail with a clear reason",
  "baseSha": "FULL_COMMIT_SHA_FROM_GIT_REV_PARSE_HEAD",
  "allowedPaths": ["src/dispatch/", "test/dispatch.test.py"],
  "acceptanceCommands": [["python3", "-m", "unittest", "test.dispatch_tests"]],
  "authorizedEffects": ["local"],
  "attempts": 1,
  "wallLimitSeconds": 300,
  "repoPolicy": "POLICY.md"
}
```

Required fields: schemaVersion, goal, baseSha, allowedPaths, acceptanceCommands. Optional strings: issue, outcome, repoPolicy, repoPolicyDigest, policyFileDigest and the paired planPath/planDigest (SHA-256). Unknown fields fail validation, preventing silently ignored typos. attempts defaults to 1 (1–20); wallLimitSeconds defaults to 300 (1–86400). attempts describes an outer retry budget; this runner deliberately makes one attempt, without hidden retries. `authorizedEffects` defaults to `["local"]`; supported declarations are local, draft-pr and issue-update. Those declarations never grant credentials or execute remote actions. Shadow requires local effects only.

A path ending in `/` grants a directory prefix; other paths grant exactly that file. Absolute paths, empty segments, traversal, `.git`, and symlink ancestors are rejected. The execution-artifact namespace cannot itself be authorized as a coding scope. `repoPolicy` is an existing repository-relative file, referenced by the task and available to the runner. The configured policy file (default `POLICY.md`) is selected automatically when present. Its policyFileDigest is always bound independently, including when repoPolicy names an auxiliary file. Bound authority, policy and plan contents are rechecked at preflight, after the runner, after each acceptance command and during verification; stale evidence prevents passed status. A supplied planDigest requires a matching actual planPath. In-scope commits descending from baseSha are allowed; receipts bind the resulting SHA, and checks must not move that SHA. The runtime does not interpret prose policy as code.

Acceptance commands are argument arrays passed with `shell=False` and without interpolation. Execute only reviewed commands: arrays can still invoke interpreters, commands with effects, or scripts. No credential lookup, network request, deployment, merge, issue update, model selection, or auth override is performed by the runtime.

## Runner protocol

An explicit non-Codex runner is invoked as a single executable, without appended arguments. It receives the contract brief on stdin and these environment variables:

- OSE_PROFILE_CONTRACT_PATH: saved normalized contract JSON.
- OSE_PROFILE_REPO: absolute repository root.
- OSE_PROFILE_RESULT_PATH: destination for final JSON.
- OSE_PROFILE_MODE: local, headless, or shadow.

It must return exit code zero and write `{"status":"passed|failed|needs-human","summary":"..."}` to the final path. Missing or invalid structured results become needs-human. Wrapper executables can adapt other coding tools to this protocol. Existing environment and authentication are retained; select a sanitized environment outside this module for pipeline runs.

`--runner codex` uses `codex exec --json --output-schema ... --output-last-message ... -`; it does not change model, authentication, approval, or sandbox settings. Codex must already be installed and configured. The generated output schema contains only status and summary; actual success is determined by recorded acceptance commands. Local and headless modes share validation and evidence rules; headless is not an elevated permission level.

## Evidence and boundaries

Default artifacts live in `<planDirectory>/osengineer/run-<uuid>/`. Existing output directories are never reused. In-repository overrides must be below `<planDirectory>/osengineer/`. A runtime manifest inventories the exact files of completed runs and validates their hashes before excluding them from subsequent scope checks. Repeated runs need no project gitignore change. Unregistered files in the artifact namespace remain scope violations; changed prior artifacts block the next run. The manifest is local evidence, not a signed authority. External output directories are also supported. A canonical contract digest, commit SHA, dirty-tree content digest, command argv, exit codes, timeouts, durations and complete stdout/stderr files are recorded. No evidence logs are silently truncated. Verification rechecks their hashes, current revision, current dirty-tree contents and scope. Acceptance commands that change task inputs fail verification and require a fresh run on final contents.

Scope detection includes Git-visible tracked changes, deletions, rename source/destination, and non-ignored untracked files before and after execution. The local hooks' volatile state (`.osengineer/runtime.yml`, `.osengineer/.state.lock`) is excluded, whether or not the repository ignores it. It cannot observe ignored file writes, restored transient changes, external writes, credential access, or remote effects. Receipts are local evidence, not signed attestations; a process with artifact write access can forge them. Permission/approval enforcement and protection from hostile runners require an external OS/container sandbox, isolated credentials and network policy. Shadow with an explicitly selected runner still executes locally and needs that sandbox. Only shadow without a runner is a guaranteed no-execution inspection.

The wall-time limit covers runner plus checks; on POSIX timeout kills the active subprocess group. Detached children and races need OS-level isolation. Disk use for full logs must be bounded externally. No prompts are used to resolve blockers: results return needs-human with reasons. Real Codex, external APIs, production systems and pipelines need separate integration validation before enabling automation.
