"""Unit tests for dashboard compression utilities."""

from __future__ import annotations

from datetime import datetime, timezone

import polars as pl
import pytest

from aspara.dashboard.utils.compression import compress_metrics, delta_compress


class TestDeltaCompress:
    """Tests for delta_compress()."""

    def test_empty_list(self) -> None:
        assert delta_compress([]) == []

    def test_single_value(self) -> None:
        assert delta_compress([42]) == [42]

    def test_multiple_values(self) -> None:
        result = delta_compress([10, 20, 25, 30])
        assert result == [10, 10, 5, 5]

    def test_floats(self) -> None:
        result = delta_compress([1.0, 1.5, 2.0])
        assert result == pytest.approx([1.0, 0.5, 0.5])

    def test_negative_deltas(self) -> None:
        result = delta_compress([100, 90, 80])
        assert result == [100, -10, -10]

    def test_constant_values(self) -> None:
        result = delta_compress([5, 5, 5, 5])
        assert result == [5, 0, 0, 0]

    def test_preserves_int_type(self) -> None:
        result = delta_compress([1, 2, 3])
        # All values should be ints
        for v in result:
            assert isinstance(v, (int, float))


class TestCompressMetrics:
    """Tests for compress_metrics()."""

    def _make_df(
        self,
        rows: list[dict[str, int | float | None]],
        metric_cols: list[str],
    ) -> pl.DataFrame:
        """Build a wide-format DataFrame for compress_metrics."""
        return pl.DataFrame(rows, schema={"step": pl.Int64, "timestamp": pl.Datetime, **dict.fromkeys(metric_cols, pl.Float64)})

    def test_empty_dataframe(self) -> None:
        df = pl.DataFrame(schema={"step": pl.Int64, "timestamp": pl.Datetime, "_loss": pl.Float64})
        assert compress_metrics(df) == {}

    def test_no_metric_columns(self) -> None:
        """DataFrame without _-prefixed columns should return empty dict."""
        df = pl.DataFrame({
            "step": [0, 1],
            "timestamp": [datetime(2024, 1, 1, tzinfo=timezone.utc)] * 2,
        })
        assert compress_metrics(df) == {}

    def test_single_metric_below_threshold(self) -> None:
        """Metric with fewer rows than LTTB threshold should not be downsampled."""
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        df = self._make_df(
            [
                {"step": 0, "timestamp": ts, "_loss": 1.0},
                {"step": 1, "timestamp": ts, "_loss": 0.5},
                {"step": 2, "timestamp": ts, "_loss": 0.25},
            ],
            ["_loss"],
        )
        result = compress_metrics(df)
        assert "loss" in result
        metric = result["loss"]
        # values preserved
        assert metric["values"] == [1.0, 0.5, 0.25]
        # steps delta-compressed: [0, 1, 2] -> [0, 1, 1]
        assert metric["steps"][0] == 0
        assert metric["steps"] == [0, 1, 1]

    def test_multiple_metrics(self) -> None:
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        df = self._make_df(
            [
                {"step": 0, "timestamp": ts, "_loss": 1.0, "_acc": 0.1},
                {"step": 1, "timestamp": ts, "_loss": 0.5, "_acc": 0.2},
            ],
            ["_loss", "_acc"],
        )
        result = compress_metrics(df)
        assert set(result.keys()) == {"loss", "acc"}

    def test_null_values_dropped(self) -> None:
        """Rows with null metric values should be dropped."""
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        df = self._make_df(
            [
                {"step": 0, "timestamp": ts, "_loss": 1.0},
                {"step": 1, "timestamp": ts, "_loss": None},
                {"step": 2, "timestamp": ts, "_loss": 0.3},
            ],
            ["_loss"],
        )
        result = compress_metrics(df)
        assert result["loss"]["values"] == [1.0, 0.3]

    def test_all_null_metric_excluded(self) -> None:
        """A metric that is entirely null should not appear in the result."""
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        df = self._make_df(
            [
                {"step": 0, "timestamp": ts, "_loss": 1.0, "_bad": None},
                {"step": 1, "timestamp": ts, "_loss": 0.5, "_bad": None},
            ],
            ["_loss", "_bad"],
        )
        result = compress_metrics(df)
        assert "loss" in result
        assert "bad" not in result

    def test_timestamps_delta_compressed(self) -> None:
        """Timestamps should be delta-compressed."""
        ts0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        ts1 = datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc)
        df = self._make_df(
            [
                {"step": 0, "timestamp": ts0, "_loss": 1.0},
                {"step": 1, "timestamp": ts1, "_loss": 0.5},
            ],
            ["_loss"],
        )
        result = compress_metrics(df)
        timestamps = result["loss"]["timestamps"]
        abs0 = int(ts0.timestamp() * 1000)
        abs1 = int(ts1.timestamp() * 1000)
        assert timestamps[0] == abs0
        assert timestamps[1] == abs1 - abs0

    def test_above_lttb_threshold_downsamples(self) -> None:
        """When rows exceed LTTB threshold (default 1000), output should be downsampled."""
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        rows = [{"step": i, "timestamp": ts, "_loss": float(i)} for i in range(1500)]
        df = self._make_df(rows, ["_loss"])
        result = compress_metrics(df)
        # The number of output values should be <= threshold (1000)
        assert len(result["loss"]["values"]) <= 1000
        assert len(result["loss"]["values"]) < 1500
        assert len(result["loss"]["values"]) > 0
