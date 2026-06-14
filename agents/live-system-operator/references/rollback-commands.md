# Rollback Commands

| Action | Rollback |
|--------|----------|
| `docker compose up -d` | `docker compose down` + restore previous image tag |
| `docker compose restart X` | `docker compose stop X && docker start X` (reverts to previous state) |
| `git reset --hard` in live | `git reflog` + `git reset --hard ORIG_HEAD` |
| Ansible playbook run | `ansible-playbook --check` first; rollback via git revert |
