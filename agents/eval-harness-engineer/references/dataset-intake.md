# Dataset intake checklist

Fill one block per candidate set in `testdata/eval/SOURCES.md` (or the repo's equivalent). A set that cannot answer every line is not admitted. It may be admitted as REPORT-ONLY with the gap written down.

## Provenance

- [ ] **URL** of the dataset card or repository.
- [ ] **Pinned revision**: a commit SHA, never `main` or `latest`.
- [ ] **File list with sha256 and byte size** for every downloaded file. The fetch script verifies them and exits non-zero on mismatch.
- [ ] **License**, read from the license file or card at that revision, not from a summary. Record per-row licenses when the set is mixed. Drop rows whose license does not allow your use.
- [ ] **Gated?** Gated sets (click-through, token) cannot run in CI without credentials. Prefer ungated mirrors at a pinned revision, or document the gate.
- [ ] **Verified by you**: title, authors and any figure you quote, from the primary source. Research handed over by another agent is a lead, not a fact.

## Content

- [ ] **Benign negatives present?** A positives-only set can only be RECALL-ONLY. Shared or reused negatives (the same benign rows in dev and holdout) make holdout precision non-independent. Write that down.
- [ ] **Label semantics** mapped to your label (1 = detect). Drop ambiguous labels (`Unclear`) rather than guess.
- [ ] **Label noise estimate**: sample about 50 rows by hand. If about 10 % of positives are not really positive, recall has a ceiling. Record it.
- [ ] **Template dominance**: count the top-k prefixes and suffixes of the positives. If a few templates cover most of them, the set can only be GUARD-ONLY.
- [ ] **Artifacts**: compare benign and positive rows on escapes (`\u`), encodings, length, markup and language. Any feature that separates the classes without being the concept is an artifact. Record it, and never tune a rule to it.
- [ ] **Synthetic or machine-translated?** Say so. Translations of other eval rows are contamination (see below).

## Splitting and contamination

- [ ] **Group split**: all variants of one source case (translations, paraphrases, the same injection string in different hosts) land on one side. Group by the upstream case id or by a normalized-text key.
- [ ] **Cross-set overlap check** in the fetch script: exact and normalized (lowercased, whitespace-collapsed) text, plus any shared payload field. Check dev vs holdout vs sealed, and every new set vs every existing one. Exit non-zero on overlap.
- [ ] **Deduplicate within pools** (keep first occurrence) before sampling.
- [ ] **Deterministic sampling**: a fixed seed, sorted inputs before sampling, and a documented allocation (stratified, largest remainder). Two runs must produce byte-identical outputs, with output sha256s recorded in the manifest.
- [ ] **Size**: fewer than about 100 positives is too small to drive design. Use GUARD-ONLY, or enable the generalization gate for it.
