# Visualizing Results in the Dashboard

This page explains how to view and compare recorded experiment results using the Aspara dashboard.

This page focuses on using the run comparison charts on the project page (`/projects/{project}`).

## Accessing the Dashboard

Start the dashboard with the following command (see Getting Started for details).

```bash
aspara dashboard
```

From the Projects page (`/`) displayed in your browser, click on a project to navigate to its project page.

## Project Page Structure

The project page (`/projects/{project}`) shows the following information:

- Project metadata (tags, notes, etc.)
- Run list (run names, status, metrics summary, etc.)
- Comparison charts for selected runs

The run comparison charts are an area for visualizing multiple runs within the same project together.

## Run Selection and Comparison Charts

In the run list on the project page, each run row has a checkbox.

- Runs with checked checkboxes are displayed in the comparison charts.
- Unchecking removes the corresponding run's line from the chart.
- When you change the check state, the chart updates in real-time with a TensorBoard-like interaction.

This allows you to quickly compare the behavior of multiple runs (e.g., `train/loss`, `val/accuracy`) on a single chart.

## Reading Metrics

In the charts, series with the same metric name are displayed color-coded by run.

- Example: The `train/loss` curves are overlaid for each selected run.
- The legend shows run names and metric names, so you can identify which line corresponds to which run.

Consistent metric naming (e.g., using `train/*`, `val/*` prefixes) makes chart comparisons easier. For naming best practices, see [Best Practices](best-practices.md).

## Typical Comparison Use Cases

Here are some common usage patterns:

- Baseline vs New Approach
    - Select 2-3 runs including a baseline run and runs with new models or methods, then compare convergence differences in `train/loss` or `val/accuracy`.
- Hyperparameter Comparison
    - Select multiple runs with different learning rates or batch sizes to compare which settings result in the most stable training.
- Data Version Comparison
    - Select runs with different data preprocessing or versions to visualize the impact on performance.

## Tips for Keeping Display Light

Displaying many runs or metrics simultaneously can slow down browser rendering. Keep the following in mind for a smooth experience:

- Only select runs you want to compare, uncheck unnecessary runs
- Focus on important metrics (e.g., `train/loss`, `val/accuracy`) when recording and viewing
- Adjust settings as needed according to [Troubleshooting](troubleshooting.md)

By leveraging run comparison charts on the project page, you can efficiently analyze experiment results from the Aspara dashboard.
