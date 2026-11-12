# Contributing

Thanks for helping improve VateCon. This repo is also a **git history
deliverable**: small, reviewable commits matter as much as the code.

## Before you start

1. Read [docs/development.md](docs/development.md) and
   [docs/architecture.md](docs/architecture.md).
2. Install pre-commit hooks: `pre-commit install`.
3. Never commit secrets (`.env`, API keys, cookies).

## Branching

- Branch from `main`.
- Use a focused name: `feat/…`, `fix/…`, `docs/…`.
- Open a PR early; keep CI green.

## Commit style (PROMPT 0)

- **Atomic** commits: one coherent change that leaves the tree
  testable.
- **Conventional Commits** in English: `feat:`, `fix:`, `docs:`,
  `refactor:`, `test:`, `chore:`, `perf:`, `ci:`.
- Body answers **why**, not what (the diff already shows what).
- If a change exceeds ~150 lines of new logic/docs dump, **split**
  before merging as one blob. Prefer ≥5 commits on epics.

Example:

```
fix: escalate on confidence parse failure

The confidence marker was defaulting to 0.8 when the LLM omitted it,
which suppressed escalation on the answers we trust least.
```

## Pull requests

- Fill the PR template (summary + test plan).
- Link ADRs or docs when behavior changes.
- Re-run `make eval` if retrieval, chunking, or confidence changes.
- Do not dismiss security CI without a fix or a documented ignore.

## Issues

Use the bug / feature templates. Include repro steps, expected vs
actual, and environment (Compose vs local venv).

## Code of collaboration

Be precise, assume good faith, and document limitations when you
discover them — see README “Limitations & non-goals”.
