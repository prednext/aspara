# Local vs Remote Tracking

Aspara has two operating modes:

- **Local Mode** (local file-based)
- **Remote Mode** (tracker server-based)

> **Note:** Internally, Aspara uses `LocalRun` and `RemoteRun` classes to implement these modes, but these are implementation details. You interact with the unified `Run` class returned by `aspara.init()`.

## Mode Comparison

| Feature | Local Mode | Remote Mode |
|---------|------------|-------------|
| **Server Required** | No | Yes (tracker) |
| **Dependencies** | Minimal | `requests` required (`aspara[remote]`) |
| **Storage** | Local files | Local files, plus a copy sent to the Tracker |
| **Team Collaboration** | Limited | Possible |
| **Offline** | Yes | Local write continues; shipping retries when the Tracker is back |

## Local Mode (Default)

A simple mode that writes metrics directly to local files:

```python
import aspara

# Default is local mode
aspara.init(project="my_project")
aspara.log({"loss": 0.5})
aspara.finish()
```

**Features:**

- Easy to use without a server
- Works in offline environments
- Lightweight and fast
- Ideal for debugging and personal development

**Data storage location:** `~/.local/share/aspara/my_project/run_name.jsonl`

## Remote Mode

A mode that sends metrics to a tracker server via HTTP:

```python
import aspara

# tracker_uri still writes local files and also ships to the Tracker
aspara.init(
    project="my_project",
    tracker_uri="http://localhost:3142"
)
aspara.log({"loss": 0.5})
aspara.finish()
```

On create, a loopback Tracker compares the client's directory with its own. When they match, it stores nothing and Aspara does not ship a second copy. A Tracker started with a different `--data-dir` receives the copy. Point `dir` at a different directory, or use a Tracker on another host, when you want a duplicate.

**Prerequisites:**

1. Tracker server must be running
2. `requests` must be installed

```bash
# Start the Tracker
aspara tracker --port 3142

# Install requests (if needed)
uv pip install "aspara[remote]"
```

## Switching Modes

Local and remote modes can be switched simply by adding `tracker_uri`:

```python
# Local mode (default)
with aspara.init(project="test") as run:
    aspara.log({"loss": 0.5})

# Remote mode
with aspara.init(project="test", tracker_uri="http://localhost:3142") as run:
    aspara.log({"loss": 0.5})
```

**Note:** You can also use the manual `finish()` pattern instead of the context manager if you need explicit control over when the run is finished:

```python
run = aspara.init(project="test")
aspara.log({"loss": 0.5})
aspara.finish()
```
