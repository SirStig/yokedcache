"""
Exception classes for YokedCache.

This module defines custom exceptions used throughout the YokedCache library
to provide clear error handling and debugging information.
"""

from typing import Any, Optional


class YokedCacheError(Exception):
    """Base exception class for all YokedCache errors."""

    def __init__(self, message: str, details: Optional[dict] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class CacheConnectionError(YokedCacheError):
    """Raised when Redis connection fails or times out."""

    def __init__(
        self,
        message: str = "Failed to connect to Redis",
        details: Optional[dict] = None,
    ) -> None:
        super().__init__(message, details)


class CacheKeyError(YokedCacheError):
    """Raised when cache key operations fail."""

    def __init__(
        self, key: str, operation: str = "unknown", details: Optional[dict] = None
    ) -> None:
        message = f"Cache key error for '{key}' during {operation}"
        super().__init__(message, details)
        self.key = key
        self.operation = operation


class CacheSerializationError(YokedCacheError):
    """Raised when data serialization/deserialization fails."""

    def __init__(
        self, data_type: str, operation: str, original_error: Optional[Exception] = None
    ) -> None:
        message = f"Failed to {operation} data of type {data_type}"
        details = {"data_type": data_type, "operation": operation}

        if original_error:
            details["original_error"] = str(original_error)
            details["original_error_type"] = type(original_error).__name__

        super().__init__(message, details)
        self.data_type = data_type
        self.operation = operation
        self.original_error = original_error


class CacheInvalidationError(YokedCacheError):
    """Raised when cache invalidation operations fail."""

    def __init__(
        self,
        target: str,
        invalidation_type: str = "unknown",
        details: Optional[dict] = None,
    ) -> None:
        message = f"Failed to invalidate {invalidation_type}: {target}"
        super().__init__(message, details)
        self.target = target
        self.invalidation_type = invalidation_type


class CacheConfigurationError(YokedCacheError):
    """Raised when cache configuration is invalid."""

    def __init__(
        self, config_key: str, issue: str, details: Optional[dict] = None
    ) -> None:
        message = f"Configuration error for '{config_key}': {issue}"
        super().__init__(message, details)
        self.config_key = config_key
        self.issue = issue


class CacheMissError(YokedCacheError):
    """Raised when a required cache entry is not found."""

    def __init__(self, key: str, details: Optional[dict] = None) -> None:
        message = f"Cache miss for key: {key}"
        super().__init__(message, details)
        self.key = key


class CacheTimeoutError(YokedCacheError):
    """Raised when cache operations timeout."""

    def __init__(
        self, operation: str, timeout: float, details: Optional[dict] = None
    ) -> None:
        message = f"Cache operation '{operation}' timed out after {timeout}s"
        super().__init__(message, details)
        self.operation = operation
        self.timeout = timeout
