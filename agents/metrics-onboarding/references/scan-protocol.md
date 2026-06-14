# Scan Protocol

For each repo in scope:

1. **Check for metrics package:**
   ```bash
   ls internal/metrics/ 2>/dev/null || echo "NO_METRICS"
   ```

2. **Check for `/metrics` endpoint:**
   ```bash
   grep -rn "promhttp\|/metrics" cmd/ internal/api/ 2>/dev/null | head -5
   ```

3. **Check existing metric pattern:**
   - `promauto` → modern, correct
   - `init() + MustRegister` → legacy, refactor to promauto
   - No metrics at all → generate from scratch

4. **Check for tests:**
   ```bash
   ls internal/metrics/*_test.go 2>/dev/null || echo "NO_TESTS"
   ```
