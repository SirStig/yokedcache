# Vector-Based Similarity Search

YokedCache 0.2.0 introduces advanced vector-based similarity search capabilities, enabling semantic search across your cached data. This feature goes beyond traditional string matching to provide intelligent, context-aware search results.

## Table of Contents

- [Overview](#overview)
- [How It Works](#how-it-works)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Similarity Methods](#similarity-methods)
- [Performance Optimization](#performance-optimization)
- [Integration with Cache](#integration-with-cache)

## Overview

Traditional fuzzy search relies on string similarity metrics like Levenshtein distance. Vector-based similarity search uses machine learning techniques to understand the semantic meaning of your data, providing more relevant and intelligent search results.

### Key Features

- **Semantic Understanding**: Finds conceptually related content, not just string matches
- **Multiple Similarity Methods**: Cosine, Euclidean, and Manhattan distance calculations
- **TF-IDF Vectorization**: Converts text to numerical vectors for comparison
- **Configurable Parameters**: Fine-tune search behavior for your specific use case
- **Real-time Updates**: Automatically updates search index when cache data changes
- **Redis Integration**: Optional Redis-backed vector storage for distributed systems

### Use Cases

- **Content Discovery**: Find related articles, products, or documents
- **Recommendation Systems**: Suggest similar items based on user behavior
- **Data Deduplication**: Identify duplicate or near-duplicate content
- **Smart Search**: Provide search results that understand user intent
- **Data Analysis**: Group and analyze similar data patterns

## How It Works

### 1. Text Extraction

The system extracts searchable text from cache keys and values:

```python
# For key-value pairs
key = "user:123"
value = {"name": "Alice Smith", "role": "engineer", "skills": ["python", "redis"]}

# Extracted text
searchable_text = "user:123 name:Alice Smith role:engineer skills:python,redis"
```

### 2. Vectorization

Text is converted to numerical vectors using TF-IDF (Term Frequency-Inverse Document Frequency):

```python
from yokedcache.vector_search import VectorSimilaritySearch

search = VectorSimilaritySearch(
    max_features=1000,      # Maximum vocabulary size
    min_df=1,               # Minimum document frequency
    max_df=0.95,            # Maximum document frequency
    ngram_range=(1, 2)      # Use unigrams and bigrams
)
```

### 3. Similarity Calculation

Vector similarities are calculated using mathematical distance metrics:

- **Cosine Similarity**: Measures angle between vectors (best for text)
- **Euclidean Distance**: Measures straight-line distance between points
- **Manhattan Distance**: Measures city-block distance between points

### 4. Result Ranking

Results are ranked by similarity score and filtered by threshold:

```python
results = search.search(
    query="python developer",
    cache_data=cache_data,
    threshold=0.1,          # Minimum similarity score
    max_results=10          # Maximum number of results
)
```

## Configuration

### Basic Setup

```python
from yokedcache.vector_search import VectorSimilaritySearch

# Default configuration
search = VectorSimilaritySearch()

# Custom configuration
search = VectorSimilaritySearch(
    similarity_method="cosine",     # "cosine", "euclidean", "manhattan"
    max_features=2000,              # Vocabulary size
    min_df=2,                       # Ignore rare terms
    max_df=0.8,                     # Ignore common terms
    ngram_range=(1, 3)              # Use 1-3 word phrases
)
```

### Advanced Configuration

```python
search = VectorSimilaritySearch(
    similarity_method="cosine",
    max_features=5000,
    min_df=0.01,                    # Percentage-based frequency
    max_df=0.95,
    ngram_range=(1, 2),
    stop_words="english",           # Remove common English words
    lowercase=True,                 # Convert to lowercase
    strip_accents="unicode"         # Remove accents
)
```

### Installation Requirements

Vector search requires additional dependencies:

```bash
# Install vector search dependencies
pip install yokedcache[vector]

# Or install manually
pip install numpy scipy scikit-learn
```

## Usage Examples

### Basic Search

```python
from yokedcache.vector_search import VectorSimilaritySearch

# Sample cache data
cache_data = {
    "user:1": {"name": "Alice", "role": "Python Developer", "skills": ["FastAPI", "Redis"]},
    "user:2": {"name": "Bob", "role": "Data Scientist", "skills": ["Python", "ML"]},
    "user:3": {"name": "Charlie", "role": "Frontend Developer", "skills": ["React", "TypeScript"]},
    "post:1": {"title": "Python Best Practices", "content": "Tips for writing clean Python code"},
    "post:2": {"title": "Redis Caching Guide", "content": "How to implement efficient caching"}
}

# Initialize and fit the search engine
search = VectorSimilaritySearch()
search.fit(cache_data)

# Search for Python-related content
results = search.search("Python programming", cache_data, threshold=0.1)

for result in results:
    print(f"Key: {result.key}")
    print(f"Score: {result.score:.3f}")
    print(f"Value: {result.value}")
    print("---")
```

### Integration with YokedCache

```python
from yokedcache import YokedCache, CacheConfig
from yokedcache.backends import MemoryBackend
from yokedcache.vector_search import VectorSimilaritySearch

# Setup cache with vector search
backend = MemoryBackend()
config = CacheConfig(
    backend=backend,
    enable_fuzzy=True,
    fuzzy_threshold=70
)

cache = YokedCache(config)

# Add vector search capability
vector_search = VectorSimilaritySearch(similarity_method="cosine")

async def enhanced_search(query: str, use_vector: bool = True):
    """Search using both traditional fuzzy and vector search."""

    # Get all cache data
    all_keys = await cache.get_all_keys("*")
    cache_data = {}

    for key in all_keys:
        value = await cache.get(key)
        if value:
            cache_data[key] = value

    if use_vector and cache_data:
        # Fit and search using vector similarity
        vector_search.fit(cache_data)
        vector_results = vector_search.search(query, cache_data, threshold=0.1)

        # Convert to consistent format
        results = [
            {
                "key": r.key,
                "value": r.value,
                "score": r.score,
                "method": "vector"
            }
            for r in vector_results
        ]
    else:
        # Fall back to traditional fuzzy search
        fuzzy_results = await cache.fuzzy_search(query)
        results = [
            {
                "key": r.key,
                "value": r.value,
                "score": r.score,
                "method": "fuzzy"
            }
            for r in fuzzy_results
        ]

    return results
```

### Real-time Index Updates

```python
class CacheWithVectorSearch:
    """Cache wrapper with automatic vector search updates."""

    def __init__(self, cache: YokedCache):
        self.cache = cache
        self.vector_search = VectorSimilaritySearch()
        self._cache_data = {}
        self._fitted = False

    async def set(self, key: str, value, **kwargs):
        """Set cache value and update search index."""
        result = await self.cache.set(key, value, **kwargs)

        # Update search index
        self._cache_data[key] = value
        self.vector_search.update_cache_entry(key, value)

        return result

    async def delete(self, key: str):
        """Delete cache value and update search index."""
        result = await self.cache.delete(key)

        # Update search index
        if key in self._cache_data:
            del self._cache_data[key]
            self.vector_search.remove_cache_entry(key)

        return result

    async def search(self, query: str, **kwargs):
        """Search using vector similarity."""
        if not self._fitted:
            # Initial fit
            all_keys = await self.cache.get_all_keys("*")
            for key in all_keys:
                value = await self.cache.get(key)
                if value:
                    self._cache_data[key] = value

            self.vector_search.fit(self._cache_data)
            self._fitted = True

        return self.vector_search.search(query, self._cache_data, **kwargs)
```

## Similarity Methods

### Cosine Similarity

Best for text-based content and high-dimensional sparse data.

```python
search = VectorSimilaritySearch(similarity_method="cosine")
```

**Characteristics:**
- Range: 0.0 to 1.0 (higher is more similar)
- Normalized by vector magnitude
- Excellent for text similarity
- Handles different document lengths well

**Use Cases:**
- Document similarity
- Content recommendation
- Semantic search

### Euclidean Distance

Measures straight-line distance between vectors in n-dimensional space.

```python
search = VectorSimilaritySearch(similarity_method="euclidean")
```

**Characteristics:**
- Range: 0.0 to ∞ (lower is more similar, converted to 1/(1+distance))
- Sensitive to magnitude differences
- Good for numerical data
- Intuitive geometric interpretation

**Use Cases:**
- Numerical data comparison
- Feature similarity
- Spatial data analysis

### Manhattan Distance

Measures city-block distance between vectors.

```python
search = VectorSimilaritySearch(similarity_method="manhattan")
```

**Characteristics:**
- Range: 0.0 to ∞ (lower is more similar, converted to 1/(1+distance))
- Less sensitive to outliers than Euclidean
- Good for sparse data
- Computationally efficient

**Use Cases:**
- Categorical data
- Sparse feature vectors
- Robust similarity measurement

### Comparison Example

```python
# Test different similarity methods
methods = ["cosine", "euclidean", "manhattan"]
query = "machine learning engineer"

for method in methods:
    search = VectorSimilaritySearch(similarity_method=method)
    search.fit(cache_data)
    results = search.search(query, cache_data, threshold=0.1, max_results=3)

    print(f"\n{method.title()} Similarity Results:")
    for result in results:
        print(f"  {result.key}: {result.score:.3f}")
```

## Performance Optimization

### Vectorizer Optimization

```python
# For large datasets
search = VectorSimilaritySearch(
    max_features=10000,         # Larger vocabulary
    min_df=5,                   # Ignore very rare terms
    max_df=0.7,                 # Ignore very common terms
    ngram_range=(1, 2)          # Limit n-gram range
)

# For small datasets
search = VectorSimilaritySearch(
    max_features=1000,          # Smaller vocabulary
    min_df=1,                   # Include rare terms
    max_df=0.95,                # Keep most terms
    ngram_range=(1, 3)          # Include trigrams
)
```

### Memory Management

```python
# Monitor memory usage
stats = search.get_stats()
print(f"Vector density: {stats['vector_density']:.3f}")
print(f"Number of features: {stats['num_features']}")
print(f"Memory efficiency: {stats['vector_density'] * 100:.1f}%")

# For memory-constrained environments
search = VectorSimilaritySearch(
    max_features=500,           # Reduce vocabulary
    min_df=3,                   # Filter rare terms
    ngram_range=(1, 1)          # Only unigrams
)
```

### Batch Operations

```python
# Batch index updates for better performance
class BatchVectorSearch:
    def __init__(self, batch_size=100):
        self.search = VectorSimilaritySearch()
        self.pending_updates = {}
        self.batch_size = batch_size

    def update_entry(self, key: str, value):
        """Add entry to batch update."""
        self.pending_updates[key] = value

        if len(self.pending_updates) >= self.batch_size:
            self.flush_updates()

    def flush_updates(self):
        """Apply all pending updates."""
        if self.pending_updates:
            # Merge with existing data and refit
            self.search.fit(self.pending_updates)
            self.pending_updates.clear()
```

## Integration with Cache

### Automatic Vector Search

```python
from yokedcache import YokedCache, CacheConfig
from yokedcache.backends import MemoryBackend

# Enable vector search in cache configuration
config = CacheConfig(
    backend=MemoryBackend(),
    enable_fuzzy=True,
    fuzzy_threshold=70,
    vector_search=True,          # Enable vector search
    vector_similarity="cosine"   # Choose similarity method
)

cache = YokedCache(config)

# Search automatically uses vector similarity
results = await cache.fuzzy_search("python developer")
```

### Redis Vector Storage

For distributed systems, store vectors in Redis:

```python
from yokedcache.vector_search import RedisVectorSearch
import redis.asyncio as redis

# Setup Redis vector storage
redis_client = redis.Redis.from_url("redis://localhost:6379/1")
vector_store = RedisVectorSearch(
    redis_client,
    vector_key_prefix="vectors:",
    similarity_method="cosine"
)

# Store and retrieve vectors
import numpy as np

vector = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
await vector_store.store_vector("doc:123", vector)

retrieved = await vector_store.get_vector("doc:123")
print(f"Vectors match: {np.array_equal(vector, retrieved)}")
```

### Hybrid Search Strategy

```python
async def hybrid_search(cache, query: str, threshold: float = 0.1):
    """Combine traditional fuzzy search with vector search."""

    # Get traditional fuzzy results
    fuzzy_results = await cache.fuzzy_search(query, threshold=threshold*100)

    # Get vector search results
    vector_search = VectorSimilaritySearch()
    all_data = await cache.get_all_data()  # Implement this method
    vector_search.fit(all_data)
    vector_results = vector_search.search(query, all_data, threshold=threshold)

    # Combine and rank results
    combined_results = {}

    # Add fuzzy results
    for result in fuzzy_results:
        combined_results[result.key] = {
            "value": result.value,
            "fuzzy_score": result.score / 100.0,
            "vector_score": 0.0
        }

    # Add vector results
    for result in vector_results:
        if result.key in combined_results:
            combined_results[result.key]["vector_score"] = result.score
        else:
            combined_results[result.key] = {
                "value": result.value,
                "fuzzy_score": 0.0,
                "vector_score": result.score
            }

    # Calculate combined score (weighted average)
    final_results = []
    for key, data in combined_results.items():
        combined_score = (data["fuzzy_score"] * 0.3 + data["vector_score"] * 0.7)
        if combined_score >= threshold:
            final_results.append({
                "key": key,
                "value": data["value"],
                "score": combined_score,
                "fuzzy_score": data["fuzzy_score"],
                "vector_score": data["vector_score"]
            })

    # Sort by combined score
    return sorted(final_results, key=lambda x: x["score"], reverse=True)
```

## Best Practices

### 1. Data Preparation

```python
def prepare_search_data(data):
    """Prepare data for optimal vector search."""
    if isinstance(data, dict):
        # Extract meaningful text fields
        text_fields = []
        for key, value in data.items():
            if isinstance(value, str):
                text_fields.append(f"{key}:{value}")
            elif isinstance(value, list):
                text_fields.append(f"{key}:{','.join(map(str, value))}")
        return " ".join(text_fields)
    return str(data)
```

### 2. Index Management

```python
class ManagedVectorSearch:
    """Vector search with automatic index management."""

    def __init__(self, rebuild_threshold=1000):
        self.search = VectorSimilaritySearch()
        self.rebuild_threshold = rebuild_threshold
        self.updates_since_rebuild = 0

    def should_rebuild_index(self):
        """Check if index should be rebuilt."""
        return self.updates_since_rebuild >= self.rebuild_threshold

    async def update_and_maybe_rebuild(self, cache_data):
        """Update index and rebuild if necessary."""
        self.updates_since_rebuild += 1

        if self.should_rebuild_index():
            self.search.fit(cache_data)
            self.updates_since_rebuild = 0
```

### 3. Error Handling

```python
async def safe_vector_search(query: str, cache_data: dict):
    """Vector search with graceful error handling."""
    try:
        search = VectorSimilaritySearch()
        search.fit(cache_data)
        return search.search(query, cache_data)
    except ImportError:
        logger.warning("Vector search dependencies not available, skipping")
        return []
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return []
```

---

Vector-based similarity search opens up powerful possibilities for intelligent caching and data discovery. By understanding semantic relationships in your data, you can build more intuitive and effective applications.
