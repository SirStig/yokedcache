"""Extra decorator coverage tests focusing on branch edges."""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from yokedcache import YokedCache
from yokedcache.decorators import CachedDatabaseWrapper, cached, cached_dependency


@pytest.mark.asyncio
async def test_cached_condition_signature_variants():
    cache = YokedCache()

    # Use a TypedDict so mypy understands precise value types
    from typing import List, TypedDict

    class _Calls(TypedDict):
        fn: int
        cond: List[str]

    calls: _Calls = {"fn": 0, "cond": []}

    def condition_one(result):  # single-arg condition
        calls["cond"].append("one")
        return True

    def condition_multi(result, x):  # multi-arg condition
        calls["cond"].append("multi")
        return False  # should prevent caching

    @cached(cache, condition=condition_one)
    async def f1(x):
        calls["fn"] += 1
        return x

    @cached(cache, condition=condition_multi)
    async def f2(x):
        calls["fn"] += 1
        return x

    with (
        patch.object(cache, "get", return_value=None),
        patch.object(cache, "set", return_value=True) as mock_set,
    ):
        await f1(1)
        await f2(2)
        # f2 condition returns False so set not called second time
        assert mock_set.call_count == 1
    assert calls["fn"] == 2
    assert "one" in calls["cond"] and "multi" in calls["cond"]


@pytest.mark.asyncio
async def test_cached_condition_exception_defaults_to_cache():
    cache = YokedCache()

    def bad_condition(result):  # raises
        raise RuntimeError("boom")

    @cached(cache, condition=bad_condition)
    async def f(x):
        return x

    with (
        patch.object(cache, "get", return_value=None),
        patch.object(cache, "set", return_value=True) as mock_set,
    ):
        await f(1)
        assert mock_set.called  # despite condition error


def test_cached_sync_skip_cache_on_error_false():
    cache = YokedCache()

    @cached(cache, skip_cache_on_error=False)
    def f(x):
        return x + 1

    with patch.object(cache, "get_sync", side_effect=Exception("err")):
        # Should raise because skip_cache_on_error False
        with pytest.raises(Exception):
            f(1)


@pytest.mark.asyncio
async def test_cached_async_key_builder():
    cache = YokedCache()

    def kb(x):
        return f"kb:{x}"

    @cached(cache, key_builder=kb)
    async def f(x):
        return x * 2

    with (
        patch.object(cache, "get", return_value=None) as g,
        patch.object(cache, "set", return_value=True),
    ):
        await f(3)
        g.assert_called_once_with("kb:3")


def test_cached_dependency_sync_generator():
    cache = YokedCache()

    def dep():
        yield MagicMock(query=MagicMock())

    wrapped = cached_dependency(dep, cache=cache)
    gen = wrapped()
    # Consume first yield
    wrapper_obj = next(gen)
    assert isinstance(wrapper_obj, CachedDatabaseWrapper)
    # Close generator
    with pytest.raises(StopIteration):
        next(gen)


@pytest.mark.asyncio
async def test_cached_dependency_async_generator():
    cache = YokedCache()

    async def dep_async():
        yield MagicMock(query=MagicMock())

    wrapped = cached_dependency(dep_async, cache=cache)
    agen = wrapped()
    wrapper_obj = await agen.__anext__()
    assert isinstance(wrapper_obj, CachedDatabaseWrapper)
    with pytest.raises(StopAsyncIteration):
        await agen.__anext__()


@pytest.mark.asyncio
async def test_database_wrapper_write_tracking_and_commit():
    cache = YokedCache()
    session = MagicMock()
    # Make execute async so wrapper path is async (avoids asyncio.run in loop)
    session.execute = AsyncMock(return_value=1)
    wrapper = CachedDatabaseWrapper(session, cache, auto_invalidate=True)

    # Force write operation tracking by calling wrapped execute
    exec_fn = wrapper.execute  # may be async or sync
    result = exec_fn("UPDATE users SET name='x'")
    if inspect.iscoroutine(result):  # ensure awaited when async
        await result
    assert wrapper._write_operations  # tracked
    with patch.object(cache, "invalidate_tags", return_value=1) as inv:
        await wrapper.commit()
        inv.assert_called()
    # After commit list cleared
    assert not wrapper._write_operations


def test_database_wrapper_build_query_cache_key_stability():
    cache = YokedCache()
    session = MagicMock()
    w = CachedDatabaseWrapper(session, cache)
    k1 = w._build_query_cache_key("query", ("SELECT * FROM x",), {})
    k2 = w._build_query_cache_key("query", ("SELECT * FROM x",), {})
    assert k1 == k2
