# Review Output

```markdown
# Review — PR #NNN

## Approval Status
CONDITIONAL_APPROVE (2 minor nits)

## Findings

### Must Fix (0)
(None)

### Should Fix (1)
- `internal/metrics/metrics.go:23` — Help string "Total count" is vague. Use "Total MissionPlan publish attempts to Supervisor".

### Nits (1)
- `cmd/strategist/main.go:471` — metrics server addr uses `cfg.MetricsAddr` but log uses hardcoded `:9091`. Use the variable.

## Coverage
- Before: 78%
- After: 81%
- Delta: +3% ✅
```
