---
scope: team
schema_version: 1
team_id: testing
parent_repo: ../
agents: [qa]
owns_paths: ["**/*_test.go", "**/test_*.py", "tests/**", "test/**", "integration/**", "e2e/**"]
reads_paths: ["internal/**", "cmd/**", "pkg/**", "src/**", "api/**", "contracts/**"]
---

# Testing team

Owns test code and coverage strategy. Frequently uses glob-only paths
(e.g. `**/*_test.go` co-located with Go production code) rather than a
single canonical folder. Reads production code freely; never edits it.

## Members

- **qa** — test strategy, edge-case analysis, load and integration testing

## Escalates to

- **coding** — when a production-code change is required to make a test passable
  (e.g. a function needs to expose `context.Context` for a test to cancel cleanly)
- **infra** — when integration tests need new docker-compose services or fixtures
- **security** — when fuzz/property tests surface a vulnerability class

## Hard rules in this team

- Tests live next to (or under) the code they verify; no centralised mega-test-folder
  unless the repo explicitly chooses that layout.
- Mocks of database / broker / vault are FORBIDDEN in integration tests for Observer
  Shield (see memory: "don't mock the database — incident pattern"). Use `dockertest`.
- Coverage drops below 80% → automatic activation as an optional agent triggers.
- Test files containing `// TODO: write me` or `t.Skip("...")` without a tracking
  ticket comment are flagged on review.
