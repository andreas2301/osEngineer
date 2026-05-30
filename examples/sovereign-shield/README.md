# Sovereign Shield / Observer Shield Reference Overlay

This directory contains the original project-specific conventions, runbooks, and patterns that were developed for the **Sovereign Shield** (also known as **Observer Shield**) platform.

It is preserved as a **reference implementation** — a concrete example of how osEngineer can be adapted to a real multi-repo project.

## Contents

| Directory | Description |
|-----------|-------------|
| `patterns/` | Engineering patterns extracted from production incidents (AMQP topology, TLS fail-closed, routing-key migrations). |
| `runbooks/` | Live-system operational runbooks (cert rotation, Docker health, RabbitMQ recovery, Vault unseal). |
| `integrations/` | MCP integration configs (Atlassian Confluence/Jira). |

## How to Use This Overlay

1. **Study it:** Read the patterns and runbooks to understand how project-specific conventions are documented.
2. **Copy and adapt:** Take the structure and replace Sovereign Shield names/paths with your own project's.
3. **Create your own overlay:** Start a new directory under `examples/<your-project>/` and add your conventions there.

## Key Design Decisions in This Overlay

- **Fail-closed security:** Any TLS or auth init error degrades the feature rather than crashing the service.
- **AMQP queue ownership:** Every consumer declares its own queue idempotently before calling `Consume()`.
- **Dual-listen migrations:** Routing key changes span at least 3 deploy cycles with an overlap window.
- **Live-system read-only:** Source code is never edited directly on the production host; all changes flow through workbench → PR → deploy.

These conventions are **not universal.** They are specific to a Go + Python + Ansible + RabbitMQ + Vault + Docker stack. Adopt what fits your stack; discard what doesn't.
