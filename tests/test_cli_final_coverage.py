"""Final CLI coverage tests for remaining uncovered branches in cli.py."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from yokedcache.cli import main, reset_cache_instance
from yokedcache.models import CacheStats


@pytest.fixture(autouse=True)
def _reset():
    reset_cache_instance()
    yield
    reset_cache_instance()


def _mk_stats() -> CacheStats:
    s = CacheStats()
    s.total_hits = 10
    s.total_misses = 5
    s.total_sets = 3
    s.total_deletes = 1
    s.total_invalidations = 2
    s.total_keys = 15
    s.total_memory_bytes = 2048
    s.uptime_seconds = 100.0
    return s


def _mk_cache(stats=None):
    c = AsyncMock()
    c.get_stats = AsyncMock(return_value=stats or _mk_stats())
    c.connect = AsyncMock()
    c.disconnect = AsyncMock()
    c.config = MagicMock()
    c.config.redis_url = "redis://localhost:6379/0"
    c.config.default_ttl = 300
    c.config.key_prefix = "test:"
    c.config.enable_fuzzy = True
    c.config.fuzzy_threshold = 80
    c.config.max_connections = 10
    c.config.log_level = "INFO"
    c.config.table_configs = {}
    return c


# ── verbose flag (lines 91-93) ────────────────────────────────────────────────


def test_main_verbose_flag_enables_logging():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cls.return_value = _mk_cache()
        result = runner.invoke(main, ["--verbose", "stats"])
    # Just ensure it runs without error; logging.basicConfig is side-effect only
    assert result.exit_code == 0


# ── stats exception branch (lines 137-139) ───────────────────────────────────


def test_stats_exception_exits_nonzero():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.connect = AsyncMock(side_effect=RuntimeError("conn fail"))
        cls.return_value = cache
        result = runner.invoke(main, ["stats"])
    assert result.exit_code == 1
    assert "Error getting stats" in result.output


# ── _display_stats json format (lines 149-173) ───────────────────────────────


def test_stats_json_format_stdout():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cls.return_value = _mk_cache()
        result = runner.invoke(main, ["stats", "--format", "json"])
    assert result.exit_code == 0
    assert "total_hits" in result.output
    assert "hit_rate" in result.output


def test_stats_json_format_to_file(tmp_path):
    out = tmp_path / "stats.json"
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cls.return_value = _mk_cache()
        result = runner.invoke(
            main, ["stats", "--format", "json", "--output", str(out)]
        )
    assert result.exit_code == 0
    assert "exported" in result.output.lower()
    assert out.exists()
    assert "total_hits" in out.read_text()


# ── _display_stats yaml format (lines 176-207) ───────────────────────────────


def test_stats_yaml_format_stdout():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cls.return_value = _mk_cache()
        result = runner.invoke(main, ["stats", "--format", "yaml"])
    assert result.exit_code == 0
    assert "cache_stats" in result.output


def test_stats_yaml_format_to_file(tmp_path):
    out = tmp_path / "stats.yaml"
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cls.return_value = _mk_cache()
        result = runner.invoke(
            main, ["stats", "--format", "yaml", "--output", str(out)]
        )
    assert result.exit_code == 0
    assert out.exists()
    assert "cache_stats" in out.read_text()


# ── _display_stats csv format (lines 211-250) ────────────────────────────────


def test_stats_csv_format_stdout():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cls.return_value = _mk_cache()
        result = runner.invoke(main, ["stats", "--format", "csv"])
    assert result.exit_code == 0
    assert "total_hits" in result.output  # header row


def test_stats_csv_format_to_file_new(tmp_path):
    out = tmp_path / "stats.csv"
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cls.return_value = _mk_cache()
        result = runner.invoke(main, ["stats", "--format", "csv", "--output", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    text = out.read_text()
    assert "total_hits" in text  # header written for new file


def test_stats_csv_format_to_existing_file(tmp_path):
    """Appending to existing CSV file skips header."""
    out = tmp_path / "stats.csv"
    out.write_text("existing content\n")
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cls.return_value = _mk_cache()
        result = runner.invoke(main, ["stats", "--format", "csv", "--output", str(out)])
    assert result.exit_code == 0
    assert "appended" in result.output.lower()


# ── list command json format (lines 313, 315) ─────────────────────────────────


def test_list_json_format():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()

        class CM:
            def __init__(self) -> None:
                self._r = AsyncMock()

            async def __aenter__(self):
                return self._r

            async def __aexit__(self, *a: object) -> bool:
                return False

        async def fake_scan(match=None, count=None):
            for k in [b"key1", b"key2"]:
                yield k

        cm = CM()
        cm._r.scan_iter = fake_scan
        cache._get_redis = MagicMock(return_value=cm)
        cache._build_key = MagicMock(side_effect=lambda p: f"ns:{p}")
        cls.return_value = cache
        result = runner.invoke(main, ["list", "--format", "json"])
    assert result.exit_code == 0
    assert '"keys"' in result.output
    assert '"count"' in result.output


# ── flush command: --all paths (lines 386-388, 398-399) ─────────────────────


def test_flush_all_with_confirmation():
    runner = CliRunner()
    with (
        patch("yokedcache.cli.YokedCache") as cls,
        patch("click.confirm", return_value=True),
    ):
        cache = _mk_cache()
        cache.flush_all = AsyncMock(return_value=100)
        cls.return_value = cache
        result = runner.invoke(main, ["flush", "--all"])
    assert result.exit_code == 0
    assert "Flushed all" in result.output


def test_flush_all_aborted():
    runner = CliRunner()
    with (
        patch("yokedcache.cli.YokedCache") as cls,
        patch("click.confirm", return_value=False),
    ):
        cache = _mk_cache()
        cls.return_value = cache
        result = runner.invoke(main, ["flush", "--all"])
    assert result.exit_code == 0
    assert "Aborted" in result.output


def test_flush_key_with_force_found():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.delete = AsyncMock(return_value=True)
        cls.return_value = cache
        result = runner.invoke(main, ["flush", "--key", "mykey", "--force"])
    assert result.exit_code == 0
    assert "Deleted key" in result.output


def test_flush_key_with_force_not_found():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.delete = AsyncMock(return_value=False)
        cls.return_value = cache
        result = runner.invoke(main, ["flush", "--key", "missing", "--force"])
    assert result.exit_code == 0
    assert "not found" in result.output.lower()


def test_flush_exception_path():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.connect = AsyncMock(side_effect=RuntimeError("boom"))
        cls.return_value = cache
        result = runner.invoke(main, ["flush", "--all", "--force"])
    assert result.exit_code == 1
    assert "Error flushing" in result.output


# ── warm exception per item (lines 475-476) ──────────────────────────────────


def test_warm_valid_items(tmp_path):
    import yaml

    cfg = {"warm": {"items": [{"key": "k1", "value": "v1", "ttl": 60}]}}
    p = tmp_path / "warm.yaml"
    p.write_text(yaml.dump(cfg))
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.set = AsyncMock(return_value=True)
        cls.return_value = cache
        result = runner.invoke(main, ["warm", "--config-file", str(p)])
    assert result.exit_code == 0
    assert "Warmed 1 keys" in result.output


# ── ping command (lines 497-506) ─────────────────────────────────────────────


def test_ping_success():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.health_check = AsyncMock(return_value=True)
        cls.return_value = cache
        result = runner.invoke(main, ["ping"])
    assert result.exit_code == 0
    assert "successful" in result.output.lower()


def test_ping_failure():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.health_check = AsyncMock(return_value=False)
        cls.return_value = cache
        result = runner.invoke(main, ["ping"])
    assert result.exit_code == 1
    assert "failed" in result.output.lower()


def test_ping_exception():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.connect = AsyncMock(side_effect=RuntimeError("no conn"))
        cls.return_value = cache
        result = runner.invoke(main, ["ping"])
    assert result.exit_code == 1
    assert "Connection error" in result.output


# ── export_config with output file (lines 537-539) ───────────────────────────


def test_export_config_to_file(tmp_path):
    out = tmp_path / "config.yaml"
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cls.return_value = _mk_cache()
        result = runner.invoke(main, ["export-config", "--output", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    assert "exported" in result.output.lower()


def test_export_config_stdout():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cls.return_value = _mk_cache()
        result = runner.invoke(main, ["export-config"])
    assert result.exit_code == 0
    assert "redis_url" in result.output


def test_export_config_exception():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        # Raise when accessing config attributes
        type(cache.config).redis_url = property(
            fget=lambda self: (_ for _ in ()).throw(RuntimeError("cfg fail"))
        )
        cls.return_value = cache
        result = runner.invoke(main, ["export-config"])
    assert result.exit_code == 1
    assert "Error exporting" in result.output


# ── get command (lines 576, 582-583) ─────────────────────────────────────────


def test_get_value_found():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.get = AsyncMock(return_value="hello world")
        cls.return_value = cache
        result = runner.invoke(main, ["get", "mykey"])
    assert result.exit_code == 0
    assert "hello world" in result.output


def test_get_key_not_found():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.get = AsyncMock(return_value=None)
        cls.return_value = cache
        result = runner.invoke(main, ["get", "missing"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_get_exception():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.connect = AsyncMock(side_effect=RuntimeError("err"))
        cls.return_value = cache
        result = runner.invoke(main, ["get", "k"])
    assert result.exit_code == 1
    assert "Error getting key" in result.output


# ── set command (lines 609, 615-616) ─────────────────────────────────────────


def test_set_success():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.set = AsyncMock(return_value=True)
        cls.return_value = cache
        result = runner.invoke(main, ["set", "mykey", "myvalue"])
    assert result.exit_code == 0
    assert "Set key" in result.output


def test_set_failure():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.set = AsyncMock(return_value=False)
        cls.return_value = cache
        result = runner.invoke(main, ["set", "mykey", "val"])
    assert result.exit_code == 1
    assert "Failed to set" in result.output


def test_set_with_ttl_and_tags():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.set = AsyncMock(return_value=True)
        cls.return_value = cache
        result = runner.invoke(main, ["set", "k", "v", "--ttl", "60", "--tags", "a,b"])
    assert result.exit_code == 0


def test_set_exception():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.connect = AsyncMock(side_effect=RuntimeError("err"))
        cls.return_value = cache
        result = runner.invoke(main, ["set", "k", "v"])
    assert result.exit_code == 1
    assert "Error setting key" in result.output


# ── delete command (lines 637, 643-644) ──────────────────────────────────────


def test_delete_success():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.delete = AsyncMock(return_value=True)
        cls.return_value = cache
        result = runner.invoke(main, ["delete", "mykey"])
    assert result.exit_code == 0
    assert "Deleted key" in result.output


def test_delete_not_found():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.delete = AsyncMock(return_value=False)
        cls.return_value = cache
        result = runner.invoke(main, ["delete", "missing"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_delete_exception():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.connect = AsyncMock(side_effect=RuntimeError("err"))
        cls.return_value = cache
        result = runner.invoke(main, ["delete", "k"])
    assert result.exit_code == 1
    assert "Error deleting key" in result.output


# ── invalidate exception (lines 678-680) ────────────────────────────────────


def test_invalidate_exception():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.connect = AsyncMock(side_effect=RuntimeError("fail"))
        cls.return_value = cache
        result = runner.invoke(main, ["invalidate", "--pattern", "x:*"])
    assert result.exit_code == 1
    assert "Error invalidating" in result.output


# ── health command (lines 700, 706-707) ──────────────────────────────────────


def test_health_healthy():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.health_check = AsyncMock(return_value=True)
        cls.return_value = cache
        result = runner.invoke(main, ["health"])
    assert result.exit_code == 0
    assert "healthy" in result.output.lower()


def test_health_unhealthy():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.health_check = AsyncMock(return_value=False)
        cls.return_value = cache
        result = runner.invoke(main, ["health"])
    assert result.exit_code == 1
    assert "not healthy" in result.output.lower()


def test_health_exception():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.connect = AsyncMock(side_effect=RuntimeError("err"))
        cls.return_value = cache
        result = runner.invoke(main, ["health"])
    assert result.exit_code == 1
    assert "Error checking health" in result.output


# ── search command (lines 745, 766-781) ──────────────────────────────────────


def _mk_search_result(key="k1", score=90, matched_term="q"):
    r = MagicMock()
    r.key = key
    r.score = score
    r.matched_term = matched_term
    r.value = "some_value"
    return r


def test_search_json_format_with_results():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.fuzzy_search = AsyncMock(
            return_value=[_mk_search_result("user:alice", 95, "alice")]
        )
        cls.return_value = cache
        result = runner.invoke(main, ["search", "alice", "--format", "json"])
    assert result.exit_code == 0
    assert '"query"' in result.output
    assert "user:alice" in result.output


def test_search_json_format_no_results():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.fuzzy_search = AsyncMock(return_value=[])
        cls.return_value = cache
        result = runner.invoke(main, ["search", "xyz", "--format", "json"])
    assert result.exit_code == 0
    assert '"count": 0' in result.output


def test_search_human_format_with_results():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.fuzzy_search = AsyncMock(
            return_value=[_mk_search_result("user:bob", 88, "bob")]
        )
        cls.return_value = cache
        result = runner.invoke(main, ["search", "bob"])
    assert result.exit_code == 0
    assert "user:bob" in result.output
    assert "Score: 88%" in result.output


def test_search_human_format_no_results():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.fuzzy_search = AsyncMock(return_value=[])
        cls.return_value = cache
        result = runner.invoke(main, ["search", "nothing"])
    assert result.exit_code == 0
    assert "No matches found" in result.output


def test_search_human_verbose_shows_value():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.fuzzy_search = AsyncMock(return_value=[_mk_search_result("k1", 91, "q")])
        cls.return_value = cache
        result = runner.invoke(main, ["--verbose", "search", "q"])
    assert result.exit_code == 0
    assert "some_value" in result.output


def test_search_exception():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as cls:
        cache = _mk_cache()
        cache.connect = AsyncMock(side_effect=RuntimeError("err"))
        cls.return_value = cache
        result = runner.invoke(main, ["search", "q"])
    assert result.exit_code == 1
    assert "Error performing search" in result.output
