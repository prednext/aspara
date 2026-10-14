# Tracker API (Advanced)

This page provides a conceptual overview of the Tracker. For detailed API documentation including usage examples and endpoint specifications, see [Tracker API Reference](../api/tracker.md).

## Overview

The Tracker is a standalone server that stores a copy of a run. `aspara.init(tracker_uri=...)` still writes local files, and sends that copy in the background. The Tracker stores it with the same storage layer as a local run.

## Starting the Tracker

```bash
aspara tracker --host 127.0.0.1 --port 3142
```

The API base path follows this format:

- `http://{host}:{port}/tracker/api/v1`

## Architecture

The Tracker uses `JsonlMetricsStorage` and `RunMetadataStorage` to persist data under the configured data directory, ensuring compatibility with the Dashboard and other Aspara tools.

For detailed endpoint documentation, usage examples, and API reference, see the [Tracker API Reference](../api/tracker.md).
