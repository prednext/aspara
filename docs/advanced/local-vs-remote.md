# Local files and a Tracker copy

`aspara.init()` always saves the run as files on the machine running your code. Metrics, config, and metadata go to the local data directory (by default `~/.local/share/aspara`). Those files are the record of the run.

A **Tracker** is an HTTP server you start with `aspara tracker`. It can store a second copy of the same run, for example so several machines show up in one place. Pass `tracker_uri` to `aspara.init()`, or set `ASPARA_TRACKER_URI`, and Aspara queues that copy and sends it in the background after the local write. `log()` returns when the local write finishes. Omit `tracker_uri` and the run stays in local files only.

| | Local only | With `tracker_uri` |
|---|---|---|
| **What `init` writes** | Local files | The same local files |
| **Tracker** | Not used | Receives a copy when it is reachable |
| **If the Tracker is down** | — | `log()` still returns. The copy stays queued and is sent later |
| **Dependencies** | Minimal | `requests` (`aspara[remote]`) for the copy |
| **Several machines** | Each machine keeps its own files | One Tracker can hold a copy from each machine |

## Local only

Omit `tracker_uri` and `ASPARA_TRACKER_URI`:

```python
import aspara

aspara.init(project="my_project")
aspara.log({"loss": 0.5})
aspara.finish()
```

**Data storage location:** `~/.local/share/aspara/my_project/run_name.jsonl`

## Also ship a copy

```python
import aspara

aspara.init(
    project="my_project",
    tracker_uri="http://localhost:3142/tracker"
)
aspara.log({"loss": 0.5})
aspara.finish()
```

`log()` returns after the local write. The Tracker does not have to be running at that moment. `tracker_uri` includes `/tracker`: the client appends `/api/v1`, and `aspara tracker` serves the API under that path. A URI of `http://localhost:3142` alone returns 404.

On create, a loopback Tracker compares the client's directory with its own. When they match, it stores nothing and Aspara does not ship a second copy. A Tracker started with a different `--data-dir` receives the copy. Point `dir` at a different directory, or use a Tracker on another host, when you want a duplicate.

To receive the copy:

```bash
# Start the Tracker
aspara tracker --port 3142

# Install requests (if needed)
uv pip install "aspara[remote]"
```

## Adding a Tracker later

```python
# Local files only
with aspara.init(project="test") as run:
    aspara.log({"loss": 0.5})

# Same local files, plus a background copy
with aspara.init(project="test", tracker_uri="http://localhost:3142/tracker") as run:
    aspara.log({"loss": 0.5})
```

**Note:** You can also use the manual `finish()` pattern instead of the context manager if you need explicit control over when the run is finished:

```python
run = aspara.init(project="test")
aspara.log({"loss": 0.5})
aspara.finish()
```
