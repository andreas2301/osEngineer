# VERIFICATION.md Template

**Phase ID:** `phase-XXX-{short-desc}`  
**Verifier:** agent name  
**Date:** YYYY-MM-DD  
**Result:** pass | fail | partial

---

## Test Results

### Unit Tests
```
Repo: repo-name-1
Command: go test ./...
Result: PASS (142/142)
Coverage: 78% → 81% (+3%)
```

### Integration Tests
```
Tracer-bullet: e2e retry with simulated network partition
Result: PASS
Evidence: logs/e2e-retry-2026-05-20.log
```

### E2E / Smoke
```
Command: docker compose up -d && ./scripts/smoke_test.sh
Result: PASS (21/21 services healthy)
```

## Acceptance Criteria Check

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| T1 | Document all retry sites | ✅ | `docs/retry-sites.md` exists |
| T3 | All tests green | ✅ | `go test` output above |
| T5 | Tracer-bullet passes | ✅ | Log file above |

## Metrics

| Metric | Planned | Actual | Delta |
|--------|---------|--------|-------|
| Total tokens | 14.5K | 16.2K | +11.7% |
| Wall-clock time | 2h | 2.5h | +25% |
| Commits | 7 | 9 | +2 (2 refactor commits added) |
| Files changed | 5 | 8 | +3 (test helpers + ansible) |

## Lessons Learned

<!-- What worked? What didn't? What pattern should we reuse? -->
- **Worked:** Graphify query found the retry sites instantly (saved ~2K tokens vs grep).
- **Didn't work:** Initial token estimate for T3 was too low; docker SDK calls are slower than expected.
- **Pattern to reuse:** "Write contract first, then test, then code" prevented 1 refactor cycle.

## Sign-off

- [ ] Developer confirms all tasks complete
- [ ] Reviewer approves PR
- [ ] Red-Team-Local scan passes
- [ ] Judge approves architectural alignment
- [ ] Human merges PR
