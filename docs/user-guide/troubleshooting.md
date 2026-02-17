# Troubleshooting

This page summarizes common issues that may occur when using Aspara and their troubleshooting steps. For detailed settings and environment variables, also refer to [Configuration (Advanced)](../advanced/configuration.md) and [Dashboard (Advanced)](../advanced/dashboard.md).

## Logs Not Being Saved

Check the following items in order:

- **Directory write permissions**
    - Make sure you have write permissions for the directory specified by `ASPARA_DATA_DIR` or `--data-dir`.
- **Disk space**
    - If the disk is full, log file creation or appending may fail.
- **Path specification errors**
    - If using a relative path, files may be saved in a different directory than expected. Use an absolute path or verify the current directory.
- **Check the active data directory**
    - Check which data directory is active in your execution environment:
        - `ASPARA_DATA_DIR` environment variable
        - `XDG_DATA_HOME` (if set)
        - `dir` parameter in code
    - For priority details, see [Configuration (Advanced)](../advanced/configuration.md).
- **Script exceptions**
    - If `aspara.init()` or `aspara.log()` calls fail with exceptions, log files won't be created. Check your script's stdout and error logs.

## Not Appearing in Dashboard

If "log files exist but runs don't appear in the dashboard," check the following:

- **Data directory mismatch**
    - Make sure the training script and dashboard are referencing the same data directory:
        - Script side: `ASPARA_DATA_DIR` / `dir` parameter
        - Dashboard side: `ASPARA_DATA_DIR` / `--data-dir`
- **Log file format correctness**
    - For the JSONL backend, each line must be valid JSON.
    - Confirm that middle lines haven't been corrupted by manual editing.
- **File corruption**
    - Opening and saving with some tools may change line endings or encoding. Open with a text editor and verify the JSON format is intact.
- **Project search mode behavior**
    - When searching on the Projects page (`/`), `manual` mode won't update results until you press the Search button or Enter key.
    - For mode and behavior details, see [Dashboard (Advanced)](../advanced/dashboard.md).

## Tracker (Remote Recording) Not Working

Troubleshooting points when using RemoteRun or Tracker API and metrics aren't being sent or errors occur:

- **Is the Tracker server running?**
    - Execute `aspara tracker --host ... --port ...` and verify the process is running.
    - You can check if the health check passes by accessing `http://{host}:{port}/tracker/api/v1/health` in a browser.
- **URL/port setting mismatch**
    - If launching the dashboard with `--tracker-uri`, verify the specified URL matches the actual Tracker server address.
- **Network access restrictions**
    - When running Tracker on Docker containers or remote servers, firewall or port forwarding settings may be required.

For Tracker API startup methods and endpoint details, see [Tracker API (Advanced)](../advanced/tracker-api.md).

## Dashboard Slow / Charts Freezing

When displaying large amounts of metrics, browser rendering may become slow.

- **Adjust LTTB threshold (ASPARA_LTTB_THRESHOLD)**
    - Lowering the downsampling threshold reduces the number of points to render, improving performance.
    - For details, see [Dashboard (Advanced)](../advanced/dashboard.md#aspara_lttb_threshold).
- **Filter runs and metrics to display**
    - On the project page, limiting comparison targets to the minimum necessary runs and metrics reduces rendering load.

If problems persist, please open an issue with your environment information (OS / browser / Aspara version) to help with investigation.
