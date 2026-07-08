# Configuration (Advanced)

This page summarizes Aspara's configuration options (environment variables, etc.).

## Data Directory (ASPARA_DATA_DIR)

### Default Storage Location

Aspara follows the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html) and saves logs to the user's data directory by default:

```text
~/.local/share/aspara/{project}/{run_name}.jsonl
```

To change the storage location, set the `ASPARA_DATA_DIR` environment variable, or set `XDG_DATA_HOME` (though the latter affects other applications as well). Additionally, dashboard, tracker, and other commands prioritize the `--data-dir` command line argument over environment variables.

#### Priority Order

1. Command line argument `--data-dir`
2. Environment variable `ASPARA_DATA_DIR`
3. Environment variable `XDG_DATA_HOME/aspara` (if `XDG_DATA_HOME` is set)
4. `~/.local/share/aspara`

### Environment Variables

Aspara references the following environment variables to modify its behavior.

#### ASPARA_DATA_DIR

Setting `ASPARA_DATA_DIR` will save data under that directory.

```bash
# Specify a custom directory
export ASPARA_DATA_DIR="/path/to/my/data"

# All Aspara programs will use the specified directory from now on
python train.py
```

#### XDG_DATA_HOME

If `ASPARA_DATA_DIR` is not set, data is saved under `XDG_DATA_HOME/aspara`.

```bash
export XDG_DATA_HOME="$HOME/.config/data"
# → Aspara uses $HOME/.config/data/aspara
```

### Project-Local Storage

To save to `./data/` within your project directory:

```bash
# Specify via environment variable
export ASPARA_DATA_DIR="./data"
```

Or

```python
# Specify in code
aspara.init(project="my_project", dir="./data")
```

### Dashboard and Data Directory

The dashboard references the same data directory:

```bash
# Default (references ~/.local/share/aspara)
aspara dashboard

# Reference a custom directory
aspara dashboard --data-dir /path/to/data

# Use environment variable
export ASPARA_DATA_DIR="/path/to/data"
aspara dashboard
```

## Metrics Storage Format (ASPARA_STORAGE_BACKEND)

The metrics storage format can be specified with `ASPARA_STORAGE_BACKEND`.

- `jsonl` (default)
- `polars` (experimental)

For details, see [Storage (Advanced)](storage.md).

## Resource Limits

Aspara enforces several resource limits to prevent excessive memory usage and protect the tracker server. All limits (except the artifact upload size) can be customized via environment variables.

### Default Limits

| Resource | Default | Environment Variable |
|----------|---------|----------------------|
| Metrics file size | 1 GB | `ASPARA_MAX_FILE_SIZE` |
| Metrics file lines | 1,000,000 | `ASPARA_MAX_JSONL_LINES` |
| ZIP file size | 1 GB | `ASPARA_MAX_ZIP_SIZE` |
| Metric names (comma-separated) | 100 | `ASPARA_MAX_METRIC_NAMES` |
| Notes length | 10 KB (10,240 chars) | `ASPARA_MAX_NOTES_LENGTH` |
| Tags count | 100 | `ASPARA_MAX_TAGS_COUNT` |
| LTTB downsampling threshold | 1,000 | `ASPARA_LTTB_THRESHOLD` |
| Artifact upload size (tracker) | 100 MB | *(hardcoded, not configurable)* |

### Customizing Limits

Set the environment variables before running your script or starting the dashboard:

```bash
# Increase metrics file size limit to 2GB
export ASPARA_MAX_FILE_SIZE=2147483648

# Allow up to 200 tags
export ASPARA_MAX_TAGS_COUNT=200

# Raise LTTB threshold to reduce downsampling
export ASPARA_LTTB_THRESHOLD=5000

python train.py
```

!!! note "Artifact upload size"
    The 100 MB limit on artifact uploads to the tracker is hardcoded in
    `src/aspara/tracker/router.py` and cannot be changed via environment
    variables. If you need to upload larger files, consider splitting
    them or storing artifacts outside the tracker.

!!! note "Local vs Remote"
    File-size and line-count limits apply when **reading** metrics files
    (e.g., in the dashboard or TUI). The notes and tags limits are
    enforced at write time by the metadata storage layer, so they apply
    to both local and remote runs.
