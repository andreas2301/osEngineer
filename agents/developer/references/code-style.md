# Code Style

- Follow existing style in the repo. Read 3–5 nearby files before writing.
- Go: Use `gofmt`, error wrapping with `%w`, structured logging with `log.Printf(JSON)`.
- Python: Use `black`, type hints, `pydantic` for schemas.
- Ansible: Use YAML anchors sparingly; prefer `ansible.builtin.*` FQCN.
- Markdown: One sentence per line (diff-friendly).
