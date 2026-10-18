# Evaluation harness — lessons-learned checklist

Generic lessons for any detector, classifier or scanner improved by a
keep/revert loop. They come from a rule-based text detector run for 42
autoresearch iterations over five rounds; set names below describe the set's
role, not a particular dataset. Each item names what went wrong, the evidence,
and the check that prevents it. `/osEngineer:recipe-eval-harness`
and the `eval-harness-engineer` agent walk this list at setup and at every
process review. Gates marked **(gate)** are enforced by `bin/ose-eval-gate`
when the policy enables them; the rest are process checks.

Citations were checked against arXiv on 2026-10-16.

## Domain-specific eval sets

osEngineer ships no domain eval content. The consuming repo supplies it: an
`EVAL_POLICY.json` (shape: `specs/SCHEMAS/eval-policy.schema.json`) that names
its sets and roles, the labeled cases, and an eval command that writes the
metrics JSON. `bin/ose-eval-gate` only reads those files. The fixtures in
`test/fixtures/eval-gate/` use placeholder set names and exist to test the gate.

## Data and splits

- [ ] **Holdout reuse leaks.** About 40 accept/revert decisions each read every
  holdout set, so the holdout numbers drifted optimistic over time. This is
  adaptive data analysis: every decision leaks holdout information into the
  detector (Dwork, Feldman, Hardt, Pitassi, Reingold, Roth 2015, *Generalization
  in Adaptive Data Analysis and Holdout Reuse*, arXiv:1506.02629; Blum & Hardt
  2015, *The Ladder: A Reliable Leaderboard for Machine Learning Competitions*,
  arXiv:1502.04585).
  **Check:** keep a SEALED set read only at round or release boundaries, at most
  `max_evaluations_per_release` times **(gate)**. Report the sealed number as the
  honest one.
- [ ] **Never design from holdout, GUARD-ONLY, REPORT-ONLY or SEALED errors.**
  Only PRIMARY and RECALL-ONLY **dev** FP/FN files are hypothesis sources. The
  eval script writes FP/FN files for every set; restrict who reads them, not
  what is written.
- [ ] **Template-dominated sets are GUARD-ONLY.** In one synthetic set, 98.4 %
  of positives used one of two fixed wrappers, so one rule per wrapper moved
  recall without generalizing.
  **Check:** at intake, count the top-k prefixes and suffixes of the positives.
  If a few templates dominate, the set may only guard against regressions.
- [ ] **Small sets overfit fast.** A single-language subset had 52 dev
  positives. In round 4, dev F1 rose +0.43 (0.400 → 0.831) while the holdout
  rose only +0.14 (0.464 → 0.605), a ratio of 0.33.
  **Check:** generalization ratio `holdout_gain ≥ k × dev_gain` for large gains
  on small sets **(gate)**. Below about 100 positives, prefer GUARD-ONLY.
- [ ] **Contamination through translations.** Machine-translated eval sets can
  contain translations of rows in your other sets. A translation of a dev row in
  a holdout is the same sample in disguise.
  **Check:** group-split by source case, so all translations of one case land
  on one side, and run cross-set exact and normalized overlap checks in the fetch
  script. The script exits non-zero on any overlap.
- [ ] **Dataset artifacts create false positives you cannot fix honestly.** On
  a set of JSON tool outputs, 29 of 31 dev FPs came from one rule firing on JSON
  `\u` escapes, and 105 positive rows also contained them. Narrowing the rule
  cut TP 189 → 160.
  **Check:** at intake, diff the feature distributions of benign and positive
  rows (escapes, encodings, length, markup). Record known artifacts in the
  sources manifest. Do not tune a rule to an artifact.
- [ ] **Shared negatives are not an independent signal.** One holdout reused
  the dev benign rows, so only its recall is a holdout measurement. Write that
  caveat into the manifest next to the set.
- [ ] **Pin everything.** Pin the upstream revision and the sha256 of every
  input file and every output file, plus a fixed sampling seed. Licenses and
  gated status go in the manifest. Resized sets are refused by the gate.

## Decision rules

- [ ] **Per-set gates, never a summed holdout.** A round-3 loop script checked
  the holdout on summed F1. One holdout set lost 2 TP (F1 0.708 → 0.702) and
  the candidate was accepted because another holdout set rose more.
  **Check:** `ose-eval-gate` checks every set on its own **(gate)**. The fixture
  `test/fixtures/eval-gate/summed-holdout.*` reproduces this case.
- [ ] **No undocumented thresholds.** The same script rejected dev F1 gains
  below 0.01, a number that was written nowhere. Iteration 20 was reverted on
  it, then retested and accepted as iteration 21.
  **Check:** every threshold lives in the policy file. `min_dev_f1_gain`
  defaults to 0 **(gate)**. The fixture is `undocumented-threshold.*`.
- [ ] **Write precedents down as rules.** One accepted version lost one TP on a
  PRIMARY holdout set (54 → 53) while FP fell 2 → 0. That decision became the single-sample tolerance:
  at most `max_tp_loss` TP lost, precision not down, and the PRIMARY holdout F1
  sum up **(gate)**. The fixture is `single-sample-tolerance.*`.
- [ ] **Never re-implement the rules in a prompt.** Loop agents call the
  evaluator and quote its reasons. Prose copies of the rules drift.
- [ ] **Small gains need significance, not only sign.** When per-sample
  predictions exist, require the paired-bootstrap CI lower bound to be above 0
  **(gate)**.

## Loop hygiene

- [ ] **Dirty-tree races.** The loop agent, a human and other agents shared one
  working tree. In round 3, one iteration (19) was evaluated even though its
  edit was never applied to the tree. Concurrent uncommitted edits from other
  writers also raced with loop measurements.
  **Check:** run each iteration in its own worktree. Refuse candidates measured
  on a dirty tree **(gate)**. Record the commit SHA in the metrics file.
- [ ] **Stale version labels.** Measuring before the version bump labels the
  candidate's reports with the baseline's version.
  **Check:** bump first, then measure. Equal version labels are refused
  **(gate)**.
- [ ] **One change per iteration.** Combined changes cannot be attributed and
  cannot be reverted cleanly.
- [ ] **Latency creep per rule.** p95 on the slowest set rose about 1.3 ms per pattern
  in round 3 and about 2.5 ms per pattern in round 4 (48.8 → 74.3 ms against a
  100 ms budget).
  **Check:** set a latency budget and a noise band **(gate)**. Every rule needs a
  cheap prefilter. Plan a latency-only iteration when headroom falls below about
  25 %.
- [ ] **Report-branch sprawl.** One report branch per iteration produced 37 local
  and 34 remote `report-*` branches, and worktrees reached 1.2 GB.
  **Check:** one report branch per **round**. Per-iteration results go to a
  scratch directory. Archive old branches at each process review, with owner
  approval.

## Research and strategy

- [ ] **Verify cheap-model research.** Research summaries from small or fast
  models had wrong author lists and numbers that do not appear in the cited
  source.
  **Check:** before a citation or number goes into a doc, policy or decision,
  open the primary source (arXiv abstract, model card, dataset card) and confirm
  the title, authors and the exact figure. Mark anything unverified as
  unverified.
- [ ] **Know the ceiling.** Regex rounds had falling returns. Round 4 spent 10
  accepted iterations on holdout F1 gains of +0.004 and +0.061 on two sets,
  and gained 0 on the human-written stress set (recall 0.167). Cheap filters in
  front of a stronger system can be bypassed in principle and in practice; for
  one example domain see Fairoze, Garg, Lee, Wang 2025, *Bypassing Prompt Guards
  in Production with Controlled-Release Prompting*, arXiv:2510.01529.
  **Check:** at each process review, compare marginal holdout gain per iteration
  with the previous round. When it falls toward zero, pause the loop and write an
  honest assessment before changing strategy. Do not keep adding rules.
- [ ] **Keep a REPORT-ONLY adversarial set.** Use a human-written, hard-benign
  set that never gates and is never read for design. It is the least
  contaminated view of real-world performance.
- [ ] **Write the honest assessment.** Cover the verdict, what it catches and
  misses per family on the holdout, the overfitting caveats, a premortem,
  base-rate math at realistic prevalence, and alternatives. A 9 % FP rate at a
  1-in-1,000 prevalence means fewer than 1 % of alerts are real.
