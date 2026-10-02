# GitHub Rulesets Guide

Server-side enforcement via GitHub rulesets. This is the **hard boundary** — client-side hooks can be bypassed, rulesets cannot.

## Quick Setup

### Via GitHub UI

1. Go to repository **Settings** → **Rules** → **Rulesets** → **New ruleset**
2. Name it `branch-enforcement`
3. Set **Target branches** to `main` (or add `master`, `develop`)
4. Enable these rules:

| Rule | Setting | Why |
|---|---|---|
| **Restrict deletions** | On | Prevent branch deletion |
| **Require a pull request** | On | Enforce code review |
| **Require status checks** | On | CI must pass |
| **Block force pushes** | On | Prevent history rewrite |
| **Require branch to be up to date** | On | Prevent merge conflicts |

5. Add **required status checks** (must match CI job names exactly):
   - `required` (the terminal aggregator job)
   - `verify` (the main verification job)

### Via GitHub API

```bash
# Create a ruleset for main branch
gh api repos/{owner}/{repo}/rulesets \
  --method POST \
  -f name="branch-enforcement" \
  -f target="branch" \
  -f enforcement="active" \
  -f conditions='{"ref_name":{"include":["refs/heads/main"]}}' \
  -f rules='[
    {"type":"deletion"},
    {"type":"non_fast_forward"},
    {"type":"required_pull_request","parameters":{"required_approving_review_count":1,"dismiss_stale_reviews_on_push":true}},
    {"type":"required_status_checks","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"required"},{"context":"verify"}]}}
  ]'
```

### Branch Naming Convention (Server-Side)

GitHub rulesets don't enforce naming patterns directly. To enforce naming:

1. **CI check** — add a workflow step that validates branch name:
   ```yaml
   - name: Check branch name
     if: github.event_name == 'pull_request'
     run: |
       BRANCH="${{ github.head_ref }}"
       if ! [[ "$BRANCH" =~ ^(feat|fix|chore|docs|refactor|test|ci|build|perf|revert)/[a-z0-9-]+$ ]]; then
         echo "Branch name does not match convention: $BRANCH"
         exit 1
       fi
   ```

2. **GitHub Ruleset** — use `branch_name_pattern` rule (available in GitHub Enterprise):
   ```json
   {"type":"branch_name_pattern","parameters":{"name":"Branch naming convention","operator":"regex","pattern":"^(feat|fix|chore|docs|refactor|test|ci|build|perf|revert)/[a-z0-9-]+$"}}
   ```

## Recommended Ruleset Configuration

```json
{
  "name": "branch-enforcement",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/main", "refs/heads/master"]
    }
  },
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {
      "type": "required_pull_request",
      "parameters": {
        "required_approving_review_count": 1,
        "dismiss_stale_reviews_on_push": true,
        "require_last_push_approval": false
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [
          {"context": "required"},
          {"context": "verify"}
        ]
      }
    },
    {
      "type": "commit_message_pattern",
      "parameters": {
        "name": "Conventional Commits",
        "operator": "regex",
        "pattern": "^(feat|fix|chore|docs|refactor|test|ci|build|perf|revert)(\\([a-z0-9-]+\\))?:\\s+.+$"
      }
    }
  ]
}
```

## Verification

```bash
# List rulesets
gh api repos/{owner}/{repo}/rulesets

# Test a ruleset
gh api repos/{owner}/{repo}/rulesets/{ruleset_id}
```

## Notes

- Rulesets are **org-level** or **repo-level**. Org-level rulesets apply to all repos.
- `commit_message_pattern` enforces Conventional Commits server-side.
- `branch_name_pattern` is available in GitHub Enterprise Cloud.
- For GitHub.com without Enterprise, use the CI check approach for naming conventions.
