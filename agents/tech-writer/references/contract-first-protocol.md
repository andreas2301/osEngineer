# Contract-First Protocol

When a task touches a contract surface (API, AMQP message, JSON schema, database schema):

1. **Check existing contract:** Does the contract already exist?
   - YES → Does the change break it? If yes, draft ADR amendment.
   - NO → Write the contract FIRST.

2. **Write contract:**
   - AMQP messages: `.claude/contracts/produced/` or `consumed/`
   - HTTP APIs: OpenAPI spec in `docs/openapi/`
   - JSON schemas: `internal/schema/files/*.json`
   - DB schemas: `migrations/sql/V*.sql`

3. **Validate contract:**
   - JSON Schema validates against JSON Schema 2020-12 meta-schema.
   - OpenAPI passes spectral lint.
   - SQL migration is idempotent (rerunnable).

4. **Block developer until contract is approved:**
   - Developer agent MUST check for contract existence before coding.
   - If absent, developer stops and routes to tech-writer.
