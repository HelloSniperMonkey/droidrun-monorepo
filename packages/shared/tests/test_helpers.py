"""
Tests for shared utilities.
"""
from ironclaw_shared.utils.helpers import (
    format_phone_number,
    generate_task_id,
    parse_time_string,
    sanitize_filename,
    truncate_text,
)


class TestGenerateTaskId:
    """Tests for generate_task_id."""

    def test_default_prefix(self):
        task_id = generate_task_id()
        assert task_id.startswith("task-")
        assert len(task_id) == 13  # "task-" + 8 chars

    def test_custom_prefix(self):
        task_id = generate_task_id("job")
        assert task_id.startswith("job-")

    def test_uniqueness(self):
        ids = [generate_task_id() for _ in range(100)]
        assert len(set(ids)) == 100  # All unique


class TestSanitizeFilename:
    """Tests for sanitize_filename."""

    def test_removes_path_separators(self):
        assert sanitize_filename("../etc/passwd") == "_etc_passwd"  # Leading dots removed
        assert sanitize_filename("foo/bar\\baz") == "foo_bar_baz"

    def test_removes_leading_dots(self):
        assert sanitize_filename(".hidden") == "hidden"
        assert sanitize_filename("...dots") == "dots"

    def test_removes_null_bytes(self):
        assert sanitize_filename("file\x00name.txt") == "filename.txt"

    def test_truncates_long_names(self):
        long_name = "a" * 300 + ".pdf"
        result = sanitize_filename(long_name)
        assert len(result) <= 255
        assert result.endswith(".pdf")

    def test_empty_becomes_unnamed(self):
        assert sanitize_filename("") == "unnamed"
        assert sanitize_filename("...") == "unnamed"


class TestTruncateText:
    """Tests for truncate_text."""

    def test_short_text_unchanged(self):
        assert truncate_text("hello", 100) == "hello"

    def test_long_text_truncated(self):
        result = truncate_text("hello world", 8)
        assert len(result) == 8
        assert result.endswith("...")

    def test_custom_suffix(self):
        result = truncate_text("hello world", 9, suffix="…")
        assert result.endswith("…")


class TestParseTimeString:
    """Tests for parse_time_string."""

    def test_24_hour_format(self):
        assert parse_time_string("07:30") == (7, 30)
        assert parse_time_string("23:59") == (23, 59)
        assert parse_time_string("00:00") == (0, 0)

    def test_12_hour_format(self):
        assert parse_time_string("7:30 AM") == (7, 30)
        assert parse_time_string("7:30 PM") == (19, 30)
        assert parse_time_string("12:00 PM") == (12, 0)
        assert parse_time_string("12:00 AM") == (0, 0)

    def test_invalid_format(self):
        assert parse_time_string("invalid") is None
        assert parse_time_string("25:00") is None
        assert parse_time_string("12:60") is None

    def test_whitespace_handling(self):
        assert parse_time_string("  07:30  ") == (7, 30)


class TestFormatPhoneNumber:
    """Tests for format_phone_number."""

    def test_us_10_digit(self):
        assert format_phone_number("5551234567") == "+15551234567"
        assert format_phone_number("555-123-4567") == "+15551234567"
        assert format_phone_number("(555) 123-4567") == "+15551234567"

    def test_us_11_digit(self):
        assert format_phone_number("15551234567") == "+15551234567"

    def test_international_preserved(self):
        assert format_phone_number("+44123456789") == "+44123456789"

    def test_non_digits_removed(self):
        assert format_phone_number("555.123.4567") == "+15551234567"
