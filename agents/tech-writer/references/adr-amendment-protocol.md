# ADR Amendment Protocol

When a change affects an existing ADR:

1. Read the ADR.
2. Determine if the change is:
   - **Clarification:** Edit the ADR, bump version, add changelog entry.
   - **Extension:** Add a new section, cite the phase that introduced it.
   - **Supersession:** Mark old ADR as "Superseded", write new ADR with `supersedes: ADR-NNN`.

3. Update `docs/adr/INDEX.md` or `.claude/adr-catalog/INDEX.md`.
