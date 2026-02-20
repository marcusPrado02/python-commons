# Contributing to mp-commons

Thank you for considering a contribution! This document covers the development
workflow, code conventions, and the release process.

---

## Table of Contents

1. [Development environment setup](#1-development-environment-setup)
2. [Reproducible installs with `uv.lock`](#2-reproducible-installs-with-uvlock)
3. [Running tests](#3-running-tests)
4. [Code quality](#4-code-quality)
5. [Architecture rules](#5-architecture-rules)
6. [Commit conventions](#6-commit-conventions)
7. [Opening a pull request](#7-opening-a-pull-request)
8. [Release process](#8-release-process)

---

## 1. Development environment setup

This project uses [uv](https://github.com/astral-sh/uv) as the package manager.
Install it if you don't have it yet:

```bash
curl -Lss https://astral.sh/uv/install.sh | sh
```

Then clone and install all dev dependencies:

```bash
git clone https://github.com/marcusPrado02/python-commons.git
cd python-commons
uv sync --extra dev      # installs all extras + dev tools into .venv
```

> `uv` automatically creates a `.venv` in the project root.
> Activate it with `source .venv/bin/activate` if you prefer explicit activation,
> or keep using `uv run <cmd>` without activating.

---

## 2. Reproducible installs with `uv.lock`

The `uv.lock` file in the repository root pins the **exact resolved versions**
of every dependency (direct + transitive) used in CI and development.

| Scenario | Command |
|---|---|
| Fresh clone / CI | `uv sync --frozen` — installs exactly what's in the lock file, fails if it would change |
| Adding a dependency | `uv add <package>` — resolves, installs, and updates `uv.lock` |
| Upgrading all deps | `uv lock --upgrade && uv sync` — re-resolves and updates `uv.lock` |
| Check lock is fresh | `uv lock --check` — exits non-zero if `pyproject.toml` changes haven't been locked yet |

**Always commit `uv.lock`** together with any `pyproject.toml` changes.
CI runs `uv sync --frozen` to ensure no implicit upgrades slip into a build.

---

## 3. Running tests

```bash
# All tests
make test

# Unit tests only (fast, no infrastructure required)
make test-unit

# Integration tests (requires Docker for testcontainers)
make test-integration

# With coverage report written to htmlcov/
make test-cov

# Unit tests in parallel (faster on multicore)
make test-fast
```

Tests live in `tests/unit/`, `tests/integration/`, and `tests/contract/`.
Each module mirrors the source tree — e.g. `src/mp_commons/kernel/ddd/`
is tested by `tests/unit/kernel/test_ddd.py`.

### pytest markers

| Marker | Meaning |
|---|---|
| `unit` | Pure Python, no I/O — always run in CI |
| `integration` | Requires live infra (Redis, Postgres, Kafka, …) |
| `contract` | Schema / contract compatibility tests |

Tag tests with `@pytest.mark.unit`, etc. Tests missing a marker will raise
a `--strict-markers` error.

---

## 4. Code quality

```bash
make lint        # ruff check (errors only)
make lint-fix    # ruff check --fix (safe auto-fixes)
make format      # ruff format --check
make format-fix  # ruff format (apply)
make typecheck   # mypy --strict
make security    # bandit + pip-audit
```

All checks above run automatically in CI on every push and pull request.
A pre-commit hook configuration is provided — install it once after cloning:

```bash
uv run pre-commit install
```

---

## 5. Architecture rules

1. **`kernel.*` is stdlib-only** — never add a third-party import inside
   `src/mp_commons/kernel/`. See [ADR-0001](docs/architecture/ADR-0001-kernel-boundaries.md).
2. **Ports & Adapters** — all infrastructure concerns are Protocols/ABCs in
   the kernel; concrete implementations live in `adapters/`.
3. **Optional extras** — adapter modules must raise a friendly `ImportError`
   with an `pip install mp-commons[<extra>]` hint if the optional dep
   is missing at import time.
4. **One class / concept per file** — implementation files are named after the
   class they contain; `__init__.py` is a pure re-export with `__all__`.
5. **Async-first** — all I/O-bound public APIs are `async`.

---

## 6. Commit conventions

We use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):

```
<type>(optional scope): <short description>

[optional body]

[optional footer(s)]
```

| Type | When to use |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test` | Adding or updating tests |
| `docs` | Documentation only |
| `chore` | Build, CI, tooling, dependencies |
| `perf` | Performance improvement |

Examples:
```
feat(kernel/ddd): add version field to AggregateRoot for optimistic locking
fix(adapters/redis): release lock on unexpected exception path
chore(deps): bump httpx from 0.27.0 to 0.28.0
```

Breaking changes must include a `BREAKING CHANGE:` footer or a `!` after the type:
```
feat(kernel/types)!: change EntityId.generate() to return UUID v7
```

---

## 7. Opening a pull request

1. Fork the repository and create a feature branch:
   ```bash
   git checkout -b feat/my-feature
   ```
2. Write tests first — aim for 90 %+ coverage on new code.
3. Ensure all checks pass locally:
   ```bash
   make lint typecheck test
   ```
4. Update `CHANGELOG.md` under the `[Unreleased]` section.
5. Open a PR against `main` — the PR template will guide you through the
   required checklist.

CI must be fully green before a PR can be merged.

---

## 8. Release process

Releases are triggered by pushing a `v*` tag:

```bash
# Update version in pyproject.toml
# Move [Unreleased] entries in CHANGELOG.md to the new version heading
git add pyproject.toml CHANGELOG.md
git commit -m "chore(release): v0.2.0"
git tag v0.2.0
git push origin main --tags
```

GitHub Actions will:
1. Run the full CI matrix (lint → test → security).
2. Build the wheel and sdist.
3. Publish to PyPI via OIDC Trusted Publisher (no tokens required).
