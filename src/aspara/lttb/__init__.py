"""LTTB (Largest Triangle Three Buckets) downsampling implementation.

This module is based on lttb-numpy by JA Viljoen, licensed under the MIT License.
Original source: https://git.sr.ht/~javiljoen/lttb-numpy
Copyright (c) 2020 JA Viljoen

This is a local optimized copy for Aspara. See LICENSE file for full license text.
See lttb.py for details on optimizations applied.
"""

from .lttb import downsample as _downsample_original
from .lttb import downsample_fast as _downsample_fast
from .lttb import downsample_fast_v2 as _downsample_fast_v2
from .lttb import downsample_fast_v3 as _downsample_fast_v3


def downsample(data, n_out, validators=None, return_indices=False):
    """Downsample data using LTTB algorithm.

    The implementation can be switched between the original LTTB and a faster
    centroid-based variant using the ASPARA_LTTB_FAST environment variable.

    - ASPARA_LTTB_FAST=0 or unset: Use original LTTB (default)
    - ASPARA_LTTB_FAST=1: Use faster centroid-based variant

    Parameters
    ----------
    data : numpy.array
        A 2-dimensional array with time values in the first column
    n_out : int
        Number of data points to downsample to
    validators : sequence of callables, optional
        Validation functions to apply
    return_indices : bool, optional
        If True, also return the indices of selected points

    Returns
    -------
    numpy.array or tuple
        If return_indices is False: Downsampled array of shape (n_out, 2)
        If return_indices is True: Tuple of (downsampled array, indices array)
    """
    from aspara.config import use_lttb_fast

    use_fast = use_lttb_fast()

    if use_fast:
        if validators is None:
            return _downsample_fast(data, n_out)
        return _downsample_fast(data, n_out, validators)
    else:
        if validators is None:
            return _downsample_original(data, n_out, return_indices=return_indices)
        return _downsample_original(data, n_out, validators, return_indices=return_indices)


__all__ = ["downsample", "downsample_fast", "downsample_fast_v2", "downsample_fast_v3"]

# Re-export for direct access if needed
downsample_fast = _downsample_fast
downsample_fast_v2 = _downsample_fast_v2
downsample_fast_v3 = _downsample_fast_v3
