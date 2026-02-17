# Tracker API

This page documents the Tracker REST API used by RemoteRun to record metrics and manage runs on a remote server.

## Overview

The Tracker is a standalone server that receives and stores experiment data from remote clients.
It provides a RESTful API for creating runs, logging metrics, and uploading artifacts.

### Starting the Tracker

```bash
aspara tracker --host 127.0.0.1 --port 3142
```

The API base path follows this format:

- `http://{host}:{port}/tracker/api/v1`

## OpenAPI Documentation

The tracker provides interactive API documentation:

- `/tracker/docs/tracker` - Tracker API documentation (Swagger UI)
- `/tracker/docs/tracker/redoc` - Tracker API documentation (ReDoc)

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/tracker/api/v1/health` | Health check endpoint |
| POST | `/tracker/api/v1/projects/{project_name}/runs` | Create a new run |
| POST | `/tracker/api/v1/projects/{project_name}/runs/{run_name}/metrics` | Save metrics |
| POST | `/tracker/api/v1/projects/{project_name}/runs/{run_name}/artifacts` | Upload an artifact |

## Usage Examples

### Health Check

```python
import requests

BASE_URL = "http://localhost:3142/tracker"

# Check if the tracker is running
response = requests.get(f"{BASE_URL}/api/v1/health")
print(response.json())  # {"status": "ok"}
```

### Creating a Run

```python
import requests

BASE_URL = "http://localhost:3142/tracker"
project_name = "my_project"

# Create a new run with metadata
response = requests.post(
    f"{BASE_URL}/api/v1/projects/{project_name}/runs",
    json={
        "name": "experiment_001",
        "tags": ["baseline", "v1"],
        "notes": "Initial experiment",
        "config": {"learning_rate": 0.001, "batch_size": 32},
        "project_tags": ["production"]
    }
)
print(response.json())
# {"project": "my_project", "name": "experiment_001", "run_id": "experiment_001"}
```

### Logging Metrics

```python
import requests
from datetime import datetime

BASE_URL = "http://localhost:3142/tracker"
project_name = "my_project"
run_name = "experiment_001"

# Log metrics for a specific step
response = requests.post(
    f"{BASE_URL}/api/v1/projects/{project_name}/runs/{run_name}/metrics",
    json={
        "type": "metrics",
        "timestamp": datetime.now().isoformat(),
        "run": run_name,
        "project": project_name,
        "step": 100,
        "metrics": {"loss": 0.5, "accuracy": 0.85}
    }
)
print(response.json())  # {"status": "ok"}
```

### Uploading Artifacts

```python
import requests

BASE_URL = "http://localhost:3142/tracker"
project_name = "my_project"
run_name = "experiment_001"

# Upload a file as an artifact
with open("model.pt", "rb") as f:
    response = requests.post(
        f"{BASE_URL}/api/v1/projects/{project_name}/runs/{run_name}/artifacts",
        files={"file": ("model.pt", f)},
        data={
            "name": "trained_model.pt",
            "description": "Final trained model",
            "category": "model"
        }
    )
print(response.json())
# {"artifact_name": "trained_model.pt", "file_size": 12345}
```

### Using RemoteRun

Instead of calling the API directly, you can use the `RemoteRun` client:

```python
import aspara

# Connect to a remote tracker
run = aspara.init(
    project="my_project",
    name="experiment_001",
    tracker_uri="http://localhost:3142",
    config={"learning_rate": 0.001}
)

# Log metrics (automatically sent to the tracker)
for step in range(100):
    run.log({"loss": 0.5 - step * 0.005, "accuracy": 0.5 + step * 0.005})

run.finish()
```

## API Reference

::: aspara.tracker.router
    options:
      members:
        - health_check
        - create_run
        - save_metrics
        - upload_artifact
      show_root_heading: false
      show_source: false
