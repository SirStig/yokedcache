"""Additional CLI tests to raise coverage for edge cases and branches."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from yokedcache.cli import main, reset_cache_instance


@pytest.fixture(autouse=True)
def reset_cache():
    reset_cache_instance()
    yield
    reset_cache_instance()


def _setup_mock_cache():
    mock_cache = AsyncMock()
    mock_cache.connect.return_value = None
    mock_cache.disconnect.return_value = None
    return mock_cache


def test_cli_list_json_output():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as mock_cls:
        cache = _setup_mock_cache()
        # Simulate keys
        fake_r = AsyncMock()
        fake_r.keys = AsyncMock(return_value=[b"prefix:key1", b"prefix:key2"])
        cache._get_redis = MagicMock()

        class CM2:
            async def __aenter__(self):
                return fake_r

            async def __aexit__(self, exc_type, exc, tb):
                return False

        cache._get_redis.return_value = CM2()
        cache._build_key = MagicMock(side_effect=lambda k: f"prefix:{k}")
        mock_cls.return_value = cache
        result = runner.invoke(main, ["list", "--format", "json", "--limit", "1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 1


def test_cli_list_error(monkeypatch):
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as mock_cls:
        cache = _setup_mock_cache()
        # Force error in keys retrieval

        class CM:  # noqa: D401 - simple context manager for test
            async def __aenter__(self):
                raise RuntimeError("boom")

            async def __aexit__(self, exc_type, exc, tb):
                return False

        cache._get_redis.return_value = CM()
        mock_cls.return_value = cache
        result = runner.invoke(main, ["list"])
        assert result.exit_code != 0


def test_cli_export_config_stdout():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as mock_cls:
        cache = _setup_mock_cache()
        cache.config.redis_url = "redis://x"
        cache.config.default_ttl = 123
        cache.config.key_prefix = "p"
        cache.config.enable_fuzzy = True
        cache.config.fuzzy_threshold = 80
        cache.config.max_connections = 5
        cache.config.log_level = "INFO"
        cache.config.table_configs = {}
        mock_cls.return_value = cache
        result = runner.invoke(main, ["export-config"])
        assert result.exit_code == 0
        assert "redis://x" in result.output


def test_cli_export_config_file(tmp_path):
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as mock_cls:
        cache = _setup_mock_cache()
        cache.config.redis_url = "redis://x"
        cache.config.default_ttl = 123
        cache.config.key_prefix = "p"
        cache.config.enable_fuzzy = True
        cache.config.fuzzy_threshold = 80
        cache.config.max_connections = 5
        cache.config.log_level = "INFO"
        cache.config.table_configs = {}
        mock_cls.return_value = cache
        out_file = tmp_path / "conf.yaml"
        result = runner.invoke(main, ["export-config", "--output", str(out_file)])
        assert result.exit_code == 0
        assert out_file.read_text() != ""


def test_cli_get_not_found():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as mock_cls:
        cache = _setup_mock_cache()
        cache.get.return_value = None
        mock_cls.return_value = cache
        result = runner.invoke(main, ["get", "missing"])
        assert result.exit_code != 0


def test_cli_set_failure():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as mock_cls:
        cache = _setup_mock_cache()
        cache.set.return_value = False
        mock_cls.return_value = cache
        result = runner.invoke(main, ["set", "k", "v"])
        assert result.exit_code != 0


def test_cli_delete_not_found():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as mock_cls:
        cache = _setup_mock_cache()
        cache.delete.return_value = False
        mock_cls.return_value = cache
        result = runner.invoke(main, ["delete", "k"])
        assert result.exit_code != 0


def test_cli_flush_requires_selector():
    runner = CliRunner()
    result = runner.invoke(main, ["flush"])
    assert result.exit_code != 0


def test_cli_flush_pattern():
    runner = CliRunner()
    with (
        patch("yokedcache.cli.YokedCache") as mock_cls,
        patch("click.confirm", return_value=True),
    ):
        cache = _setup_mock_cache()
        cache.invalidate_pattern.return_value = 2
        mock_cls.return_value = cache
        result = runner.invoke(main, ["flush", "--pattern", "u:*"])
        assert result.exit_code == 0


def test_cli_flush_tags():
    runner = CliRunner()
    with (
        patch("yokedcache.cli.YokedCache") as mock_cls,
        patch("click.confirm", return_value=True),
    ):
        cache = _setup_mock_cache()
        cache.invalidate_tags.return_value = 1
        mock_cls.return_value = cache
        result = runner.invoke(main, ["flush", "--tags", "users"])
        assert result.exit_code == 0


def test_cli_flush_key():
    runner = CliRunner()
    with (
        patch("yokedcache.cli.YokedCache") as mock_cls,
        patch("click.confirm", return_value=True),
    ):
        cache = _setup_mock_cache()
        cache.delete.return_value = True
        mock_cls.return_value = cache
        result = runner.invoke(main, ["flush", "--key", "a"])
        assert result.exit_code == 0


def test_cli_warm_requires_config():
    runner = CliRunner()
    result = runner.invoke(main, ["warm"])
    assert result.exit_code != 0


def test_cli_warm_executes_items(tmp_path):
    runner = CliRunner()
    cfg = {
        "warm": {
            "items": [
                {"key": "a", "value": "1", "ttl": 10, "tags": ["x"]},
                {"key": "b", "value": "2"},
            ]
        }
    }
    cfg_path = tmp_path / "warm.yaml"
    import yaml

    cfg_path.write_text(yaml.dump(cfg))
    with patch("yokedcache.cli.YokedCache") as mock_cls:
        cache = _setup_mock_cache()
        cache.set.return_value = True
        mock_cls.return_value = cache
        result = runner.invoke(main, ["warm", "--config-file", str(cfg_path)])
        assert result.exit_code == 0
        assert cache.set.await_count >= 2


def test_cli_ping_failure():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as mock_cls:
        cache = _setup_mock_cache()
        cache.connect.side_effect = RuntimeError("fail")
        mock_cls.return_value = cache
        result = runner.invoke(main, ["ping"])
        assert result.exit_code != 0


def test_cli_search_json_format():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as mock_cls:
        cache = _setup_mock_cache()
        cache.fuzzy_search.return_value = []
        mock_cls.return_value = cache
        result = runner.invoke(main, ["search", "q", "--format", "json"])
        assert result.exit_code == 0


def test_cli_invalidate_requires_arg():
    runner = CliRunner()
    result = runner.invoke(main, ["invalidate"])
    assert result.exit_code != 0


def test_cli_invalidate_pattern():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as mock_cls:
        cache = _setup_mock_cache()
        cache.invalidate_pattern.return_value = 1
        mock_cls.return_value = cache
        result = runner.invoke(main, ["invalidate", "--pattern", "k:*"])
        assert result.exit_code == 0


def test_cli_invalidate_tags():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as mock_cls:
        cache = _setup_mock_cache()
        cache.invalidate_tags.return_value = 2
        mock_cls.return_value = cache
        result = runner.invoke(main, ["invalidate", "--tags", "a,b"])
        assert result.exit_code == 0


def test_cli_health_unhealthy():
    runner = CliRunner()
    with patch("yokedcache.cli.YokedCache") as mock_cls:
        cache = _setup_mock_cache()
        cache.health_check.return_value = False
        mock_cls.return_value = cache
        result = runner.invoke(main, ["health"])
        assert result.exit_code != 0
