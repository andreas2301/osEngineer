# Pattern: fail-closed-on-tls-error

**Source:** Observer Shield (Go services with mTLS to RabbitMQ / Vault)
**Promoted to pattern library:** 2026-05-20
**Owning team:** coding + security

## The rule

Any TLS init error (cert load, CA verify, handshake) MUST log a WARN and
disable the feature. NEVER panic. NEVER set `InsecureSkipVerify: true` to
"recover."

```go
tlsCfg, err := loadTLSConfig(os.Getenv("SHIELD_TLS_CA_FILE"), ...)
if err != nil {
    log.Printf(`{"level":"warn","feature":"strategist-bridge","msg":"TLS init failed; bridge disabled","err":%q}`, err.Error())
    return // bridge stays nil; downstream nil-checks all return early
}
```

## Why

- Panic on TLS error takes down the entire service. A degraded
  feature is better than a crashed service that takes the platform
  with it.
- `InsecureSkipVerify: true` defeats the entire point of mTLS and
  is a hard rule violation. The red-team-local agent BLOCKS PRs
  that introduce it.
- Observer Shield uses fail-closed as a security principle: a feature
  that cannot prove its TLS identity is OFF, not in a degraded
  insecure-but-running state.

## How to apply

- The feature using TLS gates **all** of its operations on a non-nil
  TLS config or client struct.
- Log the failure at WARN with structured JSON so dashboards can
  surface it.
- Emit a Prometheus counter (e.g. `feature_init_errors_total{feature="x",cause="tls"}`)
  so alerting can fire.
- Cert rotation hooks may attempt to re-init the feature on a fresh
  cert; document this in the service's runbook (live-system/).

## Related ADRs

- ADR-021 — Certificate rotation policy
- ADR-024 — Fail-closed security defaults
