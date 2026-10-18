# Metrics JSON (input to `bin/ose-eval-gate`)

The repo's eval command (or a small adapter) writes one file per measured version:

```json
{
  "version": "0.3.45",
  "git": { "commit": "703834c", "dirty": false },
  "change_kind": "detection",
  "evaluation": "iteration",
  "sealed_evaluations": 0,
  "errors": 0,
  "corpus_findings": 11015,
  "sets": {
    "llmail":         { "tp": 240, "fp": 0,  "tn": 160, "fn": 60,  "p95_ms": 12.1 },
    "llmail-holdout": { "tp": 216, "fp": 0,  "tn": 160, "fn": 84,  "p95_ms": 12.5 },
    "browsesafe":     { "tp": 199, "fp": 26, "tn": 274, "fn": 101, "p95_ms": 44.1,
                        "predictions": [ { "id": "bs-0001", "label": 1, "pred": 1 } ] }
  }
}
```

| Field | Meaning |
|---|---|
| `version` | The version label of the build measured. Bump **before** measuring. Equal labels are refused. |
| `git.dirty` | `true` refuses the candidate (when `require_clean_tree`). |
| `change_kind` | `detection`, `latency` or `security-hardening`. `security-hardening` may be accepted without a metric gain if nothing regresses. |
| `evaluation` | `iteration`, `round` or `release`. SEALED sets are refused in `iteration`. |
| `sealed_evaluations` | How many times the sealed set has been read this release, including this one. |
| `errors` | Scanner or eval errors. Any increase reverts. |
| `corpus_findings` | Optional unlabeled-corpus count. A drop without a labeled FP reduction reverts. |
| `sets.<name>` | Raw counts (`tp`, `fp`, `tn`, `fn`). The gate computes P/R/F1 itself, so rounding never decides. Set sizes must match between baseline and candidate. |
| `sets.<name>.<latency metric>` | Defaults to `p95_ms` (policy `gates.latency.metric`). |
| `sets.<name>.predictions` | Per-sample `{id, label, pred}`, needed for the paired bootstrap. Must tally to the counts. |

Exit codes: `0` ACCEPT, `1` REVERT, `2` input error (message on stderr). Use `--json` for a machine-readable verdict that lists the reasons and the per-set metrics.
