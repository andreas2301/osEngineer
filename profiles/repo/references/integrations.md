# Task-scoped integrations

GitHub and Linear own delivery state; Notion owns product context; repository code/docs own technical behavior. Query only the source needed for the current task. Do not synchronize or update trackers as a side effect of a read.

Run `python3 scripts/repo_profile.py integrations doctor --config integrations.json` from the installed skill to inspect capabilities without network. `preflight --provider github` (or linear/notion) performs the explicitly selected provider read. Configure project, repository or page scopes first; missing credentials return unknown/needs-human, never an empty successful survey. Outputs label their text as bounded summaries; complete describes enumerated scope coverage, never full page or issue content. Readers are read-only; mutations remain governed by the repository's own tracking or delivery skill.

The registry includes GitHub (`gh`), Linear GraphQL, Notion REST and a secrets process-injection capability. Optional browser, tracker, docs, observability, hosting and database entries are generic category placeholders for task-specific capabilities, not promises of implemented readers. The doctor reports unsupported/unconfigured capabilities honestly. Prefer the existing local browser tools for interactive acceptance and repository Playwright tests for CI.

Secrets belong to the process launcher: authenticate the secret manager locally, or provision a restricted service account on a trusted pipeline runner. Use `op run --env-file <reference-only-file> -- <approved-command>` to inject only needed credentials. The reader does not search secret stores, print secrets or execute `op read`. Do not expose credential-bearing environment to untrusted tools; launcher injection is not a security sandbox.

Linear supports a read-only endpoint at `https://mcp.linear.app/mcp/readonly`; local OAuth and headless bearer credentials are separate provisioning decisions. Notion hosted MCP uses OAuth; a team-owned API integration with explicitly shared pages is appropriate for bounded pipeline reads. A Desktop plugin connection is not automatically a CI credential. GitHub/Linear/Notion account setup requires the account owner; this package installs no accounts or remote applications.

Sources: https://linear.app/docs/mcp ; https://developers.notion.com/guides/mcp/overview ; https://developers.notion.com/guides/get-started/authorization . Version-pin optional MCP packages in your launcher; do not add all providers to every task's tool list.
