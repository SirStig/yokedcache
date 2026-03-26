# CLI Reference

The `yokedcache` CLI ships with the package. It's useful for debugging, inspection, and operational tasks—inspecting keys, checking hit rates, flushing data, and running health checks.

```bash
yokedcache --help
yokedcache --version
```

---

## Global options

These apply to every command:

```
--redis-url URL        Redis connection URL (overrides YOKEDCACHE_REDIS_URL)
--config-file PATH     Path to a YAML config file
--key-prefix PREFIX    Key prefix (overrides YOKEDCACHE_KEY_PREFIX)
--log-level LEVEL      DEBUG | INFO | WARNING | ERROR (default: INFO)
--help                 Show help
--version              Show version
```

Set defaults via environment variables so you don't have to repeat them:

```bash
export YOKEDCACHE_REDIS_URL="redis://localhost:6379/0"
export YOKEDCACHE_KEY_PREFIX="myapp"
export YOKEDCACHE_LOG_LEVEL="WARNING"
```

---

## `ping` — test connection

```bash
yokedcache ping
# OK (1.2ms)

yokedcache ping --redis-url redis://other-host:6379/0
yokedcache ping --show-timing    # always show latency
yokedcache ping --count 5        # ping 5 times
yokedcache ping --count 10 --interval 0.5  # ping every 0.5 seconds
```

Returns exit code `0` on success, `3` on connection failure.

---

## `stats` — cache statistics

```bash
yokedcache stats
```

Output:

```
Hit rate:     87.3%
Miss rate:    12.7%
Keys:         1,247
Memory:       24.8 MB
Hits:         10,840
Misses:       1,582
Total ops:    12,422
Uptime:       7,200s
```

Options:

```bash
yokedcache stats --watch              # live refresh (default interval: 2s)
yokedcache stats --watch --interval 5 # refresh every 5s
yokedcache stats --format json        # machine-readable JSON
yokedcache stats --format csv --output stats.csv
```

JSON output for scripting:

```bash
yokedcache stats --format json | jq '.hit_rate'
# 0.873
```

---

## `list` — list cache keys

```bash
yokedcache list
```

Options:

```bash
yokedcache list --pattern "user:*"         # glob pattern filter
yokedcache list --tags user_data           # filter by tag
yokedcache list --tags "user_data,active"  # multiple tags (comma-separated)
yokedcache list --include-values           # include cached values
yokedcache list --limit 100                # max keys to return (default: 1000)
yokedcache list --format json
yokedcache list --format json | jq '.[] | .key'  # just the keys
```

Sample output:

```
KEY                TTL      TAGS
user:1             287s     users, tenant:acme
user:2             241s     users, tenant:acme
product:99         3520s    products, electronics
session:abc123     814s     sessions
```

---

## `search` — fuzzy key search

Find keys by approximate match (requires `yokedcache[fuzzy]`):

```bash
yokedcache search "alice"
yokedcache search "alice" --threshold 80       # similarity 0–100 (default: 80)
yokedcache search "alice" --max-results 10
yokedcache search "alice" --tags users,active  # restrict to these tags
yokedcache search "alice" --format json
```

Output:

```
KEY              SCORE   VALUE
user:alice_j     92      {"name": "Alice Johnson", ...}
user:bob_alice   78      {"name": "Bob Alice", ...}
```

---

## `flush` — delete keys

Delete keys in bulk. **Irreversible**—use `--confirm` to prompt first.

```bash
# By tag
yokedcache flush --tags "user_data" --confirm
yokedcache flush --tags "user_data,session_data" --force  # skip confirmation

# By pattern
yokedcache flush --pattern "temp:*" --confirm
yokedcache flush --pattern "session:expired:*" --force

# Everything under the current key prefix (NOT the entire Redis DB)
yokedcache flush --all --confirm
```

`--confirm` shows what would be deleted and prompts before proceeding.
`--force` deletes immediately without prompting.

---

## `warm` — pre-populate cache

Pre-populate the cache from a YAML config file:

```bash
yokedcache warm --config-file warming.yaml
yokedcache warm --config-file warming.yaml --verbose  # show progress
```

`warming.yaml` format:

```yaml
entries:
  - key: config:global
    value: {env: production, version: "1.2.0"}
    ttl: 3600

  - key: categories
    value: [electronics, books, clothing]
    ttl: 7200

  - key: feature:flags
    value: {dark_mode: true, new_checkout: false}
    ttl: 300
    tags: [features]
```

---

## `export-config` — dump configuration

Dump the active configuration:

```bash
yokedcache export-config                         # prints YAML to stdout
yokedcache export-config --output config.yaml    # write to file
yokedcache export-config --format json           # JSON format
yokedcache export-config --format json | jq      # pretty-print
```

---

## Output formats

Most commands accept `--format`:

| Format | Best for |
|--------|----------|
| `table` (default) | Human reading |
| `json` | Scripts and automation |
| `csv` | Spreadsheets and data analysis |

---

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Configuration error (bad URL, invalid option) |
| 3 | Connection error (can't reach Redis) |

Use in shell scripts:

```bash
yokedcache ping || echo "Cache is down!" && exit 1

# Check hit rate and alert if low
HIT_RATE=$(yokedcache stats --format json | jq '.hit_rate')
if (( $(echo "$HIT_RATE < 0.7" | bc -l) )); then
    echo "WARNING: cache hit rate is $HIT_RATE"
fi
```

---

## Scripting examples

```bash
# Watch hit rate in a loop
while true; do
    yokedcache stats --format json | jq '"\(.hit_rate * 100 | floor)% hit rate, \(.key_count) keys"'
    sleep 10
done

# Export all user keys to JSON
yokedcache list --pattern "user:*" --include-values --format json > users.json

# Clear all expired sessions
yokedcache flush --tags "session_data" --confirm

# Get keys with TTL > 1 hour
yokedcache list --format json | jq '.[] | select(.ttl > 3600) | .key'

# Count keys by prefix
yokedcache list --format json | jq '[.[].key | split(":")[0]] | group_by(.) | map({(.[0]): length}) | add'
```
