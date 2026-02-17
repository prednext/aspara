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
| **Storage** | Local files | Tracker (currently saves to local files) |
| **Team Collaboration** | Limited | Possible |
| **Offline** | Yes | No |

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

# Specifying tracker_uri enables remote mode
aspara.init(
    project="my_project",
    tracker_uri="http://localhost:3142"
)
aspara.log({"loss": 0.5})
aspara.finish()
```

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
