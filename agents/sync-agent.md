# Sync Agent (Optional)

**Role:** Manages live system ↔ workbench synchronization.  
**Trigger:** `/osEngineer:init`, explicit call, or daemon scheduled check.  
**Output:** `SYNC_STATUS.md`.

---

## Mandate

You are the sync agent in osEngineer. The live system (`/opt/sovereign-shield`) and the workbench can diverge. You detect and reconcile.

## Detection Protocol

### 1. Live System Drift

```bash
cd /opt/sovereign-shield/ola-management-strategist
git status --short
git log --oneline -5
```

If uncommitted changes exist → flag as `live-dirty`.

### 2. Workbench Lag

```bash
cd /home/engineer/.zeroclaw/workspace/workbench/ola-management-strategist
git log --oneline HEAD..origin/master | wc -l
```

If behind origin → flag as `workbench-behind`.

### 3. Cross-Repo Consistency

Check if the same commit exists in both live and workbench:
```bash
live_hash=$(cd /opt/sovereign-shield/ola-management-strategist && git rev-parse HEAD)
wb_hash=$(cd /home/engineer/.zeroclaw/workspace/workbench/ola-management-strategist && git rev-parse HEAD)
[ "$live_hash" = "$wb_hash" ] && echo "synced" || echo "diverged"
```

## Sync Actions

| Scenario | Action |
|----------|--------|
| Workbench behind origin | `git pull --ff-only` in workbench |
| Live has uncommitted changes | Write `LIVE_DIRTY.md`, recommend cherry-pick to workbench |
| Live ahead of workbench | Cherry-pick live commits into workbench branch |
| Workbench ahead of live | Normal flow — PR merges update both on next deploy |

## Sovereign Shield Protocol

Per `WORKBENCH.md`: "Fixes must be authored here [workbench] and submitted via Pull Requests."

**Exception:** Hotfixes on live must be backported to workbench within 24h.
