# Local and headless execution

Install from an osEngineer checkout with `python3 bin/osengineer profile install --repo /path/to/repo`, or `bash install.sh --profile repo /path/to/repo`. This installs one canonical Claude skill, its Codex projection and self-contained Python assets. It preserves the policy file, CLAUDE.md, existing hooks and settings; it does not activate or trust any hooks. An existing modified owned asset causes an explicit conflict. Uninstall removes only unchanged owned assets and its own registry entry.

From the installed skill directory:

```sh
python3 scripts/repo_profile.py runtime validate --repo /path/to/repo --contract /path/to/task.json
python3 scripts/repo_profile.py runtime preflight --repo /path/to/repo --contract /path/to/task.json --mode shadow
python3 scripts/repo_profile.py runtime run --repo /path/to/repo --contract /path/to/task.json --mode shadow
```

Without `--runner`, run records not-run and executes nothing. An explicit `--runner codex` uses structured noninteractive output without changing model/auth/sandbox settings. Another executable implements the documented runner protocol. Read `scripts/repo_runtime/README.md` for exact contract fields, argv acceptance commands, scope semantics and result verification. Author the contract from the approved issue/plan; repository policy and existing dispatch workflow lifecycle remain authoritative.

A contract names schemaVersion 1, goal, baseSha, allowedPaths (exact file or directory ending /), acceptanceCommands (argv arrays), optional issue/outcome, repoPolicy, attempts and wallLimitSeconds. Effects default to local. Headless is not higher privilege. Missing executable/capability/decision becomes needs-human; no hidden retries, tracker writes, deployment or promotion occur.

After an explicit run, verify its receipts with `runtime verify --repo ... --contract ... --result <run/result.json>`. SHA, dirty-tree contents, scope and log hashes must still match. Default artifacts live under `<planDirectory>/osengineer/` (default `.plans/osengineer/`); runtime inventories exclude only its own unchanged artifacts from repeat-run scope checks.

Use the same task cases for local and headless trials. Start with investigation and small bug fixes, then isolated feature work and shadow delivery preparation. The repository's existing evaluation scripts provide behavioral evaluation; deterministic mock tests alone cannot establish pipeline readiness.

Important execution boundary: hooks and Git-visible path checks detect mistakes; they cannot stop remote calls, transient/ignored file writes or hostile processes. A trusted pipeline launcher must enforce its OS/container sandbox, credential scope, egress, disk limits and permitted tool set. Shadow with an explicit runner executes code locally. Production/remote capabilities require separate authorization and the repository lifecycle's real evidence. Known dispatch workflow promotion, pagination or head-binding defects must be repaired in their own delivery scope before autonomous live pipeline integration.

