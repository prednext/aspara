# API Reference

This section provides detailed documentation for all Aspara APIs.

This API reference aims to use content auto-generated from source code as the authoritative source.

## Module List

* [aspara module](aspara.md) - Public APIs like `aspara.init()` / `aspara.log()` / `aspara.finish()`
* [Run class](run.md) - The central class for experiment tracking and management
* [Dashboard API](dashboard.md) - REST API for the dashboard server
* [Tracker API](tracker.md) - REST API for the tracker server

## wandb-Compatible API

Aspara provides a simple wandb-compatible API.

### aspara.init()

A function to start experiment tracking.

```python
import aspara

run = aspara.init(
    project="my_project",           # Project name (default: "default")
    name="my_run",                  # Run name (auto-generated if omitted)
    config={"lr": 0.001},           # Config parameters
    tags=["baseline"],              # Tags
    notes="First experiment",       # Notes
    dir="./data",                   # Data storage location (default: XDG compliant)
    storage_backend="polars",       # Storage backend ("jsonl" or "polars")
    tracker_uri="http://localhost:3142",  # Tracker server URI (for RemoteRun)
)
```

**Parameters:**

- **`project`**: Project name (default: `"default"`)
- **`name`**: Run name (auto-generated if omitted, e.g., `happy-falcon-42`)
- **`config`**: Dictionary of config parameters
- **`tags`**: List of tags (for search/filtering)
- **`notes`**: Run description or notes (wandb compatible)
- **`dir`**: Data storage directory (default: `~/.local/share/aspara`)
- **`storage_backend`**: Storage backend for metrics
    - `"jsonl"` (default): JSONL file format
    - `"polars"`: Efficient storage with Polars (experimental)
    - Can be overridden with `ASPARA_STORAGE_BACKEND` environment variable
- **`tracker_uri`**: Tracker server URI (enables remote tracking mode when specified)

**Returns:** `Run` object

**Using Context Manager:**

You can use `aspara.init()` with the `with` statement for automatic cleanup:

```python
with aspara.init(project="my_project") as run:
    aspara.log({"loss": 0.5})
# finish() called automatically
```

### aspara.log()

A function to log metrics.

```python
# Log metrics (step auto-increments)
aspara.log({"loss": 0.5, "accuracy": 0.95})

# Explicitly specify step
aspara.log({"loss": 0.3}, step=10)

# Group multiple logs to the same step
aspara.log({"train/loss": 0.5}, commit=False)
aspara.log({"val/loss": 0.6}, commit=True)  # Step is committed here
```

### aspara.finish()

A function to finish the experiment.

```python
aspara.finish()
```

**Note:** When using the context manager pattern (`with aspara.init(...) as run:`), `finish()` is called automatically when exiting the `with` block.

## Config and Summary

### run.config

An object to access and update config parameters.

```python
run = aspara.init(project="test", config={"lr": 0.01})

# Attribute access
print(run.config.lr)  # 0.01

# Dictionary access
print(run.config["lr"])  # 0.01

# Update
run.config.batch_size = 32
run.config.update({"epochs": 100})
```

### run.summary

An object to store final results.

```python
run = aspara.init(project="test")

# Record final results
run.summary["best_accuracy"] = 0.98
run.summary.update({"final_loss": 0.01})
```
