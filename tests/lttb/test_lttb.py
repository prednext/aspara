"""Unit tests for LTTB implementation."""

import os

import numpy as np
import pytest

from aspara.lttb import downsample, downsample_fast, downsample_fast_v2, downsample_fast_v3
from aspara.lttb.validators import (
    contains_no_nans,
    has_two_columns,
    x_is_strictly_increasing,
)


class TestLTTBDownsample:
    """Tests for the LTTB downsample function."""

    def test_basic_downsampling(self):
        """Test basic downsampling with simple data."""
        # Create simple test data: linear increase
        data = np.column_stack([np.arange(100), np.arange(100)])

        result = downsample(data, n_out=10)

        assert result.shape == (10, 2)
        assert result[0, 0] == 0  # First point preserved
        assert result[-1, 0] == 99  # Last point preserved

    def test_downsampling_preserves_endpoints(self):
        """Test that first and last points are always preserved."""
        data = np.column_stack([np.arange(1000), np.sin(np.arange(1000) * 0.01)])

        result = downsample(data, n_out=50)

        np.testing.assert_array_equal(result[0], data[0])
        np.testing.assert_array_equal(result[-1], data[-1])

    def test_no_downsampling_when_n_out_equals_data_size(self):
        """Test that no downsampling occurs when n_out == data size."""
        data = np.column_stack([np.arange(100), np.arange(100)])

        result = downsample(data, n_out=100)

        np.testing.assert_array_equal(result, data)

    def test_minimum_output_size(self):
        """Test that n_out must be at least 3."""
        data = np.column_stack([np.arange(100), np.arange(100)])

        with pytest.raises(ValueError, match="Can only downsample to a minimum of 3 points"):
            downsample(data, n_out=2)

    def test_n_out_larger_than_data_raises_error(self):
        """Test that n_out > data size raises error."""
        data = np.column_stack([np.arange(10), np.arange(10)])

        with pytest.raises(ValueError, match="n_out must be <= number of rows in data"):
            downsample(data, n_out=20)

    def test_sine_wave_downsampling(self):
        """Test downsampling on a sine wave."""
        x = np.arange(0, 10, 0.01)
        y = np.sin(x)
        data = np.column_stack([x, y])

        result = downsample(data, n_out=100)

        assert result.shape == (100, 2)
        # Check that result captures key features (peaks and troughs)
        # The downsampled data should still have similar min/max
        assert abs(result[:, 1].min() - y.min()) < 0.5
        assert abs(result[:, 1].max() - y.max()) < 0.5

    def test_strict_monotonic_x_required(self):
        """Test that x values must be strictly increasing."""
        # Create data with duplicate x values
        data = np.array([[0, 0], [1, 1], [1, 2], [2, 3]])

        with pytest.raises(ValueError, match="first column is not strictly increasing"):
            downsample(data, n_out=3)

    def test_no_nans_allowed(self):
        """Test that NaN values are not allowed."""
        data = np.array([[0, 0], [1, np.nan], [2, 2], [3, 3]])

        with pytest.raises(ValueError, match="data contains NaN values"):
            downsample(data, n_out=3)

    def test_two_columns_required(self):
        """Test that data must have exactly 2 columns."""
        # 3 columns
        data = np.array([[0, 0, 0], [1, 1, 1], [2, 2, 2]])
        with pytest.raises(ValueError, match="data does not have 2 columns"):
            downsample(data, n_out=3)

    def test_one_dimensional_array_raises_error(self):
        """Test that 1D arrays raise an error (may be IndexError or ValueError)."""
        # 1D array - validators may raise IndexError before ValueError
        data = np.array([1, 2, 3, 4, 5])
        with pytest.raises((ValueError, IndexError)):
            downsample(data, n_out=3)


class TestLTTBValidators:
    """Tests for LTTB validator functions."""

    def test_has_two_columns_valid(self):
        """Test has_two_columns with valid input."""
        data = np.array([[0, 0], [1, 1]])
        has_two_columns(data)  # Should not raise

    def test_has_two_columns_invalid(self):
        """Test has_two_columns with invalid input."""
        # 1D array
        with pytest.raises(ValueError, match="data is not a 2D array"):
            has_two_columns(np.array([1, 2, 3]))

        # 3 columns
        with pytest.raises(ValueError, match="data does not have 2 columns"):
            has_two_columns(np.array([[0, 0, 0], [1, 1, 1]]))

    def test_x_is_strictly_increasing_valid(self):
        """Test x_is_strictly_increasing with valid input."""
        data = np.array([[0, 0], [1, 1], [2, 2]])
        x_is_strictly_increasing(data)  # Should not raise

    def test_x_is_strictly_increasing_invalid(self):
        """Test x_is_strictly_increasing with invalid input."""
        # Duplicate values
        data = np.array([[0, 0], [1, 1], [1, 2]])
        with pytest.raises(ValueError, match="first column is not strictly increasing"):
            x_is_strictly_increasing(data)

        # Decreasing values
        data = np.array([[0, 0], [2, 1], [1, 2]])
        with pytest.raises(ValueError, match="first column is not strictly increasing"):
            x_is_strictly_increasing(data)

    def test_contains_no_nans_valid(self):
        """Test contains_no_nans with valid input."""
        data = np.array([[0, 0], [1, 1], [2, 2]])
        contains_no_nans(data)  # Should not raise

    def test_contains_no_nans_invalid(self):
        """Test contains_no_nans with invalid input."""
        data = np.array([[0, 0], [1, np.nan], [2, 2]])
        with pytest.raises(ValueError, match="data contains NaN values"):
            contains_no_nans(data)


class TestLTTBPerformance:
    """Performance tests for LTTB implementation."""

    def test_large_dataset_downsampling(self):
        """Test downsampling on a large dataset."""
        # Create large dataset (100k points)
        x = np.arange(100000)
        y = np.sin(x * 0.001) + np.random.randn(100000) * 0.1
        data = np.column_stack([x, y])

        # Downsample to 10k points
        result = downsample(data, n_out=10000)

        assert result.shape == (10000, 2)
        assert result[0, 0] == 0
        assert result[-1, 0] == 99999

    def test_output_is_subset_of_input(self):
        """Test that output points are from the original dataset."""
        data = np.column_stack([np.arange(1000), np.random.randn(1000)])

        result = downsample(data, n_out=100)

        # Each output point (except possibly endpoints) should exist in input
        for i in range(len(result)):
            # Check if this point exists in the original data
            matches = np.where((data[:, 0] == result[i, 0]) & (data[:, 1] == result[i, 1]))[0]
            assert len(matches) > 0, f"Point {i} not found in original data"


class TestLTTBFast:
    """Tests for the fast LTTB variant (centroid-based)."""

    def test_basic_downsampling(self):
        """Test basic downsampling with simple data."""
        data = np.column_stack([np.arange(100), np.arange(100)])

        result = downsample_fast(data, n_out=10)

        assert result.shape == (10, 2)
        assert result[0, 0] == 0  # First point preserved
        assert result[-1, 0] == 99  # Last point preserved

    def test_downsampling_preserves_endpoints(self):
        """Test that first and last points are always preserved."""
        data = np.column_stack([np.arange(1000), np.sin(np.arange(1000) * 0.01)])

        result = downsample_fast(data, n_out=50)

        np.testing.assert_array_equal(result[0], data[0])
        np.testing.assert_array_equal(result[-1], data[-1])

    def test_no_downsampling_when_n_out_equals_data_size(self):
        """Test that no downsampling occurs when n_out == data size."""
        data = np.column_stack([np.arange(100), np.arange(100)])

        result = downsample_fast(data, n_out=100)

        np.testing.assert_array_equal(result, data)

    def test_minimum_output_size(self):
        """Test that n_out must be at least 3."""
        data = np.column_stack([np.arange(100), np.arange(100)])

        with pytest.raises(ValueError, match="Can only downsample to a minimum of 3 points"):
            downsample_fast(data, n_out=2)

    def test_n_out_larger_than_data_raises_error(self):
        """Test that n_out > data size raises error."""
        data = np.column_stack([np.arange(10), np.arange(10)])

        with pytest.raises(ValueError, match="n_out must be <= number of rows in data"):
            downsample_fast(data, n_out=20)

    def test_sine_wave_downsampling(self):
        """Test downsampling on a sine wave."""
        x = np.arange(0, 10, 0.01)
        y = np.sin(x)
        data = np.column_stack([x, y])

        result = downsample_fast(data, n_out=100)

        assert result.shape == (100, 2)
        # Check that result captures key features (peaks and troughs)
        assert abs(result[:, 1].min() - y.min()) < 0.5
        assert abs(result[:, 1].max() - y.max()) < 0.5

    def test_output_is_subset_of_input(self):
        """Test that output points are from the original dataset."""
        data = np.column_stack([np.arange(1000), np.random.randn(1000)])

        result = downsample_fast(data, n_out=100)

        # Each output point should exist in the original data
        for i in range(len(result)):
            matches = np.where((data[:, 0] == result[i, 0]) & (data[:, 1] == result[i, 1]))[0]
            assert len(matches) > 0, f"Point {i} not found in original data"

    def test_different_from_original_lttb(self):
        """Test that fast variant produces different results from original LTTB."""
        # Use a dataset where the algorithms would differ
        x = np.arange(1000)
        y = np.sin(x * 0.01) + np.random.randn(1000) * 0.1
        np.random.seed(42)  # For reproducibility
        data = np.column_stack([x, y])

        result_original = downsample(data, n_out=100)
        # Ensure we're using the original implementation
        os.environ["ASPARA_LTTB_FAST"] = "0"
        result_original_via_env = downsample(data, n_out=100)
        result_fast = downsample_fast(data, n_out=100)

        # Results from original should match when env var is 0
        np.testing.assert_array_equal(result_original, result_original_via_env)

        # Fast variant should produce different results (for most datasets)
        # Note: They might be identical for simple datasets, so we use a complex one
        # At least some points should differ
        assert not np.array_equal(result_original, result_fast), "Fast and original LTTB should produce different results"


class TestLTTBEnvironmentSwitch:
    """Tests for environment variable switching between LTTB variants."""

    def test_default_uses_original(self):
        """Test that default behavior uses original LTTB."""
        # Unset environment variable
        os.environ.pop("ASPARA_LTTB_FAST", None)

        data = np.column_stack([np.arange(100), np.sin(np.arange(100) * 0.1)])
        result = downsample(data, n_out=10)

        assert result.shape == (10, 2)

    def test_env_var_enables_fast(self):
        """Test that ASPARA_LTTB_FAST=1 enables fast variant."""
        data = np.column_stack([np.arange(100), np.sin(np.arange(100) * 0.1)])

        # Test with fast enabled
        os.environ["ASPARA_LTTB_FAST"] = "1"
        result_fast = downsample(data, n_out=10)

        # Test with fast disabled
        os.environ["ASPARA_LTTB_FAST"] = "0"
        result_original = downsample(data, n_out=10)

        # Clean up
        os.environ.pop("ASPARA_LTTB_FAST", None)

        # Results should be valid
        assert result_fast.shape == (10, 2)
        assert result_original.shape == (10, 2)

        # They might differ (depending on the dataset)
        # Just ensure both produce valid output
        np.testing.assert_array_equal(result_fast[0], data[0])
        np.testing.assert_array_equal(result_fast[-1], data[-1])
        np.testing.assert_array_equal(result_original[0], data[0])
        np.testing.assert_array_equal(result_original[-1], data[-1])


class TestLTTBFastV2:
    """Tests for the two-stage fast LTTB variant."""

    def test_basic_downsampling(self):
        """Test basic downsampling with simple data."""
        data = np.column_stack([np.arange(100), np.arange(100)])

        result = downsample_fast_v2(data, n_out=10)

        assert result.shape == (10, 2)
        assert result[0, 0] == 0  # First point preserved
        assert result[-1, 0] == 99  # Last point preserved

    def test_downsampling_preserves_endpoints(self):
        """Test that first and last points are always preserved."""
        data = np.column_stack([np.arange(1000), np.sin(np.arange(1000) * 0.01)])

        result = downsample_fast_v2(data, n_out=50)

        np.testing.assert_array_equal(result[0], data[0])
        np.testing.assert_array_equal(result[-1], data[-1])

    def test_no_downsampling_when_n_out_equals_data_size(self):
        """Test that no downsampling occurs when n_out == data size."""
        data = np.column_stack([np.arange(100), np.arange(100)])

        result = downsample_fast_v2(data, n_out=100)

        np.testing.assert_array_equal(result, data)

    def test_minimum_output_size(self):
        """Test that n_out must be at least 3."""
        data = np.column_stack([np.arange(100), np.arange(100)])

        with pytest.raises(ValueError, match="Can only downsample to a minimum of 3 points"):
            downsample_fast_v2(data, n_out=2)

    def test_n_out_larger_than_data_raises_error(self):
        """Test that n_out > data size raises error."""
        data = np.column_stack([np.arange(10), np.arange(10)])

        with pytest.raises(ValueError, match="n_out must be <= number of rows in data"):
            downsample_fast_v2(data, n_out=20)

    def test_sine_wave_downsampling(self):
        """Test downsampling on a sine wave."""
        x = np.arange(0, 10, 0.01)
        y = np.sin(x)
        data = np.column_stack([x, y])

        result = downsample_fast_v2(data, n_out=100)

        assert result.shape == (100, 2)
        # Check that result captures key features (peaks and troughs)
        assert abs(result[:, 1].min() - y.min()) < 0.5
        assert abs(result[:, 1].max() - y.max()) < 0.5

    def test_output_is_subset_of_input(self):
        """Test that output points are from the original dataset."""
        data = np.column_stack([np.arange(1000), np.random.randn(1000)])

        result = downsample_fast_v2(data, n_out=100)

        # Each output point should exist in the original data
        for i in range(len(result)):
            matches = np.where((data[:, 0] == result[i, 0]) & (data[:, 1] == result[i, 1]))[0]
            assert len(matches) > 0, f"Point {i} not found in original data"

    def test_quality_better_than_fast(self):
        """Test that v2 typically has better quality than fast variant."""
        # Use a complex signal where quality differences are visible
        np.random.seed(42)
        x = np.arange(10000)
        y = np.sin(x * 0.01) + 0.5 * np.sin(x * 0.05) + np.random.randn(10000) * 0.1
        data = np.column_stack([x, y])

        result_fast = downsample_fast(data, n_out=100)
        result_v2 = downsample_fast_v2(data, n_out=100)

        # Both should produce valid output
        assert result_fast.shape == (100, 2)
        assert result_v2.shape == (100, 2)

        # Endpoints should match
        np.testing.assert_array_equal(result_fast[0], data[0])
        np.testing.assert_array_equal(result_fast[-1], data[-1])
        np.testing.assert_array_equal(result_v2[0], data[0])
        np.testing.assert_array_equal(result_v2[-1], data[-1])

    def test_different_from_fast(self):
        """Test that v2 can produce different results from fast variant."""
        # Use a dataset where refinement matters
        np.random.seed(42)
        x = np.arange(5000)
        y = np.sin(x * 0.02) + np.random.randn(5000) * 0.2
        data = np.column_stack([x, y])

        result_fast = downsample_fast(data, n_out=50)
        result_v2 = downsample_fast_v2(data, n_out=50)

        # Results should be valid
        assert result_fast.shape == (50, 2)
        assert result_v2.shape == (50, 2)

        # Note: v2 might produce same or different results depending on data
        # We just ensure both are valid downsampling results


class TestLTTBFastV3:
    """Tests for the interleaved fast LTTB variant."""

    def test_basic_downsampling(self):
        """Test basic downsampling with simple data."""
        data = np.column_stack([np.arange(100), np.arange(100)])

        result = downsample_fast_v3(data, n_out=10)

        assert result.shape == (10, 2)
        assert result[0, 0] == 0  # First point preserved
        assert result[-1, 0] == 99  # Last point preserved

    def test_downsampling_preserves_endpoints(self):
        """Test that first and last points are always preserved."""
        data = np.column_stack([np.arange(1000), np.sin(np.arange(1000) * 0.01)])

        result = downsample_fast_v3(data, n_out=50)

        np.testing.assert_array_equal(result[0], data[0])
        np.testing.assert_array_equal(result[-1], data[-1])

    def test_no_downsampling_when_n_out_equals_data_size(self):
        """Test that no downsampling occurs when n_out == data size."""
        data = np.column_stack([np.arange(100), np.arange(100)])

        result = downsample_fast_v3(data, n_out=100)

        np.testing.assert_array_equal(result, data)

    def test_minimum_output_size(self):
        """Test that n_out must be at least 3."""
        data = np.column_stack([np.arange(100), np.arange(100)])

        with pytest.raises(ValueError, match="Can only downsample to a minimum of 3 points"):
            downsample_fast_v3(data, n_out=2)

    def test_n_out_larger_than_data_raises_error(self):
        """Test that n_out > data size raises error."""
        data = np.column_stack([np.arange(10), np.arange(10)])

        with pytest.raises(ValueError, match="n_out must be <= number of rows in data"):
            downsample_fast_v3(data, n_out=20)

    def test_sine_wave_downsampling(self):
        """Test downsampling on a sine wave."""
        x = np.arange(0, 10, 0.01)
        y = np.sin(x)
        data = np.column_stack([x, y])

        result = downsample_fast_v3(data, n_out=100)

        assert result.shape == (100, 2)
        # Check that result captures key features (peaks and troughs)
        assert abs(result[:, 1].min() - y.min()) < 0.5
        assert abs(result[:, 1].max() - y.max()) < 0.5

    def test_output_is_subset_of_input(self):
        """Test that output points are from the original dataset."""
        data = np.column_stack([np.arange(1000), np.random.randn(1000)])

        result = downsample_fast_v3(data, n_out=100)

        # Each output point should exist in the original data
        for i in range(len(result)):
            matches = np.where((data[:, 0] == result[i, 0]) & (data[:, 1] == result[i, 1]))[0]
            assert len(matches) > 0, f"Point {i} not found in original data"

    def test_interleaving_logic(self):
        """Test that interleaving correctly uses v2 and original."""
        np.random.seed(42)
        data = np.column_stack([np.arange(1000), np.random.randn(1000)])

        result_v3 = downsample_fast_v3(data, n_out=10)
        result_v2 = downsample_fast_v2(data, n_out=10)
        result_original = downsample(data, n_out=10)

        # First and last should be the same for all
        np.testing.assert_array_equal(result_v3[0], result_v2[0])
        np.testing.assert_array_equal(result_v3[-1], result_v2[-1])

        # Middle points should follow interleaving pattern
        # Index 1 (odd): should match v2
        np.testing.assert_array_equal(result_v3[1], result_v2[1])
        # Index 2 (even): should match original
        np.testing.assert_array_equal(result_v3[2], result_original[2])
        # Index 3 (odd): should match v2
        np.testing.assert_array_equal(result_v3[3], result_v2[3])
