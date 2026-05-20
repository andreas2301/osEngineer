# Pattern: dual-listen-migration

**Source:** Observer Shield (AMQP routing-key migrations)
**Promoted to pattern library:** 2026-05-20
**Owning team:** coding + infra

## The rule

When migrating an AMQP routing key from `old.key` to `new.key`, the consumer
ships a release that listens to **both** keys for at least one deploy cycle
before the producer cuts over.

```
Release N    — consumer listens to: old.key  (baseline)
Release N+1  — consumer listens to: old.key + new.key   ← DUAL LISTEN
Release N+2  — producer switches to publishing on: new.key
Release N+3  — consumer listens to: new.key only   ← old binding removed
```

## Why

- AMQP doesn't support atomic switchover of bindings across services.
- If the consumer is updated *after* the producer cuts over, messages on
  `new.key` queue up unacknowledged (or worse, dead-letter) for the
  duration of the deploy window.
- If the producer is updated *after* the consumer drops `old.key`, the
  reverse happens — producer's messages get black-holed.
- Dual-listen creates an overlap window where neither order causes loss.

## How to apply

- Each migration spans **at least 3 deploy cycles** end-to-end.
- The dual-listen release MUST be live in production for at least 24h
  before the producer cuts over (allows observability + rollback).
- The consumer's `QueueBind` calls declare both bindings explicitly.
- The producer change is the smallest possible commit — flip the routing
  key in one place.
- The consumer's old-binding-removal release CAN go faster (no
  observation window needed) once `old.key` traffic is verifiably zero
  in metrics.

## Related ADRs

- ADR-014 — AMQP topology declaration ownership
- ADR-018 — Message contract versioning (any payload change also
  bumps `version` in the message-contract.yaml)
