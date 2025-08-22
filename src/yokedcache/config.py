"""
Configuration management for YokedCache.

This module handles loading and managing configuration from files,
environment variables, and programmatic settings.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from urllib.parse import urlparse

import yaml

from .exceptions import CacheConfigurationError
from .models import (
    InvalidationRule,
    InvalidationType,
    SerializationMethod,
    TableCacheConfig,
)


@dataclass
class CacheConfig:
    """Main configuration class for YokedCache."""

    # Redis connection settings
    redis_url: str = "redis://localhost:6379/0"
    redis_host: Optional[str] = None
    redis_port: Optional[int] = None
    redis_db: int = 0
    redis_password: Optional[str] = None
    redis_ssl: bool = False
    redis_ssl_cert_reqs: Optional[str] = None
    redis_ssl_ca_certs: Optional[str] = None
    redis_ssl_certfile: Optional[str] = None
    redis_ssl_keyfile: Optional[str] = None

    # Connection pool settings
    max_connections: int = 50
    retry_on_timeout: bool = True
    health_check_interval: int = 30
    socket_connect_timeout: float = 5.0
    socket_timeout: float = 5.0

    # Cache behavior settings
    default_ttl: int = 300  # 5 minutes
    key_prefix: str = "yokedcache"
    enable_compression: bool = False
    compression_threshold: int = 1024  # bytes
    default_serialization: SerializationMethod = SerializationMethod.JSON

    # Fuzzy search settings
    enable_fuzzy: bool = False
    fuzzy_threshold: int = 80
    fuzzy_max_results: int = 10
    fuzzy_backend: str = "fuzzywuzzy"  # or "redis_search"

    # Performance settings
    batch_size: int = 100
    pipeline_size: int = 20
    enable_metrics: bool = True
    metrics_interval: int = 60  # seconds

    # Logging settings
    log_level: str = "INFO"
    log_cache_hits: bool = False
    log_cache_misses: bool = False
    log_invalidations: bool = True

    # Table-specific configurations
    table_configs: Dict[str, TableCacheConfig] = field(default_factory=dict)

    # Global invalidation rules
    global_invalidation_rules: List[InvalidationRule] = field(default_factory=list)

    # Environment overrides
    enable_env_overrides: bool = True

    def __post_init__(self) -> None:
        """Post-initialization processing."""
        self._apply_env_overrides()
        self._validate_config()
        self._parse_redis_url()

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides."""
        if not self.enable_env_overrides:
            return

        env_mappings = {
            "YOKEDCACHE_REDIS_URL": "redis_url",
            "YOKEDCACHE_REDIS_HOST": "redis_host",
            "YOKEDCACHE_REDIS_PORT": "redis_port",
            "YOKEDCACHE_REDIS_DB": "redis_db",
            "YOKEDCACHE_REDIS_PASSWORD": "redis_password",
            "YOKEDCACHE_DEFAULT_TTL": "default_ttl",
            "YOKEDCACHE_KEY_PREFIX": "key_prefix",
            "YOKEDCACHE_ENABLE_FUZZY": "enable_fuzzy",
            "YOKEDCACHE_FUZZY_THRESHOLD": "fuzzy_threshold",
            "YOKEDCACHE_LOG_LEVEL": "log_level",
            "YOKEDCACHE_MAX_CONNECTIONS": "max_connections",
        }

        for env_var, attr_name in env_mappings.items():
            env_str = os.getenv(env_var)
            if env_str is not None:
                # Type conversion based on current attribute type
                current_value = getattr(self, attr_name)
                if isinstance(current_value, bool):
                    converted_value = env_str.lower() in ("true", "1", "yes", "on")
                elif isinstance(current_value, int):
                    converted_value = int(env_str)
                elif isinstance(current_value, float):
                    converted_value = float(env_str)
                else:
                    converted_value = env_str

                setattr(self, attr_name, converted_value)

    def _validate_config(self) -> None:
        """Validate configuration values."""
        if self.default_ttl <= 0:
            raise CacheConfigurationError("default_ttl", "must be greater than 0")

        if self.max_connections <= 0:
            raise CacheConfigurationError("max_connections", "must be greater than 0")

        if not (0 <= self.fuzzy_threshold <= 100):
            raise CacheConfigurationError(
                "fuzzy_threshold", "must be between 0 and 100"
            )

        if self.batch_size <= 0:
            raise CacheConfigurationError("batch_size", "must be greater than 0")

        if self.pipeline_size <= 0:
            raise CacheConfigurationError("pipeline_size", "must be greater than 0")

    def _parse_redis_url(self) -> None:
        """Parse Redis URL to extract connection components."""
        if self.redis_url:
            parsed = urlparse(self.redis_url)

            # Only override if not explicitly set
            if self.redis_host is None and parsed.hostname:
                self.redis_host = parsed.hostname

            if self.redis_port is None and parsed.port:
                self.redis_port = parsed.port

            if parsed.password and not self.redis_password:
                self.redis_password = parsed.password

            # Extract database number from path
            if parsed.path and parsed.path != "/":
                try:
                    db_num = int(parsed.path.lstrip("/"))
                    if self.redis_db == 0:  # Only override default
                        self.redis_db = db_num
                except ValueError:
                    pass

            # Check for SSL
            if parsed.scheme == "rediss":
                self.redis_ssl = True

    def get_table_config(self, table_name: str) -> TableCacheConfig:
        """Get configuration for a specific table, with fallbacks."""
        if table_name in self.table_configs:
            return self.table_configs[table_name]

        # Return default configuration
        return TableCacheConfig(
            table_name=table_name,
            ttl=self.default_ttl,
            enable_fuzzy=self.enable_fuzzy,
            fuzzy_threshold=self.fuzzy_threshold,
            serialization_method=self.default_serialization,
        )

    def add_table_config(self, config: TableCacheConfig) -> None:
        """Add or update table-specific configuration."""
        self.table_configs[config.table_name] = config

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        # This could be used for serialization or debugging
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, (str, int, float, bool)):
                result[key] = value
            elif isinstance(value, SerializationMethod):
                result[key] = value.value
            # Add more type handling as needed
        return result


def load_config_from_file(file_path: Union[str, Path]) -> CacheConfig:
    """Load configuration from a YAML file."""
    file_path = Path(file_path)

    if not file_path.exists():
        raise CacheConfigurationError(
            "config_file", f"Configuration file not found: {file_path}"
        )

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise CacheConfigurationError(
            "config_file", f"Invalid YAML in configuration file: {e}"
        )
    except Exception as e:
        raise CacheConfigurationError(
            "config_file", f"Error reading configuration file: {e}"
        )

    if not isinstance(data, dict):
        raise CacheConfigurationError(
            "config_file", "Configuration file must contain a YAML object"
        )

    return _parse_config_dict(data)


def _parse_config_dict(data: Dict[str, Any]) -> CacheConfig:
    """Parse configuration dictionary into CacheConfig object."""
    # Extract main config values
    main_config = {}
    table_configs = {}
    global_rules = []

    # Map YAML keys to CacheConfig attributes
    key_mapping = {
        "redis_url": "redis_url",
        "redis": "redis_url",  # Alternative key
        "default_ttl": "default_ttl",
        "ttl": "default_ttl",  # Alternative key
        "key_prefix": "key_prefix",
        "prefix": "key_prefix",  # Alternative key
        "enable_fuzzy": "enable_fuzzy",
        "fuzzy_threshold": "fuzzy_threshold",
        "max_connections": "max_connections",
        "log_level": "log_level",
        "enable_compression": "enable_compression",
        "batch_size": "batch_size",
    }

    for yaml_key, config_key in key_mapping.items():
        if yaml_key in data:
            main_config[config_key] = data[yaml_key]

    # Parse table-specific configurations
    if "tables" in data:
        for table_name, table_data in data["tables"].items():
            table_config = _parse_table_config(table_name, table_data)
            table_configs[table_name] = table_config

    # Parse global invalidation rules
    if "invalidation_rules" in data:
        for rule_data in data["invalidation_rules"]:
            rule = _parse_invalidation_rule(rule_data)
            global_rules.append(rule)

    # Create CacheConfig instance
    config = CacheConfig(
        **main_config,
        table_configs=table_configs,
        global_invalidation_rules=global_rules,
    )

    return config


def _parse_table_config(table_name: str, data: Dict[str, Any]) -> TableCacheConfig:
    """Parse table-specific configuration."""
    config_data = {
        "table_name": table_name,
        "ttl": data.get("ttl", 300),
        "enable_fuzzy": data.get("enable_fuzzy", False),
        "fuzzy_threshold": data.get("fuzzy_threshold", 80),
        "max_entries": data.get("max_entries"),
    }

    # Parse tags
    if "tags" in data:
        config_data["tags"] = set(data["tags"])

    # Parse invalidation rules
    invalidation_rules = []
    if "invalidation_rules" in data:
        for rule_data in data["invalidation_rules"]:
            rule = _parse_invalidation_rule(rule_data)
            invalidation_rules.append(rule)
    config_data["invalidation_rules"] = invalidation_rules

    # Parse query-specific TTLs
    if "query_ttls" in data:
        config_data["query_specific_ttls"] = data["query_ttls"]

    return TableCacheConfig(**config_data)


def _parse_invalidation_rule(data: Dict[str, Any]) -> InvalidationRule:
    """Parse invalidation rule configuration."""
    table_name = data.get("table", data.get("table_name", ""))

    # Parse invalidation types
    invalidation_types = set()
    trigger_types = data.get("on", data.get("triggers", ["update"]))
    if isinstance(trigger_types, str):
        trigger_types = [trigger_types]

    for trigger in trigger_types:
        try:
            invalidation_types.add(InvalidationType(trigger.lower()))
        except ValueError:
            # Skip unknown invalidation types
            pass

    rule = InvalidationRule(
        table_name=table_name,
        invalidation_types=invalidation_types,
        tags_to_invalidate=set(data.get("invalidate_tags", [])),
        key_patterns_to_invalidate=set(data.get("invalidate_patterns", [])),
        cascade_tables=set(data.get("cascade_tables", [])),
        delay_seconds=data.get("delay", 0.0),
    )

    return rule


def create_default_config() -> CacheConfig:
    """Create a default configuration instance."""
    return CacheConfig()


def save_config_to_file(config: CacheConfig, file_path: Union[str, Path]) -> None:
    """Save configuration to a YAML file."""
    file_path = Path(file_path)

    # Convert config to dictionary format suitable for YAML
    config_dict: Dict[str, Any] = {
        "redis_url": config.redis_url,
        "default_ttl": config.default_ttl,
        "key_prefix": config.key_prefix,
        "enable_fuzzy": config.enable_fuzzy,
        "fuzzy_threshold": config.fuzzy_threshold,
        "max_connections": config.max_connections,
        "log_level": config.log_level,
        "enable_compression": config.enable_compression,
        "batch_size": config.batch_size,
    }

    # Add table configurations
    if config.table_configs:
        config_dict["tables"] = {}
        for table_name, table_config in config.table_configs.items():
            config_dict["tables"][table_name] = {
                "ttl": table_config.ttl,
                "tags": list(table_config.tags),
                "enable_fuzzy": table_config.enable_fuzzy,
                "fuzzy_threshold": table_config.fuzzy_threshold,
            }

            if table_config.max_entries:
                config_dict["tables"][table_name][
                    "max_entries"
                ] = table_config.max_entries

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
    except Exception as e:
        raise CacheConfigurationError(
            "config_file", f"Error writing configuration file: {e}"
        )
