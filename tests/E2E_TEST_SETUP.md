# Chart Rendering E2E Tests - Setup Guide

## Running Tests

### Prerequisites

You need to manually start the Aspara dashboard servers before running tests.
Each worker needs its own server instance on a dedicated port.

### Starting Servers for Parallel Execution

```bash
# Worker 0 (port 6113)
uv run aspara dashboard --port 6113 &

# Worker 1 (port 6114) - if running with multiple workers
uv run aspara dashboard --port 6114 &

# Worker 2 (port 6115) - if running with multiple workers
uv run aspara dashboard --port 6115 &
```

### Running Tests

```bash
# Run all E2E tests (uses fixtures for port management)
npx playwright test

# Run only chart rendering tests
npx playwright test tests/dashboard/chart-rendering.spec.js

# Run with specific number of workers
npx playwright test --workers=2

# Run in headed mode (see browser)
npx playwright test --headed

# Run with UI mode (interactive)
npx playwright test --ui
```

### Port Allocation

- Base port: **6113**
- Worker 0: port **6113**
- Worker 1: port **6114**
- Worker 2: port **6115**
- etc.

Each worker automatically uses `http://localhost:{6113 + workerIndex}` as its baseURL.

### Stopping Servers

```bash
# Kill all aspara dashboard processes
pkill -f "aspara dashboard"

# Or find and kill specific ports
lsof -ti:6113 | xargs kill
lsof -ti:6114 | xargs kill
lsof -ti:6115 | xargs kill
```

## Architecture

The test setup uses **worker-scoped fixtures** to assign each Playwright worker
a unique port, preventing port conflicts during parallel test execution.

See `tests/fixtures.js` for the implementation details.

## Example: Running Tests with 2 Workers

```bash
# Terminal 1: Start servers
uv run aspara dashboard --port 6113 &
uv run aspara dashboard --port 6114 &

# Terminal 2: Run tests
npx playwright test --workers=2

# When done, clean up
pkill -f "aspara dashboard"
```

## Troubleshooting

### Port Already in Use

If you get a "port already in use" error:

```bash
# Check what's using the port
lsof -i:6113

# Kill the process
lsof -ti:6113 | xargs kill
```

### Tests Timing Out

If tests fail with timeout errors, ensure:
1. The dashboard server is running on the expected port
2. You can access `http://localhost:6113/projects/default` in your browser
3. The server has fully started before running tests
