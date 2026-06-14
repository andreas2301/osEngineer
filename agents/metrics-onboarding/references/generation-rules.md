# Generation Rules

## If no metrics exist:

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

## If legacy `init() + MustRegister` exists:

Refactor to `promauto`. Update tests to use `testutil`.

## Wire `/metrics` endpoint:

Replace stub text endpoint with:
```go
r.Get("/metrics", promhttp.Handler().ServeHTTP)
```

Add `_ "module/internal/metrics"` blank import in `main.go` for init-time registration.
