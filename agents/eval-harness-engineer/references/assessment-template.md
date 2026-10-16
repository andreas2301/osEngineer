# Premortem and honest-assessment template

## Premortem (every iteration, short)

Ask: "This change landed and the detector still failed in production. What most likely broke?" Name the top 3 risks, choosing from false positives on a content type, latency, missing variants (paraphrase, encoding, language), and dataset artifacts. Then name the measurement that would show each one.

## Honest assessment (`docs/ASSESSMENT.md`, when gains flatten or before a strategy decision)

Number every claim and attach a source tag that points to a metrics file, the policy, or your own probes.

1. **Verdict.** Three to five numbered sentences: what it catches, what it misses, whether it can block or only flag.
2. **What it catches and misses.** A per-family table with dev recall, **holdout recall**, holdout FP rate, P and F1. Add a fresh probe table: inputs never seen by the rule designers, including benign hard cases.
3. **Progress and the overfitting caveat.** Show the first baseline next to the current version. Include the dev versus holdout gain per set, the holdout reuse count, and the sealed-set number if one exists.
4. **Premortem, one year out.** For each failure mode, give likelihood, impact and evidence. Add **base-rate math** at realistic prevalence (1 in 1,000 and 1 in 10,000): true hits, false alerts, precision, alerts per real hit.
5. **Value added.** What it is worth deploying for, what it must not be relied on for, and alternatives with their published numbers. Label vendor claims as vendor claims, and check every citation against the primary source.
6. **Placement.** Where it sits in defense in depth, the build versus buy trade-off, and the cost of maintaining it.
7. **Ranked next steps.** Sealed set and tighter gates first if the holdout has been reused. Then robustness sets, a model-based alternative spike, and latency.
