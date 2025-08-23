"""
Abstract base class for cache backends.

This module defines the interface that all cache backends must implement.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Union

from ..models import CacheStats, FuzzySearchResult


class CacheBackend(ABC):
    """Abstract base class for cache backends."""

    def __init__(self, **config):
        """Initialize the backend with configuration."""
        self.config = config
        self._connected = False

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the backend."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the backend."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the backend connection is healthy."""
        pass

    @abstractmethod
    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        pass

    @abstractmethod
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[Set[str]] = None,
    ) -> bool:
        """Set value in cache."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        pass

    @abstractmethod
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time for existing key."""
        pass

    @abstractmethod
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a pattern."""
        pass

    @abstractmethod
    async def invalidate_tags(self, tags: Union[str, List[str], Set[str]]) -> int:
        """Invalidate all keys associated with given tags."""
        pass

    @abstractmethod
    async def flush_all(self) -> bool:
        """Flush all cache keys."""
        pass

    @abstractmethod
    async def get_stats(self) -> CacheStats:
        """Get current cache statistics."""
        pass

    @abstractmethod
    async def fuzzy_search(
        self,
        query: str,
        threshold: int = 80,
        max_results: int = 10,
        tags: Optional[Set[str]] = None,
    ) -> List[FuzzySearchResult]:
        """Perform fuzzy search on cached data."""
        pass

    @abstractmethod
    async def get_all_keys(self, pattern: str = "*") -> List[str]:
        """Get all keys matching pattern."""
        pass

    @abstractmethod
    async def get_size_bytes(self) -> int:
        """Get total size of cache in bytes."""
        pass

    @property
    def is_connected(self) -> bool:
        """Check if backend is connected."""
        return self._connected

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
