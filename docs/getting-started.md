# Getting Started

This guide explains how to start tracking machine learning experiments with aspara.
It covers installation, a minimal code example, and how to launch the dashboard.

If you want to understand the overall structure and terminology of Aspara (such as Tracker, local vs remote tracking modes), please also refer to [Core Concepts](user-guide/concepts.md).

## Installation

This documentation assumes you are using [uv](https://github.com/astral-sh/uv) as your Python package manager.
If you use `pip`, simply replace `uv pip` with `pip` in the commands below.

### Installing aspara

Aspara consists of three components: the client library, dashboard, and Tracker. The dashboard is a web application for visualizing recorded metrics. If you install without specifying extras, only the client library will be installed.

First, install the aspara core package:

```bash
uv pip install aspara
```

### Installing from source (GitHub)

If you install from the GitHub repository instead of pip, you must build the frontend assets before running the dashboard. The pip package includes pre-built assets, but the git repository does not.

```bash
git clone https://github.com/tkng/aspara.git
cd aspara
pnpm install && pnpm build   # Build frontend assets
uv pip install -e ".[dashboard]"
```

If you want to use the dashboard or Tracker API, install with the appropriate extras:

```bash
# Enable dashboard
uv pip install "aspara[dashboard]"

# Enable Tracker API
uv pip install "aspara[tracker]"

# Enable both dashboard and Tracker API
uv pip install "aspara[dashboard,tracker]"
```

Even if you have already installed `aspara`, you can add additional extras later using the same command.

## 3-Minute Quick Start

Aspara has a simple design that lets you start tracking experiments with just a few lines of code.

```python
import aspara

# Initialize a run (specify project name and config)
aspara.init(
    project="my_project",
    name="my_first_run",
    config={
        "learning_rate": 0.01,
        "batch_size": 32,
    },
)

# Log metrics
aspara.log({
    "loss": 0.5,
    "accuracy": 0.95,
})

# Finish the run
aspara.finish()
```

- `aspara.init(...)`
    - Initializes a project and run.
    - If the specified `project` or `name` does not exist, it will be created.
- `aspara.log({...})`
    - Logs one set of metrics.
      Typically called repeatedly in the training loop for each step or epoch.
- `aspara.finish()`
    - Explicitly ends the run and finalizes any necessary information.

That's all you need for basic setup. Metrics are automatically saved to `~/.local/share/aspara/`.

**Alternative: Using Context Manager**

You can also use `aspara.init()` with the `with` statement. This ensures `finish()` is called automatically when exiting the block:

```python
import aspara

with aspara.init(
    project="my_project",
    name="my_first_run",
    config={"learning_rate": 0.01, "batch_size": 32},
) as run:
    aspara.log({"loss": 0.5, "accuracy": 0.95})
# finish() is called automatically
```

**Tip:** If you want to change the data storage location, see [Configuration (Advanced)](advanced/configuration.md).

## Viewing in the Dashboard

**Try it first:** You can explore the dashboard with sample data at [https://prednext-aspara.hf.space/](https://prednext-aspara.hf.space/) without installing anything.

To visualize your own recorded metrics, launch the dashboard with the following command
(if not installed, install `aspara[dashboard]` as described above).

```bash
# Using aspara serve (recommended)
aspara serve              # Dashboard only
aspara serve together     # Dashboard + Tracker

# Legacy command (still supported)
aspara dashboard

# Specify a custom data directory
aspara serve --data-dir /path/to/data
```

For details on dashboard features and screen layout, see [Advanced: Dashboard](./advanced/dashboard.md).

## Using Tracker (Remote Recording)

Tracker is a feature for sending metrics and artifacts to a remote server via HTTP instead of writing to local disk.
It's useful when you want to aggregate results from multiple machines or clusters in one place.

To enable Tracker, install with the `[tracker]` extras:

```bash
uv pip install "aspara[tracker]"
```

For Tracker setup instructions and API usage, see [Advanced: Tracker API](./advanced/tracker-api.md).

## Next Steps

After trying the basic usage, you can learn more advanced features from the following documentation:

- User Guide
    - [User Guide Overview](user-guide/basics.md)
    - How to organize projects and runs
    - Detailed usage of the wandb-compatible API
    - Best practices

- Advanced Documentation
    - [Advanced: Dashboard](./advanced/dashboard.md)
    - [Advanced: Tracker API](./advanced/tracker-api.md)
    - [Advanced: Configuration and Data Directory](./advanced/configuration.md)
