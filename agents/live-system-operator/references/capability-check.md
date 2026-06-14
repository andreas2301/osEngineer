# Capability Check

Before operating, verify the environment profile allows live operations:

```yaml
# Required capabilities
shell_exec: true
docker_exec: true
human_input: true  # For hotfixes only
```

If running as **autonomous-daemon**, live operations are READ-ONLY unless explicitly allowlisted.
