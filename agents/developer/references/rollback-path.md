# Rollback Path

Before each commit, note how to revert it:

```
# If this commit breaks X, revert with:
git revert <this-commit-hash>
# And re-run: ansible-playbook ... --tags <tag>
```
