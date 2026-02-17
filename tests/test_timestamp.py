"""Tests for timestamp parsing utilities."""

from datetime import datetime, timezone

import pytest

from aspara.utils.timestamp import parse_to_datetime, parse_to_ms


class TestParseToDatetime:
    """Tests for parse_to_datetime function."""

    def test_datetime_input_returns_as_is(self) -> None:
        """datetime input should be returned as-is if timezone-aware."""
        dt = datetime(2024, 1, 15, 12, 30, 45, tzinfo=timezone.utc)
        result = parse_to_datetime(dt)
        assert result == dt

    def test_datetime_naive_gets_utc(self) -> None:
        """Naive datetime should get UTC timezone."""
        dt = datetime(2024, 1, 15, 12, 30, 45)
        result = parse_to_datetime(dt)
        assert result.tzinfo == timezone.utc
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_int_unix_ms(self) -> None:
        """Integer should be treated as UNIX milliseconds."""
        # 2024-01-15T12:30:45.123Z in ms
        ts_ms = 1705321845123
        result = parse_to_datetime(ts_ms)
        assert result.tzinfo == timezone.utc
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_float_unix_ms(self) -> None:
        """Float should be treated as UNIX milliseconds."""
        ts_ms = 1705321845123.456
        result = parse_to_datetime(ts_ms)
        assert result.tzinfo == timezone.utc
        assert result.year == 2024

    def test_iso8601_string(self) -> None:
        """ISO 8601 string should be parsed correctly."""
        result = parse_to_datetime("2024-01-15T12:30:45")
        assert result.tzinfo == timezone.utc
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12
        assert result.minute == 30
        assert result.second == 45

    def test_iso8601_string_with_z_suffix(self) -> None:
        """ISO 8601 string with Z suffix should be parsed as UTC."""
        result = parse_to_datetime("2024-01-15T12:30:45Z")
        assert result.tzinfo is not None
        assert result.year == 2024
        assert result.hour == 12

    def test_iso8601_string_with_timezone(self) -> None:
        """ISO 8601 string with timezone offset should preserve it."""
        result = parse_to_datetime("2024-01-15T12:30:45+09:00")
        assert result.tzinfo is not None
        assert result.year == 2024
        # The datetime should have the original timezone preserved
        assert result.utcoffset().total_seconds() == 9 * 3600

    def test_none_raises_value_error(self) -> None:
        """None input should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be None"):
            parse_to_datetime(None)  # type: ignore[arg-type]

    def test_empty_string_raises_value_error(self) -> None:
        """Empty string should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_to_datetime("")

    def test_whitespace_string_raises_value_error(self) -> None:
        """Whitespace-only string should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_to_datetime("   ")

    def test_invalid_string_raises_value_error(self) -> None:
        """Invalid timestamp string should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            parse_to_datetime("not-a-timestamp")

    def test_unsupported_type_raises_value_error(self) -> None:
        """Unsupported types should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported timestamp type"):
            parse_to_datetime([1, 2, 3])  # type: ignore[arg-type]


class TestParseToMs:
    """Tests for parse_to_ms function."""

    def test_int_passthrough(self) -> None:
        """Integer should be returned as-is."""
        ts_ms = 1705321845123
        result = parse_to_ms(ts_ms)
        assert result == ts_ms
        assert isinstance(result, int)

    def test_float_truncated_to_int(self) -> None:
        """Float should be truncated to int."""
        ts_ms = 1705321845123.999
        result = parse_to_ms(ts_ms)
        assert result == 1705321845123
        assert isinstance(result, int)

    def test_datetime_converted_to_ms(self) -> None:
        """datetime should be converted to UNIX milliseconds."""
        dt = datetime(2024, 1, 15, 12, 30, 45, tzinfo=timezone.utc)
        result = parse_to_ms(dt)
        # Should be close to the expected timestamp
        expected = int(dt.timestamp() * 1000)
        assert result == expected

    def test_iso8601_string_converted_to_ms(self) -> None:
        """ISO 8601 string should be converted to UNIX milliseconds."""
        result = parse_to_ms("2024-01-15T12:30:45Z")
        # Parse it back to verify
        dt = datetime.fromtimestamp(result / 1000, tz=timezone.utc)
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15
        assert dt.hour == 12

    def test_none_raises_value_error(self) -> None:
        """None input should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be None"):
            parse_to_ms(None)  # type: ignore[arg-type]

    def test_empty_string_raises_value_error(self) -> None:
        """Empty string should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_to_ms("")

    def test_invalid_string_raises_value_error(self) -> None:
        """Invalid timestamp string should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            parse_to_ms("invalid")


class TestTimezoneHandling:
    """Tests for timezone handling edge cases."""

    def test_different_timezones_convert_correctly(self) -> None:
        """Different timezone offsets should be handled correctly."""
        from datetime import timedelta

        # JST timezone (UTC+9)
        jst = timezone(timedelta(hours=9))
        dt_jst = datetime(2024, 1, 15, 21, 30, 45, tzinfo=jst)

        result = parse_to_datetime(dt_jst)
        # Should preserve the timezone
        assert result.tzinfo is not None

    def test_naive_datetime_assumed_utc(self) -> None:
        """Naive datetime should be assumed as UTC."""
        naive = datetime(2024, 1, 15, 12, 30, 45)
        result = parse_to_datetime(naive)
        assert result.tzinfo == timezone.utc

        # Converting to ms and back should give same time
        ms = parse_to_ms(naive)
        back = parse_to_datetime(ms)
        assert back.hour == 12
        assert back.minute == 30

    def test_negative_timestamp(self) -> None:
        """Negative timestamps (before 1970) should work."""
        # Negative timestamp for date before 1970
        ts_ms = -86400000  # -1 day from epoch
        result = parse_to_datetime(ts_ms)
        assert result.year == 1969
        assert result.month == 12
        assert result.day == 31
