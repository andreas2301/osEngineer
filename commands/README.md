# commands/

Slash command entry points for osEngineer.

Each `.md` file defines a command: syntax, agent dispatch, steps, and example.

## Commands

| Command | Agent | Purpose |
|---------|-------|---------|
| `/osEngineer:init` | Researcher | Initialize osEngineer on a new project |
| `/osEngineer:plan` | Planner (+ Researcher) | Generate PHASE_PLAN.md |
| `/osEngineer:fix` | Developer | Execute a fix from an existing plan |
| `/osEngineer:feature` | Developer | Execute a feature from an existing plan |
| `/osEngineer:investigate` | Researcher | Investigate a symptom or error |
| `/osEngineer:verify` | Developer + Reviewer | Run verification protocol |
