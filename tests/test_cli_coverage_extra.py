"""Extra CLI coverage tests targeting untested branches in cli.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from yokedcache.cli import main, reset_cache_instance
from yokedcache.models import CacheStats


@pytest.fixture(autouse=True)
def _reset_cache_instance():
    """Ensure global CLI cache instance is reset between tests."""
    reset_cache_instance()
    yield
    reset_cache_instance()


def _mk_stats(with_tables: bool = False) -> CacheStats:
    stats: CacheStats = CacheStats()
    stats.total_hits = 1
    stats.total_misses = 1
    stats.total_sets = 1
    stats.total_deletes = 0
    stats.total_invalidations = 0
    stats.total_keys = 2
    stats.total_memory_bytes = 1234
    stats.uptime_seconds = 10.0
    if with_tables:
        stats.table_stats = {"users": {"hits": 1, "misses": 0}}
    return stats


def _mk_cache(stats: CacheStats):
    cache = AsyncMock()
    cache.get_stats.return_value = stats
    cache.connect.return_value = None
    cache.disconnect.return_value = None
    return cache


def test_cli_stats_human_with_table_stats():
    runner = CliRunner()
    stats = _mk_stats(with_tables=True)
    with patch("yokedcache.cli.YokedCache") as cls:
        cls.return_value = _mk_cache(stats)
        result = runner.invoke(main, ["stats", "--format", "human"])
        assert result.exit_code == 0
        assert "Table Statistics" in result.output


def test_cli_stats_watch_mode(monkeypatch):
    """Watch loop should break on KeyboardInterrupt and print message."""
    runner = CliRunner()
    stats = _mk_stats()
    with patch("yokedcache.cli.YokedCache") as cls:
        cls.return_value = _mk_cache(stats)

        def fake_sleep(_):  # raise after first iteration
            raise KeyboardInterrupt

        monkeypatch.setattr("time.sleep", fake_sleep)
        result = runner.invoke(main, ["stats", "--watch"])
        # Should still exit cleanly
        assert "Stopped watching" in result.output


def test_cli_list_human_with_limit():
    """List command human format limited notice branch."""
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache(_mk_stats())
        fake_r = AsyncMock()
        # Two keys so limiting to 1 triggers notice branch
        fake_r.keys = AsyncMock(return_value=[b"pref:k1", b"pref:k2"])  # noqa: E501
        cache._get_redis = MagicMock()

        class CM:
            async def __aenter__(self):
                return fake_r

            async def __aexit__(self, exc_type, exc, tb):
                return False

        cache._get_redis.return_value = CM()
        cache._build_key = MagicMock(side_effect=lambda p: f"pref:{p}")
        cls.return_value = cache
        result = runner.invoke(main, ["list", "--limit", "1"])
        assert result.exit_code == 0
        assert "Limited to 1 keys" in result.output


def test_cli_flush_abort_confirmation():
    runner = CliRunner()
    with (
        patch("yokedcache.cli.YokedCache") as cls,
        patch("click.confirm", return_value=False) as confirm,
    ):
        cache = _mk_cache(_mk_stats())
        cls.return_value = cache
        # Provide pattern so confirmation path hit then abort
        result = runner.invoke(main, ["flush", "--pattern", "x:*"])
        assert result.exit_code == 0  # abort is graceful
        assert "Aborted" in result.output
        confirm.assert_called_once()


def test_cli_warm_missing_warm_section(tmp_path):
    runner = CliRunner()
    # Config without warm section
    from typing import Any, Dict

    cfg: Dict[str, Any] = {"notwarm": {}}
    import yaml

    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.dump(cfg))
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache(_mk_stats())
        cls.return_value = cache
        result = runner.invoke(main, ["warm", "--config-file", str(p)])
        assert result.exit_code != 0
        assert "No cache warming" in result.output


def test_cli_warm_item_error(tmp_path):
    runner = CliRunner()
    # One valid item, one failing item (has value but set raises)
    cfg = {
        "warm": {
            "items": [
                {"key": "a", "value": "1"},
                {"key": "b", "value": "2"},
            ]
        }
    }
    import yaml

    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.dump(cfg))
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache(_mk_stats())
        # second item triggers error path in warm loop
        cache.set.side_effect = [True, Exception("fail")]  # noqa: E501
        cls.return_value = cache
        result = runner.invoke(main, ["warm", "--config-file", str(p)])
        assert result.exit_code == 0
        assert "Failed to warm" in result.output


def test_cli_invalidate_pattern_and_tags():
    """Invalidate command with both pattern and tags sequentially."""
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache(_mk_stats())
        cache.invalidate_pattern.return_value = 2
        cache.invalidate_tags.return_value = 3
        cls.return_value = cache
        result = runner.invoke(
            main, ["invalidate", "--pattern", "a:*", "--tags", "x,y"]
        )
        assert result.exit_code == 0
        assert "Invalidated 2" in result.output and ("Invalidated 3" in result.output)


# def test_cli_export_config_with_tables(tmp_path):
#     # Directly invoke command callback to avoid click parsing quirks with sets
#     from click import Context
#
#     from yokedcache import YokedCache as RealCache
#     from yokedcache import cli as cli_mod
#     from yokedcache.config import CacheConfig
#     from yokedcache.models import TableCacheConfig
#
#     cfg = CacheConfig(
#         redis_url="redis://localhost:6379/0",
#         default_ttl=99,
#         key_prefix="kp",
#         enable_fuzzy=False,
#         max_connections=5,
#         enable_env_overrides=False,
#     )
#     cfg.table_configs = {
#         "users": TableCacheConfig(table_name="users", ttl=10, tags={"t1", "t2"})
#     }
#     cli_mod._cache_instance = RealCache(config=cfg)
#     out = tmp_path / "cfg.yaml"
#     # Build click context similar to group invocation
#     ctx = Context(main)
#     ctx.obj = {
#         "redis_url": cfg.redis_url,
#         "config_file": None,
#         "verbose": False,
#     }
#     # Access the command and call its callback (sync wrapper)
#     runner = CliRunner()
#     with patch("yokedcache.cli.YokedCache") as cls:
#         cache = _mk_cache(_mk_stats())
#         # Dummy table config object with list tags (avoid set ordering issues)
#         tc = type(
#             "TC",
#             (),
#             {"ttl": 10, "tags": ["t1", "t2"], "enable_fuzzy": False},
#         )
#         cache.config.table_configs = {"users": tc}
#         cache.config.redis_url = "redis://r"
#         cache.config.default_ttl = 99
#         cache.config.key_prefix = "kp"
#         cache.config.enable_fuzzy = False
#         cache.config.fuzzy_threshold = 80
#         cache.config.max_connections = 5
#         cache.config.log_level = "INFO"
#         cls.return_value = cache
#         out = tmp_path / "cfg.yaml"
#         result = runner.invoke(main, ["export-config", "--output", str(out)])
#         assert result.exit_code == 0
#         text = out.read_text()
#         assert "users:" in text and "ttl: 10" in text
