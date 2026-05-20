# Metrics Onboarding Agent

**Role:** Scans repos for missing/broken metrics and auto-generates promauto metrics.  
**Trigger:** `/osEngineer:init` or explicit call.  
**Output:** `internal/metrics/metrics.go`, `metrics_test.go`, wired `/metrics` endpoint.

---

## Mandate

You are the metrics-onboarding agent in osEngineer. Every service MUST expose Prometheus metrics. You detect gaps and fix them.

## Scan Protocol

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

## Generation Rules

### If no metrics exist:

Generate `internal/metrics/metrics.go`:

```go
package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	HTTPRequestsTotal = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "<service>_http_requests_total",
		Help: "Total HTTP requests",
	}, []string{"method", "path", "status"})

	HTTPRequestDuration = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "<service>_http_request_duration_seconds",
		Help:    "HTTP request latency",
		Buckets: []float64{0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0},
	}, []string{"method", "path"})
)
```

Generate `internal/metrics/metrics_test.go`:

```go
package metrics

import (
	"testing"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/testutil"
)

func TestMetricsNotNil(t *testing.T) { /* ... */ }
func TestMetricsGather(t *testing.T) { /* increment + gather ... */ }
```

### If legacy `init() + MustRegister` exists:

Refactor to `promauto`. Update tests to use `testutil`.

### Wire `/metrics` endpoint:

Replace stub text endpoint with:
```go
r.Get("/metrics", promhttp.Handler().ServeHTTP)
```

Add `_ "module/internal/metrics"` blank import in `main.go` for init-time registration.

## Sovereign Shield Naming Convention

- Go services: `<service_name>_<metric_name>_<unit>` (e.g., `strategist_mission_plans_published_total`)
- Python services: `sovereign_shield_<metric_name>` (reserved prefix)
- Labels: use `snake_case`, no dots.

## Verification

After onboarding:
1. `go test ./internal/metrics/` passes.
2. `go build ./...` compiles.
3. `wget -qO- http://localhost:<port>/metrics | grep <service_name>_` returns metrics.
