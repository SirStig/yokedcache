"""
Data models and structures for YokedCache.

This module defines the core data structures used throughout YokedCache,
including cache entries, statistics, and configuration models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Union
from enum import Enum


class InvalidationType(Enum):
    """Types of cache invalidation triggers."""
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    MANUAL = "manual"
    TTL_EXPIRED = "ttl_expired"


class SerializationMethod(Enum):
    """Supported data serialization methods."""
    JSON = "json"
    PICKLE = "pickle"
    MSGPACK = "msgpack"


@dataclass
class CacheEntry:
    """Represents a single cache entry with metadata."""
    
    key: str
    value: Any
    created_at: datetime
    expires_at: Optional[datetime] = None
    ttl: Optional[int] = None
    tags: Set[str] = field(default_factory=set)
    hit_count: int = 0
    last_accessed: Optional[datetime] = None
    serialization_method: SerializationMethod = SerializationMethod.JSON
    size_bytes: Optional[int] = None
    
    @property
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    @property
    def age_seconds(self) -> float:
        """Get the age of the cache entry in seconds."""
        return (datetime.utcnow() - self.created_at).total_seconds()
    
    def touch(self) -> None:
        """Update the last accessed timestamp and increment hit count."""
        self.last_accessed = datetime.utcnow()
        self.hit_count += 1


@dataclass
class CacheStats:
    """Cache performance and usage statistics."""
    
    total_hits: int = 0
    total_misses: int = 0
    total_sets: int = 0
    total_deletes: int = 0
    total_invalidations: int = 0
    total_keys: int = 0
    total_memory_bytes: int = 0
    uptime_seconds: float = 0.0
    
    # Per-table/tag statistics
    table_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    tag_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    # Performance metrics
    average_get_time_ms: float = 0.0
    average_set_time_ms: float = 0.0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate as a percentage."""
        total_requests = self.total_hits + self.total_misses
        if total_requests == 0:
            return 0.0
        return (self.total_hits / total_requests) * 100
    
    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate as a percentage."""
        return 100.0 - self.hit_rate
    
    def add_hit(self, table: Optional[str] = None, tags: Optional[Set[str]] = None) -> None:
        """Record a cache hit."""
        self.total_hits += 1
        if table:
            self._update_table_stats(table, "hits")
        if tags:
            for tag in tags:
                self._update_tag_stats(tag, "hits")
    
    def add_miss(self, table: Optional[str] = None, tags: Optional[Set[str]] = None) -> None:
        """Record a cache miss."""
        self.total_misses += 1
        if table:
            self._update_table_stats(table, "misses")
        if tags:
            for tag in tags:
                self._update_tag_stats(tag, "misses")
    
    def _update_table_stats(self, table: str, metric: str) -> None:
        """Update statistics for a specific table."""
        if table not in self.table_stats:
            self.table_stats[table] = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0}
        self.table_stats[table][metric] += 1
    
    def _update_tag_stats(self, tag: str, metric: str) -> None:
        """Update statistics for a specific tag."""
        if tag not in self.tag_stats:
            self.tag_stats[tag] = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0}
        self.tag_stats[tag][metric] += 1


@dataclass
class InvalidationRule:
    """Defines when and how to invalidate cache entries."""
    
    table_name: str
    invalidation_types: Set[InvalidationType]
    tags_to_invalidate: Set[str] = field(default_factory=set)
    key_patterns_to_invalidate: Set[str] = field(default_factory=set)
    cascade_tables: Set[str] = field(default_factory=set)
    delay_seconds: float = 0.0  # Delay before invalidation
    
    def should_invalidate(self, operation_type: InvalidationType) -> bool:
        """Check if this rule should trigger for the given operation type."""
        return operation_type in self.invalidation_types


@dataclass
class TableCacheConfig:
    """Cache configuration for a specific database table."""
    
    table_name: str
    ttl: int = 300  # Default 5 minutes
    tags: Set[str] = field(default_factory=set)
    invalidation_rules: List[InvalidationRule] = field(default_factory=list)
    enable_fuzzy: bool = False
    fuzzy_threshold: int = 80
    max_entries: Optional[int] = None
    serialization_method: SerializationMethod = SerializationMethod.JSON
    
    # Query-specific settings
    query_specific_ttls: Dict[str, int] = field(default_factory=dict)  # Query hash -> TTL


@dataclass
class FuzzySearchResult:
    """Result from a fuzzy search operation."""
    
    key: str
    value: Any
    score: float  # Similarity score (0-100)
    matched_term: str
    cache_entry: CacheEntry


@dataclass
class CacheOperation:
    """Represents a cache operation for logging/debugging."""
    
    operation_type: str  # get, set, delete, invalidate
    key: str
    table: Optional[str] = None
    tags: Optional[Set[str]] = None
    success: bool = True
    duration_ms: float = 0.0
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConnectionPoolStats:
    """Redis connection pool statistics."""
    
    total_connections: int = 0
    active_connections: int = 0
    available_connections: int = 0
    max_connections: int = 0
    connection_errors: int = 0
    reconnection_attempts: int = 0
