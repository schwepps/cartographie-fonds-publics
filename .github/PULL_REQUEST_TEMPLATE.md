## What & why

<!-- Short description. Link the issue: Closes #123 -->

## Checklist
- [ ] Title follows [Conventional Commits](https://www.conventionalcommits.org/) (e.g. `feat: ...`, `fix: ...`)
- [ ] One feature / fix per PR
- [ ] Tests added or updated, and `make test` passes
- [ ] `make lint format typecheck` clean
- [ ] RGAA (web): keyboard-navigable, visible focus, sufficient contrast; user-facing strings via i18n; any new graphical view ships a `DataTableFallback`
- [ ] If a data source changed: **only** `data/registry/sources-registry.yaml` was edited (no hardcoded slugs/URLs)
- [ ] No secrets, no raw data snapshots committed
- [ ] Docs / CHANGELOG updated if relevant
