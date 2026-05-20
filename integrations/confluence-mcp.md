# Confluence (and Jira) MCP integration

Observer Shield uses Atlassian Cloud at `observershield.atlassian.net` with
- **Jira project key:** `OSP` (Observer Shield Platform)
- **Confluence space:** `OSP`
- **CloudId:** stored in `.claude/mcp/atlassian-cloudid` per workbench
- **Auth scope:** delegated agent OAuth via the official Atlassian MCP server
- **Canonical dashboard page:** OS-MDashboard (per Phase D decisions)
- **Canonical decision feed:** Vigil (per Phase D decisions)

This file describes how osEngineer wires the Atlassian MCP server so that
Claude Code agents can read Jira tickets, post Jira comments, read
Confluence pages, and create Confluence inline/footer comments without
manual context-copy.

---

## When to load this MCP

Load this MCP when ANY of the following are true:

- The user is starting work on a Jira ticket (`OSP-N` referenced in the prompt).
- The active phase's `PHASE_PLAN.md` cites a Confluence page ID in its
  `references:` section.
- The repo's `CLAUDE.md` declares `confluence_page_id: "NNN"`.
- The user runs `/osEngineer:fix OSP-N` or `/osEngineer:feature OSP-N`.

The architect agent decides whether to load this MCP for a given prompt.
It is NOT loaded by default — Atlassian MCP responses can be large; loading
it eagerly burns context.

---

## Wiring

The Atlassian MCP server is provided by Atlassian. osEngineer does not ship
the server — it ships the **configuration** that points at the right cloud
and the **protocol** that agents follow when calling it.

### Workbench-level config

Stored at `<workbench>/.claude/mcp/atlassian.json`:

```json
{
  "mcpServers": {
    "atlassian": {
      "command": "npx",
      "args": ["-y", "@atlassian/mcp-server-atlassian"],
      "env": {
        "ATLASSIAN_CLOUD_ID": "<cloudId>",
        "ATLASSIAN_SITE_URL": "https://observershield.atlassian.net",
        "ATLASSIAN_PROJECT_KEYS": "OSP",
        "ATLASSIAN_SPACE_KEYS": "OSP"
      }
    }
  }
}
```

The `ATLASSIAN_CLOUD_ID` is sensitive (identifies the tenant) but is NOT
a secret — it's discoverable via `getAccessibleAtlassianResources` after
auth. Keep it in `.claude/mcp/` (gitignored from public sharing per
workbench `.gitignore`).

### Auth

Atlassian MCP uses delegated OAuth. The user runs:

```bash
claude mcp authenticate atlassian
```

once per workbench. Token refresh is automatic. Tokens are stored under
`~/.claude/mcp-tokens/atlassian.json`.

---

## What agents do with the MCP

### researcher agent

When loading a Jira ticket, the researcher agent calls:

```
mcp__atlassian__getJiraIssue
mcp__atlassian__getJiraIssueRemoteIssueLinks
mcp__atlassian__getTransitionsForJiraIssue
```

and writes a one-paragraph summary into `planning/active/<phase>/RESEARCH.md`
under a `## Ticket OSP-N` heading. The summary includes: title, type,
status, assignee, links to related Confluence pages, and the most recent
3 comments by timestamp.

### tech-writer agent

When authoring or amending an ADR that needs to be reflected in Confluence,
the tech-writer agent calls:

```
mcp__atlassian__getConfluencePage             # read the existing ADR page
mcp__atlassian__updateConfluencePage          # publish the new revision
mcp__atlassian__createConfluenceFooterComment # log the amendment summary
```

The ADR Markdown file remains the source of truth; the Confluence page is
a derived publication. Both must be updated within the same PHASE; the
red-team-architect verifies parity on PR.

### live-system-operator agent

When an incident is in progress, the live-system-operator agent posts
status updates to the OSP Vigil page:

```
mcp__atlassian__createConfluenceInlineComment   # post to the incident timeline
mcp__atlassian__addCommentToJiraIssue           # post the same to the OSP ticket
```

Vigil is the canonical incident feed (Phase D decision 2026-04-27).

### judge agent

On merge gate, the judge agent transitions the Jira ticket:

```
mcp__atlassian__getTransitionsForJiraIssue
mcp__atlassian__transitionJiraIssue              # to "Done" or "In Review"
mcp__atlassian__addCommentToJiraIssue            # with the PR URL
```

---

## Caching protocol

To avoid re-fetching pages every prompt, the architect agent caches
Confluence pages in `<workbench>/.osengineer/confluence-cache/<page-id>.md`
with a frontmatter block:

```yaml
---
page_id: "884813"
fetched_at: 2026-05-20T14:32:00Z
ttl_seconds: 3600
etag: "..."
---
```

Cache entries older than `ttl_seconds` (default 1h) are re-fetched.
Pages cited in PHASE_PLAN.md `references:` are pre-warmed on phase load.

---

## Hard rules

- **Never paste secrets into Jira / Confluence.** The agent does not have
  access to Vault material from MCP responses; if a ticket body contains a
  secret-looking blob, redact before quoting in any artifact.
- **Workbench-level posting only.** The osEngineer skill repo itself does
  not post to Jira/Confluence — only target repos (where OSP work happens)
  may post.
- **All Confluence updates pair with a Markdown ADR.** The Markdown is the
  source of truth; Confluence is the publication. Drift is a red-team-architect
  blocker on PR.
- **Vigil is the canonical decision feed; OS-MDashboard is the canonical
  observability page.** Other Confluence pages may exist but agents prefer
  these two for the canonical write paths (Phase D decision 2026-04-27).

---

## Custom Jira fields (per Phase D 2026-04-27)

The OSP project has three custom fields agents should populate when
creating issues:

| Field | Purpose | Default |
|---|---|---|
| `osengineer_phase` | `phase-NNN-<slug>` linking the ticket back to its phase plan | inferred from current phase if active |
| `affected_team` | Which osEngineer team owns the work (`coding`/`testing`/`infra`/`docs`/`security`) | inferred from current_team in state.yml |
| `verification_evidence` | Link to VERIFICATION.md after the phase enters `verify` | populated by verifier agent |

The `mcp__atlassian__createJiraIssue` call should include these in the
`fields:` payload.

---

## Tool index (Atlassian MCP — for reference)

The agents listed above use these MCP tools. See the Atlassian MCP docs
for full schemas:

- `getJiraIssue`, `getJiraIssueRemoteIssueLinks`, `editJiraIssue`,
  `createJiraIssue`, `transitionJiraIssue`, `addCommentToJiraIssue`,
  `addWorklogToJiraIssue`, `searchJiraIssuesUsingJql`,
  `getTransitionsForJiraIssue`, `getVisibleJiraProjects`,
  `getJiraIssueTypeMetaWithFields`, `getJiraProjectIssueTypesMetadata`,
  `lookupJiraAccountId`, `createIssueLink`, `getIssueLinkTypes`.
- `getConfluencePage`, `getConfluencePageDescendants`,
  `getPagesInConfluenceSpace`, `getConfluenceSpaces`, `getConfluencePageFooterComments`,
  `getConfluencePageInlineComments`, `getConfluenceCommentChildren`,
  `createConfluencePage`, `updateConfluencePage`,
  `createConfluenceFooterComment`, `createConfluenceInlineComment`,
  `searchConfluenceUsingCql`.
- `getAccessibleAtlassianResources`, `atlassianUserInfo`, `fetch`, `search`.
