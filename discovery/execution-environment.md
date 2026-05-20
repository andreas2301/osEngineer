# Execution Environment Detection

**Agent:** Researcher (auto-fired on `/osEngineer:init`)  
**Purpose:** Detect where osEngineer is running and adapt behavior.  
**Rule:** NEVER assume. Always ask the user when detection is ambiguous.

---

## Environment Profiles

| Profile | Typical Context | Capabilities | Limitations |
|---------|----------------|--------------|-------------|
| **terminal-cli** | SSH session, bash/zsh, Kimi CLI, Gemini CLI | Shell exec, file system, git, docker | No GUI, no IDE file tree |
| **ide-integrated** | VS Code, Cursor, Claude Code, Windsurf | File ops, terminal panel, git UI, LSP | May not have direct shell access |
| **web-ui** | Browser-based AI assistant, chat interface | Limited file upload/download, no shell | Sandboxed, ephemeral filesystem |
| **autonomous-daemon** | systemd service, cron job, CI/CD pipeline | Pre-scheduled tasks, no HITL | No human input during execution |

## Detection Protocol

On `/osEngineer:init`, the researcher agent MUST run this protocol:

### Step 1: Automated Probes

```bash
# Probe 1: Are we in a terminal?
if [ -t 0 ]; then echo "terminal"; fi

# Probe 2: Is an IDE present?
if [ -n "${VSCODE_PID:-}" ] || [ -n "${CURSOR_TRACE_ID:-}" ]; then echo "ide"; fi

# Probe 3: Is Docker available?
command -v docker &>/dev/null && docker ps &>/dev/null && echo "docker"

# Probe 4: Is gh authenticated?
gh auth status &>/dev/null && echo "github-cli"

# Probe 5: Can we write to filesystem?
touch /tmp/osengineer_probe_$$ 2>/dev/null && rm /tmp/osengineer_probe_$$ && echo "fs-write"

# Probe 6: Is zeroclaw daemon running?
pgrep -x zeroclaw &>/dev/null && echo "daemon"

# Probe 7: Context window size (ask LLM to self-report)
# This is done via prompt, not shell
```

### Step 2: User Confirmation (MANDATORY)

**NEVER skip this step.** Automated probes can be wrong.

Present findings to user:

```
[osEngineer] Environment Detection Results:

  Detected profile: terminal-cli
  Shell: /bin/bash
  File system: read-write
  Docker: available
  GitHub CLI: authenticated (andreas2301)
  Context window: ~128K tokens (inferred)

  Is this correct? [yes / no / partial]
  If NO, please select your environment:
    [1] Terminal / CLI (SSH, bash, Kimi CLI, etc.)
    [2] IDE Integrated (VS Code, Cursor, Claude Code, etc.)
    [3] Web UI (browser-based assistant)
    [4] Autonomous Daemon (systemd, CI/CD)
    [5] Hybrid (describe: __________)
```

### Step 3: Capability Matrix

Based on confirmed profile, build a capability matrix:

```yaml
profile: terminal-cli
capabilities:
  shell_exec: true
  file_write: true
  git_ops: true
  docker_exec: true
  github_pr: true
  human_input: true
  long_running: true
  gui_interaction: false
  browser_automation: false
constraints:
  context_window: 128000
  max_parallel_agents: 4
  preferred_output: markdown_files
```

### Step 4: Adapt Agent Behavior

Based on capability matrix, adjust:

- **IDE profile:** Use IDE file operations instead of `cat`/`sed`. Use terminal panel for shell commands. Leverage LSP for code navigation.
- **Web UI profile:** Batch file uploads. Minimize round trips. Use `WriteFile` tool heavily. No shell commands.
- **Daemon profile:** Skip all HITL gates. Log everything. Use exit codes for success/failure. No interactive prompts.
- **Terminal profile:** Standard shell + file ops. Full capability.

## Environment-Specific Adaptations

### IDE Integrated

- **File ops:** Use IDE's native file API when available (faster than shell `cat`/`sed`).
- **Git:** Use IDE's git panel for visual diffs; fall back to `git` CLI for automation.
- **Terminal:** Use integrated terminal for docker/ansible commands.
- **LSP:** Leverage go-to-definition instead of grep for navigation (saves tokens).

### Web UI

- **Batching:** Combine multiple file reads into one request.
- **No shell:** Replace `docker ps` with API calls or screenshot-based verification.
- **State persistence:** Upload/download `RESEARCH.md` and `PHASE_PLAN.md` as files.
- **Context compression:** Summarize long outputs before presenting.

### Autonomous Daemon

- **No prompts:** All decisions must be rule-based or pre-configured.
- **Structured logging:** JSON logs only. Journald integration.
- **Alert channels:** Slack/Discord/Telegram for blocks requiring HITL.
- **Circuit breakers:** Hard abort on any ambiguity. No "ask user" fallback.
- **Scheduled execution:** Cron-like phase scheduling with retry logic.

## Stored Artifact

Environment detection results are stored in:
```
memory/environment-profile.yml
```

This file is read by all agents to adapt their behavior. If capabilities change (e.g., Docker daemon stops), re-run `/osEngineer:init`.
