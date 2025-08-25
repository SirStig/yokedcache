"""
Comprehensive tests for YokedCache exception classes.
"""

import pytest

from yokedcache.exceptions import (
    CacheConfigurationError,
    CacheConnectionError,
    CacheInvalidationError,
    CacheKeyError,
    CacheMissError,
    CacheSerializationError,
    CacheTimeoutError,
    YokedCacheError,
)


class TestYokedCacheError:
    """Test the base YokedCacheError class."""

    def test_basic_creation(self):
        """Test basic exception creation."""
        error = YokedCacheError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.details == {}

    def test_creation_with_details(self):
        """Test exception creation with details."""
        details = {"key": "value", "number": 42}
        error = YokedCacheError("Test error", details)
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.details == details

    def test_creation_with_none_details(self):
        """Test exception creation with None details."""
        error = YokedCacheError("Test error", None)
        assert error.details == {}

    def test_inheritance(self):
        """Test that YokedCacheError inherits from Exception."""
        error = YokedCacheError("Test error")
        assert isinstance(error, Exception)
        assert isinstance(error, YokedCacheError)


class TestCacheConnectionError:
    """Test the CacheConnectionError class."""

    def test_default_creation(self):
        """Test default exception creation."""
        error = CacheConnectionError()
        assert str(error) == "Failed to connect to Redis"
        assert error.message == "Failed to connect to Redis"
        assert error.details == {}

    def test_custom_message(self):
        """Test exception creation with custom message."""
        error = CacheConnectionError("Custom connection error")
        assert str(error) == "Custom connection error"
        assert error.message == "Custom connection error"

    def test_with_details(self):
        """Test exception creation with details."""
        details = {"host": "localhost", "port": 6379}
        error = CacheConnectionError("Connection failed", details)
        assert error.details == details

    def test_inheritance(self):
        """Test inheritance from YokedCacheError."""
        error = CacheConnectionError()
        assert isinstance(error, YokedCacheError)
        assert isinstance(error, Exception)


class TestCacheKeyError:
    """Test the CacheKeyError class."""

    def test_basic_creation(self):
        """Test basic exception creation."""
        error = CacheKeyError("test_key")
        assert "test_key" in str(error)
        assert "unknown" in str(error)
        assert error.key == "test_key"
        assert error.operation == "unknown"

    def test_with_operation(self):
        """Test exception creation with operation."""
        error = CacheKeyError("test_key", "get")
        assert "test_key" in str(error)
        assert "get" in str(error)
        assert error.key == "test_key"
        assert error.operation == "get"

    def test_with_details(self):
        """Test exception creation with details."""
        details = {"timeout": 5.0}
        error = CacheKeyError("test_key", "set", details)
        assert error.details == details

    def test_inheritance(self):
        """Test inheritance from YokedCacheError."""
        error = CacheKeyError("test_key")
        assert isinstance(error, YokedCacheError)


class TestCacheSerializationError:
    """Test the CacheSerializationError class."""

    def test_basic_creation(self):
        """Test basic exception creation."""
        error = CacheSerializationError("dict", "serialize")
        assert "dict" in str(error)
        assert "serialize" in str(error)
        assert error.data_type == "dict"
        assert error.operation == "serialize"
        assert error.original_error is None

    def test_with_original_error(self):
        """Test exception creation with original error."""
        original = ValueError("Invalid value")
        error = CacheSerializationError("list", "deserialize", original)

        assert error.data_type == "list"
        assert error.operation == "deserialize"
        assert error.original_error == original
        assert error.details["original_error"] == "Invalid value"
        assert error.details["original_error_type"] == "ValueError"

    def test_details_structure(self):
        """Test the details dictionary structure."""
        error = CacheSerializationError("str", "encode")
        expected_details = {"data_type": "str", "operation": "encode"}
        assert error.details == expected_details

    def test_inheritance(self):
        """Test inheritance from YokedCacheError."""
        error = CacheSerializationError("dict", "serialize")
        assert isinstance(error, YokedCacheError)


class TestCacheInvalidationError:
    """Test the CacheInvalidationError class."""

    def test_basic_creation(self):
        """Test basic exception creation."""
        error = CacheInvalidationError("pattern:*")
        assert "pattern:*" in str(error)
        assert "unknown" in str(error)
        assert error.target == "pattern:*"
        assert error.invalidation_type == "unknown"

    def test_with_invalidation_type(self):
        """Test exception creation with invalidation type."""
        error = CacheInvalidationError("tag:user", "tag")
        assert "tag:user" in str(error)
        assert "tag" in str(error)
        assert error.target == "tag:user"
        assert error.invalidation_type == "tag"

    def test_with_details(self):
        """Test exception creation with details."""
        details = {"count": 5}
        error = CacheInvalidationError("pattern:*", "pattern", details)
        assert error.details == details

    def test_inheritance(self):
        """Test inheritance from YokedCacheError."""
        error = CacheInvalidationError("target")
        assert isinstance(error, YokedCacheError)


class TestCacheConfigurationError:
    """Test the CacheConfigurationError class."""

    def test_basic_creation(self):
        """Test basic exception creation."""
        error = CacheConfigurationError("redis_url", "Invalid format")
        assert "redis_url" in str(error)
        assert "Invalid format" in str(error)
        assert error.config_key == "redis_url"
        assert error.issue == "Invalid format"

    def test_with_details(self):
        """Test exception creation with details."""
        details = {"provided_value": "invalid://url"}
        error = CacheConfigurationError("redis_url", "Invalid format", details)
        assert error.details == details

    def test_inheritance(self):
        """Test inheritance from YokedCacheError."""
        error = CacheConfigurationError("key", "issue")
        assert isinstance(error, YokedCacheError)


class TestCacheMissError:
    """Test the CacheMissError class."""

    def test_basic_creation(self):
        """Test basic exception creation."""
        error = CacheMissError("missing_key")
        assert "missing_key" in str(error)
        assert error.key == "missing_key"

    def test_with_details(self):
        """Test exception creation with details."""
        details = {"attempted_at": "2023-01-01T00:00:00Z"}
        error = CacheMissError("missing_key", details)
        assert error.details == details

    def test_inheritance(self):
        """Test inheritance from YokedCacheError."""
        error = CacheMissError("key")
        assert isinstance(error, YokedCacheError)


class TestCacheTimeoutError:
    """Test the CacheTimeoutError class."""

    def test_basic_creation(self):
        """Test basic exception creation."""
        error = CacheTimeoutError("get", 5.0)
        assert "get" in str(error)
        assert "5.0" in str(error)
        assert error.operation == "get"
        assert error.timeout == 5.0

    def test_with_details(self):
        """Test exception creation with details."""
        details = {"retry_count": 3}
        error = CacheTimeoutError("set", 10.0, details)
        assert error.details == details

    def test_inheritance(self):
        """Test inheritance from YokedCacheError."""
        error = CacheTimeoutError("operation", 1.0)
        assert isinstance(error, YokedCacheError)


class TestExceptionChaining:
    """Test exception chaining and context."""

    def test_exception_chaining(self):
        """Test that exceptions can be chained properly."""
        try:
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise CacheSerializationError("dict", "serialize", e) from e
        except CacheSerializationError as cache_error:
            assert cache_error.original_error is not None
            assert isinstance(cache_error.original_error, ValueError)
            assert str(cache_error.original_error) == "Original error"

    def test_exception_context_preservation(self):
        """Test that exception context is preserved."""
        original_error = RuntimeError("Runtime issue")
        cache_error = CacheSerializationError("list", "deserialize", original_error)

        assert cache_error.details["original_error_type"] == "RuntimeError"
        assert cache_error.details["original_error"] == "Runtime issue"


class TestExceptionStringRepresentations:
    """Test string representations of exceptions."""

    def test_all_exceptions_have_meaningful_messages(self):
        """Test that all exceptions have meaningful string representations."""
        exceptions = [
            YokedCacheError("Base error"),
            CacheConnectionError("Connection failed"),
            CacheKeyError("key", "operation"),
            CacheSerializationError("type", "operation"),
            CacheInvalidationError("target", "type"),
            CacheConfigurationError("key", "issue"),
            CacheMissError("key"),
            CacheTimeoutError("operation", 5.0),
        ]

        for exc in exceptions:
            message = str(exc)
            assert len(message) > 0
            assert message != ""
            # Each exception should contain some identifying information
            assert any(
                word in message.lower()
                for word in [
                    "error",
                    "failed",
                    "miss",
                    "timeout",
                    "cache",
                    "key",
                    "operation",
                    "invalidat",
                ]
            )
