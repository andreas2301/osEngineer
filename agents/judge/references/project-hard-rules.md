# Project Hard Rules

The judge has special authority on these rules. Violation = automatic BLOCK:

1. **SOLID wall preserved:** Strategist knows missions, not Docker. Supervisor knows containers, not mission planning.
2. **Fail-closed:** Any init error must disable the feature, not panic or fallback insecure.
3. **mTLS everywhere:** No `InsecureSkipVerify: true` in production paths.
4. **Vault for secrets:** No hardcoded passwords, tokens, or keys in production code.
5. **Graphify parity:** Any new module > 500 LOC must be graphified before merge.
