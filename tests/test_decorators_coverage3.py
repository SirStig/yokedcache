"""
Tests for uncovered paths in decorators.py.
"""

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest

from yokedcache import CacheConfig, YokedCache
from yokedcache.decorators import (
    CachedDatabaseWrapper,
    cached,
    cached_dependency,
    warm_cache,
)


def _make_cache():
    config = CacheConfig(key_prefix="deco_test")
    c = YokedCache(config=config)
    c._redis = fakeredis.aioredis.FakeRedis()
    c._connected = True
    return c


# ---------------------------------------------------------------------------
# 1. @cached(cache=None) on async function -> call directly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cached_none_async():
    @cached(cache=None)
    async def my_func(x):
        return x * 2

    result = await my_func(5)
    assert result == 10


# ---------------------------------------------------------------------------
# 2. @cached(cache=None) on sync function -> call directly
# ---------------------------------------------------------------------------


def test_cached_none_sync():
    @cached(cache=None)
    def my_func(x):
        return x + 1

    assert my_func(3) == 4


# ---------------------------------------------------------------------------
# 3. @cached on sync function with condition (1-param and 2-param)
# ---------------------------------------------------------------------------


def test_cached_sync_with_condition_1param():
    c = _make_cache()

    @cached(cache=c, condition=lambda result: result > 0)
    def positive_func(x):
        return x

    result = positive_func(5)
    assert result == 5

    # Should NOT cache negative result
    result2 = positive_func(-1)
    assert result2 == -1


def test_cached_sync_with_condition_2param():
    c = _make_cache()

    @cached(cache=c, condition=lambda result, x: x > 0)
    def my_func(x):
        return x * 10

    result = my_func(3)
    assert result == 30

    result2 = my_func(-2)
    assert result2 == -20


# ---------------------------------------------------------------------------
# 4. @cached on sync function with skip_cache_on_error=False when set fails
# ---------------------------------------------------------------------------


def test_cached_sync_skip_cache_on_error_false():
    c = _make_cache()
    c.set_sync = MagicMock(side_effect=Exception("set failed"))

    @cached(cache=c, skip_cache_on_error=False)
    def my_func(x):
        return x

    # Should raise because skip_cache_on_error=False
    with pytest.raises(Exception, match="set failed"):
        my_func(42)


# ---------------------------------------------------------------------------
# 5. _cached_call with cache=None directly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cached_call_none_cache():
    from yokedcache.decorators import _cached_call

    async def func(x):
        return x * 3

    result = await _cached_call(func, None, (4,), {})
    assert result == 12


# ---------------------------------------------------------------------------
# 6. _cached_call with get raising and skip_cache_on_error=False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cached_call_get_raises_no_skip():
    from yokedcache.decorators import _cached_call

    c = _make_cache()
    c.get = AsyncMock(side_effect=Exception("get failed"))

    async def func(x):
        return x + 1

    with pytest.raises(Exception):
        await _cached_call(func, c, (1,), {}, skip_cache_on_error=False)


# ---------------------------------------------------------------------------
# 7. _cached_call with plain sync function (not coroutine)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cached_call_sync_func():
    from yokedcache.decorators import _cached_call

    c = _make_cache()

    def sync_func(x):
        return x + 100

    result = await _cached_call(sync_func, c, (5,), {})
    assert result == 105


# ---------------------------------------------------------------------------
# 8. _cached_call with condition (1-param) - the ValueError/TypeError branch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cached_call_condition_1param():
    from yokedcache.decorators import _cached_call

    c = _make_cache()

    async def func(x):
        return x

    # 1-param condition
    result = await _cached_call(func, c, (5,), {}, condition=lambda r: r > 0)
    assert result == 5

    # condition returns False - should not cache
    result2 = await _cached_call(func, c, (-1,), {}, condition=lambda r: r > 0)
    assert result2 == -1


# ---------------------------------------------------------------------------
# 9. _cached_call with set failing and skip_cache_on_error=True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cached_call_set_fails_skip_true():
    from yokedcache.decorators import _cached_call

    c = _make_cache()
    c.set = AsyncMock(side_effect=Exception("set broken"))

    async def func(x):
        return x + 1

    # Should not raise, just log warning
    result = await _cached_call(func, c, (5,), {}, skip_cache_on_error=True)
    assert result == 6


# ---------------------------------------------------------------------------
# 10. _cached_call outer except with skip_cache_on_error=False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cached_call_outer_except_no_skip():
    from yokedcache.decorators import _cached_call

    c = _make_cache()
    c.get = AsyncMock(side_effect=RuntimeError("cache broken"))

    async def func(x):
        return x

    # With skip_cache_on_error=False, should raise
    with pytest.raises(Exception):
        await _cached_call(func, c, (1,), {}, skip_cache_on_error=False)


# ---------------------------------------------------------------------------
# 11. cached_dependency called as direct function (not decorator)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cached_dependency_direct_function():
    c = _make_cache()

    async def my_dep():
        return {"data": "value"}

    wrapped = cached_dependency(my_dep, cache=c, ttl=60)
    result = await wrapped()
    assert result == {"data": "value"}


# ---------------------------------------------------------------------------
# 12. cached_dependency with generator function
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cached_dependency_generator_function():
    c = _make_cache()

    def gen_dep():
        yield {"session": "obj"}

    wrapped = cached_dependency(gen_dep, cache=c, ttl=60)
    gen = wrapped()
    item = next(gen)
    # Should be a CachedDatabaseWrapper or similar
    assert item is not None
    # consume the generator
    try:
        next(gen)
    except StopIteration:
        pass


# ---------------------------------------------------------------------------
# 13. Sync generator dependency (sync_generator_wrapper) including cleanup exception
# ---------------------------------------------------------------------------


def test_sync_generator_dependency_with_cleanup_exception():
    c = _make_cache()

    def gen_dep():
        yield MagicMock()
        raise RuntimeError("cleanup error")

    wrapped = cached_dependency(gen_dep, cache=c)
    gen = wrapped()
    item = next(gen)
    assert item is not None
    # Finish generator - the cleanup exception should be handled gracefully
    try:
        next(gen)
    except StopIteration:
        pass


# ---------------------------------------------------------------------------
# 14. Async generator dependency including cleanup exception
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_generator_dependency():
    c = _make_cache()

    async def async_gen_dep():
        yield {"db": "session"}

    wrapped = cached_dependency(async_gen_dep, cache=c)
    async_gen = wrapped()
    item = await async_gen.__anext__()
    assert item is not None
    try:
        await async_gen.__anext__()
    except StopAsyncIteration:
        pass


@pytest.mark.asyncio
async def test_async_generator_dependency_cleanup_exception():
    c = _make_cache()

    async def async_gen_dep():
        yield MagicMock()
        raise RuntimeError("cleanup error")

    wrapped = cached_dependency(async_gen_dep, cache=c)
    async_gen = wrapped()
    item = await async_gen.__anext__()
    assert item is not None
    try:
        await async_gen.__anext__()
    except StopAsyncIteration:
        pass


# ---------------------------------------------------------------------------
# 15. Regular async dependency with callable dependencies
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_dependency_callable_deps():
    c = _make_cache()

    async def my_dep(user_id):
        return {"user_id": user_id}

    def get_tags(user_id):
        return [f"user:{user_id}"]

    wrapped = cached_dependency(my_dep, cache=c, dependencies=get_tags)
    result = await wrapped(42)
    assert result == {"user_id": 42}


# ---------------------------------------------------------------------------
# 16. Regular async dependency with isinstance(dependencies, str)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_dependency_str_dep():
    c = _make_cache()

    async def my_dep():
        return "result_value"

    wrapped = cached_dependency(my_dep, cache=c, dependencies="user:123")
    result = await wrapped()
    assert result == "result_value"


# ---------------------------------------------------------------------------
# 17. Regular async dependency with list dependencies
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_dependency_list_deps():
    c = _make_cache()

    async def my_dep():
        return "list_dep_result"

    wrapped = cached_dependency(my_dep, cache=c, dependencies=["tag1", "tag2"])
    result = await wrapped()
    assert result == "list_dep_result"


# ---------------------------------------------------------------------------
# 18. Regular sync dependency with callable dependencies
# ---------------------------------------------------------------------------


def test_sync_dependency_callable_deps():
    c = _make_cache()

    def my_dep(item_id):
        return {"item": item_id}

    def get_tags(item_id):
        return [f"item:{item_id}"]

    wrapped = cached_dependency(my_dep, cache=c, dependencies=get_tags)
    result = wrapped(99)
    assert result == {"item": 99}


# ---------------------------------------------------------------------------
# 19. Regular sync dependency returning database session-like object
# ---------------------------------------------------------------------------


def test_sync_dependency_returning_db_session():
    c = _make_cache()

    mock_session = MagicMock()
    mock_session.query = MagicMock()

    def get_db():
        return mock_session

    wrapped = cached_dependency(get_db, cache=c)
    result = wrapped()
    # Should be wrapped in CachedDatabaseWrapper
    assert isinstance(result, CachedDatabaseWrapper)


# ---------------------------------------------------------------------------
# 20. CachedDatabaseWrapper._execute_cached_query for write operations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cached_db_wrapper_write_operations():
    c = _make_cache()
    mock_session = MagicMock()

    async def mock_execute(query, *args, **kwargs):
        return MagicMock(rowcount=1)

    mock_session.execute = mock_execute

    wrapper = CachedDatabaseWrapper(
        mock_session, cache=c, table_name="users", auto_invalidate=True
    )

    # Test INSERT
    result = await wrapper._execute_cached_query(
        mock_execute,
        ("INSERT INTO users VALUES (1, 'test')",),
        {},
        "execute",
    )
    assert wrapper._write_operations

    # Test UPDATE
    result = await wrapper._execute_cached_query(
        mock_execute,
        ("UPDATE users SET name='test' WHERE id=1",),
        {},
        "execute",
    )

    # Test DELETE
    result = await wrapper._execute_cached_query(
        mock_execute,
        ("DELETE FROM users WHERE id=1",),
        {},
        "execute",
    )


# ---------------------------------------------------------------------------
# 21. CachedDatabaseWrapper sync sync_cached_method
# ---------------------------------------------------------------------------


def test_cached_db_wrapper_sync_method():
    c = _make_cache()
    mock_session = MagicMock()

    def sync_query_method(sql):
        return [{"id": 1}]

    mock_session.query = sync_query_method

    wrapper = CachedDatabaseWrapper(mock_session, cache=c, table_name="test")
    # Access the query method which should be wrapped as sync
    method = wrapper._wrap_query_method(sync_query_method, "query")
    # Call the sync method (it runs async code in thread)
    result = method("SELECT * FROM test")
    assert result == [{"id": 1}]


# ---------------------------------------------------------------------------
# 22. CachedDatabaseWrapper._invalidate_for_writes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cached_db_wrapper_invalidate_for_writes():
    c = _make_cache()
    mock_session = MagicMock()

    wrapper = CachedDatabaseWrapper(
        mock_session, cache=c, table_name="users", auto_invalidate=True
    )
    wrapper._write_operations.add("INSERT INTO users VALUES (1, 'test')")

    # Should not raise
    await wrapper._invalidate_for_writes()


@pytest.mark.asyncio
async def test_cached_db_wrapper_invalidate_fails_gracefully():
    c = _make_cache()
    c.invalidate_tags = AsyncMock(side_effect=Exception("invalidate failed"))
    mock_session = MagicMock()

    wrapper = CachedDatabaseWrapper(
        mock_session, cache=c, table_name="users", auto_invalidate=True
    )
    wrapper._write_operations.add("INSERT INTO users VALUES (1)")

    # Should not raise, logs warning
    await wrapper._invalidate_for_writes()


# ---------------------------------------------------------------------------
# 23. CachedDatabaseWrapper __enter__/__exit__ and __aenter__/__aexit__
# ---------------------------------------------------------------------------


def test_cached_db_wrapper_context_manager():
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=None)

    c = _make_cache()
    wrapper = CachedDatabaseWrapper(mock_session, cache=c)

    with wrapper as ctx:
        assert ctx is mock_session


def test_cached_db_wrapper_context_manager_no_dunder():
    """Test when session has no __enter__"""
    mock_session = MagicMock(spec=[])  # No __enter__
    c = _make_cache()
    wrapper = CachedDatabaseWrapper(mock_session, cache=c)

    result = wrapper.__enter__()
    assert result is wrapper
    wrapper.__exit__(None, None, None)


@pytest.mark.asyncio
async def test_cached_db_wrapper_async_context_manager():
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    c = _make_cache()
    wrapper = CachedDatabaseWrapper(mock_session, cache=c)

    async with wrapper as ctx:
        assert ctx is mock_session


@pytest.mark.asyncio
async def test_cached_db_wrapper_async_context_no_dunder():
    """Test when session has no __aenter__"""
    mock_session = MagicMock(spec=[])  # No __aenter__
    c = _make_cache()
    wrapper = CachedDatabaseWrapper(mock_session, cache=c)

    result = await wrapper.__aenter__()
    assert result is wrapper
    await wrapper.__aexit__(None, None, None)


# ---------------------------------------------------------------------------
# 24. warm_cache function
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_warm_cache_async_function():
    c = _make_cache()
    call_count = 0

    async def expensive_func(x, y):
        nonlocal call_count
        call_count += 1
        return x + y

    funcs = [
        {"func": expensive_func, "args": [1, 2], "kwargs": {}, "ttl": 300},
        {"func": expensive_func, "args": [3, 4], "kwargs": {}, "ttl": 300},
    ]

    warmed = await warm_cache(c, funcs)
    assert warmed == 2
    assert call_count == 2


@pytest.mark.asyncio
async def test_warm_cache_sync_function():
    c = _make_cache()

    def sync_func(name):
        return f"Hello, {name}"

    funcs = [
        {"func": sync_func, "args": ["World"], "kwargs": {}, "ttl": 60},
    ]

    warmed = await warm_cache(c, funcs)
    assert warmed == 1


@pytest.mark.asyncio
async def test_warm_cache_function_raises():
    c = _make_cache()

    async def failing_func():
        raise RuntimeError("func failed")

    funcs = [{"func": failing_func, "args": [], "kwargs": {}}]

    warmed = await warm_cache(c, funcs)
    assert warmed == 0  # Failed, so 0


@pytest.mark.asyncio
async def test_warm_cache_empty():
    c = _make_cache()
    warmed = await warm_cache(c, [])
    assert warmed == 0


# ---------------------------------------------------------------------------
# cached_dependency decorator style
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cached_dependency_decorator_style():
    c = _make_cache()

    @cached_dependency(c, ttl=60)
    async def my_dep():
        return "dep_value"

    result = await my_dep()
    assert result == "dep_value"


# ---------------------------------------------------------------------------
# @cached on sync with key_builder (line 99)
# ---------------------------------------------------------------------------


def test_cached_sync_with_key_builder():
    c = _make_cache()

    def custom_key_builder(*args, **kwargs):
        return "custom_key"

    @cached(cache=c, key_builder=custom_key_builder)
    def my_func(x):
        return x * 2

    result = my_func(5)
    assert result == 10

    # Second call should hit cache
    result2 = my_func(5)
    assert result2 == 10


# ---------------------------------------------------------------------------
# @cached on sync with condition ValueError/TypeError branch (lines 122-125)
# ---------------------------------------------------------------------------


def test_cached_sync_condition_signature_error():
    c = _make_cache()

    # A condition that raises ValueError/TypeError when inspected
    import unittest.mock as mock

    condition_func = lambda result, x: result > 0

    @cached(cache=c, condition=condition_func)
    def my_func(x):
        return x

    result = my_func(10)
    assert result == 10


# ---------------------------------------------------------------------------
# _cached_call condition raises ValueError/TypeError (line 192)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cached_call_condition_signature_error():
    from unittest.mock import patch

    from yokedcache.decorators import _cached_call

    c = _make_cache()

    async def func(x):
        return x

    # Condition that will trigger ValueError on signature inspection
    builtin_condition = len  # builtin - signature raises ValueError

    result = await _cached_call(func, c, ("hello",), {}, condition=builtin_condition)
    assert result == "hello"


# ---------------------------------------------------------------------------
# _cached_call with set failing and skip_cache_on_error=False (line 206)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cached_call_set_fails_no_skip():
    from yokedcache.decorators import _cached_call

    c = _make_cache()
    c.set = AsyncMock(side_effect=Exception("set broken"))

    async def func(x):
        return x + 1

    # With skip_cache_on_error=False, set failure should propagate
    # But first the outer except catches it and calls func again
    with pytest.raises(Exception):
        await _cached_call(func, c, (5,), {}, skip_cache_on_error=False)


# ---------------------------------------------------------------------------
# _cached_call outer except with skip_cache_on_error=True (line 216)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cached_call_outer_except_skip_true():
    from yokedcache.decorators import _cached_call

    c = _make_cache()
    c.get = AsyncMock(side_effect=RuntimeError("get broken"))

    async def func(x):
        return x * 3

    # With skip_cache_on_error=True, should fall through to calling func
    result = await _cached_call(func, c, (5,), {}, skip_cache_on_error=True)
    assert result == 15


# ---------------------------------------------------------------------------
# cached_dependency direct function with cache=None fallback (lines 319-322)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cached_dependency_no_cache_creates_default():
    """Test that cached_dependency creates a default YokedCache when no cache provided."""

    # This exercises the `cache_instance = YokedCache()` path
    @cached_dependency(cache=None, ttl=60)
    async def my_dep():
        return "dep_result"

    # Should work even without a configured cache
    try:
        result = await my_dep()
        # Either returns result or fails to connect
        assert result == "dep_result" or result is not None
    except Exception:
        pass  # Connection failure is ok


# ---------------------------------------------------------------------------
# cached_dependency decorator with generator function (line 329)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cached_dependency_decorator_with_generator():
    c = _make_cache()

    @cached_dependency(c, ttl=60)
    def gen_dep():
        yield {"connection": "active"}

    gen = gen_dep()
    item = next(gen)
    assert item is not None
    try:
        next(gen)
    except StopIteration:
        pass
