# CLI Reference

YokedCache provides a comprehensive command-line interface for cache management, monitoring, and troubleshooting. This guide covers all available commands and their options.

## Installation and Setup

The CLI is automatically available after installing YokedCache:

```bash
# Install YokedCache
pip install yokedcache

# Verify CLI installation
yokedcache --version

# Get help
yokedcache --help
```

## Global Options

All commands support these global options:

```bash
yokedcache [GLOBAL_OPTIONS] COMMAND [COMMAND_OPTIONS]

Global Options:
  --config-file PATH     Configuration file path
  --redis-url URL        Redis connection URL
  --key-prefix PREFIX    Key prefix for cache operations
  --log-level LEVEL      Logging level (DEBUG, INFO, WARNING, ERROR)
  --help                 Show help message
  --version              Show version information
```

## Core Commands

### `ping` - Test Connection

Test connectivity to your cache backend:

```bash
# Basic connection test
yokedcache ping

# With custom Redis URL
yokedcache ping --redis-url redis://localhost:6380/1

# Include response time
yokedcache ping --show-timing

# Test multiple times
yokedcache ping --count 5 --interval 1
```

### `stats` - Cache Statistics

View detailed cache statistics and performance metrics:

```bash
# Basic statistics
yokedcache stats

# Watch mode (auto-refresh)
yokedcache stats --watch

# Custom refresh interval
yokedcache stats --watch --interval 5

# JSON output
yokedcache stats --format json

# CSV output for analysis
yokedcache stats --format csv --output stats.csv
```

### `list` - List Cache Keys

List and filter cache keys:

```bash
# List all keys
yokedcache list

# List with pattern matching
yokedcache list --pattern "user:*"

# List by prefix
yokedcache list --prefix users:

# List by tags
yokedcache list --tags user_data,active

# Include values
yokedcache list --include-values

# Output formats
yokedcache list --format json --output keys.json
```

### `search` - Fuzzy Search

Perform fuzzy search across cache keys:

```bash
# Basic fuzzy search
yokedcache search "alice"

# Adjust similarity threshold
yokedcache search "alice" --threshold 80

# Limit results
yokedcache search "alice" --max-results 10

# Search within specific tags
yokedcache search "alice" --tags users,active
```

### `flush` - Clear Cache Data

Clear cache data in bulk:

```bash
# Flush by tags
yokedcache flush --tags "user_data,expired"

# Flush by pattern
yokedcache flush --pattern "temp:*" --force

# Confirm before flushing
yokedcache flush --tags "test_data" --confirm
```

### `export-config` - Export Configuration

Export current configuration:

```bash
# Export to YAML
yokedcache export-config --output config.yaml

# Export to JSON
yokedcache export-config --format json --output config.json
```

### `warm` - Cache Warming

Pre-populate cache with data:

```bash
# Warm from configuration file
yokedcache warm --config-file warming_config.yaml

# Warm with progress tracking
yokedcache warm --config-file warming_config.yaml --verbose
```

## CLI Cookbook

### Monitor Cache Performance
```bash
# Watch cache statistics continuously
yokedcache stats --watch

# Monitor with custom interval
yokedcache stats --watch --interval 5
```

### Export Configuration
```bash
# Export current config to YAML
yokedcache export-config --output config.yaml

# Export to JSON format
yokedcache export-config --format json --output config.json
```

### List Keys by Prefix
```bash
# List all user keys
yokedcache list --prefix users:

# List with pattern matching
yokedcache list --pattern "session:*"
```

### Delete by Pattern
```bash
# Delete temporary keys (with confirmation)
yokedcache flush --pattern "temp:*" --confirm

# Force delete without confirmation
yokedcache flush --pattern "cache:test:*" --force
```

### Invalidate by Tags
```bash
# Clear user data cache
yokedcache flush --tags "user_data" --confirm

# Clear multiple tag categories
yokedcache flush --tags "user_data,session_data" --force
```

### Search Cache Contents
```bash
# Find keys containing "alice"
yokedcache search "alice" --threshold 80

# Search with higher precision
yokedcache search "alice" --threshold 90 --max-results 5
```

## Output Formats

Most commands support multiple output formats:

- **table**: Human-readable table format (default)
- **json**: JSON format for programmatic processing
- **csv**: CSV format for data analysis

Example:
```bash
# JSON output for scripting
yokedcache stats --format json

# CSV output for analysis
yokedcache list --format csv --output keys.csv
```

## Environment Variables

Configure CLI behavior:

```bash
# Default Redis URL
export YOKEDCACHE_REDIS_URL="redis://localhost:6379/0"

# Default configuration file
export YOKEDCACHE_CONFIG_FILE="/etc/yokedcache/config.yaml"

# Default log level
export YOKEDCACHE_LOG_LEVEL="INFO"
```

## Scripting and Automation

Commands return standard exit codes for scripting:

- `0`: Success
- `1`: General error
- `2`: Configuration error
- `3`: Connection error

Process JSON output with tools like `jq`:

```bash
# Get cache hit rate
yokedcache stats --format json | jq '.hit_rate'

# List keys with high TTL
yokedcache list --format json | jq '.[] | select(.ttl > 3600) | .key'
```

The YokedCache CLI provides powerful tools for cache management, monitoring, and troubleshooting.
