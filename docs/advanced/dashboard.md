# Dashboard (Advanced)

This page covers advanced topics for the dashboard, including operations, detailed settings, and API usage.

## Starting the Dashboard

### Using `aspara serve` (Recommended)

The `aspara serve` command provides a unified way to start server components:

```bash
aspara serve              # Dashboard only (default, port 3141)
aspara serve dashboard    # Dashboard only (explicit)
aspara serve tracker      # Tracker only (port 3142)
aspara serve together     # Dashboard + Tracker (port 3141)
```

**Options:**
```bash
aspara serve --host 0.0.0.0 --port 3000    # Customize host and port
aspara serve --data-dir /custom/path       # Specify data directory
aspara serve --dev                         # Development mode with auto-reload
```

### Legacy Commands (Still Supported)

The following commands are still available for backward compatibility:

```bash
aspara dashboard              # Dashboard only
aspara dashboard --with-tracker  # Dashboard + Tracker
aspara tracker                # Tracker only
```

**Features of integrated mode (`together` or `--with-tracker`):**
- Full functionality with a single command
- Dashboard + tracker integration
- Supports both LocalRun and RemoteRun

**Use cases:**
- When you want full features easily
- Development and test environments

## Other Options

```bash
# Using aspara serve (recommended)
aspara serve --host 0.0.0.0 --port 3000
aspara serve --data-dir /custom/path

# Using legacy commands
aspara dashboard --host 0.0.0.0 --port 3000
aspara dashboard --data-dir /custom/path

# Specify data directory via environment variable
export ASPARA_DATA_DIR="/custom/path"
aspara serve
```

## Project Search Mode

On the Projects page (`/`), you can search by both project name and project tags.

- Input field placeholder: `Search by project name or tags...`
- Search targets:
    - Project name
    - `tags` written in project metadata (`<data_dir>/<project>/metadata.json`)

You can select from **two search modes**:

- `realtime` mode
    - Filters in real-time with 300ms debounce as you type
    - Results update as you type
- `manual` mode
    - Search executes when you press the Search button or Enter key
    - For when you want to confirm input before updating results

How to specify the mode:

```bash
# Using aspara serve (recommended)
aspara serve --project-search-mode realtime  # default
aspara serve --project-search-mode manual

# Using legacy command
aspara dashboard --project-search-mode realtime
aspara dashboard --project-search-mode manual

# Can also specify via environment variable
export ASPARA_PROJECT_SEARCH_MODE="manual"
aspara serve
```

If an invalid value is set or not specified, it automatically falls back to `realtime` mode.

## Environment Variables

### ASPARA_DATA_DIR

Specifies the data directory path.

```bash
export ASPARA_DATA_DIR="/custom/path"
aspara serve
```

By default, the data directory is determined in the following priority order:
1. `ASPARA_DATA_DIR` environment variable (if set)
2. `XDG_DATA_HOME/aspara` (if `XDG_DATA_HOME` is set)
3. `~/.local/share/aspara` (fallback)

### ASPARA_LTTB_THRESHOLD

Sets the threshold for downsampling large amounts of metrics data. Default is `1000` points.

```bash
export ASPARA_LTTB_THRESHOLD=50000
aspara serve
```

When the number of data points in a metric series exceeds this threshold, automatic downsampling is performed using the [LTTB (Largest-Triangle-Three-Buckets) algorithm](https://github.com/sveinn-steinarsson/flot-downsample).

**LTTB Features:**
- Downsamples while preserving the visual shape of data
- Prevents browser crashes
- Improves chart rendering performance
- Saves network bandwidth

## Dashboard API

For detailed API documentation, see the [Dashboard API Reference](../api/dashboard.md).
