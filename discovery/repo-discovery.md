# Repo Discovery Protocol

**Agent:** Researcher  
**Trigger:** `/osEngineer:init` or first run on new project  
**Output:** `RESEARCH.md` with repo topology

---

## Protocol

### 1. Scan

```bash
find /project/root -maxdepth 3 -type d -name ".git" | sed 's|/.git$||' | sort
```

### 2. Classify Each Repo

For each repo found:

```bash
cd $repo
# Size
find . -type f | wc -l
# Language
dominant_ext=$(find . -type f | sed 's/.*\.//' | sort | uniq -c | sort -rn | head -1 | awk '{print $2}')
# Purpose
head -5 README.md 2>/dev/null || head -5 README 2>/dev/null || echo "no README"
# Dependencies
ls go.mod package.json requirements.txt pyproject.toml Cargo.toml 2>/dev/null
# Graphify
ls graphify-out/graph.json 2>/dev/null && echo "has graphify" || echo "no graphify"
# ADRs
ls docs/adr/ .claude/adr-catalog/ 2>/dev/null && echo "has ADRs" || echo "no ADRs"
# Contracts
ls .claude/contracts/ specs/ schemas/ 2>/dev/null && echo "has contracts" || echo "no contracts"
```

### 3. Build Repo Map

Output YAML structure:

```yaml
project: <project-name>
repo_count: <n>
repos:
  <repo-name>:
    branch: <default-branch>
    language: <dominant-language>
    size_loc: ~<approx>
    classification: small | medium | large
    has_graphify: true | false
    has_adrs: true | false
    has_contracts: true | false
    dependencies:
      - <other-repo-name>
```

The actual repo list is read from `.osengineer/workbench-config.yml` (created during `install.sh`), not hardcoded.

### 4. Identify Gaps

- Repos without `CLAUDE.md` or `AGENTS.md` → flag for onboarding.
- Repos without graphify → flag for graphify build.
- Repos without ADRs → flag for ADR adoption.
