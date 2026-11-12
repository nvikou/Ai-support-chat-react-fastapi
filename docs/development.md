# Development

## Prerequisites

- Python 3.11+ (CI also runs 3.12)
- Node 20+
- Docker Desktop (recommended for full stack)
- `pre-commit` (hooks on commit)

## Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest
ruff check app tests
mypy app
```

App package: `backend/app`. Tests: `backend/tests`.

## Frontend

```bash
cd frontend
npm install
npm run dev      # Vite, usually http://localhost:5173
npm run lint
npm run test
```

Point the API base URL at a running backend (see `.env` /
Vite env docs in the frontend README section of root README).

## Evaluation harness

```bash
pip install -r evaluation/requirements.txt
make eval
```

Details: [evaluation.md](evaluation.md).

## Git conventions (PROMPT 0)

- Atomic Conventional Commits (`feat:`, `fix:`, `docs:`, …) in
  English.
- Commit **body explains why**, not what the diff already shows.
- Prefer ≥5 commits on large features; propose a split before a
  150+ LOC dump.
- Do not commit secrets (`.env`, keys). `detect-secrets` runs in
  pre-commit.

See [CONTRIBUTING.md](../CONTRIBUTING.md).

## Useful references

- [architecture.md](architecture.md)
- [OBSERVABILITY.md](OBSERVABILITY.md)
- ADRs: [adr/README.md](adr/README.md)
