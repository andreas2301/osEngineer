# Pattern: queue-declare-before-consume

**Source:** Observer Shield (Go services using `streadway/amqp`)
**Promoted to pattern library:** 2026-05-20
**Owning team:** coding

## The rule

Always declare an AMQP queue idempotently *before* calling `Consume()` on it.

```go
// Wrong — Consume can hang forever or fail silently if the queue is missing
_, err := ch.Consume("q.strategist.inbound", "", false, false, false, false, nil)

// Right — declare with the same args every service uses, then consume
_, err := ch.QueueDeclare(
    "q.strategist.inbound",
    true,  // durable
    false, // autoDelete
    false, // exclusive
    false, // noWait
    nil,   // args
)
if err != nil { return fmt.Errorf("queue declare: %w", err) }
_, err = ch.Consume(...)
```

## Why

- Order of service startup is not guaranteed. The producer may declare the
  exchange but not the consumer's queue. If the consumer doesn't declare its
  own queue first, `Consume()` returns "no such queue" — usually silently
  in `streadway/amqp` if the channel-close handler is swallowed.
- AMQP queue declaration is idempotent when arguments match. Declaring on
  startup is cheap and ensures the topology exists from the consumer side.
- This pattern surfaced after a real Observer Shield incident: the
  install-guide declared the topology but a service redeployment lost its
  declarations, causing 100% non-functional consumption that no test
  caught.

## How to apply

- Every service that consumes from an AMQP queue **owns** that queue's
  declaration.
- Declaration args MUST match the install-guide ansible task that ALSO
  declares it; mismatched args cause a hard PRECONDITION_FAILED error
  visible immediately.
- Place declaration in the same init function that opens the channel,
  before the consumer loop starts.
- Test with `dockertest` — bring up RabbitMQ, start the service, verify
  the queue exists via the management API.

## Related ADRs

- ADR-014 — AMQP topology declaration ownership
- See also memory: "Install-guide ahead of services" (Observer Shield pre-push rule)
