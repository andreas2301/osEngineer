# Log Auditing & Diagnostics Rules

If any of the following strings appear in container log streams, automatically fail the mission test run and mark the sandbox phase `BLOCKED`:

* `panic:` (Go runtime crash)
* `FATAL:` or `CRITICAL:` (Service level failure)
* `AMQP connection refused` (Broker connection error)
* `Vault token expired` or `Permission Denied` (Security token failure)
* `Prometheus scrape timeout` (Metrics connection lag)
