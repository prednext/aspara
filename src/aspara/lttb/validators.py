"""Functions to check that input data is in a valid format.

This module is based on lttb-numpy by JA Viljoen, licensed under the MIT License.
Original source: https://git.sr.ht/~javiljoen/lttb-numpy
Copyright (c) 2020 JA Viljoen

No modifications have been made to this module.
"""

import numpy as np


def has_two_columns(data):
    """Raise ValueError if ``data`` is not a 2D array with 2 columns."""
    if len(data.shape) != 2:
        raise ValueError("data is not a 2D array")

    if data.shape[1] != 2:
        raise ValueError("data does not have 2 columns")


def x_is_sorted(data):
    """Raise ValueError if the first column of ``data`` is not sorted."""
    if np.any(data[1:, 0] < data[:-1, 0]):
        raise ValueError("data is not sorted on the first column")


def x_is_strictly_increasing(data):
    """Raise ValueError if 1st column is not strictly increasing.

    I.e. if the first column of ``data`` either is not sorted
    or it contains repeated (duplicate) values.
    """
    if np.any(data[1:, 0] <= data[:-1, 0]):
        raise ValueError("first column is not strictly increasing")


def x_is_regular(data):
    """Raise ValueError if 1st column of ``data`` is irregularly spaced.

    I.e. if the intervals between successive values in the first column
    are not constant.
    """
    if len(np.unique(np.diff(data[:, 0]))) != 1:
        raise ValueError("first column is not regularly spaced")


def contains_no_nans(data):
    """Raise ValueError if ``data`` contains any missing/NaN values."""
    if np.any(np.isnan(data)):
        raise ValueError("data contains NaN values")


def validate(data, validators):
    """Check an array against each of the given validators.

    All validators are run (rather than failing at the first error)
    and their error messages are concatenated into the message for the
    raised ``ValueError``, if any.

    Parameters
    ----------
    data : numpy.array
        Data to validate
    validators : sequence of callables
        Validation functions that take an array as argument and
        raise ``ValueError`` if the array fails some criterion

    Raises
    ------
    ValueError
        If any of the validators raise a ``ValueError`` for ``data``
    """
    errors = []

    for validator in validators:
        try:
            validator(data)
        except ValueError as err:
            errors.append(err)

    if errors:
        raise ValueError("; ".join(map(str, errors)))
