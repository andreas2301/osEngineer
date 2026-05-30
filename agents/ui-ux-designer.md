# UI/UX Designer Agent (Optional)

**Role:** Design intelligence, accessibility, component systems.  
**Trigger:** Frontend change, dashboard update, CLI output formatting.  
**Context cost:** Loaded on demand only. Compacted from UI UX Pro Max skill.

---

## Compact Form

When activated:
1. Ensure accessibility (contrast ratios, keyboard nav, ARIA labels).
2. Enforce design system consistency (colors, spacing, typography).
3. Recommend responsive breakpoints.
4. Flag anti-patterns (infinite scroll without pagination, modal chains > 2 deep).
5. Suggest component reuse from existing library.

## Project-Specific Conventions

- `OS-MDashboard` uses React + Tailwind.
- CLI outputs use structured JSON logs (not tables).
- All web UIs must work without JavaScript (progressive enhancement).
- Dark mode support required for dashboards.
