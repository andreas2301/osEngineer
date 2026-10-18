---
name: osEngineer:recipe-eval-harness
description: >-
  Linear recipe that sets up an evaluation harness for a detector,
  classifier or scanner repo and runs its keep/revert improvement loop. It
  researches and verifies labeled datasets (license, gated status, pinned
  revision, sha256, benign negatives, overlap and contamination), builds
  group-split dev/holdout/sealed sets with roles (PRIMARY, RECALL-ONLY,
  GUARD-ONLY, REPORT-ONLY, SEALED), writes a deterministic fetch script,
  per-set P/R/F1/latency metrics, and an eval policy decided by
  bin/ose-eval-gate. It also covers the karpathy/autoresearch-style loop,
  process reviews, one report branch per round, and a premortem plus honest
  assessment. Use when a repo's output is a label (prompt-injection
  scanner, secret detector, spam or toxicity classifier, SAST rule pack)
  and changes to it must be measured before they are kept. Don't use for
  unit or e2e test coverage (use /osEngineer:verify or the qa agent).
  Don't use for a one-off benchmark with no decision attached (use
  /osEngineer:investigate). Don't use to ship the detector itself (use
  /osEngineer:recipe-cut-release).
phase_allowed: [idle, discuss]
phase_after: idle
plan_artifact: none
recipe_steps: 9
---

# /osEngineer:recipe-eval-harness

Set up a measurement-driven improvement loop for a detector repo, then run it honestly. Most steps are local. Step 8 pushes a report branch, and only after explicit confirmation.

**Syntax:** `/osEngineer:recipe-eval-harness <repo-path> [--resume <step>] [--yes]`
**Role:** eval-harness-engineer (with researcher, developer, red-team-local, verifier, judge)
**Output:** `EVAL_POLICY.json`, `testdata/eval/SOURCES.md`, `scripts/fetch_eval.sh` (or the repo's equivalent), an eval command that emits metrics JSON, a decision-rules section in the repo's `CLAUDE.md`, per-round report branches, `docs/ASSESSMENT.md`.

Reference implementation: safeanalyze (prompt-injection scanner), whose loop the lessons in [`docs/eval-harness-lessons.md`](../docs/eval-harness-lessons.md) come from.

## Preconditions

- `.osengineer/state.yml` phase ∈ {idle, discuss}.
- The repo has a command that labels one input (or a batch). If it has none, run `/osEngineer:feature` first to add one.
- Clean working tree (`git status --porcelain` empty). Each loop iteration runs in its own worktree.
- `python3` (stdlib only), `curl` and `sha256sum` on PATH. `bin/ose-eval-gate` is reachable via `$OSENGINEER_HOME/bin/ose-eval-gate`.

## Single-Question Policy

Ask at most **one question per step**. Three steps always ask, whatever `--yes` says:

- the role assignment (step 3), because roles decide which data may shape the detector;
- any later role or threshold change, which needs user approval and judge review;
- the report-branch push (step 8), because it crosses the local↔remote boundary.

## Hard rules (apply to every step)

1. Never read holdout, GUARD-ONLY, REPORT-ONLY or SEALED misclassifications to design a change.
2. Never decide keep/revert in prose. Run `ose-eval-gate` and quote its reasons.
3. A threshold exists only if `EVAL_POLICY.json` declares it.
4. Verify every citation, dataset fact and number from research output against its primary source before it is written down.
5. One change per iteration. Bump the version, then measure on a clean tree.

## Steps

### Step 1 — Scope the detector
Write down:
- the positive label ("prompt injection present"),
- the input families (plain text, HTML, JSON tool output, mail, code, languages),
- the operating modes and their latency budget (for example fast mode at most 100 ms p95),
- the eval command to build or reuse.

Record the families as the coverage target for step 2.

### Step 2 — Research and verify datasets
Hand the input families to the **researcher**. Ask for candidate labeled sets, each with URL, license, revision, gated status and benign-row availability. Then the eval-harness-engineer verifies each candidate against [dataset-intake](../agents/eval-harness-engineer/references/dataset-intake.md):
- **Provenance:** pinned SHA, sha256 and size of each file, and the license read at that revision.
- **Content:** benign negatives present, label noise sampled by hand, template dominance counted, artifacts diffed between classes.
- **Origin:** synthetic or machine-translated. Translations of other eval rows count as contamination.

Write one block per admitted set in `testdata/eval/SOURCES.md`. Record rejected sets and the reason.

### Step 3 — Splits and set roles
- **Splits:** group-split each set by source case into dev / holdout. Carve a **SEALED** set from data no one has looked at. Keep one hard, human-written adversarial set with hard-benign rows as **REPORT-ONLY**.
- **Roles:** propose a role per set ([set-roles](../agents/eval-harness-engineer/references/set-roles.md)):
  - positives-only → RECALL-ONLY;
  - template-dominated, or fewer than about 100 positives → GUARD-ONLY;
  - adversarial stress → REPORT-ONLY.
- **Policy:** write `EVAL_POLICY.json` against [`specs/SCHEMAS/eval-policy.schema.json`](../specs/SCHEMAS/eval-policy.schema.json). Set the gates: per-set non-regression, single-sample tolerance, recall-only TP loss, generalization ratio `holdout_gain ≥ k × dev_gain`, paired bootstrap (if per-sample predictions are available), latency budget and noise band, latency-only accept, and sealed cadence.

**Question (mandatory):** "Approve these set roles and gates? (y/N)"

### Step 4 — Deterministic fetch script
Write `scripts/fetch_eval.sh`, or the repo's equivalent, using bash, curl, sha256sum and stdlib python3:
- pinned revisions, sha256 verification of each download, and a cache directory;
- a fixed seed, with sorted inputs before sampling;
- exact and normalized overlap checks across dev, holdout, sealed and report sets, plus a check of every new set against every existing one, all exiting non-zero on overlap;
- output sha256s printed at the end and recorded in `SOURCES.md`.

Labeled data is **not committed**. Run the script twice: the outputs must be byte-identical.

### Step 5 — Eval command and baseline
Build or extend the eval command (TDD, through the **developer**). For each set it writes:
- the counts (TP/FP/TN/FN),
- p50 and p95 latency,
- optional per-sample predictions,
- FP/FN JSONL files.

It also emits the metrics JSON described in [metrics-format](../agents/eval-harness-engineer/references/metrics-format.md), including `version`, `git.commit`, `git.dirty` and `errors`. Measure the baseline on every non-sealed set, then read the sealed set once.

### Step 6 — Decision rules in the repo
Add an "Autoresearch improvement loop" section to the repo's `CLAUDE.md` with:
- the prerequisites,
- the iteration steps (step 7 below),
- a set-taxonomy table that points to `EVAL_POLICY.json`,
- a pointer to the decision rules, phrased as "run `ose-eval-gate`" and not restated as prose with numbers.

Smoke-test the gate on the shipped fixtures:

```
$OSENGINEER_HOME/bin/ose-eval-gate --policy $OSENGINEER_HOME/test/fixtures/eval-gate/policy.json \
  --baseline $OSENGINEER_HOME/test/fixtures/eval-gate/summed-holdout.baseline.json \
  --candidate $OSENGINEER_HOME/test/fixtures/eval-gate/summed-holdout.candidate.json
```

The expected verdict is `REVERT`, naming `browsesafe-holdout`.

### Step 7 — The keep/revert loop (inspired by karpathy/autoresearch)
Each iteration runs in its own worktree:
1. **Baseline:** the last accepted metrics JSON.
2. **Premortem:** list the top 3 ways this change could still fail in production ([assessment-template](../agents/eval-harness-engineer/references/assessment-template.md)).
3. **Gap analysis:** read only the PRIMARY and RECALL-ONLY **dev** FP/FN files.
4. **Hypothesis:** exactly one concrete change. The developer implements it with TDD.
5. **Red team:** the **red-team-local** agent tries paraphrase, encoding, multilingual and hard-benign evasions. If the change is trivially bypassed, harden it or drop it.
6. **Bump, then measure:** commit, bump the version, re-run the fetch script (sha256s must match), then measure every non-sealed set.
7. **Gate:** run `ose-eval-gate --policy EVAL_POLICY.json --baseline <last-accepted>.json --candidate <this>.json --json`.
   - **ACCEPT:** keep the change and record the verdict reasons in the iteration notes.
   - **REVERT:** revert the change. Record the attempt under "rejected options".
   - **Exit 2:** fix the input. Never hand-decide.
8. **Record:** write per-iteration results to a scratch directory, never to a branch.

Stop when `loop.stagnation_window` consecutive iterations bring no gain, or at `loop.max_iterations_per_round`.

### Step 8 — Process review, sealed read and round report
After every `loop.process_review_every` iterations, or at stagnation, run the process review:
- **Metrics:** is the right metric being measured? Compare dev and holdout gain per set.
- **Data:** are the sets still representative?
- **Optimizations:** which skipped optimizations matter now, given latency creep per rule?
- **Branches:** how many report branches exist, and which should be archived?
- **Lessons:** walk [`docs/eval-harness-lessons.md`](../docs/eval-harness-lessons.md).

Then:
1. Read the SEALED set once (`"evaluation": "round"`).
2. Create **one** report branch for the round, as a worktree from the default branch: `report-<devicename>-<date>`. It holds a `COMPARISON.md` of the round's final version against the version the round started from.
3. Hand the round to the **verifier**, which reproduces the numbers, and then to the **judge**.

**Question (mandatory, `--yes` does not override):** print the exact `git push -u origin report-<...>` command, then ask "Type 'push' to confirm:". Only the report branch is pushed, never the default branch.

### Step 9 — Honest assessment
When the marginal holdout gain per iteration falls toward zero, or before any strategy change, pause the loop and write `docs/ASSESSMENT.md` from [assessment-template](../agents/eval-harness-engineer/references/assessment-template.md). It contains:
- the verdict;
- per-family holdout recall and FP rate;
- fresh probes;
- the overfitting caveats;
- a premortem with base-rate math at realistic prevalence;
- value and alternatives, with verified citations;
- ranked next steps.

## Example

```
/osEngineer:recipe-eval-harness ~/src/safeanalyze
```

Output shape (illustrative):
```
Step 2  datasets: 9 candidates, 7 admitted, 2 rejected (gated; no benign rows)
Step 3  roles: PRIMARY llmail browsesafe toolresp | RECALL-ONLY multilingual |
        GUARD-ONLY deepset nemotron spanish | REPORT-ONLY promptprotection-stress |
        SEALED sealed-2026q4                       Approve? y
Step 4  fetch_eval.sh: 2 runs byte-identical, 0 overlaps, 15 sha256s recorded
Step 5  baseline v0.3.45 measured (sealed read 1/1)
Step 7  iter 43: REVERT  generalization: spanish dev f1 +0.4315 but spanish-holdout +0.1415 (ratio 0.33 < k 0.5)
        iter 44: ACCEPT  latency-only: browsesafe p95_ms 70.7 -> 44.1 (-37.6 %)
Step 8  report-maximum-effort-chimichanga-9f7d-2026-10-20   Type 'push' to confirm:
```

## Failure handling

- **Fetch sha256 mismatch or overlap:** the script exits non-zero and the recipe stops. Either upstream moved or the script is non-deterministic. Re-pin only with user approval and record the re-baseline date in `SOURCES.md`.
- **`ose-eval-gate` exit 2:** the stderr message names the input defect (dirty tree, stale version label, missing set, resized set, sealed set read in an iteration, bootstrap without predictions). Fix it and re-measure.
- **Steps 1–7 are local and reversible:** discard the worktree. **Step 8's push** is the only remote mutation, and the mandatory confirmation is its gate.

## What this recipe deliberately does not do

- It does not write detector rules itself. Each hypothesis goes to the developer through `/osEngineer:feature` or `/osEngineer:fix`.
- It does not change set roles or thresholds after step 3 without user approval and judge review.
- It does not commit labeled data, build artifacts or experiments to report branches.
- It does not delete or archive old report branches. It proposes that at the process review, and the owner decides.
- It does not release the detector. Use `/osEngineer:recipe-cut-release`.
