"""
Utility functions for YokedCache.

This module provides common utility functions for key generation,
data serialization, hashing, and other helper operations.
"""

import hashlib
import logging

import orjson
import pickle
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, List, Optional, Set, Union

from .exceptions import CacheSerializationError
from .models import SerializationMethod

logger = logging.getLogger(__name__)


def generate_cache_key(
    prefix: str,
    table: Optional[str] = None,
    query: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    user_id: Optional[Union[str, int]] = None,
    namespace: Optional[str] = None,
) -> str:
    """
    Generate a standardized cache key.

    Args:
        prefix: Cache key prefix (usually app name)
        table: Database table name
        query: SQL query or operation identifier
        params: Query parameters or filters
        user_id: User identifier for user-specific caching
        namespace: Additional namespace for multi-tenancy

    Returns:
        Formatted cache key string
    """
    key_parts = [prefix]

    if namespace:
        key_parts.append(f"ns:{namespace}")

    if table:
        key_parts.append(f"table:{table}")

    if user_id:
        key_parts.append(f"user:{user_id}")

    # Create a hash for query and params to ensure consistent key length
    if query or params:
        query_hash = _create_query_hash(query, params)
        key_parts.append(f"query:{query_hash}")

    return ":".join(key_parts)


def _create_query_hash(query: Optional[str], params: Optional[Dict[str, Any]]) -> str:
    """Create a hash from query and parameters."""
    hash_input = ""

    if query:
        # Normalize query string (remove extra whitespace, convert to lowercase)
        normalized_query = " ".join(query.strip().lower().split())
        hash_input += normalized_query

    if params:
        # Sort parameters for consistent hashing
        sorted_params = orjson.dumps(params, option=orjson.OPT_SORT_KEYS, default=str)
        hash_input += sorted_params.decode("utf-8")

    # Use SHA-256 for consistent, collision-resistant hashing
    return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]


def serialize_data(
    data: Any, method: SerializationMethod = SerializationMethod.JSON
) -> bytes:
    """
    Serialize data using the specified method.

    Args:
        data: Data to serialize
        method: Serialization method to use

    Returns:
        Serialized data as bytes

    Raises:
        CacheSerializationError: If serialization fails
    """
    try:
        if method == SerializationMethod.JSON:
            return orjson.dumps(data, default=_json_serializer)

        elif method == SerializationMethod.PICKLE:
            return pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)

        elif method == SerializationMethod.MSGPACK:
            try:
                import msgpack

                return msgpack.packb(
                    data, default=_msgpack_serializer, use_bin_type=True
                )
            except ImportError:
                raise CacheSerializationError(
                    "msgpack", "serialize", ImportError("msgpack library not installed")
                )

        else:
            raise CacheSerializationError(
                str(method),
                "serialize",
                ValueError(f"Unsupported serialization method: {method}"),
            )

    except Exception as e:
        raise CacheSerializationError(type(data).__name__, "serialize", e)


def deserialize_data(
    data: bytes, method: SerializationMethod = SerializationMethod.JSON
) -> Any:
    """
    Deserialize data using the specified method.

    Args:
        data: Serialized data as bytes
        method: Serialization method that was used

    Returns:
        Deserialized data

    Raises:
        CacheSerializationError: If deserialization fails
    """
    try:
        if method == SerializationMethod.JSON:
            return orjson.loads(data)

        elif method == SerializationMethod.PICKLE:
            return pickle.loads(data)

        elif method == SerializationMethod.MSGPACK:
            try:
                import msgpack

                return msgpack.unpackb(data, raw=False, strict_map_key=False)
            except ImportError:
                raise CacheSerializationError(
                    "msgpack",
                    "deserialize",
                    ImportError("msgpack library not installed"),
                )

        else:
            raise CacheSerializationError(
                str(method),
                "deserialize",
                ValueError(f"Unsupported serialization method: {method}"),
            )

    except Exception as e:
        raise CacheSerializationError("bytes", "deserialize", e)


_CACHE_MAGIC_V1 = b"\x89Yc\x01"
_METHOD_BYTE = {
    SerializationMethod.JSON: 1,
    SerializationMethod.PICKLE: 2,
    SerializationMethod.MSGPACK: 3,
}
_BYTE_TO_METHOD = {v: k for k, v in _METHOD_BYTE.items()}


def serialize_for_cache(value: Any, method: SerializationMethod) -> bytes:
    payload = serialize_data(value, method)
    tag = _METHOD_BYTE[method]
    return _CACHE_MAGIC_V1 + bytes([tag]) + payload


def deserialize_cache_payload_legacy(data: bytes) -> Any:
    try:
        return deserialize_data(data, SerializationMethod.JSON)
    except CacheSerializationError:
        return deserialize_data(data, SerializationMethod.PICKLE)


def deserialize_from_cache(data: bytes, allow_legacy_insecure: bool) -> Any:
    data = bytes(data)
    if len(data) >= 5 and data[:4] == _CACHE_MAGIC_V1:
        code = data[4]
        method = _BYTE_TO_METHOD.get(code)
        if method is None:
            raise CacheSerializationError(
                "bytes",
                "deserialize",
                ValueError("unknown cache payload format"),
            )
        return deserialize_data(data[5:], method)
    if allow_legacy_insecure:
        return deserialize_cache_payload_legacy(data)
    raise CacheSerializationError(
        "bytes",
        "deserialize",
        ValueError("legacy cache payload rejected"),
    )


def is_enveloped_cache_payload(data: bytes) -> bool:
    return len(data) >= 5 and data[:4] == _CACHE_MAGIC_V1


async def redis_scan_keys(redis_client: Any, pattern: str) -> List[Any]:
    out: List[Any] = []
    async for key in redis_client.scan_iter(match=pattern):
        out.append(key)
    return out


async def redis_scan_keys_max(
    redis_client: Any, pattern: str, max_keys: Optional[int] = None
) -> List[Any]:
    out: List[Any] = []
    async for key in redis_client.scan_iter(match=pattern):
        out.append(key)
        if max_keys is not None and len(out) >= max_keys:
            break
    return out


async def redis_delete_keys(
    redis_client: Any, keys: List[Any], chunk_size: int = 500
) -> int:
    if not keys:
        return 0
    total = 0
    for i in range(0, len(keys), chunk_size):
        chunk = keys[i : i + chunk_size]
        total += int(await redis_client.delete(*chunk))
    return total


def _json_serializer(obj: Any) -> Any:
    """Custom JSON serializer for non-standard types."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, set):
        return list(obj)
    elif hasattr(obj, "__dict__"):
        return obj.__dict__
    else:
        return str(obj)


def _msgpack_serializer(obj: Any) -> Any:
    """Custom msgpack serializer for non-standard types."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, set):
        return list(obj)
    else:
        return obj


def calculate_ttl_with_jitter(base_ttl: int, jitter_percent: float = 10.0) -> int:
    """
    Calculate TTL with random jitter to prevent thundering herd.

    Args:
        base_ttl: Base TTL in seconds
        jitter_percent: Percentage of jitter to add (0-100)

    Returns:
        TTL with jitter applied
    """
    import random

    if jitter_percent <= 0:
        return base_ttl

    jitter_amount = int(base_ttl * (jitter_percent / 100))
    jitter = random.randint(-jitter_amount, jitter_amount)

    return max(1, base_ttl + jitter)  # Ensure TTL is at least 1 second


def extract_table_from_query(query: str) -> Optional[str]:
    """
    Extract table name from SQL query (simple heuristic).

    Args:
        query: SQL query string

    Returns:
        Extracted table name or None if not found
    """
    if not query:
        return None

    # Simple regex patterns for common SQL operations
    import re

    # Normalize query
    normalized = query.strip().lower()

    # Pattern for SELECT ... FROM table
    select_pattern = r"\bfrom\s+([a-zA-Z_][a-zA-Z0-9_]*)"
    match = re.search(select_pattern, normalized)
    if match:
        return match.group(1)

    # Pattern for INSERT INTO table
    insert_pattern = r"\binsert\s+into\s+([a-zA-Z_][a-zA-Z0-9_]*)"
    match = re.search(insert_pattern, normalized)
    if match:
        return match.group(1)

    # Pattern for UPDATE table
    update_pattern = r"\bupdate\s+([a-zA-Z_][a-zA-Z0-9_]*)"
    match = re.search(update_pattern, normalized)
    if match:
        return match.group(1)

    # Pattern for DELETE FROM table
    delete_pattern = r"\bdelete\s+from\s+([a-zA-Z_][a-zA-Z0-9_]*)"
    match = re.search(delete_pattern, normalized)
    if match:
        return match.group(1)

    return None


def get_operation_type_from_query(query: str) -> str:
    """
    Determine operation type from SQL query.

    Args:
        query: SQL query string

    Returns:
        Operation type ('select', 'insert', 'update', 'delete', 'unknown')
    """
    if not query:
        return "unknown"

    normalized = query.strip().lower()

    if normalized.startswith("select"):
        return "select"
    elif normalized.startswith("insert"):
        return "insert"
    elif normalized.startswith("update"):
        return "update"
    elif normalized.startswith("delete"):
        return "delete"
    else:
        return "unknown"


def timing_decorator(func):
    """Decorator to measure function execution time."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000
            logger.debug(f"{func.__name__} executed in {duration_ms:.2f}ms")

    return wrapper


def timing_decorator_async(func):
    """Async decorator to measure function execution time."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000
            logger.debug(f"{func.__name__} executed in {duration_ms:.2f}ms")

    return wrapper


def sanitize_key(key: str) -> str:
    """
    Sanitize cache key to ensure Redis compatibility.

    Args:
        key: Original cache key

    Returns:
        Sanitized cache key
    """
    # Replace problematic characters
    sanitized = key.replace(" ", "_").replace("\n", "").replace("\r", "")

    # Ensure reasonable length (Redis keys can be up to 512MB, but shorter is better)
    if len(sanitized) > 250:
        prefix = sanitized[:100]
        suffix_hash = hashlib.sha256(sanitized[100:].encode()).hexdigest()
        sanitized = f"{prefix}#{suffix_hash}"

    return sanitized


def parse_redis_url(url: str) -> Dict[str, Any]:
    """
    Parse Redis URL into connection parameters.

    Args:
        url: Redis URL (e.g., redis://user:pass@host:port/db)

    Returns:
        Dictionary of connection parameters
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)

    params = {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 6379,
        "db": 0,
        "password": parsed.password,
        "ssl": parsed.scheme == "rediss",
    }

    # Extract database number from path
    if parsed.path and parsed.path != "/":
        try:
            params["db"] = int(parsed.path.lstrip("/"))
        except ValueError:
            pass

    return params


def format_bytes(bytes_value: int) -> str:
    """
    Format bytes value in human-readable format.

    Args:
        bytes_value: Number of bytes

    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    if bytes_value < 1024:
        return f"{bytes_value} B"
    elif bytes_value < 1024**2:
        return f"{bytes_value / 1024:.1f} KB"
    elif bytes_value < 1024**3:
        return f"{bytes_value / (1024 ** 2):.1f} MB"
    else:
        return f"{bytes_value / (1024 ** 3):.1f} GB"


def normalize_tags(tags: Union[str, List[str], Set[str]]) -> Set[str]:
    """
    Normalize tags to a consistent set format.

    Args:
        tags: Tags in various formats

    Returns:
        Normalized set of tags
    """
    if isinstance(tags, str):
        return {tags}
    elif isinstance(tags, (list, tuple)):
        return set(tags)
    elif isinstance(tags, set):
        return tags
    else:
        return set()


def get_current_timestamp() -> float:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc).timestamp()


def timestamp_to_datetime(timestamp: float) -> datetime:
    """Convert timestamp to UTC datetime."""
    return datetime.fromtimestamp(timestamp, timezone.utc)
