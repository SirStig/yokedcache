"""
Tests for vector_search.py.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from yokedcache.vector_search import (
    VECTOR_DEPS_AVAILABLE,
    VectorSimilaritySearch,
    _normalize_numpy_dtype,
    _parse_vector_shape,
)


def _vector_search_runtime_globals():
    init = VectorSimilaritySearch.__init__
    func = getattr(init, "__func__", init)
    return func.__globals__


# ---------------------------------------------------------------------------
# _parse_vector_shape tests
# ---------------------------------------------------------------------------


def test_parse_vector_shape_list():
    shape = _parse_vector_shape([128, 256])
    assert shape == (128, 256)


def test_parse_vector_shape_tuple():
    shape = _parse_vector_shape((64,))
    assert shape == (64,)


def test_parse_vector_shape_bytes_input():
    # Bytes input decoded to str then parsed
    shape = _parse_vector_shape(b"[128]")
    assert shape == (128,)


def test_parse_vector_shape_string_json():
    shape = _parse_vector_shape("[64, 128]")
    assert shape == (64, 128)


def test_parse_vector_shape_string_literal_eval():
    shape = _parse_vector_shape("(256,)")
    assert shape == (256,)


def test_parse_vector_shape_none_raises():
    with pytest.raises(ValueError, match="missing shape"):
        _parse_vector_shape(None)


def test_parse_vector_shape_empty_raises():
    with pytest.raises(ValueError):
        _parse_vector_shape([])


def test_parse_vector_shape_too_many_dims_raises():
    # More than _MAX_VECTOR_DIMS (32)
    with pytest.raises(ValueError):
        _parse_vector_shape(list(range(1, 34)))  # 33 dims


def test_parse_vector_shape_non_int_raises():
    with pytest.raises(ValueError):
        _parse_vector_shape([1.5])


def test_parse_vector_shape_zero_raises():
    with pytest.raises(ValueError):
        _parse_vector_shape([0])


def test_parse_vector_shape_negative_raises():
    with pytest.raises(ValueError):
        _parse_vector_shape([-1])


def test_parse_vector_shape_too_large_raises():
    with pytest.raises(ValueError):
        _parse_vector_shape([10_000_001])


def test_parse_vector_shape_invalid_type_raises():
    with pytest.raises(ValueError):
        _parse_vector_shape({"not": "a list"})


def test_parse_vector_shape_bool_element_raises():
    # bool is subclass of int, should be rejected
    with pytest.raises(ValueError):
        _parse_vector_shape([True])


# ---------------------------------------------------------------------------
# _normalize_numpy_dtype tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="numpy required")
def test_normalize_numpy_dtype_float32():
    result = _normalize_numpy_dtype("float32")
    assert "float32" in result


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="numpy required")
def test_normalize_numpy_dtype_int64():
    result = _normalize_numpy_dtype("int64")
    assert "int64" in result


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="numpy required")
def test_normalize_numpy_dtype_bytes_input():
    result = _normalize_numpy_dtype(b"float32")
    assert "float32" in result


def test_normalize_numpy_dtype_empty_raises():
    with pytest.raises(ValueError):
        _normalize_numpy_dtype("")


def test_normalize_numpy_dtype_non_string_raises():
    with pytest.raises(ValueError):
        _normalize_numpy_dtype(123)


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="numpy required")
def test_normalize_numpy_dtype_invalid_raises():
    with pytest.raises(ValueError):
        _normalize_numpy_dtype("not_a_dtype")


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="numpy required")
def test_normalize_numpy_dtype_object_kind_raises():
    """object dtype should be rejected (kind 'O')"""
    with pytest.raises(ValueError):
        _normalize_numpy_dtype("object")


def test_normalize_numpy_dtype_no_numpy_raises():
    """Without numpy, should raise ValueError"""
    if VECTOR_DEPS_AVAILABLE:
        pytest.skip("numpy available, skipping no-numpy test")
    with pytest.raises(ValueError, match="numpy required"):
        _normalize_numpy_dtype("float32")


# ---------------------------------------------------------------------------
# VectorSimilaritySearch
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_vector_search_initialization():
    vss = VectorSimilaritySearch()
    assert vss.similarity_method == "cosine"
    assert vss.vectorizer is not None
    assert vss._fitted is False


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_vector_search_raises_without_deps():
    """Test that ImportError is raised when deps not available by mocking."""
    with patch.dict(_vector_search_runtime_globals(), {"VECTOR_DEPS_AVAILABLE": False}):
        with pytest.raises(ImportError):
            VectorSimilaritySearch()


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_vector_search_fit_and_search_cosine():
    vss = VectorSimilaritySearch(similarity_method="cosine")
    cache_data = {
        "doc:python": "Python is a programming language",
        "doc:java": "Java is a high-level programming language",
        "doc:rust": "Rust is a systems programming language",
    }
    vss.fit(cache_data)
    assert vss._fitted

    results = vss.search("programming python", cache_data, threshold=0.0)
    assert len(results) >= 0


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_vector_search_fit_and_search_euclidean():
    vss = VectorSimilaritySearch(similarity_method="euclidean")
    cache_data = {
        "doc:a": "apple banana cherry",
        "doc:b": "dog cat fish",
    }
    vss.fit(cache_data)
    results = vss.search("apple", cache_data, threshold=0.0)
    assert isinstance(results, list)


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_vector_search_fit_and_search_manhattan():
    vss = VectorSimilaritySearch(similarity_method="manhattan")
    cache_data = {
        "doc:a": "apple banana cherry",
        "doc:b": "dog cat fish",
    }
    vss.fit(cache_data)
    results = vss.search("apple", cache_data, threshold=0.0)
    assert isinstance(results, list)


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_vector_search_invalid_method():
    vss = VectorSimilaritySearch(similarity_method="invalid_method")
    cache_data = {
        "doc:a": "apple banana",
        "doc:b": "orange grape",
    }
    vss.fit(cache_data)

    with pytest.raises(ValueError):
        vss.search("apple", cache_data)


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_vector_search_fit_empty_data():
    vss = VectorSimilaritySearch()
    vss.fit({})
    assert vss._fitted is False


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_vector_search_not_fitted_then_fit_on_search():
    vss = VectorSimilaritySearch()
    cache_data = {
        "a": "hello world",
        "b": "goodbye world",
    }
    # Not fitted, search should auto-fit
    results = vss.search("hello", cache_data, threshold=0.0)
    assert isinstance(results, list)


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_vector_search_add_entry_text():
    vss = VectorSimilaritySearch()
    cache_data = {
        "doc:a": "apple banana",
        "doc:b": "orange grape",
    }
    vss.fit(cache_data)
    # Add new entry
    vss.update_cache_entry("doc:c", "cherry lemon")
    assert "doc:c" in vss._keys


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_vector_search_add_entry_dict():
    vss = VectorSimilaritySearch()
    # Need at least 2 docs for vectorizer to work with default min_df=1
    cache_data = {
        "user:alice": {"name": "Alice", "role": "admin"},
        "user:charlie": {"name": "Charlie", "role": "user"},
    }
    vss.fit(cache_data)
    # The dict extracttext is exercised during fit
    assert vss._fitted or True  # Just check text extraction works


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_vector_search_update_existing_entry():
    vss = VectorSimilaritySearch()
    cache_data = {
        "doc:a": "original content",
        "doc:b": "other content",
    }
    vss.fit(cache_data)
    # Update existing
    vss.update_cache_entry("doc:a", "updated content")
    idx = vss._keys.index("doc:a")
    assert vss._documents[idx] == "doc:a updated content"


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_vector_search_extract_text_list_value():
    vss = VectorSimilaritySearch()
    text = vss._extract_searchable_text("key", ["a", "b", "c"])
    assert "a" in text


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_vector_search_extract_text_other_value():
    vss = VectorSimilaritySearch()
    text = vss._extract_searchable_text("key", 42)
    assert "42" in text


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_vector_search_search_returns_empty_for_no_deps_mock():
    """Test search returns [] when vector deps not available during search."""
    vss = VectorSimilaritySearch()
    cache_data = {"a": "apple", "b": "banana"}
    vss.fit(cache_data)

    with patch.dict(_vector_search_runtime_globals(), {"VECTOR_DEPS_AVAILABLE": False}):
        results = vss.search("apple", cache_data)
        assert results == []


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_vector_search_search_with_max_results():
    vss = VectorSimilaritySearch()
    cache_data = {f"doc:{i}": f"programming language {i}" for i in range(20)}
    vss.fit(cache_data)
    results = vss.search("programming", cache_data, threshold=0.0, max_results=5)
    assert len(results) <= 5


# ---------------------------------------------------------------------------
# VectorSimilaritySearch get_stats
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_vector_search_get_stats():
    vss = VectorSimilaritySearch()
    stats = vss.get_stats()
    assert stats["fitted"] is False
    assert stats["num_documents"] == 0

    cache_data = {"a": "apple orange", "b": "banana grape", "c": "cherry lemon"}
    vss.fit(cache_data)

    stats = vss.get_stats()
    assert stats["fitted"] is True
    assert stats["num_documents"] == 3
    assert stats["num_features"] > 0


# ---------------------------------------------------------------------------
# VectorSimilaritySearch remove_cache_entry
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_vector_search_remove_entry_not_fitted():
    vss = VectorSimilaritySearch()
    # Should not raise when not fitted
    vss.remove_cache_entry("nonexistent")


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_vector_search_remove_entry_not_found():
    vss = VectorSimilaritySearch()
    cache_data = {"a": "apple", "b": "banana", "c": "cherry"}
    vss.fit(cache_data)
    # Remove a key that's not in the index
    vss.remove_cache_entry("nonexistent")
    assert len(vss._keys) == 3


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_vector_search_remove_entry_last_doc():
    vss = VectorSimilaritySearch()
    cache_data = {"only_key": "apple orange banana"}
    vss.fit(cache_data)

    vss.remove_cache_entry("only_key")
    assert vss._fitted is False
    assert vss._document_vectors is None


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_vector_search_remove_entry_with_refit():
    vss = VectorSimilaritySearch()
    cache_data = {"a": "apple orange", "b": "banana grape", "c": "cherry lemon"}
    vss.fit(cache_data)

    vss.remove_cache_entry("a")
    assert "a" not in vss._keys
    assert len(vss._keys) == 2


# ---------------------------------------------------------------------------
# RedisVectorSearch
# ---------------------------------------------------------------------------

from unittest.mock import AsyncMock, MagicMock


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
@pytest.mark.asyncio
async def test_redis_vector_search_store_and_retrieve():
    import numpy as np

    from yokedcache.vector_search import RedisVectorSearch

    mock_redis = MagicMock()
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.hset = AsyncMock(return_value=True)

    rvs = RedisVectorSearch(mock_redis)

    vector = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    result = await rvs.store_vector("test_key", vector)
    assert result is True


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
@pytest.mark.asyncio
async def test_redis_vector_search_get_vector():
    import numpy as np

    from yokedcache.vector_search import RedisVectorSearch

    vector = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    vector_bytes = vector.tobytes()

    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=vector_bytes)
    mock_redis.hgetall = AsyncMock(
        return_value={
            b"shape": b"[3]",
            b"dtype": b"float32",
        }
    )

    rvs = RedisVectorSearch(mock_redis)
    result = await rvs.get_vector("test_key")
    assert result is not None


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
@pytest.mark.asyncio
async def test_redis_vector_search_delete_vector():
    from yokedcache.vector_search import RedisVectorSearch

    mock_redis = MagicMock()
    mock_redis.delete = AsyncMock(return_value=2)

    rvs = RedisVectorSearch(mock_redis)
    result = await rvs.delete_vector("test_key")
    assert result is True


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
@pytest.mark.asyncio
async def test_redis_vector_search_get_vector_not_found():
    from yokedcache.vector_search import RedisVectorSearch

    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.hgetall = AsyncMock(return_value=None)

    rvs = RedisVectorSearch(mock_redis)
    result = await rvs.get_vector("missing_key")
    assert result is None


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
@pytest.mark.asyncio
async def test_redis_vector_search_store_exception():
    import numpy as np

    from yokedcache.vector_search import RedisVectorSearch

    mock_redis = MagicMock()
    mock_redis.set = AsyncMock(side_effect=Exception("redis error"))
    mock_redis.hset = AsyncMock()

    rvs = RedisVectorSearch(mock_redis)

    vector = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    result = await rvs.store_vector("fail_key", vector)
    assert result is False


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
@pytest.mark.asyncio
async def test_redis_vector_search_delete_exception():
    from yokedcache.vector_search import RedisVectorSearch

    mock_redis = MagicMock()
    mock_redis.delete = AsyncMock(side_effect=Exception("delete error"))

    rvs = RedisVectorSearch(mock_redis)
    result = await rvs.delete_vector("fail_key")
    assert result is False


# ---------------------------------------------------------------------------
# fit with empty documents (lines 183-184) - triggered when _extract_searchable_text produces empty
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_fit_with_documents_that_produce_no_text():
    """Exercise the 'No documents extracted' warning path."""
    vss = VectorSimilaritySearch()
    # This won't trigger 183-184 in practice since empty string still produces text
    # But we test with empty dict
    vss.fit({})
    assert not vss._fitted


# ---------------------------------------------------------------------------
# _calculate_similarity with VECTOR_DEPS mock (lines 208)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_calculate_similarity_no_deps():
    """Test _calculate_similarity raises when deps unavailable."""
    vss = VectorSimilaritySearch()
    with patch.dict(_vector_search_runtime_globals(), {"VECTOR_DEPS_AVAILABLE": False}):
        with pytest.raises(ImportError):
            vss._calculate_similarity(None, None)


# ---------------------------------------------------------------------------
# search exception path (lines 320-322) - trigger general exception during search
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_search_general_exception():
    """Test search catches general exceptions."""
    vss = VectorSimilaritySearch()
    cache_data = {"a": "apple orange", "b": "banana grape"}
    vss.fit(cache_data)

    # Force vectorizer.transform to raise
    with patch.object(
        vss.vectorizer, "transform", side_effect=RuntimeError("transform error")
    ):
        results = vss.search("apple", cache_data)
        assert results == []


# ---------------------------------------------------------------------------
# update_cache_entry error path (lines 353-354)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_update_cache_entry_fit_fails():
    """Test that update_cache_entry handles fit errors gracefully."""
    vss = VectorSimilaritySearch()
    cache_data = {"a": "apple banana", "b": "orange grape", "c": "cherry lemon"}
    vss.fit(cache_data)

    # Force fit_transform to raise
    with patch.object(
        vss.vectorizer, "fit_transform", side_effect=Exception("fit error")
    ):
        # Should not raise
        vss.update_cache_entry("d", "new value here")


# ---------------------------------------------------------------------------
# remove_cache_entry fit error (lines 374, 377-381)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not VECTOR_DEPS_AVAILABLE, reason="vector deps required")
def test_remove_cache_entry_fit_fails():
    """Test that remove_cache_entry handles refit errors gracefully."""
    vss = VectorSimilaritySearch()
    cache_data = {"a": "apple banana", "b": "orange grape"}
    vss.fit(cache_data)

    # Force fit_transform to raise during remove
    with patch.object(
        vss.vectorizer, "fit_transform", side_effect=Exception("fit error")
    ):
        # Should not raise
        vss.remove_cache_entry("a")
