# Verification

After onboarding:

1. `go test ./internal/metrics/` passes.
2. `go build ./...` compiles.
3. `wget -qO- http://localhost:<port>/metrics | grep <service_name>_` returns metrics.
