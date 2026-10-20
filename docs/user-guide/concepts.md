# Core Concepts

This page introduces the fundamental concepts and overall architecture of Aspara. Understanding these terms will make it easier to follow the rest of the User Guide.

## Overview of Aspara

Aspara is a lightweight experiment tracking tool that saves machine learning experiment results locally or remotely and allows you to visualize and compare them in a dashboard.

- Experiments are recorded as **Runs**.
- Multiple runs are organized into **Projects**.
- Each run has associated **Metrics**, **Config**, and **Metadata (tags / notes / artifacts / status)**.

## Projects and Runs

Aspara organizes experiments in a 2-level hierarchy.

```text
project/                    # High-level task (e.g., image classification)
  run.jsonl                 # Individual run metrics
```

- **Project**
    - Represents a single problem domain or experiment theme (e.g., image classification, recommendation system).
    - Acts as a "folder" that groups multiple runs with the same purpose.
- **Run**
    - Represents a single execution of training or evaluation.
    - Different hyperparameters or code versions should be recorded as separate runs.

```python
import aspara

# Initialize a run
aspara.init(
    project="image-classification",    # Project name
    name="resnet18-adam-lr0.01",       # Run name
    config={
        "model": "resnet18",
        "optimizer": "adam",
        "learning_rate": 0.01,
    },
)
```

## Metrics and Config

Aspara separately records **input conditions** as config and **results** as metrics.

- **Config**
    - A dictionary of input conditions for the experiment (model configuration, learning rate, batch size, dataset name, etc.).
    - Saved via `aspara.init(config=...)` and can be used later for reproducibility verification and comparison.
- **Metrics**
    - Numerical results such as loss or accuracy during training or evaluation.
    - Saved as time series via `aspara.log({...})` and displayed as charts in the dashboard.

For more practical recording patterns and naming tips, see [Best Practices](best-practices.md).

## Metadata (Tags, Notes, Artifacts, Status)

Each project and run can have various metadata beyond metrics.

- **Tags**
    - Labels representing model type, dataset, experiment group name, etc.
    - Can be used for searching and filtering in the dashboard.
- **Notes**
    - Free-form text for recording experiment purposes, assumptions, observations, etc.
- **Artifacts**
    - Files associated with the run, such as trained models, log files, configuration files, etc.
    - Uploads to the tracker are limited to 100 MB per file.
- **Status**
    - A field representing the run's state (running, completed, etc.).

For details on metadata structure and storage location, see [Metadata and Notes](metadata.md).

## Data Directory and Storage

Aspara saves all metrics, metadata, and artifacts under a **data directory**.

- The default storage location is `~/.local/share/aspara`.
- Can be changed via the `ASPARA_DATA_DIR` environment variable or the CLI `--data-dir` option.
- The storage format for metrics (JSONL / Polars, etc.) is determined by the storage backend.

For details, see [Configuration (Advanced)](../advanced/configuration.md) and [Storage (Advanced)](../advanced/storage.md).

## Local files and a Tracker copy

`aspara.init()` always writes metrics and metadata to the local data directory.

- **Local only** (default)
    - Omit `tracker_uri`.
    - Suitable for a laptop or a single machine.
- **With a Tracker**
    - Set `tracker_uri`, or `ASPARA_TRACKER_URI`.
    - Local files remain the record. A copy is queued and sent to the Tracker in the background.
    - `log()` does not wait for the Tracker. If the Tracker is down, logging still succeeds.
    - Useful when several machines should show up in one Tracker.
    - A loopback Tracker that already stores this directory does not keep a second copy.

See [Local files and a Tracker copy](../advanced/local-vs-remote.md) and [Tracker API](../advanced/tracker-api.md).
