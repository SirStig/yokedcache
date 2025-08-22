"""
Decorators for YokedCache integration.

This module provides decorators for easy integration with FastAPI and other
Python frameworks, enabling automatic caching of functions and dependencies.
"""

import asyncio
import functools
import inspect
from typing import Any, Callable, Optional, Union, Set, List, TypeVar, Dict
from datetime import datetime

from .cache import YokedCache
from .config import CacheConfig
from .utils import generate_cache_key, extract_table_from_query
from .models import SerializationMethod


F = TypeVar('F', bound=Callable[..., Any])


def cached(
    cache: Optional[YokedCache] = None,
    ttl: Optional[int] = None,
    key_prefix: Optional[str] = None,
    tags: Optional[Union[str, List[str], Set[str]]] = None,
    table: Optional[str] = None,
    serialization: Optional[SerializationMethod] = None,
    skip_cache_on_error: bool = True,
    key_builder: Optional[Callable] = None,
) -> Callable[[F], F]:
    """
    Decorator to cache function results.
    
    Args:
        cache: YokedCache instance (if None, creates default)
        ttl: Cache TTL in seconds
        key_prefix: Custom key prefix for this function
        tags: Tags for cache invalidation
        table: Database table name for auto-invalidation
        serialization: Serialization method
        skip_cache_on_error: If True, skip cache on errors and call original function
        key_builder: Custom function to build cache keys
    
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        # Get cache instance
        actual_cache = cache if cache is not None else YokedCache()
        
        # Determine if function is async
        is_async = inspect.iscoroutinefunction(func)
        
        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await _cached_call(
                    func, actual_cache, args, kwargs,
                    ttl=ttl,
                    key_prefix=key_prefix or func.__name__,
                    tags=tags,
                    table=table,
                    serialization=serialization,
                    skip_cache_on_error=skip_cache_on_error,
                    key_builder=key_builder,
                )
            return async_wrapper  # type: ignore
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                # For sync functions, we need to handle the async cache operations
                return asyncio.run(_cached_call(
                    func, actual_cache, args, kwargs,
                    ttl=ttl,
                    key_prefix=key_prefix or func.__name__,
                    tags=tags,
                    table=table,
                    serialization=serialization,
                    skip_cache_on_error=skip_cache_on_error,
                    key_builder=key_builder,
                ))
            return sync_wrapper  # type: ignore
    
    return decorator


async def _cached_call(
    func: Callable,
    cache: YokedCache,
    args: tuple,
    kwargs: dict,
    ttl: Optional[int] = None,
    key_prefix: str = "cached_func",
    tags: Optional[Union[str, List[str], Set[str]]] = None,
    table: Optional[str] = None,
    serialization: Optional[SerializationMethod] = None,
    skip_cache_on_error: bool = True,
    key_builder: Optional[Callable] = None,
) -> Any:
    """Internal function to handle cached function calls."""
    
    try:
        # Build cache key
        if key_builder:
            cache_key = key_builder(func, args, kwargs)
        else:
            cache_key = _build_function_cache_key(func, args, kwargs, key_prefix)
        
        # Try to get from cache first
        try:
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                return cached_result
        except Exception as e:
            if not skip_cache_on_error:
                raise
            # Continue to call original function
        
        # Call original function
        if inspect.iscoroutinefunction(func):
            result = await func(*args, **kwargs)
        else:
            result = func(*args, **kwargs)
        
        # Cache the result
        try:
            await cache.set(
                cache_key,
                result,
                ttl=ttl,
                tags=tags,
                serialization=serialization,
            )
        except Exception as e:
            if not skip_cache_on_error:
                raise
            # Just log and continue
            import logging
            logging.getLogger(__name__).warning(f"Failed to cache result: {e}")
        
        return result
        
    except Exception as e:
        if skip_cache_on_error:
            # Fall back to original function
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        else:
            raise


def cached_dependency(
    dependency_func: Callable,
    cache: Optional[YokedCache] = None,
    ttl: Optional[int] = None,
    key_prefix: Optional[str] = None,
    table_name: Optional[str] = None,
    auto_invalidate: bool = True,
) -> Callable:
    """
    Wrap a FastAPI dependency with caching.
    
    This is specifically designed for database dependencies like get_db().
    
    Args:
        dependency_func: Original dependency function
        cache: YokedCache instance
        ttl: Cache TTL in seconds
        key_prefix: Custom key prefix
        table_name: Table name for auto-invalidation
        auto_invalidate: Enable auto-invalidation on writes
    
    Returns:
        Cached dependency function
    """
    if cache is None:
        cache = YokedCache()
    
    # Create a cached database wrapper
    async def cached_db_dependency(*args, **kwargs):
        # Get the original database session/connection
        if inspect.iscoroutinefunction(dependency_func):
            db_session = await dependency_func(*args, **kwargs)
        else:
            db_session = dependency_func(*args, **kwargs)
        
        # Wrap it with caching capabilities
        return CachedDatabaseWrapper(
            db_session,
            cache=cache,
            ttl=ttl,
            key_prefix=key_prefix or "db",
            table_name=table_name,
            auto_invalidate=auto_invalidate,
        )
    
    return cached_db_dependency


class CachedDatabaseWrapper:
    """
    Wrapper for database sessions that adds caching capabilities.
    
    This wrapper intercepts database queries and automatically caches results
    while also handling cache invalidation on write operations.
    """
    
    def __init__(
        self,
        db_session: Any,
        cache: YokedCache,
        ttl: Optional[int] = None,
        key_prefix: str = "db",
        table_name: Optional[str] = None,
        auto_invalidate: bool = True,
    ):
        self._db_session = db_session
        self._cache = cache
        self._ttl = ttl
        self._key_prefix = key_prefix
        self._table_name = table_name
        self._auto_invalidate = auto_invalidate
        
        # Track queries for invalidation
        self._write_operations: Set[str] = set()
    
    def __getattr__(self, name):
        """Delegate attribute access to the underlying database session."""
        attr = getattr(self._db_session, name)
        
        # If it's a method that might be a query, wrap it
        if callable(attr) and name in ('query', 'execute', 'exec', 'get', 'first', 'all'):
            return self._wrap_query_method(attr, name)
        
        return attr
    
    def _wrap_query_method(self, method: Callable, method_name: str) -> Callable:
        """Wrap database query methods with caching logic."""
        
        @functools.wraps(method)
        async def async_cached_method(*args, **kwargs):
            return await self._execute_cached_query(method, args, kwargs, method_name)
        
        @functools.wraps(method)
        def sync_cached_method(*args, **kwargs):
            # For sync methods, we need to run the async cache operations
            return asyncio.run(self._execute_cached_query(method, args, kwargs, method_name))
        
        # Return appropriate wrapper based on whether original method is async
        if inspect.iscoroutinefunction(method):
            return async_cached_method
        else:
            return sync_cached_method
    
    async def _execute_cached_query(
        self,
        method: Callable,
        args: tuple,
        kwargs: dict,
        method_name: str,
    ) -> Any:
        """Execute a database query with caching logic."""
        
        # Build cache key from query
        cache_key = self._build_query_cache_key(method_name, args, kwargs)
        
        # For read operations, try cache first
        if method_name in ('query', 'get', 'first', 'all'):
            try:
                cached_result = await self._cache.get(cache_key)
                if cached_result is not None:
                    return cached_result
            except Exception:
                pass  # Continue with actual query
        
        # Execute the actual query
        if inspect.iscoroutinefunction(method):
            result = await method(*args, **kwargs)
        else:
            result = method(*args, **kwargs)
        
        # For read operations, cache the result
        if method_name in ('query', 'get', 'first', 'all') and result is not None:
            try:
                # Determine TTL and tags
                actual_ttl = self._ttl or self._cache.config.default_ttl
                tags = set()
                
                if self._table_name:
                    tags.add(f"table:{self._table_name}")
                
                # Try to extract table from query if available
                if args and isinstance(args[0], str):
                    extracted_table = extract_table_from_query(args[0])
                    if extracted_table:
                        tags.add(f"table:{extracted_table}")
                
                await self._cache.set(
                    cache_key,
                    result,
                    ttl=actual_ttl,
                    tags=tags,
                )
            except Exception:
                pass  # Don't fail the query if caching fails
        
        # For write operations, track for invalidation
        if self._auto_invalidate and method_name in ('execute', 'exec'):
            if args and isinstance(args[0], str):
                query_str = args[0].lower().strip()
                if any(op in query_str for op in ['insert', 'update', 'delete']):
                    self._write_operations.add(args[0])
        
        return result
    
    def _build_query_cache_key(self, method_name: str, args: tuple, kwargs: dict) -> str:
        """Build cache key for database query."""
        # Create a hash of the query and parameters
        key_parts = [self._key_prefix, method_name]
        
        # Add table name if available
        if self._table_name:
            key_parts.append(f"table:{self._table_name}")
        
        # Hash the arguments
        import hashlib
        import json
        
        # Convert args and kwargs to hashable representation
        hashable_data = {
            "args": [str(arg) for arg in args],
            "kwargs": {k: str(v) for k, v in kwargs.items()},
        }
        
        data_str = json.dumps(hashable_data, sort_keys=True)
        query_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]
        
        key_parts.append(f"hash:{query_hash}")
        
        return ":".join(key_parts)
    
    async def commit(self):
        """Handle commit operations with cache invalidation."""
        # Call original commit
        if hasattr(self._db_session, 'commit'):
            if inspect.iscoroutinefunction(self._db_session.commit):
                await self._db_session.commit()
            else:
                self._db_session.commit()
        
        # Invalidate caches for any write operations
        if self._auto_invalidate and self._write_operations:
            await self._invalidate_for_writes()
            self._write_operations.clear()
    
    async def _invalidate_for_writes(self):
        """Invalidate caches based on write operations."""
        tables_to_invalidate = set()
        
        for query in self._write_operations:
            table = extract_table_from_query(query)
            if table:
                tables_to_invalidate.add(table)
        
        # Invalidate by table tags
        for table in tables_to_invalidate:
            try:
                await self._cache.invalidate_tags([f"table:{table}"])
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to invalidate cache for table {table}: {e}")
    
    def __enter__(self):
        """Context manager support."""
        if hasattr(self._db_session, '__enter__'):
            return self._db_session.__enter__()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager support."""
        if hasattr(self._db_session, '__exit__'):
            return self._db_session.__exit__(exc_type, exc_val, exc_tb)
    
    async def __aenter__(self):
        """Async context manager support."""
        if hasattr(self._db_session, '__aenter__'):
            return await self._db_session.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager support."""
        if hasattr(self._db_session, '__aexit__'):
            return await self._db_session.__aexit__(exc_type, exc_val, exc_tb)
        
        # Always try to commit and invalidate on exit
        await self.commit()


def _build_function_cache_key(
    func: Callable,
    args: tuple,
    kwargs: dict,
    prefix: str = "func",
) -> str:
    """Build cache key for function calls."""
    import hashlib
    import json
    
    # Get function signature for consistent key generation
    sig = inspect.signature(func)
    bound_args = sig.bind(*args, **kwargs)
    bound_args.apply_defaults()
    
    # Create hashable representation
    key_data = {
        "function": f"{func.__module__}.{func.__name__}",
        "args": {},
    }
    
    # Add bound arguments
    for param_name, value in bound_args.arguments.items():
        try:
            # Try to convert to JSON-serializable format
            key_data["args"][param_name] = json.loads(json.dumps(value, default=str))
        except (TypeError, ValueError):
            # Fall back to string representation
            key_data["args"][param_name] = str(value)
    
    # Generate hash
    data_str = json.dumps(key_data, sort_keys=True)
    func_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]
    
    return f"{prefix}:func:{func.__name__}:hash:{func_hash}"


# Utility function for manual cache warming
async def warm_cache(
    cache: YokedCache,
    functions_to_warm: List[Dict[str, Any]],
) -> int:
    """
    Warm cache by pre-executing functions.
    
    Args:
        cache: YokedCache instance
        functions_to_warm: List of function configurations
            [{"func": function, "args": [], "kwargs": {}, "ttl": 300}, ...]
    
    Returns:
        Number of functions successfully warmed
    """
    warmed_count = 0
    
    for func_config in functions_to_warm:
        try:
            func = func_config["func"]
            args = func_config.get("args", [])
            kwargs = func_config.get("kwargs", {})
            ttl = func_config.get("ttl")
            
            # Execute function and cache result
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Build cache key and store
            cache_key = _build_function_cache_key(func, args, kwargs)
            await cache.set(cache_key, result, ttl=ttl)
            
            warmed_count += 1
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to warm cache for function: {e}")
    
    return warmed_count
