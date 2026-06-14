# Severity Levels

| Level | Action | Examples |
|-------|--------|----------|
| **CRITICAL** | BLOCK merge | Hardcoded secret, `InsecureSkipVerify`, shell injection |
| **HIGH** | Must fix before merge | Missing error handling, unbounded retry |
| **MEDIUM** | Should fix (human decides) | Missing metric, log leak |
| **LOW** | Nit (reviewer handles) | Style inconsistency |
