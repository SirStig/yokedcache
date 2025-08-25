"""
Comprehensive tests for decorators module to increase coverage.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from yokedcache import CacheConfig, YokedCache
from yokedcache.decorators import CachedDatabaseWrapper, cached, cached_dependency


class TestCachedDecorator:
    """Test the @cached decorator."""

    @pytest.mark.asyncio
    async def test_cached_decorator_basic(self):
        """Test basic cached decorator functionality."""
        cache = YokedCache()

        @cached(cache, ttl=300)
        async def test_function(x, y):
            return x + y

        with (
            patch.object(cache, "get") as mock_get,
            patch.object(cache, "set") as mock_set,
        ):

            mock_get.return_value = None  # Cache miss
            mock_set.return_value = True

            result = await test_function(1, 2)
            assert result == 3

            mock_get.assert_called_once()
            mock_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_cached_decorator_cache_hit(self):
        """Test cached decorator with cache hit."""
        cache = YokedCache()

        @cached(cache, ttl=300)
        async def test_function(x, y):
            return x + y

        with patch.object(cache, "get") as mock_get:
            mock_get.return_value = 5  # Cache hit

            result = await test_function(1, 2)
            assert result == 5  # Should return cached value

            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_cached_decorator_with_tags(self):
        """Test cached decorator with tags."""
        cache = YokedCache()

        @cached(cache, ttl=300, tags=["user", "profile"])
        async def get_user_profile(user_id):
            return {"id": user_id, "name": "Test User"}

        with (
            patch.object(cache, "get") as mock_get,
            patch.object(cache, "set") as mock_set,
        ):

            mock_get.return_value = None
            mock_set.return_value = True

            result = await get_user_profile(123)
            assert result["id"] == 123

            # Check that set was called with tags
            mock_set.assert_called_once()
            args, kwargs = mock_set.call_args
            assert kwargs.get("tags") == ["user", "profile"]

    @pytest.mark.asyncio
    async def test_cached_decorator_custom_key_func(self):
        """Test cached decorator with custom key function."""
        cache = YokedCache()

        def custom_key_func(*args, **kwargs):
            return f"custom:{args[0]}"

        @cached(cache, key_func=custom_key_func)
        async def test_function(user_id):
            return f"user_{user_id}"

        with patch.object(cache, "get") as mock_get:
            mock_get.return_value = None

            await test_function(123)

            # Check that get was called with custom key
            mock_get.assert_called_once()
            args, kwargs = mock_get.call_args
            assert args[0] == "custom:123"

    @pytest.mark.asyncio
    async def test_cached_decorator_sync_function(self):
        """Test cached decorator with synchronous function."""
        cache = YokedCache()

        @cached(cache, ttl=300)
        def sync_function(x, y):
            return x * y

        with (
            patch.object(cache, "get_sync") as mock_get,
            patch.object(cache, "set_sync") as mock_set,
        ):

            mock_get.return_value = None
            mock_set.return_value = True

            result = sync_function(3, 4)
            assert result == 12

            mock_get.assert_called_once()
            mock_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_cached_decorator_cache_error(self):
        """Test cached decorator handling cache errors."""
        cache = YokedCache()

        @cached(cache, ttl=300)
        async def test_function(x):
            return x * 2

        with patch.object(cache, "get", side_effect=Exception("Cache error")):
            # Should still execute function when cache fails
            result = await test_function(5)
            assert result == 10

    def test_cached_decorator_no_cache(self):
        """Test cached decorator with no cache instance."""

        @cached(None)
        def test_function(x):
            return x + 1

        # Should work normally without caching
        result = test_function(5)
        assert result == 6

    @pytest.mark.asyncio
    async def test_cached_decorator_conditional_caching(self):
        """Test cached decorator with conditional caching."""
        cache = YokedCache()

        def should_cache(result):
            return result > 0

        @cached(cache, condition=should_cache)
        async def test_function(x):
            return x

        with (
            patch.object(cache, "get") as mock_get,
            patch.object(cache, "set") as mock_set,
        ):

            mock_get.return_value = None
            mock_set.return_value = True

            # Test positive result (should cache)
            result = await test_function(5)
            assert result == 5
            mock_set.assert_called_once()

            mock_set.reset_mock()

            # Test negative result (should not cache)
            result = await test_function(-1)
            assert result == -1
            mock_set.assert_not_called()


class TestCachedDependencyDecorator:
    """Test the @cached_dependency decorator."""

    @pytest.mark.asyncio
    async def test_cached_dependency_basic(self):
        """Test basic cached_dependency decorator."""
        cache = YokedCache()

        @cached_dependency(cache, dependencies=["user:123"])
        async def get_user_data(user_id):
            return {"id": user_id, "data": "test"}

        with (
            patch.object(cache, "get") as mock_get,
            patch.object(cache, "set") as mock_set,
        ):

            mock_get.return_value = None
            mock_set.return_value = True

            result = await get_user_data(123)
            assert result["id"] == 123

            mock_get.assert_called_once()
            mock_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_cached_dependency_invalidation(self):
        """Test cached_dependency invalidation."""
        cache = YokedCache()

        @cached_dependency(cache, dependencies=["user:123"])
        async def get_user_data(user_id):
            return {"id": user_id, "version": 1}

        with (
            patch.object(cache, "get") as mock_get,
            patch.object(cache, "set") as mock_set,
            patch.object(cache, "invalidate_by_tags") as mock_invalidate,
        ):

            mock_get.return_value = None
            mock_set.return_value = True
            mock_invalidate.return_value = True

            # First call should cache
            result = await get_user_data(123)
            assert result["id"] == 123

            # Simulate dependency change
            await cache.invalidate_by_tags(["user:123"])
            mock_invalidate.assert_called_once()

    @pytest.mark.asyncio
    async def test_cached_dependency_dynamic_dependencies(self):
        """Test cached_dependency with dynamic dependencies."""
        cache = YokedCache()

        def get_dependencies(*args, **kwargs):
            user_id = args[0]
            return [f"user:{user_id}", f"profile:{user_id}"]

        @cached_dependency(cache, dependencies=get_dependencies)
        async def get_user_profile(user_id):
            return {"id": user_id, "profile": "data"}

        with (
            patch.object(cache, "get") as mock_get,
            patch.object(cache, "set") as mock_set,
        ):

            mock_get.return_value = None
            mock_set.return_value = True

            result = await get_user_profile(456)
            assert result["id"] == 456

            # Check that set was called with dynamic dependencies as tags
            mock_set.assert_called_once()
            args, kwargs = mock_set.call_args
            expected_tags = ["user:456", "profile:456"]
            assert kwargs.get("tags") == expected_tags


class TestCachedDatabaseWrapper:
    """Test the CachedDatabaseWrapper class."""

    def test_database_wrapper_init(self):
        """Test CachedDatabaseWrapper initialization."""
        cache = YokedCache()

        # Mock database session
        mock_session = MagicMock()

        wrapper = CachedDatabaseWrapper(mock_session, cache)
        assert wrapper.session == mock_session
        assert wrapper.cache == cache

    def test_database_wrapper_context_manager(self):
        """Test CachedDatabaseWrapper as context manager."""
        cache = YokedCache()
        mock_session = MagicMock()

        wrapper = CachedDatabaseWrapper(mock_session, cache)

        # Test that it can be used as context manager
        assert hasattr(wrapper, "__aenter__")
        assert hasattr(wrapper, "__aexit__")

    def test_database_wrapper_attributes(self):
        """Test CachedDatabaseWrapper attributes."""
        cache = YokedCache()
        mock_session = MagicMock()

        wrapper = CachedDatabaseWrapper(mock_session, cache)

        # Test basic attributes
        assert wrapper.session == mock_session
        assert wrapper.cache == cache
        assert hasattr(wrapper, "pending_invalidations")

    @pytest.mark.asyncio
    async def test_database_wrapper_commit(self):
        """Test CachedDatabaseWrapper commit functionality."""
        cache = YokedCache()
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()

        wrapper = CachedDatabaseWrapper(mock_session, cache)

        with patch.object(wrapper, "invalidate_pending") as mock_invalidate:
            await wrapper.commit()
            mock_session.commit.assert_called_once()
            mock_invalidate.assert_called_once()


class TestDecoratorUtilities:
    """Test decorator utility functions."""

    def test_build_function_cache_key(self):
        """Test cache key generation from function."""
        from yokedcache.decorators import _build_function_cache_key

        def test_func(a, b, c=None):
            pass

        key = _build_function_cache_key(test_func, (1, 2), {"c": 3})
        assert isinstance(key, str)
        assert len(key) > 0

    def test_build_function_cache_key_consistency(self):
        """Test cache key generation consistency."""
        from yokedcache.decorators import _build_function_cache_key

        def test_func(a, b):
            pass

        key1 = _build_function_cache_key(test_func, (1, 2), {})
        key2 = _build_function_cache_key(test_func, (1, 2), {})
        assert key1 == key2

    def test_build_function_cache_key_different_args(self):
        """Test cache key generation with different arguments."""
        from yokedcache.decorators import _build_function_cache_key

        def test_func(a, b):
            pass

        key1 = _build_function_cache_key(test_func, (1, 2), {})
        key2 = _build_function_cache_key(test_func, (3, 4), {})
        assert key1 != key2

    def test_decorator_module_imports(self):
        """Test that decorator module imports work correctly."""
        import yokedcache.decorators

        # Test that key functions are available
        assert hasattr(yokedcache.decorators, "cached")
        assert hasattr(yokedcache.decorators, "cached_dependency")
        assert hasattr(yokedcache.decorators, "CachedDatabaseWrapper")

    def test_cached_decorator_function_inspection(self):
        """Test that cached decorator preserves function metadata."""
        cache = YokedCache()

        @cached(cache)
        def test_function(x, y):
            """Test function docstring."""
            return x + y

        # Function should preserve its name and docstring
        assert test_function.__name__ == "test_function"
        doc = test_function.__doc__
        assert doc is not None and "Test function docstring" in doc

    def test_cached_dependency_function_inspection(self):
        """Test that cached_dependency preserves function metadata."""
        cache = YokedCache()

        @cached_dependency
        def test_dependency():
            """Test dependency docstring."""
            return "dependency_result"

        # Function should preserve its name and docstring
        assert test_dependency.__name__ == "test_dependency"
        dep_doc = test_dependency.__doc__
        assert dep_doc is not None and "Test dependency docstring" in dep_doc
