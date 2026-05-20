# Memory Persistence Protocol

Adapted from [AgentMemory](https://github.com/rohitg00/agentmemory).  
**Purpose:** Survive across sessions. Reconstruct context cold.

---

## Session Recovery

When osEngineer starts a new session:

1. **Read last phase:** `planning/active/` — what was in progress?
2. **Read verification:** `planning/completed/` — what was recently delivered?
3. **Read retrospectives:** `memory/retrospectives/` — what broke last time?
4. **Read patterns:** `memory/patterns/` — what reusable solutions exist?
5. **Read repo state:** `git status` in affected repos.

## Cold Start Reconstruction

If NO previous session data exists:

1. Run `/osEngineer:init` on the project.
2. Build `RESEARCH.md` from scratch.
3. Ask human: "What phase should I work on?"

## Persistent Artifacts

| Artifact | Location | Lifetime |
|----------|----------|----------|
| Active phases | `planning/active/` | Until accepted |
| Completed phases | `planning/completed/` | Permanent |
| Retrospectives | `memory/retrospectives/` | Permanent |
| Patterns | `memory/patterns/` | Evolving |
| Repo map | `RESEARCH.md` | Refreshed per init |
| Graph | `graphify-out/` | Refreshed per build |

## Cross-Session Context

What to carry between sessions:
- ✅ Active phase ID and current task.
- ✅ Repo map and ADR catalog.
- ✅ Verified patterns.
- ✅ Open questions / blocked items.
- ❌ Full code context (re-read via graphify/grep).
- ❌ Token-by-token reasoning (re-derive).
