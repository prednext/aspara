# Tracker API (Advanced)

This page provides a conceptual overview of the Tracker. For detailed API documentation including usage examples and endpoint specifications, see [Tracker API Reference](../api/tracker.md).

## Overview

The Tracker is a standalone server that enables remote experiment tracking. It receives metrics, metadata, and artifacts from `RemoteRun` clients and stores them using the same storage layer as local runs.

## Starting the Tracker

```bash
aspara tracker --host 127.0.0.1 --port 3142
```

The API base path follows this format:

- `http://{host}:{port}/tracker/api/v1`

## Architecture

The Tracker uses `JsonlMetricsStorage` and `RunMetadataStorage` to persist data under the configured data directory, ensuring compatibility with the Dashboard and other Aspara tools.

For detailed endpoint documentation, usage examples, and API reference, see the [Tracker API Reference](../api/tracker.md).
