# Git Workflow & Cleanliness Rules

Strict git discipline rules mandated for this workspace:

1. **Pull Before Push:**
   - Always run `git pull --rebase origin <branch>` before pushing any commits to ensure the local branch is completely up to date with remote changes.

2. **Clean Working Tree Before New Work:**
   - Always ensure `git status` reports a clean working tree (`nothing to commit, working tree clean`) before embarking on any new task or session.
   - Never carry untracked, scratch, or dirty uncommitted files into a new task.

3. **Branch Before New Work:**
   - Never do new work directly on `master`/`main`.
   - Always create and switch to a dedicated feature/task branch (e.g. `feature/<task-name>` or `fix/<issue-name>`) before creating or modifying any files.
