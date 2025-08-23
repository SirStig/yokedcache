"""
Vector-based similarity search for YokedCache.

This module provides advanced fuzzy search capabilities using vector embeddings
and similarity calculations for more accurate and semantic search results.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import CacheEntry, FuzzySearchResult

logger = logging.getLogger(__name__)

try:
    import numpy as np
    from scipy.spatial.distance import euclidean
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity, manhattan_distances

    VECTOR_DEPS_AVAILABLE = True
except ImportError:
    VECTOR_DEPS_AVAILABLE = False
    np = None  # type: ignore
    TfidfVectorizer = None
    cosine_similarity = None
    euclidean = None
    manhattan_distances = None


class VectorSimilaritySearch:
    """Vector-based similarity search for cache entries."""

    def __init__(
        self,
        similarity_method: str = "cosine",
        max_features: int = 1000,
        min_df: int = 1,
        max_df: float = 0.95,
        ngram_range: Tuple[int, int] = (1, 2),
    ):
        """
        Initialize vector similarity search.

        Args:
            similarity_method: Method for calculating similarity ('cosine', 'euclidean', 'manhattan')
            max_features: Maximum number of features for TF-IDF
            min_df: Minimum document frequency for TF-IDF
            max_df: Maximum document frequency for TF-IDF
            ngram_range: N-gram range for TF-IDF
        """
        if not VECTOR_DEPS_AVAILABLE:
            raise ImportError(
                "Vector dependencies not available. Install with: "
                "pip install yokedcache[vector]"
            )

        self.similarity_method = similarity_method
        self.max_features = max_features
        self.min_df = min_df
        self.max_df = max_df
        self.ngram_range = ngram_range

        if TfidfVectorizer is not None:
            self.vectorizer = TfidfVectorizer(
                max_features=max_features,
                min_df=min_df,
                max_df=max_df,
                ngram_range=ngram_range,
                stop_words="english",
                lowercase=True,
                strip_accents="unicode",
            )
        else:
            self.vectorizer = None

        self._fitted = False
        self._document_vectors = None
        self._documents: List[str] = []
        self._keys: List[str] = []

    def _extract_searchable_text(self, key: str, value: Any) -> str:
        """Extract searchable text from cache key and value."""
        texts = [str(key)]

        if isinstance(value, str):
            texts.append(value)
        elif isinstance(value, dict):
            # Extract values from dict
            for k, v in value.items():
                texts.append(f"{k}:{v}")
        elif isinstance(value, (list, tuple)):
            # Extract values from list/tuple
            texts.extend([str(item) for item in value])
        else:
            texts.append(str(value))

        return " ".join(texts)

    def fit(self, cache_data: Dict[str, Any]) -> None:
        """
        Fit the vectorizer on cache data.

        Args:
            cache_data: Dictionary of cache key -> value pairs
        """
        if not cache_data:
            logger.warning("No cache data provided for vector similarity fitting")
            return

        # Extract documents for vectorization
        self._documents = []
        self._keys = []

        for key, value in cache_data.items():
            text = self._extract_searchable_text(key, value)
            self._documents.append(text)
            self._keys.append(key)

        if not self._documents:
            logger.warning("No documents extracted from cache data")
            return

        try:
            # Fit vectorizer and transform documents
            if self.vectorizer is None:
                raise ImportError("TfidfVectorizer not available")
            self._document_vectors = self.vectorizer.fit_transform(self._documents)
            self._fitted = True

            logger.info(
                f"Vector similarity search fitted on {len(self._documents)} documents "
                f"with {self._document_vectors.shape[1] if self._document_vectors is not None else 0} features"
            )

        except Exception as e:
            logger.error(f"Error fitting vector similarity search: {e}")
            self._fitted = False

    def _calculate_similarity(self, query_vector, document_vectors):
        """Calculate similarity scores based on the configured method."""
        if not VECTOR_DEPS_AVAILABLE:
            raise ImportError("Vector dependencies not available")

        if self.similarity_method == "cosine":
            if cosine_similarity is None:
                raise ImportError("cosine_similarity not available")
            return cosine_similarity(query_vector, document_vectors).flatten()
        elif self.similarity_method == "euclidean":
            # Convert to dense arrays for euclidean distance
            query_dense = query_vector.toarray().flatten()
            doc_dense = document_vectors.toarray()

            # Calculate euclidean distances and convert to similarities (1 / (1 + distance))
            if np is None or euclidean is None:
                raise ImportError("numpy or euclidean distance not available")
            distances = np.array([euclidean(query_dense, doc) for doc in doc_dense])
            return 1.0 / (1.0 + distances)
        elif self.similarity_method == "manhattan":
            # Convert to dense arrays for manhattan distance
            query_dense = query_vector.toarray().reshape(1, -1)
            doc_dense = document_vectors.toarray()

            # Calculate manhattan distances and convert to similarities
            if manhattan_distances is None:
                raise ImportError("manhattan_distances not available")
            distances = manhattan_distances(query_dense, doc_dense)[0]
            return 1.0 / (1.0 + distances)
        else:
            raise ValueError(f"Unknown similarity method: {self.similarity_method}")

    def search(
        self,
        query: str,
        cache_data: Dict[str, Any],
        threshold: float = 0.1,
        max_results: int = 10,
    ) -> List[FuzzySearchResult]:
        """
        Perform vector-based similarity search.

        Args:
            query: Search query
            cache_data: Dictionary of cache key -> value pairs
            threshold: Similarity threshold (0.0 - 1.0)
            max_results: Maximum number of results

        Returns:
            List of fuzzy search results sorted by similarity score
        """
        if not VECTOR_DEPS_AVAILABLE:
            logger.error("Vector dependencies not available")
            return []

        if not self._fitted or not cache_data:
            # Fit on current data if not fitted
            self.fit(cache_data)

        if not self._fitted:
            logger.warning("Vector similarity search not fitted")
            return []

        try:
            # Transform query
            if self.vectorizer is None:
                raise ImportError("TfidfVectorizer not available")
            query_vector = self.vectorizer.transform([query])

            # Calculate similarities
            similarities = self._calculate_similarity(
                query_vector, self._document_vectors
            )

            # Get top results above threshold
            results = []

            # Get indices sorted by similarity score (descending)
            if not VECTOR_DEPS_AVAILABLE or np is None:
                raise ImportError("Vector dependencies not available")
            sorted_indices = np.argsort(similarities)[::-1]

            for i in sorted_indices[:max_results]:
                score = similarities[i]

                if score >= threshold:
                    key = self._keys[i]
                    value = cache_data.get(key)

                    if value is not None:
                        # Convert similarity score to percentage (0-100)
                        score_percentage = int(score * 100)

                        result = FuzzySearchResult(
                            key=key,
                            value=value,
                            score=score_percentage,
                            matched_term=query,
                            cache_entry=CacheEntry(
                                key=key,
                                value=value,
                                created_at=datetime.utcnow(),
                            ),
                        )
                        results.append(result)

            logger.debug(
                f"Vector similarity search for '{query}' returned {len(results)} results"
            )

            return results

        except ValueError:
            # Re-raise ValueError for invalid similarity methods
            raise
        except Exception as e:
            logger.error(f"Error in vector similarity search: {e}")
            return []

    def update_cache_entry(self, key: str, value: Any) -> None:
        """
        Update a single cache entry in the search index.

        Args:
            key: Cache key
            value: Cache value
        """
        if not self._fitted:
            return

        try:
            # Check if key already exists
            if key in self._keys:
                # Update existing entry
                index = self._keys.index(key)
                text = self._extract_searchable_text(key, value)
                self._documents[index] = text
            else:
                # Add new entry
                text = self._extract_searchable_text(key, value)
                self._documents.append(text)
                self._keys.append(key)

            # Re-fit the vectorizer (this is expensive, consider batching updates)
            if self.vectorizer is None:
                raise ImportError("TfidfVectorizer not available")
            self._document_vectors = self.vectorizer.fit_transform(self._documents)

        except Exception as e:
            logger.error(f"Error updating cache entry in vector search: {e}")

    def remove_cache_entry(self, key: str) -> None:
        """
        Remove a cache entry from the search index.

        Args:
            key: Cache key to remove
        """
        if not self._fitted or key not in self._keys:
            return

        try:
            index = self._keys.index(key)
            del self._documents[index]
            del self._keys[index]

            if self._documents:
                # Re-fit the vectorizer
                if self.vectorizer is None:
                    raise ImportError("TfidfVectorizer not available")
                self._document_vectors = self.vectorizer.fit_transform(self._documents)
            else:
                self._fitted = False
                self._document_vectors = None

        except Exception as e:
            logger.error(f"Error removing cache entry from vector search: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector search index."""
        stats = {
            "fitted": self._fitted,
            "similarity_method": self.similarity_method,
            "num_documents": len(self._documents),
            "num_features": 0,
            "vectorizer_params": {
                "max_features": self.max_features,
                "min_df": self.min_df,
                "max_df": self.max_df,
                "ngram_range": self.ngram_range,
            },
        }

        if self._fitted and self._document_vectors is not None:
            stats["num_features"] = self._document_vectors.shape[1]
            # Handle sparse matrix attribute access
            try:
                # For sparse matrices, get non-zero elements count
                nnz = getattr(self._document_vectors, "nnz", None)
                if nnz is not None:
                    stats["vector_density"] = nnz / (
                        self._document_vectors.shape[0]
                        * self._document_vectors.shape[1]
                    )
                else:
                    stats["vector_density"] = 1.0  # Dense matrix
            except AttributeError:
                stats["vector_density"] = 1.0  # Fallback for dense matrices

        return stats


class RedisVectorSearch:
    """Redis-specific vector search with persistence."""

    def __init__(self, redis_client, vector_key_prefix: str = "vectors"):
        """
        Initialize Redis vector search.

        Args:
            redis_client: Redis client instance
            vector_key_prefix: Prefix for vector storage keys
        """
        self.redis = redis_client
        self.vector_key_prefix = vector_key_prefix
        self.search_engine = VectorSimilaritySearch()

    async def store_vector(self, key: str, vector) -> bool:
        """Store a vector in Redis."""
        try:
            vector_key = f"{self.vector_key_prefix}:{key}"
            vector_bytes = vector.tobytes()

            await self.redis.set(vector_key, vector_bytes)

            # Store metadata
            metadata_key = f"{self.vector_key_prefix}:meta:{key}"
            metadata = {"shape": vector.shape, "dtype": str(vector.dtype)}

            await self.redis.hset(metadata_key, mapping=metadata)

            return True

        except Exception as e:
            logger.error(f"Error storing vector for key {key}: {e}")
            return False

    async def get_vector(self, key: str):
        """Retrieve a vector from Redis."""
        try:
            vector_key = f"{self.vector_key_prefix}:{key}"
            metadata_key = f"{self.vector_key_prefix}:meta:{key}"

            # Get vector bytes and metadata
            vector_bytes = await self.redis.get(vector_key)
            metadata = await self.redis.hgetall(metadata_key)

            if not vector_bytes or not metadata:
                return None

            # Reconstruct vector
            shape = eval(metadata[b"shape"].decode())
            dtype = metadata[b"dtype"].decode()

            if not VECTOR_DEPS_AVAILABLE or np is None:
                raise ImportError("Vector dependencies not available")
            vector = np.frombuffer(vector_bytes, dtype=dtype).reshape(shape)

            return vector

        except Exception as e:
            logger.error(f"Error retrieving vector for key {key}: {e}")
            return None

    async def delete_vector(self, key: str) -> bool:
        """Delete a vector from Redis."""
        try:
            vector_key = f"{self.vector_key_prefix}:{key}"
            metadata_key = f"{self.vector_key_prefix}:meta:{key}"

            deleted = await self.redis.delete(vector_key, metadata_key)

            return deleted > 0

        except Exception as e:
            logger.error(f"Error deleting vector for key {key}: {e}")
            return False
