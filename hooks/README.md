# hooks/

Python hooks adapt local assistant events; shell hooks implement Git checks.
Python guards read JSON payloads from stdin. Unexpected execution or payload errors
are reported to stderr with nonzero exit status; known missing optional inputs can
produce no output. Runners must treat guard failures as failed checks rather than
assuming that a failed hook granted permission. `OSE_BYPASS=1` is an explicit,
audited bypass in the edit, Bash and prompt guards.

## Repo profile

Activate with `.osengineer/profile.json` containing `{"profile":"repo"}`,
or `validation_profile: repo` in `.osengineer/workbench-config.yml`.
The prompt hook routes through the skill registry (`skillRegistry` in `.osengineer/profile.json`, default `.osengineer/skill-registry.json`) using registry
`skills[].name`, `canonical` and `projections.codex`. It reads at most 8 KiB of
frontmatter per available skill and emits at most two matching paths, including
aliases for the configured dispatch skill (`dispatchSkill`, default `dispatch`). Generic reviewer/verifier/judge
entries are excluded. It never loads complete skill bodies into the prompt.
Repo profile plans are referenced under the configured plan directory (`planDirectory`, default `.plans/`); no planning directory is
created by these hooks. The generic profile keeps its `planning/` namespace.

Prompt summaries are emitted only on phase, route or context-level changes for a
valid session. Low context causes a compact checkpoint reminder, not repeated
policy text. Context warnings occur on warning/critical transitions and rearm
after recovery. Temporary metrics expire after 60 seconds. Telemetry records
`context_used_pct`, which is context-window occupancy, **not task token spend**.
Repo profile stores derived context telemetry in `<planDirectory>/osengineer/context.json`;
it does not create an independent `.osengineer/state.yml`. Repo profile execution
scope comes from repository policy and the dispatch contract, not legacy team
`owns_paths` caches. Generic profiles deny execution edits if the active team
cache has missing or malformed ownership configuration.
These hooks do not implement a budget circuit breaker.

The edit guard denies edits during `blocked` and `suspended` until explicit
resume, and checks team ownership during execution. Nested working directories
resolve the repository configuration before destructive-command checks.
These local hooks are defense in depth; a headless runner must enforce its own
permissions and contract checks. They do not provide a complete shell sandbox.

Run payload regressions with:

```sh
python3 -m unittest discover -s test -p test_repo_profile_hooks.py -v
```
