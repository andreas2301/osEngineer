# Improve through observed usage

Keep learning under the repository's existing plan directory (`planDirectory`, default `.plans/`). The repository's own findings and rules govern durable learning. An osEngineer usage receipt is evidence, not a replacement tracker or automatic policy update.

Use `python3 scripts/repo_profile.py learn record --input <sanitized-receipt.json> --out <local-jsonl>` to capture outcome, task/profile version, checks, input/output tokens, wall time, repetitions, corrections and evidence locators. No raw transcript, hidden reasoning, credentials or full source dumps. `learn summarize <local-jsonl>` reports observed rates and cost per successful task. `learn compare <baseline.jsonl> <candidate.jsonl>` requires the same cases/models/repetitions and flags missing observations.

A defect can justify a direct code correction; a repeated decision mistake can justify a narrow skill change. Do not turn every event into another always-loaded rule. Never modify the skill during its own executing task. Review the proposed diff, reproduce the failure and compare against the repository's existing evaluation scripts before a wider rollout. The profile's deterministic fixture suite checks process behavior; it is not a substitute for measured agent pass@1/pass^k.

Local use comes first. Then run headless shadow tasks without remote effects. Only promote a bounded capability once actual checks and human approval required by the repository lifecycle support it. No automatic promotion based on fabricated or missing counts.

Each summary or comparison arm must contain one condition and profileVersion. Compare different versions in separate arms with identical task/model/repetition coverage. Schema version is the integer 1; booleans and floats are rejected.
