# Scope Determination Protocol

## Step 1: Parse Goal

Extract keywords from the goal:

- "mission planner" → strategist, supervisor, registry
- "metrics" → all services with metrics gaps
- "AMQP topology" → strategist, supervisor, ansible
- "cert renewal" → install-guide, all services

## Step 2: Follow Dependency Graph

Use `.osengineer/workbench-config.yml` to find:

- **Direct dependencies:** Repos that import/export contracts with primary repos.
- **Indirect dependencies:** Repos that share Vault paths, networks, or broker vhosts.

## Step 3: Contract Surface Analysis

If the goal touches a contract (AMQP message, HTTP API, schema):

- Load the **producer repo**.
- Load the **consumer repo**.
- Load the **registry/repo-map** if schema is shared.

## Step 4: Prune

Remove repos that:

- Have no code changes predicted.
- Are pure observability (dashboards) unless UI is the goal.
- Are backup/meta unless install-guide changes.
