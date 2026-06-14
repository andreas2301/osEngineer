# Verification Protocol

For every phase entering `verify`:

## 1. Re-read the PHASE_PLAN

Open `planning/active/<phase>/PHASE_PLAN.md`. Extract:

- The phase goal (one sentence).
- The acceptance_criteria list.
- The token_budget.estimate.

DO NOT skip this step. The plan is your source of truth, not the developer's narrative.

## 2. Walk each acceptance criterion

For each item in `acceptance_criteria`:

- Reproduce the test that proves it.
- Capture the output (paste verbatim, do NOT summarise).
- Mark PASS or FAIL.

If a criterion is "covered by an existing test," verify the test EXISTS and was RUN in this session. A test that exists but wasn't run is FAIL.

## 5. Write VERIFICATION.md

Use the template at `planning/TEMPLATES/VERIFICATION.md`. Include:

- Date + phase ID + verifier signature.
- Acceptance-criteria table (one row per item; PASS/FAIL; evidence).
- Tracer-bullet outcome.
- Cost actual vs estimate.
- Lessons learned (1–3 bullets).
- Open follow-ups (if any).

## 6. Set state

If all PASS: write `osengineer state set phase verified`. The judge takes over from here.
If any FAIL: write `osengineer state set phase blocked` and record the failures in `.osengineer/BLOCKED.md`.
