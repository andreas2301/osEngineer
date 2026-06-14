# Run the tracer-bullet & Dynamic Mission Sandboxing

If the phase involves a cross-service or multi-repo flow (such as AMQP microservices, Vault credential fetching, or distributed databases):

- **Dynamic Mission Sandboxing:** Spin up an isolated local containerized sandbox by executing `/osEngineer:sandbox start <mission-plan-path> --clean` to test the mission end-to-end.
- **Verification Metrics:** Scrape metrics, audit container logs for panics or timeouts, verify Vault unsealing, and ensure all assertions pass.
- **Tracer Evidence:** Capture the compiled `MISSION_TEST_REPORT.md` and attach the latency profiles, Vault clearance lists, and log snippets directly to `VERIFICATION.md` as concrete evidence.

If no cross-service flow applies, verify local unit tests, document why the sandbox wasn't required, and skip.
