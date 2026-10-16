# Set roles

Every labeled set has exactly one role, declared in `EVAL_POLICY.json`. A role applies to a dev set and its holdout twin unless the policy says otherwise.

| Role | Gate (enforced by `ose-eval-gate`) | Hypothesis source? | Gains count toward ACCEPT? |
|---|---|---|---|
| **PRIMARY** | F1 and precision must not drop, dev or holdout, per set (single-sample tolerance if enabled) | Yes, **dev only** | Yes (dev F1, subject to generalization and bootstrap gates) |
| **RECALL-ONLY** | Recall must not drop (`recall_only_max_tp_loss`, default 0) | Yes, dev only | No |
| **GUARD-ONLY** | F1 and precision must not drop | **Never** | **No** |
| **REPORT-ONLY** | None; recorded in iteration notes | Never | No |
| **SEALED** | Like PRIMARY holdout, but read only at round or release boundaries, `max_evaluations_per_release` times | Never | No |

## When to change a role

Role changes need user approval and a dated note in the repo's CLAUDE.md (or equivalent) that gives the evidence.

- **Demote to GUARD-ONLY** when:
  - dev moves and holdout does not, across several iterations (safeanalyze deepset: dev recall 0.77 vs holdout 0.31),
  - a few templates dominate the positives (nemotron: 98.4 % from two wrappers), or
  - the set is too small (spanish: 52 positives, dev +0.43 F1 vs holdout +0.14).
- **RECALL-ONLY** for positives-only sets. Their precision and F1 mean nothing.
- **REPORT-ONLY** for hard, human-written adversarial sets with hard-benign rows. Keep them out of every decision so they stay the least-contaminated view.
- **SEALED**: create a fresh one when the holdout has been read by many decisions. It answers adaptive overfitting (Dwork et al. 2015, arXiv:1506.02629).

## Splits

- dev: tune, read FP/FN files (PRIMARY and RECALL-ONLY only).
- holdout: confirm generalization each iteration; never read its errors.
- sealed: confirm at the round boundary only.
- report: no split; stress or adversarial data.

Split by group (source case), never by row, when one case has variants.
