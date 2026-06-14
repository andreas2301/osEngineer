# Repo Discovery Protocol

When initialized on a new project:

1. **Scan for repos:**
   ```bash
   find /project/root -maxdepth 2 -type d -name ".git" | sed 's|/.git$||'
   ```

2. **Classify each repo:**
   - Size: `find . -type f | wc -l`
   - Language: dominant file extension
   - Purpose: read `README.md` first 10 lines
   - Dependencies: read `go.mod`, `package.json`, `requirements.txt`

3. **Check for graphify:**
   - `ls graphify-out/graph.json` → exists? load metadata.
   - Missing? Note: "Recommend running graphify build."

4. **Check for ADRs:**
   - `docs/adr/`, `.claude/adr-catalog/`, `META/docs/adr/`
   - Count ADRs, read INDEX.md.

5. **Check for contracts:**
   - `.claude/contracts/`, `specs/`, `schemas/`
   - Note which repos have machine-readable contracts.

6. **Build repo map:**
   - Output: `RESEARCH.md` with topology, classification, and open questions.
