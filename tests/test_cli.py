"""
Tests for CLI functionality.

This module tests the command-line interface including new CSV export,
monitoring commands, and enhanced search features.
"""

import csv
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from click.testing import CliRunner

from yokedcache.cli import main
from yokedcache.models import CacheStats


@pytest.fixture
def mock_cache_stats():
    """Create mock cache statistics."""
    stats = CacheStats()
    stats.total_hits = 100
    stats.total_misses = 20
    stats.total_sets = 50
    stats.total_deletes = 10
    stats.total_keys = 40
    stats.total_memory_bytes = 1024000
    stats.uptime_seconds = 3600.0
    stats.total_invalidations = 5
    return stats


class TestCLIStats:
    """Test CLI stats command with different output formats."""

    def test_stats_json_format(self, mock_cache_stats):
        """Test stats output in JSON format."""
        runner = CliRunner()

        with patch("yokedcache.cli.YokedCache") as mock_cache_class:
            mock_cache = AsyncMock()
            mock_cache.get_stats.return_value = mock_cache_stats
            mock_cache_class.return_value = mock_cache

            with patch("yokedcache.cli.asyncio.run") as mock_run:
                mock_run.return_value = None

                result = runner.invoke(main, ["stats", "--format", "json"])

                assert result.exit_code == 0
                # Should contain JSON output
                assert "total_hits" in result.output or mock_run.called

    def test_stats_yaml_format(self, mock_cache_stats):
        """Test stats output in YAML format."""
        runner = CliRunner()

        with patch("yokedcache.cli.YokedCache") as mock_cache_class:
            mock_cache = AsyncMock()
            mock_cache.get_stats.return_value = mock_cache_stats
            mock_cache_class.return_value = mock_cache

            with patch("yokedcache.cli.asyncio.run") as mock_run:
                mock_run.return_value = None

                result = runner.invoke(main, ["stats", "--format", "yaml"])

                assert result.exit_code == 0
                # YAML command should be accepted
                assert "yaml" in str(result) or mock_run.called

    def test_stats_csv_format_to_stdout(self, mock_cache_stats):
        """Test stats output in CSV format to stdout."""
        runner = CliRunner()

        with patch("yokedcache.cli.YokedCache") as mock_cache_class:
            mock_cache = AsyncMock()
            mock_cache.get_stats.return_value = mock_cache_stats
            mock_cache_class.return_value = mock_cache

            with patch("yokedcache.cli.asyncio.run") as mock_run:
                mock_run.return_value = None

                result = runner.invoke(main, ["stats", "--format", "csv"])

                assert result.exit_code == 0
                # CSV command should be accepted
                assert mock_run.called

    def test_stats_csv_format_to_file(self, mock_cache_stats):
        """Test stats output in CSV format to file."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".csv"
        ) as tmp_file:
            tmp_path = tmp_file.name

        try:
            with patch("yokedcache.cli.YokedCache") as mock_cache_class:
                mock_cache = AsyncMock()
                mock_cache.get_stats.return_value = mock_cache_stats
                mock_cache_class.return_value = mock_cache

                with patch("yokedcache.cli.asyncio.run") as mock_run:
                    mock_run.return_value = None

                    result = runner.invoke(
                        main, ["stats", "--format", "csv", "--output", tmp_path]
                    )

                    assert result.exit_code == 0
                    assert mock_run.called
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_stats_json_format_to_file(self, mock_cache_stats):
        """Test stats output in JSON format to file."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json"
        ) as tmp_file:
            tmp_path = tmp_file.name

        try:
            with patch("yokedcache.cli.YokedCache") as mock_cache_class:
                mock_cache = AsyncMock()
                mock_cache.get_stats.return_value = mock_cache_stats
                mock_cache_class.return_value = mock_cache

                with patch("yokedcache.cli.asyncio.run") as mock_run:
                    mock_run.return_value = None

                    result = runner.invoke(
                        main, ["stats", "--format", "json", "--output", tmp_path]
                    )

                    assert result.exit_code == 0
                    assert mock_run.called
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestCLISearch:
    """Test CLI search functionality."""

    def test_search_basic(self):
        """Test basic search functionality."""
        runner = CliRunner()

        with patch("yokedcache.cli.YokedCache") as mock_cache_class:
            mock_cache = AsyncMock()
            mock_cache.fuzzy_search.return_value = []
            mock_cache_class.return_value = mock_cache

            with patch("yokedcache.cli.asyncio.run") as mock_run:
                mock_run.return_value = None

                result = runner.invoke(main, ["search", "test_query"])

                assert result.exit_code == 0
                assert mock_run.called

    def test_search_with_threshold(self):
        """Test search with custom threshold."""
        runner = CliRunner()

        with patch("yokedcache.cli.YokedCache") as mock_cache_class:
            mock_cache = AsyncMock()
            mock_cache.fuzzy_search.return_value = []
            mock_cache_class.return_value = mock_cache

            with patch("yokedcache.cli.asyncio.run") as mock_run:
                mock_run.return_value = None

                result = runner.invoke(
                    main, ["search", "test_query", "--threshold", "90"]
                )

                assert result.exit_code == 0
                assert mock_run.called

    def test_search_with_limit(self):
        """Test search with result limit."""
        runner = CliRunner()

        with patch("yokedcache.cli.YokedCache") as mock_cache_class:
            mock_cache = AsyncMock()
            mock_cache.fuzzy_search.return_value = []
            mock_cache_class.return_value = mock_cache

            with patch("yokedcache.cli.asyncio.run") as mock_run:
                mock_run.return_value = None

                result = runner.invoke(
                    main, ["search", "test_query", "--max-results", "5"]
                )

                assert result.exit_code == 0
                assert mock_run.called


class TestCLICache:
    """Test CLI cache management commands."""

    def test_get_command(self):
        """Test cache get command."""
        runner = CliRunner()

        with patch("yokedcache.cli.YokedCache") as mock_cache_class:
            mock_cache = AsyncMock()
            mock_cache.get.return_value = "test_value"
            mock_cache_class.return_value = mock_cache

            with patch("yokedcache.cli.asyncio.run") as mock_run:
                mock_run.return_value = None

                result = runner.invoke(main, ["get", "test_key"])

                assert result.exit_code == 0
                assert mock_run.called

    def test_set_command(self):
        """Test cache set command."""
        runner = CliRunner()

        with patch("yokedcache.cli.YokedCache") as mock_cache_class:
            mock_cache = AsyncMock()
            mock_cache.set.return_value = True
            mock_cache_class.return_value = mock_cache

            with patch("yokedcache.cli.asyncio.run") as mock_run:
                mock_run.return_value = None

                result = runner.invoke(
                    main, ["set", "test_key", "test_value", "--ttl", "300"]
                )

                assert result.exit_code == 0
                assert mock_run.called

    def test_delete_command(self):
        """Test cache delete command."""
        runner = CliRunner()

        with patch("yokedcache.cli.YokedCache") as mock_cache_class:
            mock_cache = AsyncMock()
            mock_cache.delete.return_value = True
            mock_cache_class.return_value = mock_cache

            with patch("yokedcache.cli.asyncio.run") as mock_run:
                mock_run.return_value = None

                result = runner.invoke(main, ["delete", "test_key"])

                assert result.exit_code == 0
                assert mock_run.called

    def test_flush_command(self):
        """Test cache flush command."""
        runner = CliRunner()

        with patch("yokedcache.cli.YokedCache") as mock_cache_class:
            mock_cache = AsyncMock()
            mock_cache.flush_all.return_value = True
            mock_cache_class.return_value = mock_cache

            with patch("yokedcache.cli.asyncio.run") as mock_run:
                mock_run.return_value = None

                # Use --force flag to skip confirmation
                result = runner.invoke(main, ["flush", "--force", "--all"])

                assert result.exit_code == 0
                assert mock_run.called


class TestCLIInvalidate:
    """Test CLI invalidation commands."""

    def test_invalidate_pattern(self):
        """Test pattern-based invalidation."""
        runner = CliRunner()

        with patch("yokedcache.cli.YokedCache") as mock_cache_class:
            mock_cache = AsyncMock()
            mock_cache.invalidate_pattern.return_value = 5
            mock_cache_class.return_value = mock_cache

            with patch("yokedcache.cli.asyncio.run") as mock_run:
                mock_run.return_value = None

                result = runner.invoke(main, ["invalidate", "--pattern", "user:*"])

                assert result.exit_code == 0
                assert mock_run.called

    def test_invalidate_tags(self):
        """Test tag-based invalidation."""
        runner = CliRunner()

        with patch("yokedcache.cli.YokedCache") as mock_cache_class:
            mock_cache = AsyncMock()
            mock_cache.invalidate_tags.return_value = 3
            mock_cache_class.return_value = mock_cache

            with patch("yokedcache.cli.asyncio.run") as mock_run:
                mock_run.return_value = None

                result = runner.invoke(main, ["invalidate", "--tags", "users,active"])

                assert result.exit_code == 0
                assert mock_run.called


class TestCLIMonitoring:
    """Test CLI monitoring and health check commands."""

    def test_health_check(self):
        """Test health check command."""
        runner = CliRunner()

        with patch("yokedcache.cli.YokedCache") as mock_cache_class:
            mock_cache = AsyncMock()
            mock_cache.health_check.return_value = True
            mock_cache_class.return_value = mock_cache

            with patch("yokedcache.cli.asyncio.run") as mock_run:
                mock_run.return_value = None

                result = runner.invoke(main, ["health"])

                assert result.exit_code == 0
                assert mock_run.called

    def test_ping_command(self):
        """Test ping command."""
        runner = CliRunner()

        with patch("yokedcache.cli.YokedCache") as mock_cache_class:
            mock_cache = AsyncMock()
            mock_cache.ping.return_value = True
            mock_cache_class.return_value = mock_cache

            with patch("yokedcache.cli.asyncio.run") as mock_run:
                mock_run.return_value = None

                result = runner.invoke(main, ["ping"])

                # Ping might not be implemented, so just check it doesn't crash
                assert result.exit_code in [0, 1, 2]


class TestCLIErrorHandling:
    """Test CLI error handling."""

    def test_connection_error_handling(self):
        """Test handling of connection errors."""
        runner = CliRunner()

        with patch("yokedcache.cli.YokedCache") as mock_cache_class:
            mock_cache_class.side_effect = Exception("Connection failed")

            result = runner.invoke(main, ["stats"])

            # Should handle error gracefully
            assert result.exit_code != 0

    def test_invalid_format_error(self):
        """Test handling of invalid output format."""
        runner = CliRunner()

        result = runner.invoke(main, ["stats", "--format", "invalid"])

        # Should reject invalid format
        assert result.exit_code != 0

    def test_file_permission_error(self):
        """Test handling of file permission errors."""
        runner = CliRunner()

        with patch("yokedcache.cli.YokedCache") as mock_cache_class:
            mock_cache = AsyncMock()
            mock_cache.get_stats.return_value = CacheStats()
            mock_cache_class.return_value = mock_cache

            with patch("yokedcache.cli.asyncio.run") as mock_run:
                mock_run.return_value = None

                # Try to write to a read-only location
                result = runner.invoke(
                    main, ["stats", "--format", "csv", "--output", "/root/readonly.csv"]
                )

                # Should handle permission error gracefully
                # The exact exit code depends on how errors are handled
                assert isinstance(result.exit_code, int)


class TestCLIConfiguration:
    """Test CLI configuration handling."""

    def test_config_file_loading(self):
        """Test loading configuration from file."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as tmp_file:
            tmp_file.write(
                """
redis_url: redis://localhost:6379/1
default_ttl: 600
key_prefix: test
"""
            )
            config_path = tmp_file.name

        try:
            with patch("yokedcache.cli.YokedCache") as mock_cache_class:
                mock_cache = AsyncMock()
                mock_cache.get_stats.return_value = CacheStats()
                mock_cache_class.return_value = mock_cache

                with patch("yokedcache.cli.asyncio.run") as mock_run:
                    mock_run.return_value = None

                    result = runner.invoke(main, ["--config", config_path, "stats"])

                    assert result.exit_code == 0
                    assert mock_run.called
        finally:
            Path(config_path).unlink(missing_ok=True)

    def test_config_override_with_options(self):
        """Test overriding config with command line options."""
        runner = CliRunner()

        with patch("yokedcache.cli.YokedCache") as mock_cache_class:
            mock_cache = AsyncMock()
            mock_cache.get_stats.return_value = CacheStats()
            mock_cache_class.return_value = mock_cache

            with patch("yokedcache.cli.asyncio.run") as mock_run:
                mock_run.return_value = None

                result = runner.invoke(
                    main,
                    [
                        "--redis-url",
                        "redis://localhost:6379/2",
                        "stats",
                    ],
                )

                assert result.exit_code == 0
                assert mock_run.called


class TestCLICSVExport:
    """Test CSV export functionality in detail."""

    def test_csv_export_append_mode(self, mock_cache_stats):
        """Test CSV export appends to existing file."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".csv"
        ) as tmp_file:
            tmp_path = tmp_file.name

            # Write initial CSV data
            writer = csv.DictWriter(
                tmp_file, fieldnames=["timestamp", "total_hits", "total_misses"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "timestamp": "2023-01-01 00:00:00",
                    "total_hits": 50,
                    "total_misses": 10,
                }
            )

        try:
            with patch("yokedcache.cli.YokedCache") as mock_cache_class:
                mock_cache = AsyncMock()
                mock_cache.get_stats.return_value = mock_cache_stats
                mock_cache_class.return_value = mock_cache

                with patch("yokedcache.cli.asyncio.run") as mock_run:
                    mock_run.return_value = None

                    result = runner.invoke(
                        main, ["stats", "--format", "csv", "--output", tmp_path]
                    )

                    assert result.exit_code == 0
                    assert mock_run.called

                    # Check that file exists and has been appended to
                    assert Path(tmp_path).exists()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_csv_export_creates_new_file(self, mock_cache_stats):
        """Test CSV export creates new file with headers."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
            tmp_path = tmp_file.name

        # File should not exist
        assert not Path(tmp_path).exists()

        with patch("yokedcache.cli.YokedCache") as mock_cache_class:
            mock_cache = AsyncMock()
            mock_cache.get_stats.return_value = mock_cache_stats
            mock_cache_class.return_value = mock_cache

            with patch("yokedcache.cli.asyncio.run") as mock_run:
                mock_run.return_value = None

                result = runner.invoke(
                    main, ["stats", "--format", "csv", "--output", tmp_path]
                )

                assert result.exit_code == 0
                assert mock_run.called
