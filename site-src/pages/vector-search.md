# Vector Search

Find semantically related content in your cache—not just key name matches. Vector search converts text to TF-IDF vectors and compares them using cosine similarity, so a query for "Python developer" returns results about "FastAPI engineer" and "backend programmer."

```bash
pip install "yokedcache[vector]"
```

---

## How it works

```
Query: "Python developer"
         │
         ▼
   TF-IDF vectorizer
         │
         ▼
  [0.4, 0.0, 0.8, ...]   ← query vector
         │
         ▼
  Compare against indexed cache entries using cosine similarity
         │
         ▼
  Ranked results filtered by threshold
```

1. **Text extraction:** YokedCache extracts searchable text from cache keys and values
2. **Vectorization:** Text is converted to TF-IDF vectors (weights terms by frequency + rarity)
3. **Similarity:** Compares query vector to all indexed vectors using your chosen metric
4. **Ranking:** Results sorted by score, filtered by threshold

---

## Basic usage

```python
from yokedcache.vector_search import VectorSimilaritySearch

cache_data = {
    "user:1": {"name": "Alice", "role": "Python Developer", "skills": ["FastAPI", "Redis"]},
    "user:2": {"name": "Bob", "role": "Data Scientist", "skills": ["Python", "ML", "PyTorch"]},
    "user:3": {"name": "Charlie", "role": "Frontend Developer", "skills": ["React", "TypeScript"]},
    "post:1": {"title": "Getting started with FastAPI", "tags": ["python", "web"]},
    "post:2": {"title": "Redis caching patterns", "tags": ["redis", "performance"]},
}

# Initialize and fit the vectorizer
search = VectorSimilaritySearch()
search.fit(cache_data)

# Search
results = search.search("Python web developer", cache_data, threshold=0.1, max_results=5)

for r in results:
    print(f"{r.key:20s}  score={r.score:.3f}  value={r.value}")

# user:1               score=0.742  value={'name': 'Alice', ...}
# user:2               score=0.521  value={'name': 'Bob', ...}
# post:1               score=0.389  value={'title': 'Getting started with FastAPI', ...}
```

---

## Configuration

```python
search = VectorSimilaritySearch(
    similarity_method="cosine",  # "cosine" | "euclidean" | "manhattan"
    max_features=2000,           # vocabulary size (more = more accurate, slower)
    ngram_range=(1, 2),          # word n-grams: (1,1) unigrams, (1,2) unigrams+bigrams
    min_df=1,                    # ignore terms appearing in fewer than N documents
    max_df=0.95,                 # ignore terms appearing in more than 95% of documents
    stop_words="english",        # filter common English words (None to disable)
    lowercase=True,              # normalize to lowercase
    strip_accents="unicode",     # remove accents
)
```

### Similarity methods

| Method | Formula | Range | Best for |
|--------|---------|-------|---------|
| **Cosine** (default) | `dot(A,B) / (‖A‖ × ‖B‖)` | 0.0–1.0 (higher = more similar) | Text; handles different document lengths |
| **Euclidean** | `√Σ(Aᵢ-Bᵢ)²` | 0.0–∞ (lower = more similar) | Dense vectors with similar magnitudes |
| **Manhattan** | `Σ‖Aᵢ-Bᵢ‖` | 0.0–∞ (lower = more similar) | Robust to outliers |

Cosine similarity is almost always the right choice for text data.

---

## Integration with YokedCache

### Search against live cache

```python
from yokedcache import YokedCache
from yokedcache.config import CacheConfig
from yokedcache.vector_search import VectorSimilaritySearch

cache = YokedCache(CacheConfig())
vector_search = VectorSimilaritySearch(similarity_method="cosine")

async def search_cache(query: str, threshold: float = 0.1, limit: int = 10):
    """Search the live cache using vector similarity."""
    keys = await cache.get_all_keys()
    cache_data = {k: v for k in keys if (v := await cache.get(k)) is not None}

    if not cache_data:
        return []

    vector_search.fit(cache_data)
    return vector_search.search(query, cache_data, threshold=threshold, max_results=limit)
```

### Maintained index (recommended for large caches)

Re-fitting on every search is expensive. Instead, maintain a rolling index:

```python
class IndexedCache:
    """Cache wrapper that keeps a vector search index in sync."""

    def __init__(self, cache: YokedCache):
        self.cache = cache
        self._search = VectorSimilaritySearch()
        self._data: dict = {}
        self._fitted = False

    async def set(self, key: str, value, **kwargs):
        await self.cache.set(key, value, **kwargs)
        self._data[key] = value
        self._search.update_cache_entry(key, value)
        self._fitted = False  # mark for re-fit on next search

    async def delete(self, key: str):
        await self.cache.delete(key)
        self._data.pop(key, None)
        self._search.remove_cache_entry(key)

    async def search(self, query: str, **kwargs):
        if not self._fitted:
            self._search.fit(self._data)
            self._fitted = True
        return self._search.search(query, self._data, **kwargs)
```

### FastAPI endpoint

```python
@app.get("/search")
async def semantic_search(
    q: str,
    threshold: float = 0.1,
    limit: int = 10,
    tags: str | None = None,
):
    tag_filter = set(tags.split(",")) if tags else None
    results = await search_cache(q, threshold=threshold, limit=limit)

    if tag_filter:
        results = [r for r in results if tag_filter & set(r.value.get("tags", []))]

    return [{"key": r.key, "score": r.score, "value": r.value} for r in results]
```

---

## Search result object

`VectorSearchResult` fields:

| Field | Type | Description |
|-------|------|-------------|
| `key` | `str` | Cache key |
| `score` | `float` | Similarity score (0.0–1.0 for cosine) |
| `value` | `Any` | Cached value |

---

## Threshold tuning

| Threshold | Effect |
|-----------|--------|
| `0.05` | Very broad—returns loosely related results |
| `0.1–0.2` | Good for exploratory search |
| `0.3–0.5` | Moderate precision |
| `0.5+` | High precision—only closely related content |

Start with `0.1` and tune based on your data.

---

## vs. Fuzzy search

| | Fuzzy search | Vector search |
|-|--------------|---------------|
| **Matches** | String similarity (typos, partial matches) | Semantic similarity (meaning) |
| **Example** | "alce" → "alice" | "python developer" → "software engineer" |
| **Speed** | Fast | Slower (fit + transform) |
| **Dependencies** | `yokedcache[fuzzy]` | `yokedcache[vector]` |
| **Best for** | Key lookups, name search | Content discovery, recommendations |

Use both together for the best results:

```python
# Check fuzzy first (fast)
fuzzy_results = await cache.fuzzy_search(query, threshold=80)
if fuzzy_results:
    return fuzzy_results

# Fall back to vector search (semantic)
vector_search.fit(cache_data)
return vector_search.search(query, cache_data, threshold=0.1)
```

---

## Performance tips

- **`max_features`**: Start at 1000–2000. Increase if search quality is poor, decrease if memory/speed matters.
- **`ngram_range=(1, 2)`**: Bigrams improve phrase matching but increase memory. Use `(1, 1)` for large caches.
- **Re-fit periodically**: For large caches, re-fit the vectorizer on a schedule (e.g., every 5 minutes) rather than on every write.
- **Pre-filter by tag**: Narrow the search space before fitting to improve performance on large caches.

```python
# Pre-filter: only search within "products" tagged entries
keys = await cache.get_keys_by_tag("products")
filtered_data = {k: v for k in keys if (v := await cache.get(k)) is not None}
vector_search.fit(filtered_data)
results = vector_search.search(query, filtered_data, threshold=0.1)
```
