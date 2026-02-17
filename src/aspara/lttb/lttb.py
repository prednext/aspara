"""Downsample data using the Largest-Triangle-Three-Buckets algorithm.

This module is based on lttb-numpy by JA Viljoen, licensed under the MIT License.
Original source: https://git.sr.ht/~javiljoen/lttb-numpy
Copyright (c) 2020 JA Viljoen

Modifications for Aspara:
- Optimized bin centroid calculation using np.add.reduceat
- Removed conditional branch in main loop
- Optimized _areas_of_triangles function (removed redundant operations, 0.5 factor)

Reference
---------
Sveinn Steinarsson. 2013. Downsampling Time Series for Visual
Representation. MSc thesis. University of Iceland.
"""

from __future__ import annotations

import numpy as np

from .validators import (
    contains_no_nans,
    has_two_columns,
    validate,
    x_is_strictly_increasing,
)

default_validators = [has_two_columns, contains_no_nans, x_is_strictly_increasing]


def _areas_of_triangles(a, bs, c):
    """Calculate areas of triangles from duples of vertex coordinates.

    Uses implicit numpy broadcasting along first axis of ``bs``.

    Note: Returns 2x the actual area since we only need relative magnitudes
    for comparison (argmax), not absolute areas.

    Returns
    -------
    numpy.array
        Array of area measures of shape (len(bs),)
    """
    # Optimized: removed redundant subtraction, use np.abs, and removed 0.5 factor
    # (not needed since we only compare relative magnitudes)
    return np.abs((a[0] - c[0]) * (bs[:, 1] - a[1]) + (bs[:, 0] - a[0]) * (c[1] - a[1]))


def _areas_of_triangles_vectorized(a_points, b_points, c_points):
    """Calculate areas of triangles with vectorized a and c points.

    This is a fully vectorized version where a, b, and c are all arrays
    of the same length, representing multiple triangles.

    Parameters
    ----------
    a_points : numpy.array
        Array of shape (n, 2) representing the first vertices
    b_points : numpy.array
        Array of shape (n, 2) representing the second vertices
    c_points : numpy.array
        Array of shape (n, 2) representing the third vertices

    Returns
    -------
    numpy.array
        Array of area measures of shape (n,)
    """
    return np.abs((a_points[:, 0] - c_points[:, 0]) * (b_points[:, 1] - a_points[:, 1]) + (b_points[:, 0] - a_points[:, 0]) * (c_points[:, 1] - a_points[:, 1]))


def downsample(data, n_out, validators=default_validators, return_indices=False):
    """Downsample ``data`` to ``n_out`` points using the LTTB algorithm.

    Parameters
    ----------
    data : numpy.array
        A 2-dimensional array with time values in the first column
    n_out : int
        Number of data points to downsample to
    validators : sequence of callables, optional
        Validation functions that take an array as argument and
        raise ``ValueError`` if the array fails some criterion
    return_indices : bool, optional
        If True, also return the indices of selected points in the original data array

    Constraints
    -----------
      - ncols(data) == 2
      - 3 <= n_out <= nrows(data)
      - the first column of ``data`` should be strictly monotonic.

    Returns
    -------
    numpy.array or tuple
        If return_indices is False: Array of shape (n_out, 2)
        If return_indices is True: Tuple of (array of shape (n_out, 2), array of indices)

    Raises
    ------
    ValueError
        If ``data`` fails the validation checks,
        or if ``n_out`` falls outside the valid range.
    """
    # Validate input
    validate(data, validators)

    if n_out > data.shape[0]:
        raise ValueError("n_out must be <= number of rows in data")

    if n_out == data.shape[0]:
        if return_indices:
            return data, np.arange(len(data))
        return data

    if n_out < 3:
        raise ValueError("Can only downsample to a minimum of 3 points")

    # Split data into bins
    n_bins = n_out - 2
    middle_data = data[1:-1]

    # Pre-compute centroids of all bins using vectorized operations
    # Calculate bin boundaries
    bin_edges = np.linspace(0, len(middle_data), n_bins + 1, dtype=int)

    # Calculate sum for each bin using reduceat (vectorized operation)
    bin_sums = np.add.reduceat(middle_data, bin_edges[:-1], axis=0)

    # Calculate bin sizes and compute means
    bin_sizes = np.diff(bin_edges)
    bin_centroids_data = bin_sums / bin_sizes[:, np.newaxis]

    # Append the last data point to eliminate conditional branch in loop
    bin_centroids = np.vstack([bin_centroids_data, data[-1]])

    # Prepare output array
    # First and last points are the same as in the input.
    out = np.zeros((n_out, 2))
    out[0] = data[0]
    out[-1] = data[-1]

    # Track indices if requested
    if return_indices:
        indices = np.zeros(n_out, dtype=int)
        indices[0] = 0
        indices[-1] = len(data) - 1

    # Largest Triangle Three Buckets (LTTB):
    # In each bin, find the point that makes the largest triangle
    # with the point saved in the previous bin
    # and the centroid of the points in the next bin.
    for i in range(n_bins):
        # Extract this bin's data using pre-computed bin edges
        bin_start = bin_edges[i]
        bin_end = bin_edges[i + 1]
        this_bin = middle_data[bin_start:bin_end]

        a = out[i]
        bs = this_bin
        c = bin_centroids[i + 1]  # No conditional needed!

        areas = _areas_of_triangles(a, bs, c)
        local_idx = np.argmax(areas)

        out[i + 1] = bs[local_idx]

        if return_indices:
            # Convert local bin index to global data index
            # +1 because middle_data starts at index 1
            indices[i + 1] = bin_start + local_idx + 1

    if return_indices:
        return out, indices
    return out


def downsample_fast(data, n_out, validators=default_validators):
    """Downsample using a faster variant of LTTB with centroid-based previous points.

    This is a modified version of LTTB that uses bin centroids for the previous point (A)
    instead of the actually selected point. This eliminates loop dependencies and enables
    full vectorization, at the cost of slightly different downsampling behavior.

    Parameters
    ----------
    data : numpy.array
        A 2-dimensional array with time values in the first column
    n_out : int
        Number of data points to downsample to
    validators : sequence of callables, optional
        Validation functions that take an array as argument and
        raise ``ValueError`` if the array fails some criterion

    Constraints
    -----------
      - ncols(data) == 2
      - 3 <= n_out <= nrows(data)
      - the first column of ``data`` should be strictly monotonic.

    Returns
    -------
    numpy.array
        Array of shape (n_out, 2)

    Raises
    ------
    ValueError
        If ``data`` fails the validation checks,
        or if ``n_out`` falls outside the valid range.
    """
    # Validate input
    validate(data, validators)

    if n_out > data.shape[0]:
        raise ValueError("n_out must be <= number of rows in data")

    if n_out == data.shape[0]:
        return data

    if n_out < 3:
        raise ValueError("Can only downsample to a minimum of 3 points")

    # Split data into bins
    n_bins = n_out - 2
    middle_data = data[1:-1]

    # Pre-compute centroids of all bins using vectorized operations
    bin_edges = np.linspace(0, len(middle_data), n_bins + 1, dtype=int)
    bin_sums = np.add.reduceat(middle_data, bin_edges[:-1], axis=0)
    bin_sizes = np.diff(bin_edges)
    bin_centroids = bin_sums / bin_sizes[:, np.newaxis]

    # Prepare A points (previous bin's centroid or first point for first bin)
    a_points = np.vstack([data[0:1], bin_centroids[:-1]])  # Shape: (n_bins, 2)

    # Prepare C points (next bin's centroid or last point for last bin)
    c_points = np.vstack([bin_centroids[1:], data[-1:]])  # Shape: (n_bins, 2)

    # Repeat A and C points to match each candidate point in their respective bins
    a_repeated = np.repeat(a_points, bin_sizes, axis=0)  # Shape: (total_points, 2)
    c_repeated = np.repeat(c_points, bin_sizes, axis=0)  # Shape: (total_points, 2)

    # Calculate all triangle areas at once (fully vectorized)
    all_areas = _areas_of_triangles_vectorized(a_repeated, middle_data, c_repeated)

    # Find the point with maximum area in each bin
    # Split areas back into bins and find argmax for each bin
    area_bins = np.split(all_areas, bin_edges[1:-1])
    selected_indices = np.array([np.argmax(bin_areas) for bin_areas in area_bins])

    # Convert local bin indices to global middle_data indices
    global_indices = bin_edges[:-1] + selected_indices

    # Prepare output array
    out = np.zeros((n_out, 2))
    out[0] = data[0]
    out[-1] = data[-1]
    out[1:-1] = middle_data[global_indices]

    return out


def downsample_fast_v2(data, n_out, validators=default_validators):
    """Two-stage LTTB downsampling for improved quality with vectorization.

    This variant performs LTTB in two stages:
    1. First stage: Use downsample_fast to get initial point selection
    2. Second stage: Use the selected points from stage 1 as fixed A points,
       and recompute optimal B points with full vectorization

    This approach balances quality and speed - better than fast variant,
    faster than original LTTB.

    Parameters
    ----------
    data : numpy.array
        A 2-dimensional array with time values in the first column
    n_out : int
        Number of data points to downsample to
    validators : sequence of callables, optional
        Validation functions that take an array as argument and
        raise ``ValueError`` if the array fails some criterion

    Constraints
    -----------
      - ncols(data) == 2
      - 3 <= n_out <= nrows(data)
      - the first column of ``data`` should be strictly monotonic.

    Returns
    -------
    numpy.array
        Array of shape (n_out, 2)

    Raises
    ------
    ValueError
        If ``data`` fails the validation checks,
        or if ``n_out`` falls outside the valid range.
    """
    # Validate input
    validate(data, validators)

    if n_out > data.shape[0]:
        raise ValueError("n_out must be <= number of rows in data")

    if n_out == data.shape[0]:
        return data

    if n_out < 3:
        raise ValueError("Can only downsample to a minimum of 3 points")

    # Stage 1: Get initial selection using fast variant
    initial_selection = downsample_fast(data, n_out, validators=[])

    # Stage 2: Refine selection using initial points as fixed A points
    n_bins = n_out - 2
    middle_data = data[1:-1]

    # Calculate bin boundaries
    bin_edges = np.linspace(0, len(middle_data), n_bins + 1, dtype=int)
    bin_sizes = np.diff(bin_edges)

    # Pre-compute centroids for C points (next bin)
    bin_sums = np.add.reduceat(middle_data, bin_edges[:-1], axis=0)
    bin_centroids = bin_sums / bin_sizes[:, np.newaxis]

    # Prepare A points from initial selection
    # A[i] = initial_selection[i] for bin i (i=0 to n_bins-1)
    a_points = initial_selection[:n_bins]  # Shape: (n_bins, 2)

    # Prepare C points (next bin's centroid or last point for last bin)
    c_points = np.vstack([bin_centroids[1:], data[-1:]])  # Shape: (n_bins, 2)

    # Repeat A and C points to match each candidate point in their respective bins
    a_repeated = np.repeat(a_points, bin_sizes, axis=0)  # Shape: (total_points, 2)
    c_repeated = np.repeat(c_points, bin_sizes, axis=0)  # Shape: (total_points, 2)

    # Calculate all triangle areas at once (fully vectorized)
    all_areas = _areas_of_triangles_vectorized(a_repeated, middle_data, c_repeated)

    # Find the point with maximum area in each bin
    area_bins = np.split(all_areas, bin_edges[1:-1])
    selected_indices = np.array([np.argmax(bin_areas) for bin_areas in area_bins])

    # Convert local bin indices to global middle_data indices
    global_indices = bin_edges[:-1] + selected_indices

    # Prepare output array
    out = np.zeros((n_out, 2))
    out[0] = data[0]
    out[-1] = data[-1]
    out[1:-1] = middle_data[global_indices]

    return out


def downsample_fast_v3(data, n_out, validators=default_validators):
    """Interleaved LTTB downsampling combining v2 and original algorithms.

    This variant combines two approaches by interleaving their results:
    - Odd-indexed points: Use downsample_fast_v2 (fast, centroid-based refinement)
    - Even-indexed points: Use downsample (original, high quality)

    This approach aims to balance quality and speed by mixing both algorithms.

    Parameters
    ----------
    data : numpy.array
        A 2-dimensional array with time values in the first column
    n_out : int
        Number of data points to downsample to
    validators : sequence of callables, optional
        Validation functions that take an array as argument and
        raise ``ValueError`` if the array fails some criterion

    Constraints
    -----------
      - ncols(data) == 2
      - 3 <= n_out <= nrows(data)
      - the first column of ``data`` should be strictly monotonic.

    Returns
    -------
    numpy.array
        Array of shape (n_out, 2)

    Raises
    ------
    ValueError
        If ``data`` fails the validation checks,
        or if ``n_out`` falls outside the valid range.
    """
    # Validate input
    validate(data, validators)

    if n_out > data.shape[0]:
        raise ValueError("n_out must be <= number of rows in data")

    if n_out == data.shape[0]:
        return data

    if n_out < 3:
        raise ValueError("Can only downsample to a minimum of 3 points")

    # Get results from both algorithms
    result_v2 = downsample_fast_v2(data, n_out, validators=[])
    result_original = downsample(data, n_out, validators=[])

    # Prepare output array
    out = np.zeros((n_out, 2))
    out[0] = data[0]  # First point is always the same
    out[-1] = data[-1]  # Last point is always the same

    # Interleave: odd indices from v2, even indices from original
    for i in range(1, n_out - 1):
        if i % 2 == 1:  # Odd index
            out[i] = result_v2[i]
        else:  # Even index
            out[i] = result_original[i]

    return out
