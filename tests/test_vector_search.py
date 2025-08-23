"""
Tests for vector-based similarity search functionality.

This module tests the vector similarity search features including TF-IDF
vectorization, similarity calculations, and search operations.
"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from yokedcache.models import CacheEntry, FuzzySearchResult


class TestVectorSimilaritySearch:
    """Test vector similarity search functionality."""

    @pytest.fixture
    def sample_cache_data(self):
        """Sample cache data for testing."""
        return {
            "user:1": {
                "name": "Alice Smith",
                "email": "alice@example.com",
                "role": "admin",
            },
            "user:2": {
                "name": "Bob Johnson",
                "email": "bob@example.com",
                "role": "user",
            },
            "user:3": {
                "name": "Charlie Brown",
                "email": "charlie@example.com",
                "role": "user",
            },
            "post:1": {
                "title": "Introduction to Python",
                "content": "Python programming basics",
            },
            "post:2": {
                "title": "Advanced Python",
                "content": "Advanced Python concepts and patterns",
            },
            "post:3": {
                "title": "Machine Learning",
                "content": "Introduction to machine learning with Python",
            },
        }

    @pytest.mark.skipif(
        not pytest.importorskip(
            "yokedcache.vector_search",
            reason="Vector search dependencies not available",
        ),
        reason="Vector search dependencies not available",
    )
    def test_vector_search_import(self):
        """Test that vector search can be imported when dependencies are available."""
        from yokedcache.vector_search import VectorSimilaritySearch

        assert VectorSimilaritySearch is not None

    @pytest.mark.skipif(
        not pytest.importorskip("numpy", reason="numpy not available")
        or not pytest.importorskip("sklearn", reason="sklearn not available"),
        reason="Vector search dependencies not available",
    )
    def test_vector_search_initialization(self):
        """Test VectorSimilaritySearch initialization."""
        from yokedcache.vector_search import VectorSimilaritySearch

        # Test default initialization
        search = VectorSimilaritySearch()
        assert search.similarity_method == "cosine"
        assert search.max_features == 1000
        assert not search._fitted

        # Test custom initialization
        search = VectorSimilaritySearch(
            similarity_method="euclidean", max_features=500, min_df=2, max_df=0.8
        )
        assert search.similarity_method == "euclidean"
        assert search.max_features == 500
        assert search.min_df == 2
        assert search.max_df == 0.8

    @pytest.mark.skipif(
        not pytest.importorskip("numpy", reason="numpy not available")
        or not pytest.importorskip("sklearn", reason="sklearn not available"),
        reason="Vector search dependencies not available",
    )
    def test_vector_search_text_extraction(self, sample_cache_data):
        """Test text extraction from cache keys and values."""
        from yokedcache.vector_search import VectorSimilaritySearch

        search = VectorSimilaritySearch()

        # Test with string value
        text = search._extract_searchable_text("user:1", "Alice Smith")
        assert "user:1" in text
        assert "Alice Smith" in text

        # Test with dict value
        text = search._extract_searchable_text(
            "user:1", {"name": "Alice", "role": "admin"}
        )
        assert "user:1" in text
        assert "name:Alice" in text
        assert "role:admin" in text

        # Test with list value
        text = search._extract_searchable_text("tags", ["python", "programming"])
        assert "tags" in text
        assert "python" in text
        assert "programming" in text

    @pytest.mark.skipif(
        not pytest.importorskip("numpy", reason="numpy not available")
        or not pytest.importorskip("sklearn", reason="sklearn not available"),
        reason="Vector search dependencies not available",
    )
    def test_vector_search_fitting(self, sample_cache_data):
        """Test fitting the vectorizer on cache data."""
        from yokedcache.vector_search import VectorSimilaritySearch

        search = VectorSimilaritySearch()

        # Test fitting
        search.fit(sample_cache_data)
        assert search._fitted
        assert len(search._documents) == len(sample_cache_data)
        assert len(search._keys) == len(sample_cache_data)
        assert search._document_vectors is not None

    @pytest.mark.skipif(
        not pytest.importorskip("numpy", reason="numpy not available")
        or not pytest.importorskip("sklearn", reason="sklearn not available"),
        reason="Vector search dependencies not available",
    )
    def test_vector_search_cosine_similarity(self, sample_cache_data):
        """Test cosine similarity search."""
        from yokedcache.vector_search import VectorSimilaritySearch

        search = VectorSimilaritySearch(similarity_method="cosine")
        search.fit(sample_cache_data)

        # Search for Python-related content
        results = search.search("Python programming", sample_cache_data, threshold=0.1)

        assert isinstance(results, list)
        assert all(isinstance(result, FuzzySearchResult) for result in results)

        # Should find posts about Python
        python_results = [r for r in results if "post:" in r.key and r.score > 10]
        assert len(python_results) > 0

    @pytest.mark.skipif(
        not pytest.importorskip("numpy", reason="numpy not available")
        or not pytest.importorskip("sklearn", reason="sklearn not available"),
        reason="Vector search dependencies not available",
    )
    def test_vector_search_different_similarity_methods(self, sample_cache_data):
        """Test different similarity calculation methods."""
        from yokedcache.vector_search import VectorSimilaritySearch

        methods = ["cosine", "euclidean", "manhattan"]

        for method in methods:
            search = VectorSimilaritySearch(similarity_method=method)
            search.fit(sample_cache_data)

            results = search.search("Alice user", sample_cache_data, threshold=0.1)
            assert isinstance(results, list)
            # Should find the Alice user
            alice_results = [r for r in results if "user:1" in r.key]
            assert len(alice_results) > 0

    @pytest.mark.skipif(
        not pytest.importorskip("numpy", reason="numpy not available")
        or not pytest.importorskip("sklearn", reason="sklearn not available"),
        reason="Vector search dependencies not available",
    )
    def test_vector_search_empty_data(self):
        """Test vector search with empty data."""
        from yokedcache.vector_search import VectorSimilaritySearch

        search = VectorSimilaritySearch()

        # Test with empty data
        search.fit({})
        assert not search._fitted

        results = search.search("test", {})
        assert results == []

    @pytest.mark.skipif(
        not pytest.importorskip("numpy", reason="numpy not available")
        or not pytest.importorskip("sklearn", reason="sklearn not available"),
        reason="Vector search dependencies not available",
    )
    def test_vector_search_update_cache_entry(self, sample_cache_data):
        """Test updating a single cache entry."""
        from yokedcache.vector_search import VectorSimilaritySearch

        search = VectorSimilaritySearch()
        search.fit(sample_cache_data)

        original_doc_count = len(search._documents)

        # Update existing entry
        search.update_cache_entry(
            "user:1", {"name": "Alice Williams", "role": "superuser"}
        )
        assert len(search._documents) == original_doc_count

        # Add new entry
        search.update_cache_entry("user:4", {"name": "David Lee", "role": "user"})
        assert len(search._documents) == original_doc_count + 1

    @pytest.mark.skipif(
        not pytest.importorskip("numpy", reason="numpy not available")
        or not pytest.importorskip("sklearn", reason="sklearn not available"),
        reason="Vector search dependencies not available",
    )
    def test_vector_search_remove_cache_entry(self, sample_cache_data):
        """Test removing a cache entry."""
        from yokedcache.vector_search import VectorSimilaritySearch

        search = VectorSimilaritySearch()
        search.fit(sample_cache_data)

        original_doc_count = len(search._documents)

        # Remove existing entry
        search.remove_cache_entry("user:1")
        assert len(search._documents) == original_doc_count - 1
        assert "user:1" not in search._keys

        # Remove non-existent entry (should not crash)
        search.remove_cache_entry("nonexistent")
        assert len(search._documents) == original_doc_count - 1

    @pytest.mark.skipif(
        not pytest.importorskip("numpy", reason="numpy not available")
        or not pytest.importorskip("sklearn", reason="sklearn not available"),
        reason="Vector search dependencies not available",
    )
    def test_vector_search_stats(self, sample_cache_data):
        """Test getting vector search statistics."""
        from yokedcache.vector_search import VectorSimilaritySearch

        search = VectorSimilaritySearch()
        search.fit(sample_cache_data)

        stats = search.get_stats()

        assert isinstance(stats, dict)
        assert stats["fitted"] is True
        assert stats["similarity_method"] == "cosine"
        assert stats["num_documents"] == len(sample_cache_data)
        assert stats["num_features"] > 0
        assert "vectorizer_params" in stats
        assert "vector_density" in stats

    @pytest.mark.skipif(
        not pytest.importorskip("numpy", reason="numpy not available")
        or not pytest.importorskip("sklearn", reason="sklearn not available"),
        reason="Vector search dependencies not available",
    )
    def test_vector_search_invalid_similarity_method(self):
        """Test handling of invalid similarity method."""
        from yokedcache.vector_search import VectorSimilaritySearch

        search = VectorSimilaritySearch(similarity_method="invalid_method")
        # Use more data to ensure fitting succeeds
        cache_data = {
            "key1": "value1",
            "key2": "value2",
            "key3": "value3",
            "key4": "value4",
            "key5": "value5",
        }
        search.fit(cache_data)

        # Should raise an error when trying to calculate similarity
        with pytest.raises(ValueError, match="Unknown similarity method"):
            search.search("test", cache_data)


class TestRedisVectorSearch:
    """Test Redis-specific vector search functionality."""

    @pytest.mark.skipif(
        not pytest.importorskip("numpy", reason="numpy not available")
        or not pytest.importorskip("redis", reason="redis not available"),
        reason="Redis vector search dependencies not available",
    )
    @pytest.mark.asyncio
    async def test_redis_vector_search_initialization(self):
        """Test RedisVectorSearch initialization."""
        from yokedcache.vector_search import RedisVectorSearch

        mock_redis = Mock()
        search = RedisVectorSearch(mock_redis, vector_key_prefix="test_vectors")

        assert search.redis == mock_redis
        assert search.vector_key_prefix == "test_vectors"
        assert search.search_engine is not None

    @pytest.mark.skipif(
        not pytest.importorskip("numpy", reason="numpy not available")
        or not pytest.importorskip("redis", reason="redis not available"),
        reason="Redis vector search dependencies not available",
    )
    @pytest.mark.asyncio
    async def test_redis_vector_store_and_retrieve(self):
        """Test storing and retrieving vectors in Redis."""
        import numpy as np

        from yokedcache.vector_search import RedisVectorSearch

        mock_redis = Mock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.hset = AsyncMock(return_value=True)
        mock_redis.get = AsyncMock()
        mock_redis.hgetall = AsyncMock()

        search = RedisVectorSearch(mock_redis)

        # Create test vector
        test_vector = np.array([1.0, 2.0, 3.0])

        result = await search.store_vector("test_key", test_vector)
        assert result is True

        # Verify Redis calls
        mock_redis.set.assert_called_once()
        mock_redis.hset.assert_called_once()

        # Test retrieving vector
        mock_redis.get.return_value = test_vector.tobytes()
        mock_redis.hgetall.return_value = {b"shape": b"(3,)", b"dtype": b"float64"}

        retrieved_vector = await search.get_vector("test_key")
        assert retrieved_vector is not None
        np.testing.assert_array_equal(retrieved_vector, test_vector)

    @pytest.mark.skipif(
        not pytest.importorskip("numpy", reason="numpy not available")
        or not pytest.importorskip("redis", reason="redis not available"),
        reason="Redis vector search dependencies not available",
    )
    @pytest.mark.asyncio
    async def test_redis_vector_delete(self):
        """Test deleting vectors from Redis."""
        from yokedcache.vector_search import RedisVectorSearch

        mock_redis = Mock()
        mock_redis.delete = AsyncMock(return_value=2)  # Both keys deleted

        search = RedisVectorSearch(mock_redis)

        result = await search.delete_vector("test_key")
        assert result is True

        # Should delete both the vector and metadata keys
        mock_redis.delete.assert_called_once()


class TestVectorSearchErrorHandling:
    """Test error handling in vector search."""

    def test_vector_search_without_dependencies(self):
        """Test vector search behavior when dependencies are not available."""
        import importlib
        import sys

        # Mock the import to fail and reload the module
        with patch.dict("sys.modules", {"numpy": None, "sklearn": None, "scipy": None}):
            # Remove the module from cache so it gets reloaded with mocked dependencies
            if "yokedcache.vector_search" in sys.modules:
                del sys.modules["yokedcache.vector_search"]

            # Import should work but initialization should fail
            from yokedcache.vector_search import VectorSimilaritySearch

            with pytest.raises(ImportError, match="Vector dependencies not available"):
                VectorSimilaritySearch()

    @pytest.mark.skipif(
        not pytest.importorskip("numpy", reason="numpy not available")
        or not pytest.importorskip("sklearn", reason="sklearn not available"),
        reason="Vector search dependencies not available",
    )
    def test_vector_search_fitting_error_handling(self):
        """Test error handling during vectorizer fitting."""
        from yokedcache.vector_search import VectorSimilaritySearch

        search = VectorSimilaritySearch()

        # Mock TfidfVectorizer to raise an error
        with patch.object(
            search.vectorizer, "fit_transform", side_effect=Exception("Fit error")
        ):
            search.fit({"key": "value"})
            assert not search._fitted

    @pytest.mark.skipif(
        not pytest.importorskip("numpy", reason="numpy not available")
        or not pytest.importorskip("sklearn", reason="sklearn not available"),
        reason="Vector search dependencies not available",
    )
    def test_vector_search_search_error_handling(self):
        """Test error handling during search."""
        from yokedcache.vector_search import VectorSimilaritySearch

        search = VectorSimilaritySearch()
        search.fit({"key": "value"})

        # Mock transform to raise an error
        with patch.object(
            search.vectorizer, "transform", side_effect=Exception("Transform error")
        ):
            results = search.search("test", {"key": "value"})
            assert results == []
