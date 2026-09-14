# Jira: REST in CI, MCP on the workstation

osEngineer talks to Jira two different ways, because the two contexts have
different capabilities.

| Context | Transport | Why |
|---|---|---|
| Interactive session | Atlassian MCP (`integrations/confluence-mcp.md`) | The harness already holds the connection; the agent can explore issues conversationally. |
| Headless run / CI | `bin/ose-jira` over REST | CI has no MCP server. A run that cannot report back to a ticket is not a pipeline. |

## Why the client is deliberately tiny

Two verbs only — `comment` and `transition`. Everything else an agent might
want to do with Jira it can do interactively, where a human is watching. The
headless path exists to *report*, not to administer.

```bash
ose-jira comment PROJ-123 "phase complete" --corr run-20260914T120000Z
ose-jira transition PROJ-123 "In Review"
```

## Credentials

Environment only — `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_TOKEN`. Never flags:
a token passed as argv is visible in the process table and is echoed into CI
logs by most runners. The client refuses to start if any are missing rather
than failing later against a 401.

## Idempotency

CI jobs get retried. Jira returns comments oldest-first and paginates, so a
duplicate check that reads only the first page silently re-comments on any
ticket with more than a page of history — exactly the long-running tickets
where the noise is worst. `find_corr_comment` pages to the end looking for
`osengineer:corr=<id>`, and `--corr` is what makes a retry a no-op.

## Ingress

Inbound triggering is GitHub-only in v1: `workflow_dispatch` and
`repository_dispatch`, validated against
`specs/SCHEMAS/dispatch-payload.schema.json`.

Jira Cloud automation cannot compute an HMAC, so a signed webhook is
unbuildable by its own stated producer; and pointing a Jira rule straight at
GitHub with a PAT puts a repo write credential inside a rule any project admin
can read. A real signing gateway becomes worth building when there is a second
non-GitHub producer — not before.

## Payload text is untrusted

Ticket summaries, descriptions and comments are written by people outside this
repo. They are prompt text: never interpolated into a workflow `run:` body,
never passed to a shell, and length-capped by the schema.
