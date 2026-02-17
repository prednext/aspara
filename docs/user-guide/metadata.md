# Metadata and Notes

In aspara, you can attach metadata such as tags, notes, and config values to projects and individual runs.
This allows you to record experiment context, hyperparameters, model versions, and more together, making it easier to review later.

This page explains how to set metadata from code, edit notes in the dashboard, and describes the storage location and file structure.

## Setting Metadata from Code

With `aspara.init()`, you can specify tags, notes, and config values associated with a project or run.

```python
import aspara

run = aspara.init(
    project="my_project",
    tags=["baseline", "resnet18"],          # Tags to identify the experiment
    notes="Initial baseline experiment",    # Notes about the experiment's intent
    config={"lr": 0.01}                     # Hyperparameters and other settings
)
```

- **tags**
    - A list of strings to label the run.
    - Useful for representing model architecture, dataset name, experiment version or group name.
- **notes**
    - Saves free-form notes about the experiment's purpose, assumptions, observations, etc.
- **config**
    - A JSON object representing hyperparameters like learning rate and batch size, model and dataset settings, etc.
    - Can also be viewed in the dashboard, which helps with experiment reproducibility.

## Adding/Editing Notes (Dashboard)

You can add or edit notes for projects and runs from the dashboard.

- Project page
    - Select a project to open its project page, then click the "Edit" button in the notes section.
- Run page
    - Select the target run to open its run page, then click the "Edit" button in the notes section.

## Notes Feature Characteristics

- **Inline Editing**
    - Click the "Edit" button in the notes section to edit content directly in place (similar to editing GitHub issue comments).
- **Multi-line Support**
    - Multi-line text with line breaks can be saved as-is. Longer notes or checklists can be recorded.
- **Real-time Saving**
    - Edit content is reflected to the server immediately after saving and is available from other views in the dashboard.
- **Keyboard Shortcuts**
    - `Ctrl + Enter`: Save current edits
    - `Escape`: Cancel editing and revert to original content

## Metadata Storage Location

Metadata, run metrics, and artifacts are stored by default in the following directory structure.
The example below is for the JSONL backend.

```text
~/.local/share/aspara/          # Default (see Advanced Configuration for changing this)
└── project_name/
    ├── metadata.json           # Project metadata
    ├── run_name.jsonl          # Run metrics (for JSONL backend)
    ├── run_name.meta.json      # Run metadata (tags / notes / config / artifacts, etc.)
    └── run_name/
        └── artifacts/          # Artifacts
```

For details on the data directory (default storage location, `ASPARA_DATA_DIR`, `--data-dir` priority, etc.) and storage backends, see [Configuration (Advanced)](../advanced/configuration.md).

> **Note:** Directly editing the JSON files may break consistency.
> We recommend updating through the library or dashboard.

## Metadata Structure

### Project Metadata (`{project}/metadata.json`)

Metadata shared at the project level. Records the project's overall purpose and common settings.

```json
{
  "notes": "This project is for image classification benchmark experiments.\nUsing the CIFAR-10 dataset.",
  "tags": ["image-classification", "CIFAR-10", "ResNet"],
  "created_at": "2025-06-16T10:30:00",
  "updated_at": "2025-06-16T11:15:00"
}
```

- `notes`: Overall description and background of the project
- `tags`: Tags assigned to the project
- `created_at`, `updated_at`: Project metadata creation and update timestamps (ISO 8601 format strings)

### Run Metadata (`{project}/{run}.meta.json`)

Metadata specific to individual runs. Represents the differences and conditions for each experiment.

```json
{
  "run_id": "...",
  "tags": ["baseline", "resnet18"],
  "notes": "Initial baseline experiment",
  "config": {"lr": 0.01},
  "artifacts": [],
  "status": "wip",
  "start_time": "2025-06-16T10:30:00",
  "finish_time": null
}
```

- `run_id`: Unique identifier for the run
- `tags`: Tags assigned to this run
- `notes`: Notes about the run
- `config`: Settings used in this run (hyperparameters, etc.)
- `artifacts`: Information about generated model files, logs, and other artifacts
- `status`: Run state (e.g., in progress, completed)
- `start_time`, `finish_time`: Run start and end timestamps (ISO 8601 format strings)

By combining project and run metadata, you can:

- Project-wide purposes and conditions (project metadata)
- Run-specific settings and results (run metadata)

manage separately, making it easier to organize even large-scale experiments.
