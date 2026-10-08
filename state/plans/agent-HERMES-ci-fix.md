# Plan: Fix CI setup-uv cache failure

## Objective

Fix the CI failure caused by `setup-uv` with `enable-cache: true` but no `uv.lock`.

## Scope

- `.github/workflows/ci.yml` — remove `enable-cache: true` from setup-uv step

## Approach

1. Remove `enable-cache: true` from the setup-uv action in ci.yml
2. Run `make check` and `make status` to verify no regressions
3. Commit and push

## Risks

- None — this is a one-line removal of a cache optimization that cannot work without uv.lock

## Rollback

- Re-add `enable-cache: true` if a `uv.lock` is ever introduced

## Success Criteria

- `make check` passes
- `make status` passes
- CI runs green on the remote
