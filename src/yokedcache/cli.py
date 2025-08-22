"""
Command-line interface for YokedCache.

This module provides CLI commands for cache management, monitoring,
and maintenance operations.
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

import click
import yaml

from .cache import YokedCache
from .config import CacheConfig, load_config_from_file
from .utils import format_bytes
from .exceptions import YokedCacheError


# Global cache instance for CLI commands
_cache_instance: Optional[YokedCache] = None


def get_cache_instance(
    redis_url: Optional[str] = None,
    config_file: Optional[str] = None,
) -> YokedCache:
    """Get or create cache instance for CLI operations."""
    global _cache_instance
    
    if _cache_instance is None:
        if config_file and Path(config_file).exists():
            config = load_config_from_file(config_file)
        else:
            config = CacheConfig()
        
        if redis_url:
            config.redis_url = redis_url
        
        _cache_instance = YokedCache(config=config)
    
    return _cache_instance


def async_command(f):
    """Decorator to handle async commands."""
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return asyncio.run(f(ctx, *args, **kwargs))
    return wrapper


@click.group()
@click.option(
    '--redis-url', '-r',
    help='Redis connection URL',
    envvar='YOKEDCACHE_REDIS_URL',
    default='redis://localhost:6379/0'
)
@click.option(
    '--config', '-c',
    help='Configuration file path',
    type=click.Path(exists=False),
    envvar='YOKEDCACHE_CONFIG_FILE'
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='Enable verbose output'
)
@click.pass_context
def main(ctx, redis_url: str, config: Optional[str], verbose: bool):
    """YokedCache CLI - Manage and monitor your cache."""
    ctx.ensure_object(dict)
    ctx.obj['redis_url'] = redis_url
    ctx.obj['config_file'] = config
    ctx.obj['verbose'] = verbose
    
    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)


@main.command()
@click.option(
    '--format', '-f',
    type=click.Choice(['human', 'json', 'yaml']),
    default='human',
    help='Output format'
)
@click.option(
    '--watch', '-w',
    is_flag=True,
    help='Watch mode (refresh every 5 seconds)'
)
@click.pass_context
@async_command
async def stats(ctx, format: str, watch: bool):
    """Show cache statistics and performance metrics."""
    cache = get_cache_instance(
        redis_url=ctx.obj['redis_url'],
        config_file=ctx.obj['config_file']
    )
    
    try:
        await cache.connect()
        
        if watch:
            while True:
                await _display_stats(cache, format)
                if format == 'human':
                    click.echo("\n" + "="*60)
                    click.echo("Press Ctrl+C to stop watching...")
                time.sleep(5)
        else:
            await _display_stats(cache, format)
    
    except KeyboardInterrupt:
        if watch:
            click.echo("\nStopped watching.")
    except Exception as e:
        click.echo(f"Error getting stats: {e}", err=True)
        sys.exit(1)
    finally:
        await cache.disconnect()


async def _display_stats(cache: YokedCache, format: str):
    """Display cache statistics in the specified format."""
    stats = await cache.get_stats()
    
    if format == 'json':
        stats_dict = {
            'total_hits': stats.total_hits,
            'total_misses': stats.total_misses,
            'total_sets': stats.total_sets,
            'total_deletes': stats.total_deletes,
            'total_invalidations': stats.total_invalidations,
            'total_keys': stats.total_keys,
            'total_memory_bytes': stats.total_memory_bytes,
            'uptime_seconds': stats.uptime_seconds,
            'hit_rate': stats.hit_rate,
            'miss_rate': stats.miss_rate,
            'average_get_time_ms': stats.average_get_time_ms,
            'average_set_time_ms': stats.average_set_time_ms,
            'table_stats': stats.table_stats,
            'tag_stats': stats.tag_stats,
        }
        click.echo(json.dumps(stats_dict, indent=2))
    
    elif format == 'yaml':
        stats_dict = {
            'cache_stats': {
                'operations': {
                    'hits': stats.total_hits,
                    'misses': stats.total_misses,
                    'sets': stats.total_sets,
                    'deletes': stats.total_deletes,
                    'invalidations': stats.total_invalidations,
                },
                'performance': {
                    'hit_rate_percent': round(stats.hit_rate, 2),
                    'miss_rate_percent': round(stats.miss_rate, 2),
                    'avg_get_time_ms': stats.average_get_time_ms,
                    'avg_set_time_ms': stats.average_set_time_ms,
                },
                'memory': {
                    'total_keys': stats.total_keys,
                    'total_memory_bytes': stats.total_memory_bytes,
                    'total_memory_human': format_bytes(stats.total_memory_bytes),
                },
                'uptime_seconds': stats.uptime_seconds,
                'table_stats': stats.table_stats,
                'tag_stats': stats.tag_stats,
            }
        }
        click.echo(yaml.dump(stats_dict, default_flow_style=False))
    
    else:  # human format
        click.echo("YokedCache Statistics")
        click.echo("=" * 30)
        click.echo(f"Cache Operations:")
        click.echo(f"  Hits:           {stats.total_hits:,}")
        click.echo(f"  Misses:         {stats.total_misses:,}")
        click.echo(f"  Sets:           {stats.total_sets:,}")
        click.echo(f"  Deletes:        {stats.total_deletes:,}")
        click.echo(f"  Invalidations:  {stats.total_invalidations:,}")
        click.echo()
        click.echo(f"Performance:")
        click.echo(f"  Hit Rate:       {stats.hit_rate:.2f}%")
        click.echo(f"  Miss Rate:      {stats.miss_rate:.2f}%")
        click.echo(f"  Avg Get Time:   {stats.average_get_time_ms:.2f}ms")
        click.echo(f"  Avg Set Time:   {stats.average_set_time_ms:.2f}ms")
        click.echo()
        click.echo(f"Memory Usage:")
        click.echo(f"  Total Keys:     {stats.total_keys:,}")
        click.echo(f"  Memory Used:    {format_bytes(stats.total_memory_bytes)}")
        click.echo()
        click.echo(f"Uptime:         {stats.uptime_seconds:.1f} seconds")
        
        if stats.table_stats:
            click.echo()
            click.echo("Table Statistics:")
            for table, table_stats in stats.table_stats.items():
                click.echo(f"  {table}:")
                click.echo(f"    Hits: {table_stats.get('hits', 0)}, Misses: {table_stats.get('misses', 0)}")


@main.command()
@click.option(
    '--prefix', '-p',
    help='Key prefix to filter by'
)
@click.option(
    '--pattern', '-P',
    help='Key pattern (supports * and ?)'
)
@click.option(
    '--limit', '-l',
    type=int,
    default=100,
    help='Maximum number of keys to show'
)
@click.option(
    '--format', '-f',
    type=click.Choice(['human', 'json']),
    default='human',
    help='Output format'
)
@click.pass_context
@async_command
async def list(ctx, prefix: Optional[str], pattern: Optional[str], limit: int, format: str):
    """List cached keys."""
    cache = get_cache_instance(
        redis_url=ctx.obj['redis_url'],
        config_file=ctx.obj['config_file']
    )
    
    try:
        await cache.connect()
        
        # Build search pattern
        search_pattern = "*"
        if pattern:
            search_pattern = pattern
        elif prefix:
            search_pattern = f"{prefix}*"
        
        # Get keys from Redis
        async with cache._get_redis() as r:
            full_pattern = cache._build_key(search_pattern)
            keys = await r.keys(full_pattern)
            
            # Limit results
            keys = keys[:limit]
            
            if format == 'json':
                key_list = [key.decode() if isinstance(key, bytes) else str(key) for key in keys]
                click.echo(json.dumps({
                    'keys': key_list,
                    'count': len(key_list),
                    'pattern': search_pattern
                }, indent=2))
            else:
                click.echo(f"Found {len(keys)} keys matching pattern: {search_pattern}")
                click.echo("-" * 50)
                for key in keys:
                    key_str = key.decode() if isinstance(key, bytes) else str(key)
                    click.echo(f"  {key_str}")
                
                if len(keys) == limit:
                    click.echo(f"\n(Limited to {limit} keys)")
    
    except Exception as e:
        click.echo(f"Error listing keys: {e}", err=True)
        sys.exit(1)
    finally:
        await cache.disconnect()


@main.command()
@click.option(
    '--pattern', '-p',
    help='Key pattern to flush (supports * and ?)'
)
@click.option(
    '--tags', '-t',
    help='Comma-separated list of tags to invalidate'
)
@click.option(
    '--key', '-k',
    help='Specific key to delete'
)
@click.option(
    '--all', '-a',
    is_flag=True,
    help='Flush all cache keys (use with caution!)'
)
@click.option(
    '--force', '-f',
    is_flag=True,
    help='Skip confirmation prompt'
)
@click.pass_context
@async_command
async def flush(
    ctx, 
    pattern: Optional[str], 
    tags: Optional[str], 
    key: Optional[str], 
    all: bool, 
    force: bool
):
    """Flush cache keys or tags."""
    if not any([pattern, tags, key, all]):
        click.echo("Error: Must specify --pattern, --tags, --key, or --all", err=True)
        sys.exit(1)
    
    cache = get_cache_instance(
        redis_url=ctx.obj['redis_url'],
        config_file=ctx.obj['config_file']
    )
    
    try:
        await cache.connect()
        
        # Confirmation prompt
        if not force:
            if all:
                if not click.confirm("Are you sure you want to flush ALL cache keys?"):
                    click.echo("Aborted.")
                    return
            else:
                target = pattern or tags or key
                if not click.confirm(f"Are you sure you want to flush: {target}?"):
                    click.echo("Aborted.")
                    return
        
        deleted_count = 0
        
        if all:
            deleted_count = await cache.flush_all()
            click.echo(f"Flushed all cache keys")
        
        elif key:
            success = await cache.delete(key)
            deleted_count = 1 if success else 0
            click.echo(f"Deleted key: {key}" if success else f"Key not found: {key}")
        
        elif pattern:
            deleted_count = await cache.invalidate_pattern(pattern)
            click.echo(f"Deleted {deleted_count} keys matching pattern: {pattern}")
        
        elif tags:
            tag_list = [tag.strip() for tag in tags.split(',')]
            deleted_count = await cache.invalidate_tags(tag_list)
            click.echo(f"Deleted {deleted_count} keys with tags: {tag_list}")
    
    except Exception as e:
        click.echo(f"Error flushing cache: {e}", err=True)
        sys.exit(1)
    finally:
        await cache.disconnect()


@main.command()
@click.option(
    '--config-file', '-c',
    type=click.Path(exists=True),
    help='Configuration file for cache warming'
)
@click.pass_context
@async_command
async def warm(ctx, config_file: Optional[str]):
    """Warm cache with predefined queries."""
    cache = get_cache_instance(
        redis_url=ctx.obj['redis_url'],
        config_file=ctx.obj['config_file']
    )
    
    config_path = config_file or ctx.obj.get('config_file')
    if not config_path or not Path(config_path).exists():
        click.echo("Error: Configuration file required for cache warming", err=True)
        sys.exit(1)
    
    try:
        await cache.connect()
        
        # Load warming configuration
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        warm_config = config_data.get('warm', {})
        if not warm_config:
            click.echo("No cache warming configuration found", err=True)
            sys.exit(1)
        
        # Execute warming operations
        warmed_count = 0
        
        for warm_item in warm_config.get('items', []):
            try:
                key = warm_item.get('key')
                value = warm_item.get('value')
                ttl = warm_item.get('ttl', cache.config.default_ttl)
                tags = warm_item.get('tags', [])
                
                if key and value:
                    await cache.set(key, value, ttl=ttl, tags=tags)
                    warmed_count += 1
                    click.echo(f"Warmed: {key}")
            
            except Exception as e:
                click.echo(f"Failed to warm {warm_item.get('key', 'unknown')}: {e}")
        
        click.echo(f"\nCache warming completed. Warmed {warmed_count} keys.")
    
    except Exception as e:
        click.echo(f"Error warming cache: {e}", err=True)
        sys.exit(1)
    finally:
        await cache.disconnect()


@main.command()
@click.option(
    '--timeout', '-t',
    type=int,
    default=5,
    help='Connection timeout in seconds'
)
@click.pass_context
@async_command
async def ping(ctx, timeout: int):
    """Test connection to Redis."""
    cache = get_cache_instance(
        redis_url=ctx.obj['redis_url'],
        config_file=ctx.obj['config_file']
    )
    
    try:
        start_time = time.time()
        await cache.connect()
        
        healthy = await cache.health_check()
        end_time = time.time()
        
        if healthy:
            response_time = (end_time - start_time) * 1000
            click.echo(f"✓ Redis connection successful ({response_time:.2f}ms)")
            click.echo(f"  URL: {cache.config.redis_url}")
        else:
            click.echo("✗ Redis connection failed", err=True)
            sys.exit(1)
    
    except Exception as e:
        click.echo(f"✗ Connection error: {e}", err=True)
        sys.exit(1)
    finally:
        await cache.disconnect()


@main.command()
@click.option(
    '--output', '-o',
    type=click.Path(),
    help='Output file path'
)
@click.pass_context
@async_command
async def export_config(ctx, output: Optional[str]):
    """Export current configuration to file."""
    cache = get_cache_instance(
        redis_url=ctx.obj['redis_url'],
        config_file=ctx.obj['config_file']
    )
    
    try:
        config_dict = {
            'redis_url': cache.config.redis_url,
            'default_ttl': cache.config.default_ttl,
            'key_prefix': cache.config.key_prefix,
            'enable_fuzzy': cache.config.enable_fuzzy,
            'fuzzy_threshold': cache.config.fuzzy_threshold,
            'max_connections': cache.config.max_connections,
            'log_level': cache.config.log_level,
        }
        
        if cache.config.table_configs:
            config_dict['tables'] = {}
            for table_name, table_config in cache.config.table_configs.items():
                config_dict['tables'][table_name] = {
                    'ttl': table_config.ttl,
                    'tags': list(table_config.tags),
                    'enable_fuzzy': table_config.enable_fuzzy,
                }
        
        config_yaml = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)
        
        if output:
            with open(output, 'w') as f:
                f.write(config_yaml)
            click.echo(f"Configuration exported to: {output}")
        else:
            click.echo("Current Configuration:")
            click.echo("-" * 30)
            click.echo(config_yaml)
    
    except Exception as e:
        click.echo(f"Error exporting configuration: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument('query', required=True)
@click.option(
    '--threshold', '-t',
    type=int,
    default=80,
    help='Similarity threshold (0-100)'
)
@click.option(
    '--max-results', '-m',
    type=int,
    default=10,
    help='Maximum number of results'
)
@click.option(
    '--format', '-f',
    type=click.Choice(['human', 'json']),
    default='human',
    help='Output format'
)
@click.pass_context
@async_command
async def search(ctx, query: str, threshold: int, max_results: int, format: str):
    """Perform fuzzy search on cached data."""
    cache = get_cache_instance(
        redis_url=ctx.obj['redis_url'],
        config_file=ctx.obj['config_file']
    )
    
    try:
        await cache.connect()
        
        results = await cache.fuzzy_search(
            query,
            threshold=threshold,
            max_results=max_results
        )
        
        if format == 'json':
            results_data = []
            for result in results:
                results_data.append({
                    'key': result.key,
                    'score': result.score,
                    'matched_term': result.matched_term,
                    'value': result.value
                })
            
            click.echo(json.dumps({
                'query': query,
                'results': results_data,
                'count': len(results_data)
            }, indent=2))
        
        else:
            click.echo(f"Fuzzy search results for: '{query}'")
            click.echo(f"Threshold: {threshold}%, Max results: {max_results}")
            click.echo("-" * 50)
            
            if results:
                for result in results:
                    click.echo(f"Score: {result.score}% | Key: {result.key}")
                    if ctx.obj['verbose']:
                        click.echo(f"  Value: {result.value}")
                    click.echo()
            else:
                click.echo("No matches found.")
    
    except Exception as e:
        click.echo(f"Error performing search: {e}", err=True)
        sys.exit(1)
    finally:
        await cache.disconnect()


if __name__ == '__main__':
    main()
