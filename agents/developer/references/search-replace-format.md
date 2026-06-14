# Code Modification Format (SEARCH/REPLACE)

To optimize token efficiency and guarantee edit precision, you MUST express all file modifications in your reasoning as unified SEARCH/REPLACE blocks. This aligns with Aider-style precise edits:

```markdown
<<<<<<< SEARCH
// exact old code to be replaced
=======
// new code replacement
>>>>>>> REPLACE
```

- Each SEARCH block must be a unique, exact match in the target file, including all leading whitespace.
- Keep the SEARCH block as small and focused as possible, containing only the lines that actually change.
- Never write placeholders or truncated segments inside the REPLACE block.
