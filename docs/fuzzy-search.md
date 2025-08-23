# Fuzzy Search

Find approximate matches across cached keys (and optionally values you load).

## Enable

- Install extras: `pip install "yokedcache[fuzzy]"`
- Set `enable_fuzzy: true` in config (or `CacheConfig(enable_fuzzy=True)`).

## Usage (Python)

```python
results = await cache.fuzzy_search("alice", threshold=80, max_results=10)
for r in results:
    print(r.score, r.key)
```

## Usage (CLI)

```bash
yokedcache search "alice" --threshold 80 --max-results 10
```

Notes:
- Uses `fuzzywuzzy` by default; ensure keys are meaningful.
- Filter by tags by passing `tags` set to API.
