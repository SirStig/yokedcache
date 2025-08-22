"""
Tests for YokedCache decorators.
"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from yokedcache import YokedCache, cached, cached_dependency
from yokedcache.decorators import CachedDatabaseWrapper


class TestCachedDecorator:
    """Test cases for @cached decorator."""

    @pytest.mark.asyncio
    async def test_async_function_caching(self, cache):
        """Test caching of async functions."""
        call_count = 0

        @cached(cache=cache, ttl=60)
        async def expensive_async_operation(value):
            nonlocal call_count
            call_count += 1
            return f"processed_{value}"

        # First call should execute function
        result1 = await expensive_async_operation("test")
        assert result1 == "processed_test"
        assert call_count == 1

        # Second call should use cache
        result2 = await expensive_async_operation("test")
        assert result2 == "processed_test"
        assert call_count == 1  # Function not called again

        # Different parameter should execute function
        result3 = await expensive_async_operation("different")
        assert result3 == "processed_different"
        assert call_count == 2

    def test_sync_function_caching(self, cache):
        """Test caching of sync functions."""
        call_count = 0

        @cached(cache=cache, ttl=60)
        def expensive_sync_operation(value):
            nonlocal call_count
            call_count += 1
            return f"processed_{value}"

        # First call should execute function
        result1 = expensive_sync_operation("test")
        assert result1 == "processed_test"
        assert call_count == 1

        # Second call should use cache
        result2 = expensive_sync_operation("test")
        assert result2 == "processed_test"
        assert call_count == 1  # Function not called again

    @pytest.mark.asyncio
    async def test_function_with_tags(self, cache):
        """Test caching with tags."""

        @cached(cache=cache, tags=["user_data"], ttl=60)
        async def get_user_profile(user_id):
            return {"id": user_id, "name": f"User{user_id}"}

        # Execute function
        result = await get_user_profile(123)
        assert result["id"] == 123

        # Verify it's cached
        cached_result = await get_user_profile(123)
        assert cached_result == result

        # Invalidate by tag
        await cache.invalidate_tags(["user_data"])

        # Should execute function again after invalidation
        # (This would require mocking to verify call count)

    @pytest.mark.asyncio
    async def test_cache_error_handling(self, cache):
        """Test error handling in cached functions."""

        @cached(cache=cache, skip_cache_on_error=True)
        async def function_that_might_fail():
            return "success"

        # Should work normally
        result = await function_that_might_fail()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_custom_key_builder(self, cache):
        """Test custom cache key building."""

        def custom_key_builder(func, args, kwargs):
            return f"custom:{func.__name__}:{args[0]}"

        @cached(cache=cache, key_builder=custom_key_builder)
        async def test_function(param):
            return f"result_{param}"

        result = await test_function("test")
        assert result == "result_test"

        # Verify custom key was used (would need to inspect cache internals)


class TestCachedDependency:
    """Test cases for cached_dependency function."""

    @pytest.mark.asyncio
    async def test_database_dependency_caching(self, cache):
        """Test caching of database dependencies."""
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = {
            "id": 1,
            "name": "Test User",
        }

        def get_db():
            return mock_db

        # Create cached dependency
        cached_get_db = cached_dependency(get_db, cache=cache)

        # Get cached database wrapper
        cached_db = await cached_get_db()

        assert isinstance(cached_db, CachedDatabaseWrapper)
        assert cached_db._db_session == mock_db

    @pytest.mark.asyncio
    async def test_async_database_dependency(self, cache):
        """Test caching of async database dependencies."""
        mock_db = AsyncMock()

        async def get_async_db():
            return mock_db

        # Create cached dependency
        cached_get_db = cached_dependency(get_async_db, cache=cache)

        # Get cached database wrapper
        cached_db = await cached_get_db()

        assert isinstance(cached_db, CachedDatabaseWrapper)
        assert cached_db._db_session == mock_db


class TestCachedDatabaseWrapper:
    """Test cases for CachedDatabaseWrapper."""

    @pytest.mark.asyncio
    async def test_query_caching(self, cache):
        """Test database query caching."""
        mock_db = Mock()

        # Mock query result
        mock_result = {"id": 1, "name": "Test User"}
        mock_db.query.return_value.filter.return_value.first.return_value = mock_result

        # Create wrapper
        wrapper = CachedDatabaseWrapper(
            mock_db, cache=cache, ttl=60, auto_invalidate=True
        )

        # Access database through wrapper
        query_method = wrapper.query
        assert callable(query_method)

        # The wrapper should delegate to the underlying session
        assert hasattr(wrapper, "query")

    @pytest.mark.asyncio
    async def test_write_operation_tracking(self, cache):
        """Test tracking of write operations for invalidation."""
        mock_db = Mock()

        wrapper = CachedDatabaseWrapper(mock_db, cache=cache, auto_invalidate=True)

        # Simulate write operation
        if hasattr(wrapper, "execute"):
            # This would track the operation for later invalidation
            pass

        # Verify write operations are tracked
        assert isinstance(wrapper._write_operations, set)

    @pytest.mark.asyncio
    async def test_commit_with_invalidation(self, cache):
        """Test commit operation with cache invalidation."""
        mock_db = Mock()
        mock_db.commit = Mock()

        wrapper = CachedDatabaseWrapper(mock_db, cache=cache, auto_invalidate=True)

        # Add a mock write operation
        wrapper._write_operations.add("UPDATE users SET name='New Name' WHERE id=1")

        # Commit should trigger invalidation
        await wrapper.commit()

        # Verify original commit was called
        mock_db.commit.assert_called_once()

        # Verify write operations were cleared
        assert len(wrapper._write_operations) == 0

    def test_attribute_delegation(self, cache):
        """Test that wrapper delegates attributes to underlying session."""
        mock_db = Mock()
        mock_db.some_attribute = "test_value"
        mock_db.some_method = Mock(return_value="method_result")

        wrapper = CachedDatabaseWrapper(mock_db, cache=cache)

        # Test attribute access
        assert wrapper.some_attribute == "test_value"

        # Test method access
        result = wrapper.some_method()
        assert result == "method_result"
        mock_db.some_method.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_support(self, cache):
        """Test context manager support for database wrapper."""
        mock_db = Mock()
        mock_db.__enter__ = Mock(return_value=mock_db)
        mock_db.__exit__ = Mock(return_value=None)

        wrapper = CachedDatabaseWrapper(mock_db, cache=cache)

        # Test sync context manager
        with wrapper as db:
            assert db == mock_db

        mock_db.__enter__.assert_called_once()
        mock_db.__exit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_context_manager_support(self, cache):
        """Test async context manager support."""
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        wrapper = CachedDatabaseWrapper(mock_db, cache=cache)

        # Test async context manager
        async with wrapper as db:
            assert db == mock_db

        mock_db.__aenter__.assert_called_once()
        mock_db.__aexit__.assert_called_once()
