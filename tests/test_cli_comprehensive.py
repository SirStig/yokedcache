"""
Comprehensive tests for CLI module to increase coverage.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from yokedcache.cli import async_command, get_cache_instance, reset_cache_instance


class TestCLIUtilities:
    """Test CLI utility functions."""

    def test_get_cache_instance_default(self):
        """Test getting cache instance with defaults."""
        reset_cache_instance()  # Reset global state
        with patch("yokedcache.cli.YokedCache") as mock_cache_class:
            mock_cache = MagicMock()
            mock_cache_class.return_value = mock_cache

            cache = get_cache_instance()
            assert cache == mock_cache
            mock_cache_class.assert_called_once()

    def test_get_cache_instance_with_redis_url(self):
        """Test getting cache instance with custom Redis URL."""
        reset_cache_instance()  # Reset global state
        with patch("yokedcache.cli.YokedCache") as mock_cache_class:
            mock_cache = MagicMock()
            mock_cache_class.return_value = mock_cache

            cache = get_cache_instance(redis_url="redis://custom:6379/1")
            assert cache == mock_cache

    def test_get_cache_instance_with_config_file(self):
        """Test getting cache instance with config file."""
        reset_cache_instance()  # Reset global state
        with (
            patch("yokedcache.cli.YokedCache") as mock_cache_class,
            patch("yokedcache.cli.load_config_from_file") as mock_load_config,
            patch("pathlib.Path.exists", return_value=True),
        ):

            mock_cache = MagicMock()
            mock_cache_class.return_value = mock_cache
            mock_config = MagicMock()
            mock_load_config.return_value = mock_config

            cache = get_cache_instance(config_file="test_config.yaml")
            assert cache == mock_cache
            mock_load_config.assert_called_once_with("test_config.yaml")

    def test_get_cache_instance_singleton(self):
        """Test that get_cache_instance returns the same instance."""
        with patch("yokedcache.cli.YokedCache") as mock_cache_class:
            mock_cache = MagicMock()
            mock_cache_class.return_value = mock_cache

            # Reset the global instance
            import yokedcache.cli

            yokedcache.cli._cache_instance = None

            cache1 = get_cache_instance()
            cache2 = get_cache_instance()

            assert cache1 == cache2
            # Should only create one instance
            mock_cache_class.assert_called_once()


class TestAsyncCommandDecorator:
    """Test the async_command decorator."""

    def test_async_command_decorator(self):
        """Test async_command decorator functionality."""

        @async_command
        async def test_async_func():
            return "test_result"

        with patch("asyncio.run") as mock_run:
            mock_run.return_value = "test_result"

            result = test_async_func()
            mock_run.assert_called_once()

    def test_async_command_decorator_with_args(self):
        """Test async_command decorator with arguments."""

        @async_command
        async def test_async_func(x, y):
            return x + y

        with patch("asyncio.run") as mock_run:
            mock_run.return_value = 5

            result = test_async_func(2, 3)
            mock_run.assert_called_once()

    def test_async_command_decorator_preserves_function_name(self):
        """Test that async_command preserves function metadata."""

        @async_command
        async def test_function():
            """Test docstring."""
            pass

        assert test_function.__name__ == "test_function"
        assert "Test docstring" in test_function.__doc__


class TestCLIFormatting:
    """Test CLI formatting functions."""

    def test_format_bytes_function(self):
        """Test format_bytes function import."""
        from yokedcache.cli import format_bytes

        result = format_bytes(1024)
        assert "KB" in result or "B" in result

    def test_cli_module_imports(self):
        """Test that CLI module imports work correctly."""
        import yokedcache.cli

        # Test that key functions are available
        assert hasattr(yokedcache.cli, "get_cache_instance")
        assert hasattr(yokedcache.cli, "async_command")
        assert hasattr(yokedcache.cli, "main")

    def test_cli_global_cache_instance(self):
        """Test global cache instance management."""
        import yokedcache.cli

        # Reset global instance
        yokedcache.cli._cache_instance = None

        with patch("yokedcache.cli.YokedCache") as mock_cache_class:
            mock_cache = MagicMock()
            mock_cache_class.return_value = mock_cache

            # First call should create instance
            cache1 = get_cache_instance()
            assert cache1 == mock_cache

            # Second call should return same instance
            cache2 = get_cache_instance()
            assert cache1 == cache2

            # Should only create one instance
            mock_cache_class.assert_called_once()
