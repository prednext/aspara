# Contributing

Thank you for your interest in contributing to Aspara. This page explains how to participate in development.

## Setting Up the Development Environment

First, set up your development environment.

```bash
# Clone the repository
git clone https://github.com/tkng/aspara.git
cd aspara

# Build frontend assets (required - not included in the git repository)
pnpm install && pnpm build

# Install in development mode
uv pip install -e ".[dev]"
```

## Coding Conventions

Aspara follows these coding conventions:

* **Type hints**: Write type hints for all functions and methods
* **Documentation**: Write documentation for all new features
* **Unit tests**: Write unit tests for all new features
* **Linting and formatting**: Use ruff to lint and format code

## Linting and Formatting

### Python

We use `ruff` for Python code linting and formatting.

```bash
# Lint
uv run ruff check .

# Format
uv run ruff format .
```

### JavaScript

We use `biome` for JavaScript code linting and formatting.

```bash
# Lint
pnpm biome lint

# Format
pnpm biome format
```

## Running Tests

We use `pytest` for running tests.

```bash
# Run all tests
uv run pytest

# Run specific tests
uv run pytest tests/test_run.py
```

## Pull Requests

Before submitting a pull request, please verify the following:

1. All tests pass
2. Code follows linting and formatting rules
3. New features have documentation and tests
4. Commit messages are clear

## Updating Documentation

When updating documentation, build and verify with the following commands.

```bash
# Build documentation
uv run mkdocs build

# Preview documentation locally
uv run mkdocs serve
```
