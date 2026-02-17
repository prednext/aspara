# Development Guide

This document is a developer guide for Aspara.

## Setup

### Python dependencies

```bash
uv sync --dev
```

### JavaScript dependencies

```bash
pnpm install
```

## Building Assets

After cloning the repository, you must build frontend assets before running Aspara.
These build artifacts are not tracked in git, but are included in pip packages.

### Build all assets (CSS + JavaScript)

```bash
pnpm build
```

This command generates:
- CSS: `src/aspara/dashboard/static/dist/css/styles.css`
- JavaScript: `src/aspara/dashboard/static/dist/*.js`

### Build CSS only

```bash
pnpm run build:css
```

### Build JavaScript only

```bash
pnpm run build:js
```

### Development mode (watch mode)

To automatically detect file changes and rebuild during development:

```bash
# Watch CSS
pnpm run watch:css

# Watch JavaScript
pnpm run watch:js
```

## Testing

### Python tests

```bash
uv run pytest
```

### JavaScript tests

```bash
pnpm test
```

### E2E tests

```bash
npx playwright test
```

## Linting and Formatting

### Python

```bash
# Lint
ruff check .

# Format
ruff format .
```

### JavaScript

```bash
# Lint
pnpm lint

# Format
pnpm format
```

## Documentation

### Build documentation

```bash
uv run mkdocs build
```

### Serve documentation locally

```bash
uv run mkdocs serve
```

You can view the documentation by accessing http://localhost:8000 in your browser.
