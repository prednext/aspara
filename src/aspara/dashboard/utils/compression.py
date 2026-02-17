"""
Metrics transformation utilities for dashboard.

This module provides functions for downsampling and compressing metrics data
for efficient transfer to the frontend.
"""

from __future__ import annotations

import logging
import time

import numpy as np
import polars as pl

from aspara import lttb
from aspara.config import get_resource_limits

logger = logging.getLogger(__name__)


def delta_compress(values: list[int | float]) -> list[int | float]:
    """Delta-compress a sequence using NumPy.

    Args:
        values: List of numeric values

    Returns:
        Delta-compressed list where first value is absolute,
        subsequent values are deltas from previous value
    """
    if not values:
        return []
    arr = np.asarray(values)
    deltas = np.concatenate([[arr[0]], np.diff(arr)])
    return deltas.tolist()


def compress_metrics(df: pl.DataFrame) -> dict[str, dict[str, list]]:
    """Compress metrics DataFrame for API response.

    Applies LTTB downsampling and delta compression to reduce data size.
    Optimized for performance by applying LTTB during DataFrame processing.

    Args:
        df: Wide-format DataFrame with columns: timestamp, step, _<metric_name>

    Returns:
        Metric-first format with delta-compressed arrays:
        {metric_name: {steps: [...], values: [...], timestamps: [...]}}
        - steps: delta-compressed (monotonically increasing)
        - timestamps: unix time in milliseconds, delta-compressed
    """
    if len(df) == 0:
        return {}

    limits = get_resource_limits()
    threshold = limits.lttb_threshold

    # Get all metric columns (those starting with underscore)
    metric_cols = [col for col in df.columns if col.startswith("_")]

    if not metric_cols:
        return {}

    logger.debug(f"[LTTB] Starting downsampling: {len(df)} rows, {len(metric_cols)} metrics")
    start_total = time.time()

    # 1.2 Optimization: Pre-convert timestamp to milliseconds once before the loop
    t1 = time.time()
    df = df.with_columns(pl.col("timestamp").dt.epoch(time_unit="ms").alias("timestamp_ms"))
    t2 = time.time()
    logger.debug(f"[LTTB] Pre-convert timestamp_ms: {(t2 - t1) * 1000:.1f}ms")

    result: dict[str, dict[str, list]] = {}

    for i, metric_col in enumerate(metric_cols):
        start_metric = time.time()
        metric_name = metric_col[1:]  # Remove underscore prefix

        # Extract step, value, and timestamp_ms for this metric, dropping nulls
        t1 = time.time()
        metric_data = df.select(["step", metric_col, "timestamp_ms"]).drop_nulls()
        t2 = time.time()
        logger.debug(f"  [Metric {i + 1}/{len(metric_cols)}] select+drop_nulls: {(t2 - t1) * 1000:.1f}ms ({len(metric_data)} rows)")

        if len(metric_data) == 0:
            continue

        if len(metric_data) <= threshold:
            # No downsampling needed - extract all columns at once
            t1 = time.time()
            # 1.3 Optimization: Single extraction for all columns
            steps = metric_data["step"].to_list()
            values = metric_data[metric_col].to_list()
            timestamps_ms = metric_data["timestamp_ms"].to_list()
            t2 = time.time()
            logger.debug(f"  [Metric {i + 1}/{len(metric_cols)}] to_list (no downsample): {(t2 - t1) * 1000:.1f}ms")
        else:
            # Prepare data for LTTB: [[step, value], ...]
            t1 = time.time()
            lttb_input = metric_data.select(["step", metric_col]).to_numpy()
            t2 = time.time()
            logger.debug(f"  [Metric {i + 1}/{len(metric_cols)}] to_numpy: {(t2 - t1) * 1000:.1f}ms")

            # Apply LTTB downsampling with indices
            t1 = time.time()
            lttb_output, indices = lttb.downsample(lttb_input, n_out=threshold, return_indices=True)
            t2 = time.time()
            logger.debug(f"  [Metric {i + 1}/{len(metric_cols)}] lttb.downsample: {(t2 - t1) * 1000:.1f}ms ({len(lttb_output)} out)")

            # 1.3 Optimization: Single index operation then extract all columns
            t1 = time.time()
            selected = metric_data[indices]
            steps = selected["step"].to_list()
            values = selected[metric_col].to_list()
            timestamps_ms = selected["timestamp_ms"].to_list()
            t2 = time.time()
            logger.debug(f"  [Metric {i + 1}/{len(metric_cols)}] extract by indices: {(t2 - t1) * 1000:.1f}ms")

        # Delta-compress steps and timestamps (monotonically increasing)
        # 1.4 Optimization: Uses NumPy vectorized delta_compress
        t1 = time.time()
        steps_delta = delta_compress(steps)
        timestamps_delta = delta_compress(timestamps_ms)
        t2 = time.time()
        logger.debug(f"  [Metric {i + 1}/{len(metric_cols)}] delta compression: {(t2 - t1) * 1000:.1f}ms")

        result[metric_name] = {
            "steps": steps_delta,
            "values": values,
            "timestamps": timestamps_delta,
        }

        elapsed_metric = time.time() - start_metric
        logger.debug(f"  [Metric {i + 1}/{len(metric_cols)}] TOTAL: {elapsed_metric * 1000:.1f}ms")

    elapsed_total = time.time() - start_total
    logger.debug(f"[LTTB] TOTAL: {elapsed_total * 1000:.1f}ms -> {len(result)} metrics")

    return result
