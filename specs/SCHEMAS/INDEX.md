# specs/SCHEMAS/ INDEX

- contract-schema.json — Meta-schema for message contracts
- service-manifest-schema.json — Meta-schema for service manifests
- eval-policy.schema.json — Evaluation-harness decision rules (set roles, gates, loop cadence); read by `bin/ose-eval-gate`
- repo-profile.schema.json — `.osengineer/profile.json` (policy, plan dir, context thresholds, routing, codexRunner, fact→handler map); enforced by `repo_profile/config.py`
