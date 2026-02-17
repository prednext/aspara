# Dashboard API

This page documents the Dashboard REST API for interacting with Aspara programmatically.

## OpenAPI Documentation

The dashboard provides interactive API documentation:

- `/docs` - Documentation list
- `/docs/dashboard` - Dashboard API documentation (Swagger UI)

## URI Structure

### HTML Pages

| Path | Description |
|------|-------------|
| `/` | Projects list page |
| `/projects/{project}` | Project detail page (metrics charts) |
| `/projects/{project}/runs` | Project runs list page |
| `/projects/{project}/runs/{run}` | Run detail page |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/projects/{project}/runs` | List runs in a project |
| GET | `/api/projects/{project}/runs/metrics` | Get metrics for multiple runs |
| GET | `/api/projects/{project}/runs/stream` | SSE stream for multiple runs |
| GET | `/api/projects/{project}/runs/{run}/metrics` | Get metrics for a run |
| GET | `/api/projects/{project}/runs/{run}/params` | Get parameters for a run |
| GET | `/api/projects/{project}/runs/{run}/stream` | SSE stream for a run |
| GET | `/api/projects/{project}/runs/{run}/artifacts/download` | Download artifacts as ZIP |
| GET | `/api/projects/{project}/runs/{run}/metadata` | Get run metadata |
| PUT | `/api/projects/{project}/runs/{run}/metadata` | Update run metadata |
| DELETE | `/api/projects/{project}/runs/{run}` | Delete a run |
| GET | `/api/projects/{project}/metadata` | Get project metadata |
| PUT | `/api/projects/{project}/metadata` | Update project metadata |
| DELETE | `/api/projects/{project}` | Delete a project |

## Usage Examples

### Basic Data Retrieval

```python
import requests

BASE_URL = "http://localhost:3141"

# Get run list for a specific project
runs = requests.get(f"{BASE_URL}/api/projects/{project_name}/runs").json()

# Get specific run details (JSON header required)
run_detail = requests.get(
    f"{BASE_URL}/projects/{project_name}/runs/{run_name}",
    headers={"Accept": "application/json"}
).json()

# Get metrics for a specific run
metrics = requests.get(
    f"{BASE_URL}/api/projects/{project_name}/runs/{run_name}/metrics"
).json()

# Get parameters for a specific run
params = requests.get(
    f"{BASE_URL}/api/projects/{project_name}/runs/{run_name}/params"
).json()
```

### Getting Metrics for Multiple Runs

```python
# Get metrics for multiple runs (useful for comparison)
runs_to_compare = "run1,run2,run3"
comparison = requests.get(
    f"{BASE_URL}/api/projects/{project_name}/runs/metrics",
    params={"runs": runs_to_compare}
).json()

# Response structure:
# {
#     "project": "my_project",
#     "metrics": {
#         "loss": {
#             "run1": {"steps": [...], "values": [...], "timestamps": [...]},
#             "run2": {"steps": [...], "values": [...], "timestamps": [...]}
#         }
#     }
# }

# MessagePack format for better performance
comparison_msgpack = requests.get(
    f"{BASE_URL}/api/projects/{project_name}/runs/metrics",
    params={"runs": runs_to_compare, "format": "msgpack"}
).content
```

### Getting/Updating Metadata

```python
# Get run metadata
metadata = requests.get(
    f"{BASE_URL}/api/projects/{project_name}/runs/{run_name}/metadata"
).json()

# Update run notes
updated_metadata = requests.put(
    f"{BASE_URL}/api/projects/{project_name}/runs/{run_name}/metadata",
    json={"notes": "Experiment results were good"}
).json()

# Get project metadata
project_metadata = requests.get(
    f"{BASE_URL}/api/projects/{project_name}/metadata"
).json()

# Update project tags
updated_project = requests.put(
    f"{BASE_URL}/api/projects/{project_name}/metadata",
    json={"tags": ["production", "v2"]}
).json()
```

### Downloading Artifacts

```python
# Download artifacts as ZIP
response = requests.get(
    f"{BASE_URL}/api/projects/{project_name}/runs/{run_name}/artifacts/download"
)
with open(f"{run_name}_artifacts.zip", "wb") as f:
    f.write(response.content)
```

### Real-time Streaming (SSE)

```python
import sseclient
import requests

# Stream metrics for a single run
response = requests.get(
    f"{BASE_URL}/api/projects/{project_name}/runs/{run_name}/stream",
    stream=True
)
client = sseclient.SSEClient(response)
for event in client.events():
    if event.event == "metric":
        print(f"New metric: {event.data}")

# Stream metrics for multiple runs
runs_to_watch = "run1,run2,run3"
response = requests.get(
    f"{BASE_URL}/api/projects/{project_name}/runs/stream",
    params={"runs": runs_to_watch},
    stream=True
)
client = sseclient.SSEClient(response)
for event in client.events():
    if event.event == "metric":
        print(f"Metric update: {event.data}")
    elif event.event == "status":
        print(f"Status update: {event.data}")
```

### Deleting Projects/Runs

```python
# Delete a run (irreversible!)
response = requests.delete(
    f"{BASE_URL}/api/projects/{project_name}/runs/{run_name}"
)
print(response.json())  # {"message": "Run 'project/run' deleted successfully"}

# Delete an entire project (all runs will also be deleted!)
response = requests.delete(f"{BASE_URL}/api/projects/{project_name}")
print(response.json())  # {"message": "Project 'project' deleted successfully"}
```

## API Reference

::: aspara.dashboard.router
    options:
      members:
        - list_runs_api
        - get_metrics_api
        - get_params_api
        - download_artifacts_zip
        - stream_metrics
        - stream_multiple_runs
        - runs_metrics_api
        - get_project_metadata_api
        - update_project_metadata_api
        - delete_project
        - get_run_metadata_api
        - update_run_metadata_api
        - delete_run
      show_root_heading: false
      show_source: false
