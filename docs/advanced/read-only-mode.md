# Read-only Mode

Read-only mode allows you to run the Aspara dashboard as a public demo without exposing write operations. When enabled, the dashboard and tracker API accept all requests normally but silently skip any data modifications.

## Enabling Read-only Mode

Set the `ASPARA_READ_ONLY` environment variable to `1`:

```bash
ASPARA_READ_ONLY=1 uv run aspara dashboard
```

Or export it before launching:

```bash
export ASPARA_READ_ONLY=1
uv run aspara dashboard
```

To disable read-only mode, unset the variable or set it to any value other than `1`:

```bash
unset ASPARA_READ_ONLY
uv run aspara dashboard
```

## Behavior

### Dashboard API

The following write endpoints return success responses without performing any actual writes:

| Endpoint | Method | Read-only behavior |
|----------|--------|--------------------|
| `/api/projects/{project}/metadata` | PUT | Returns existing metadata unchanged |
| `/api/projects/{project}/runs/{run}/metadata` | PUT | Returns existing metadata unchanged |
| `/api/projects/{project}` | DELETE | Returns 204 (no deletion) |
| `/api/projects/{project}/runs/{run}` | DELETE | Returns 204 (no deletion) |

All read endpoints (GET) work normally.

### Tracker API

The following tracker endpoints return success responses without performing any actual writes:

| Endpoint | Method | Read-only behavior |
|----------|--------|--------------------|
| `/api/v1/projects/{project}/runs` | POST | Returns dummy `RunCreateResponse` |
| `/api/v1/projects/{project}/runs/{run}/metrics` | POST | Returns `MetricsResponse` |
| `/api/v1/projects/{project}/runs/{run}/artifacts` | POST | Returns dummy `ArtifactUploadResponse` |
| `/api/v1/projects/{project}/runs/{run}/config` | POST | Returns `StatusResponse` |
| `/api/v1/projects/{project}/runs/{run}/summary` | POST | Returns `StatusResponse` |
| `/api/v1/projects/{project}/runs/{run}/finish` | POST | Returns `StatusResponse` |

### Frontend

When read-only mode is enabled, the UI buttons (edit, delete) remain visible. However, clicking them displays an informational dialog indicating that the instance is running in read-only mode, instead of proceeding with the edit or delete action.

The following interactions are guarded:

- **Note editing** - Clicking the edit button on project/run notes shows the read-only dialog.
- **Tag editing** - Clicking the edit button on project/run tags shows the read-only dialog.
- **Deletion** - Clicking any delete button shows the read-only dialog instead of the delete confirmation dialog.

## Use Cases

- **Public demos** - Share a live dashboard without worrying about visitors modifying or deleting data.
- **Shared read-only access** - Allow team members to view experiment results without accidental modifications.
