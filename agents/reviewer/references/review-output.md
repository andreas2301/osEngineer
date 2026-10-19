# Review Output

```markdown
# Review — PR #NNN

## Approval Status
CHANGES_REQUESTED (1 must fix)

## Findings

### Must Fix (1)
1. **Where:** `internal/publish/publish.go:58`. **What fails:** a publish error is logged and dropped, so the plan counts as sent. **Failing case:** broker down during publish → caller gets nil, the plan is lost. **Fix:** return the error and let the caller retry.

### Should Fix (0)
(None)

### Nits (1)
2. **Where:** `cmd/strategist/main.go:471`. **What fails:** the log names `:9091` while the server listens on `cfg.MetricsAddr`. **Failing case:** `MetricsAddr=:9200` → the log points operators at the wrong port. **Fix:** log `cfg.MetricsAddr`.

## Not checked
- Load behaviour of the new retry path; no benchmark was run.

## Coverage
- Before: 78%
- After: 81%
- Delta: +3% ✅
```
