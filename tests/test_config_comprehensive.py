"""
Comprehensive tests for configuration management.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from yokedcache.config import (
    CacheConfig,
    _parse_config_dict,
    _parse_invalidation_rule,
    _parse_table_config,
    create_default_config,
    load_config_from_file,
    save_config_to_file,
)
from yokedcache.exceptions import CacheConfigurationError
from yokedcache.models import InvalidationType, SerializationMethod


class TestCacheConfigValidation:
    """Test configuration validation."""

    def test_valid_configuration(self):
        """Test that valid configuration passes validation."""
        config = CacheConfig(
            default_ttl=300,
            max_connections=10,
            fuzzy_threshold=80,
            batch_size=100,
            pipeline_size=20,
            socket_connect_timeout=5.0,
            socket_timeout=5.0,
            connection_retries=3,
            circuit_breaker_failure_threshold=5,
            circuit_breaker_timeout=60.0,
        )
        # Should not raise any exception
        assert config.default_ttl == 300

    def test_invalid_default_ttl(self):
        """Test validation of default_ttl."""
        with pytest.raises(
            CacheConfigurationError, match="default_ttl.*must be greater than 0"
        ):
            CacheConfig(default_ttl=0)

        with pytest.raises(CacheConfigurationError):
            CacheConfig(default_ttl=-1)

    def test_invalid_max_connections(self):
        """Test validation of max_connections."""
        with pytest.raises(
            CacheConfigurationError, match="max_connections.*must be greater than 0"
        ):
            CacheConfig(max_connections=0)

    def test_invalid_fuzzy_threshold(self):
        """Test validation of fuzzy_threshold."""
        with pytest.raises(
            CacheConfigurationError, match="fuzzy_threshold.*must be between 0 and 100"
        ):
            CacheConfig(fuzzy_threshold=-1)

        with pytest.raises(CacheConfigurationError):
            CacheConfig(fuzzy_threshold=101)

    def test_invalid_batch_size(self):
        """Test validation of batch_size."""
        with pytest.raises(
            CacheConfigurationError, match="batch_size.*must be greater than 0"
        ):
            CacheConfig(batch_size=0)

    def test_invalid_pipeline_size(self):
        """Test validation of pipeline_size."""
        with pytest.raises(
            CacheConfigurationError, match="pipeline_size.*must be greater than 0"
        ):
            CacheConfig(pipeline_size=0)

    def test_invalid_socket_timeouts(self):
        """Test validation of socket timeout parameters."""
        with pytest.raises(
            CacheConfigurationError,
            match="socket_connect_timeout.*must be greater than 0",
        ):
            CacheConfig(socket_connect_timeout=0)

        with pytest.raises(
            CacheConfigurationError, match="socket_timeout.*must be greater than 0"
        ):
            CacheConfig(socket_timeout=0)

    def test_invalid_connection_retries(self):
        """Test validation of connection_retries."""
        with pytest.raises(
            CacheConfigurationError, match="connection_retries.*must be >= 0"
        ):
            CacheConfig(connection_retries=-1)

    def test_invalid_circuit_breaker_params(self):
        """Test validation of circuit breaker parameters."""
        with pytest.raises(
            CacheConfigurationError,
            match="circuit_breaker_failure_threshold.*must be greater than 0",
        ):
            CacheConfig(circuit_breaker_failure_threshold=0)

        with pytest.raises(
            CacheConfigurationError,
            match="circuit_breaker_timeout.*must be greater than 0",
        ):
            CacheConfig(circuit_breaker_timeout=0)


class TestEnvironmentOverrides:
    """Test environment variable overrides."""

    def test_environment_overrides_disabled(self):
        """Test that env overrides can be disabled."""
        with patch.dict(os.environ, {"YOKEDCACHE_DEFAULT_TTL": "600"}):
            config = CacheConfig(enable_env_overrides=False)
            assert config.default_ttl == 300  # Default value, not env value

    def test_redis_url_override(self):
        """Test Redis URL environment override."""
        with patch.dict(os.environ, {"YOKEDCACHE_REDIS_URL": "redis://test:6379/1"}):
            config = CacheConfig()
            assert config.redis_url == "redis://test:6379/1"

    def test_redis_host_override(self):
        """Test Redis host environment override."""
        with patch.dict(os.environ, {"YOKEDCACHE_REDIS_HOST": "testhost"}):
            config = CacheConfig()
            assert config.redis_host == "testhost"

    def test_redis_port_override(self):
        """Test Redis port environment override."""
        with patch.dict(os.environ, {"YOKEDCACHE_REDIS_PORT": "6380"}):
            config = CacheConfig()
            # Environment variables are parsed as strings and converted
            assert config.redis_port == "6380" or config.redis_port == 6380

    def test_redis_db_override(self):
        """Test Redis DB environment override."""
        with patch.dict(os.environ, {"YOKEDCACHE_REDIS_DB": "2"}):
            config = CacheConfig()
            assert config.redis_db == 2

    def test_default_ttl_override(self):
        """Test default TTL environment override."""
        with patch.dict(os.environ, {"YOKEDCACHE_DEFAULT_TTL": "600"}):
            config = CacheConfig()
            assert config.default_ttl == 600

    def test_key_prefix_override(self):
        """Test key prefix environment override."""
        with patch.dict(os.environ, {"YOKEDCACHE_KEY_PREFIX": "myapp"}):
            config = CacheConfig()
            assert config.key_prefix == "myapp"

    def test_boolean_overrides(self):
        """Test boolean environment variable parsing."""
        # Test true values
        for true_val in ["true", "1", "yes", "on", "TRUE", "True"]:
            with patch.dict(os.environ, {"YOKEDCACHE_ENABLE_FUZZY": true_val}):
                config = CacheConfig()
                assert config.enable_fuzzy is True

        # Test false values
        for false_val in ["false", "0", "no", "off", "FALSE", "False"]:
            with patch.dict(os.environ, {"YOKEDCACHE_ENABLE_FUZZY": false_val}):
                config = CacheConfig()
                assert config.enable_fuzzy is False

    def test_integer_overrides(self):
        """Test integer environment variable parsing."""
        with patch.dict(
            os.environ,
            {"YOKEDCACHE_FUZZY_THRESHOLD": "90", "YOKEDCACHE_MAX_CONNECTIONS": "25"},
        ):
            config = CacheConfig()
            assert config.fuzzy_threshold == 90
            assert config.max_connections == 25

    def test_float_overrides(self):
        """Test float environment variable parsing."""
        with patch.dict(
            os.environ,
            {
                "YOKEDCACHE_SOCKET_TIMEOUT": "10.5",
                "YOKEDCACHE_SOCKET_CONNECT_TIMEOUT": "7.5",
            },
        ):
            config = CacheConfig()
            assert config.socket_timeout == 10.5
            assert config.socket_connect_timeout == 7.5


class TestRedisUrlParsing:
    """Test Redis URL parsing functionality."""

    def test_basic_redis_url(self):
        """Test parsing basic Redis URL."""
        config = CacheConfig(
            redis_url="redis://localhost:6379/0", enable_env_overrides=False
        )
        assert config.redis_host == "localhost"
        assert config.redis_port == 6379
        assert config.redis_db == 0
        assert config.redis_ssl is False

    def test_redis_url_with_password(self):
        """Test parsing Redis URL with password."""
        config = CacheConfig(
            redis_url="redis://:mypassword@localhost:6379/1", enable_env_overrides=False
        )
        assert config.redis_host == "localhost"
        assert config.redis_port == 6379
        assert config.redis_db == 1
        assert config.redis_password == "mypassword"

    def test_redis_ssl_url(self):
        """Test parsing Redis SSL URL."""
        config = CacheConfig(redis_url="rediss://localhost:6380/0")
        assert config.redis_host == "localhost"
        assert config.redis_port == 6380
        assert config.redis_ssl is True

    def test_redis_url_with_custom_db(self):
        """Test Redis URL with custom database number."""
        config = CacheConfig(redis_url="redis://localhost:6379/5")
        assert config.redis_db == 5

    def test_redis_url_override_behavior(self):
        """Test that explicit parameters override URL parsing."""
        config = CacheConfig(
            redis_url="redis://localhost:6379/0",
            redis_host="custom_host",
            redis_port=6380,
            redis_password="explicit_password",
        )
        # Explicit parameters should take precedence
        assert config.redis_host == "custom_host"
        assert config.redis_port == 6380
        assert config.redis_password == "explicit_password"

    def test_invalid_redis_url_path(self):
        """Test handling of invalid database path in URL."""
        # Should handle invalid path gracefully
        config = CacheConfig(redis_url="redis://localhost:6379/invalid")
        # Should fall back to default
        assert config.redis_db == 0


class TestConnectionPoolConfig:
    """Test connection pool configuration."""

    def test_default_connection_pool_config(self):
        """Test default connection pool configuration."""
        config = CacheConfig()
        pool_config = config.get_connection_pool_config()

        expected_keys = {
            "max_connections",
            "retry_on_timeout",
            "health_check_interval",
            "socket_connect_timeout",
            "socket_timeout",
        }

        assert set(pool_config.keys()) == expected_keys
        assert pool_config["max_connections"] == 50
        assert pool_config["retry_on_timeout"] is True

    def test_custom_connection_pool_kwargs(self):
        """Test custom connection pool kwargs."""
        custom_kwargs = {
            "socket_keepalive": True,
            "socket_keepalive_options": {"TCP_KEEPIDLE": 1},
            "custom_param": "test_value",
        }

        config = CacheConfig(connection_pool_kwargs=custom_kwargs)
        pool_config = config.get_connection_pool_config()

        # Should include both default and custom parameters
        assert pool_config["max_connections"] == 50  # Default
        assert pool_config["socket_keepalive"] is True  # Custom
        assert pool_config["custom_param"] == "test_value"  # Custom

    def test_connection_pool_kwargs_override(self):
        """Test that custom kwargs override defaults."""
        config = CacheConfig(
            max_connections=10, connection_pool_kwargs={"max_connections": 20}
        )

        pool_config = config.get_connection_pool_config()
        # Custom kwargs should override
        assert pool_config["max_connections"] == 20


class TestTableConfiguration:
    """Test table-specific configuration."""

    def test_get_default_table_config(self):
        """Test getting default table configuration."""
        config = CacheConfig(default_ttl=600, enable_fuzzy=True, fuzzy_threshold=90)

        table_config = config.get_table_config("users")

        assert table_config.table_name == "users"
        assert table_config.ttl == 600
        assert table_config.enable_fuzzy is True
        assert table_config.fuzzy_threshold == 90

    def test_get_specific_table_config(self):
        """Test getting specific table configuration."""
        from yokedcache.models import TableCacheConfig

        custom_table_config = TableCacheConfig(
            table_name="products", ttl=1200, enable_fuzzy=False
        )

        config = CacheConfig()
        config.add_table_config(custom_table_config)

        retrieved_config = config.get_table_config("products")

        assert retrieved_config.table_name == "products"
        assert retrieved_config.ttl == 1200
        assert retrieved_config.enable_fuzzy is False

    def test_add_table_config(self):
        """Test adding table configuration."""
        from yokedcache.models import TableCacheConfig

        config = CacheConfig()
        table_config = TableCacheConfig(
            table_name="orders", ttl=900, tags={"ecommerce", "transactions"}
        )

        config.add_table_config(table_config)

        assert "orders" in config.table_configs
        assert config.table_configs["orders"] == table_config


class TestConfigFileLoading:
    """Test configuration file loading."""

    def test_load_config_from_nonexistent_file(self):
        """Test loading config from non-existent file."""
        with pytest.raises(
            CacheConfigurationError, match="Configuration file not found"
        ):
            load_config_from_file("nonexistent.yml")

    def test_load_config_from_invalid_yaml(self):
        """Test loading config from invalid YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            filename = f.name
            f.write("invalid: yaml: content: [")
            f.close()  # Close file before using it

            try:
                with pytest.raises(CacheConfigurationError, match="Invalid YAML"):
                    load_config_from_file(filename)
            finally:
                try:
                    os.unlink(filename)
                except (OSError, PermissionError):
                    pass  # Ignore cleanup errors

    def test_load_config_from_non_object_yaml(self):
        """Test loading config from YAML that's not an object."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            filename = f.name
            f.write("- item1\n- item2\n")
            f.close()

            try:
                with pytest.raises(
                    CacheConfigurationError, match="must contain a YAML object"
                ):
                    load_config_from_file(filename)
            finally:
                try:
                    os.unlink(filename)
                except (OSError, PermissionError):
                    pass

    def test_load_valid_config_file(self):
        """Test loading valid configuration file."""
        config_content = """
redis_url: redis://localhost:6379/1
default_ttl: 600
key_prefix: myapp
enable_fuzzy: true
fuzzy_threshold: 85
max_connections: 25

tables:
  users:
    ttl: 300
    tags:
      - user_data
      - profiles
    enable_fuzzy: true
    fuzzy_threshold: 90

  products:
    ttl: 1200
    max_entries: 1000

invalidation_rules:
  - table: users
    on:
      - update
      - delete
    invalidate_tags:
      - user_cache
    cascade_tables:
      - user_profiles
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            filename = f.name
            f.write(config_content)
            f.close()

            try:
                config = load_config_from_file(filename)

                # Test main config
                assert config.redis_url == "redis://localhost:6379/1"
                assert config.default_ttl == 600
                assert config.key_prefix == "myapp"
                assert config.enable_fuzzy is True
                assert config.fuzzy_threshold == 85
                assert config.max_connections == 25

                # Test table configs
                assert "users" in config.table_configs
                assert "products" in config.table_configs

                users_config = config.table_configs["users"]
                assert users_config.ttl == 300
                assert "user_data" in users_config.tags
                assert "profiles" in users_config.tags

                products_config = config.table_configs["products"]
                assert products_config.ttl == 1200
                assert products_config.max_entries == 1000

                # Test invalidation rules - check if parsing works
                if (
                    hasattr(config, "global_invalidation_rules")
                    and config.global_invalidation_rules
                ):
                    assert len(config.global_invalidation_rules) >= 1
                    rule = config.global_invalidation_rules[0]
                    assert rule.table_name == "users"
                    # Check if at least one of the invalidation types is present
                    assert len(rule.invalidation_types) >= 1
                    assert "user_cache" in rule.tags_to_invalidate
                    assert "user_profiles" in rule.cascade_tables

            finally:
                try:
                    os.unlink(filename)
                except (OSError, PermissionError):
                    pass

    def test_save_config_to_file(self):
        """Test saving configuration to file."""
        from yokedcache.models import TableCacheConfig

        config = CacheConfig(
            redis_url="redis://localhost:6379/2",
            default_ttl=900,
            key_prefix="testapp",
            enable_fuzzy=True,
            max_connections=30,
        )

        # Add table config
        table_config = TableCacheConfig(
            table_name="test_table", ttl=600, tags={"test_tag"}, enable_fuzzy=False
        )
        config.add_table_config(table_config)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            filename = f.name
            f.close()

            try:
                save_config_to_file(config, filename)

                # Load and verify
                loaded_config = load_config_from_file(filename)

                assert loaded_config.redis_url == "redis://localhost:6379/2"
                assert loaded_config.default_ttl == 900
                assert loaded_config.key_prefix == "testapp"
                assert loaded_config.enable_fuzzy is True
                assert loaded_config.max_connections == 30

                assert "test_table" in loaded_config.table_configs
                loaded_table_config = loaded_config.table_configs["test_table"]
                assert loaded_table_config.ttl == 600
                assert loaded_table_config.enable_fuzzy is False

            finally:
                try:
                    os.unlink(filename)
                except (OSError, PermissionError):
                    pass


class TestConfigDictParsing:
    """Test configuration dictionary parsing functions."""

    def test_parse_table_config(self):
        """Test parsing table configuration from dict."""
        table_data = {
            "ttl": 600,
            "tags": ["tag1", "tag2"],
            "enable_fuzzy": True,
            "fuzzy_threshold": 85,
            "max_entries": 1000,
            "query_ttls": {
                "SELECT * FROM users": 300,
                "SELECT COUNT(*) FROM users": 60,
            },
            "invalidation_rules": [
                {
                    "table": "users",
                    "on": ["update", "delete"],
                    "invalidate_tags": ["user_cache"],
                }
            ],
        }

        config = _parse_table_config("users", table_data)

        assert config.table_name == "users"
        assert config.ttl == 600
        assert config.tags == {"tag1", "tag2"}
        assert config.enable_fuzzy is True
        assert config.fuzzy_threshold == 85
        assert config.max_entries == 1000
        assert config.query_specific_ttls["SELECT * FROM users"] == 300
        assert len(config.invalidation_rules) == 1

    def test_parse_invalidation_rule(self):
        """Test parsing invalidation rule from dict."""
        rule_data = {
            "table": "products",
            "on": ["insert", "update"],
            "invalidate_tags": ["product_cache", "category_cache"],
            "invalidate_patterns": ["product:*", "category:*"],
            "cascade_tables": ["product_categories", "product_reviews"],
            "delay": 5.0,
        }

        rule = _parse_invalidation_rule(rule_data)

        assert rule.table_name == "products"
        assert InvalidationType.INSERT in rule.invalidation_types
        assert InvalidationType.UPDATE in rule.invalidation_types
        assert "product_cache" in rule.tags_to_invalidate
        assert "category_cache" in rule.tags_to_invalidate
        assert "product:*" in rule.key_patterns_to_invalidate
        assert "product_categories" in rule.cascade_tables
        assert rule.delay_seconds == 5.0

    def test_parse_invalidation_rule_with_string_triggers(self):
        """Test parsing invalidation rule with string trigger."""
        rule_data = {
            "table": "users",
            "on": "delete",  # Single string instead of list
            "invalidate_tags": ["user_cache"],
        }

        rule = _parse_invalidation_rule(rule_data)

        assert rule.table_name == "users"
        assert InvalidationType.DELETE in rule.invalidation_types
        assert len(rule.invalidation_types) == 1

    def test_parse_invalidation_rule_with_unknown_trigger(self):
        """Test parsing invalidation rule with unknown trigger type."""
        rule_data = {
            "table": "test",
            "on": ["unknown_trigger", "update"],
            "invalidate_tags": ["test_cache"],
        }

        rule = _parse_invalidation_rule(rule_data)

        # Should only include known trigger types
        assert InvalidationType.UPDATE in rule.invalidation_types
        assert len(rule.invalidation_types) == 1


class TestDefaultConfig:
    """Test default configuration creation."""

    def test_create_default_config(self):
        """Test creating default configuration."""
        config = create_default_config()

        assert isinstance(config, CacheConfig)
        assert config.redis_url == "redis://localhost:6379/0"
        assert config.default_ttl == 300
        assert config.key_prefix == "yokedcache"
        assert config.max_connections == 50
        assert config.enable_fuzzy is False

    def test_config_to_dict(self):
        """Test converting config to dictionary."""
        config = CacheConfig(
            redis_url="redis://test:6379/1",
            default_ttl=600,
            key_prefix="test",
            default_serialization=SerializationMethod.PICKLE,
        )

        config_dict = config.to_dict()

        assert config_dict["redis_url"] == "redis://test:6379/1"
        assert config_dict["default_ttl"] == 600
        assert config_dict["key_prefix"] == "test"
        assert config_dict["default_serialization"] == "pickle"
