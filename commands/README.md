# commands/

Slash command entry points for osEngineer.

Each `.md` file defines a command: syntax, agent dispatch, steps, and example.

## Commands

| Command | Agent | Purpose |
|---------|-------|---------|
| `/observer:init` | Researcher | Initialize osEngineer on a new project |
| `/observer:plan` | Planner (+ Researcher) | Generate PHASE_PLAN.md |
| `/observer:fix` | Developer | Execute a fix from an existing plan |
| `/observer:feature` | Developer | Execute a feature from an existing plan |
| `/observer:investigate` | Researcher | Investigate a symptom or error |
| `/observer:verify` | Developer + Reviewer | Run verification protocol |
