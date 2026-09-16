# VateCon backend

## Runtime

```bash
pip install -r requirements.txt
```

## Development (lint, typecheck, tests)

```bash
pip install -r requirements.txt
pip install -e ".[dev]"
```

Tooling is declared in `pyproject.toml` (Ruff, Mypy strict on
`app/`, pytest-cov with a 60% floor). Production Docker images install
**only** `requirements.txt` so test/lint packages never ship.
