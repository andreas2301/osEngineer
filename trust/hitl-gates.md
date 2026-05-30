# Human-in-the-Loop (HITL) Gates

**Purpose:** Humans gate AI work at critical decision points.

---

## Mandatory HITL Gates

| Gate | Trigger | Human Action |
|------|---------|--------------|
| **Plan confirmation** | `PHASE_PLAN.md` generated | Confirm scope, budget, and risk flags before execution |
| **ADR creation** | New cross-cutting decision | Review and approve ADR draft |
| **Override** | Judge blocks, but urgency requires merge | Write `OVERRIDE.md` with risk acceptance |
| **Merge** | All automated gates pass | Final PR review and merge |

## Optional HITL Gates

| Gate | Trigger | Human Action |
|------|---------|--------------|
| **Token budget extension** | Circuit breaker trips | Approve additional tokens or redirect |
| **Scope expansion** | >20% scope creep detected | Approve new scope or split into new phase |
| **Security exception** | Red-team HIGH finding with business justification | Approve exception with mitigation plan |

## HITL Bypass Rules

Some gates can be bypassed under specific conditions:

- **Hotfix + outage:** Plan confirmation can be verbal/slack; document retroactively.
- **Revert:** Reverting a bad merge does NOT require full planning cycle.
- **Docs-only:** ADR amendments that are purely editorial (no decision change) skip HITL.

## Project-Specific Conventions

- **Production deploy:** Always requires human approval (ansible-playbook --check first).
- **Vault policy changes:** Always requires human approval (security-critical).
- **TLS cert rotation:** Human approves schedule; agent executes.
