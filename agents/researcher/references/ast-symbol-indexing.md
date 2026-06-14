# AST-Based Symbol Indexing (Cross-Repo Graphing)

When researching a multi-repo codebase:

- Use AST symbol maps (such as tree-sitter or Context7 symbol tags) to map types, structs, interfaces, and function signatures. This enables instant cross-repo definition lookups.
- Prioritize querying Context7's symbol index or the local `graphify` tag index over raw `grep` when locating shared types, interfaces, or structs.
- Maintain high accuracy and save tokens by locating exact symbol declarations rather than fuzzy keyword matches.
