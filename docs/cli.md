# CLI

```bash
# View cache statistics
$ yokedcache stats --watch

# Test Redis connection
$ yokedcache ping

# List cached keys
$ yokedcache list --pattern "user:*"

# Flush specific caches
$ yokedcache flush --tags "user_data"

# Search cache contents
$ yokedcache search "alice" --threshold 80

# Monitor in real-time (JSON output)
$ yokedcache stats --format json

# Export current configuration
$ yokedcache export-config --output config.yaml

# Warm cache with predefined data
$ yokedcache warm --config-file cache_config.yaml
```
