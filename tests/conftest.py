"""
Pytest configuration and fixtures for YokedCache tests.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import fakeredis.aioredis
import pytest
import pytest_asyncio

from yokedcache import CacheConfig, YokedCache


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def fake_redis():
    """Provide a fake Redis instance for testing."""
    return fakeredis.aioredis.FakeRedis()


@pytest_asyncio.fixture
async def test_config():
    """Provide a test configuration."""
    import os

    # Use environment variable or default to CI Redis (localhost:6379)
    # Dev container sets YOKEDCACHE_REDIS_URL=redis://redis:56379/0
    redis_url = os.getenv("YOKEDCACHE_REDIS_URL", "redis://localhost:6379/0")
    return CacheConfig(
        redis_url=redis_url,
        default_ttl=300,
        key_prefix="test",
        enable_fuzzy=True,
        fuzzy_threshold=80,
        log_level="DEBUG",
    )


@pytest_asyncio.fixture
async def cache(test_config, fake_redis):
    """Provide a YokedCache instance with fake Redis for testing."""
    cache_instance = YokedCache(config=test_config)

    # Replace the Redis connection with fake Redis
    cache_instance._redis = fake_redis
    cache_instance._connected = True

    yield cache_instance

    # Cleanup
    if cache_instance._connected:
        await cache_instance.disconnect()


@pytest_asyncio.fixture
async def real_cache():
    """Provide a YokedCache instance that connects to real Redis."""
    import os

    redis_url = os.getenv("YOKEDCACHE_REDIS_URL", "redis://localhost:6379/0")
    config = CacheConfig(redis_url=redis_url, key_prefix="test_real")
    cache_instance = YokedCache(config=config)

    try:
        await cache_instance.connect()
        yield cache_instance
    finally:
        if cache_instance._connected:
            await cache_instance.disconnect()


@pytest.fixture
def sample_data():
    """Provide sample data for testing."""
    return {
        "users": [
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
            {"id": 2, "name": "Bob", "email": "bob@example.com"},
        ],
        "posts": [
            {
                "id": 1,
                "title": "Test Post",
                "user_id": 1,
                "content": "Test content",
            },
            {
                "id": 2,
                "title": "Another Post",
                "user_id": 2,
                "content": "More content",
            },
        ],
    }


@pytest.fixture
def mock_db_session():
    """Provide a mock database session."""
    session = Mock()
    session.query = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    session.close = Mock()
    return session


@pytest_asyncio.fixture
async def async_mock_db_session():
    """Provide an async mock database session."""
    session = AsyncMock()
    session.query = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_redis():
    """Provide a mock Redis instance for testing backends."""
    redis_mock = Mock()
    redis_mock.ping = AsyncMock()
    redis_mock.get = AsyncMock()
    redis_mock.set = AsyncMock()
    redis_mock.setex = AsyncMock()
    redis_mock.delete = AsyncMock()
    redis_mock.exists = AsyncMock()
    redis_mock.expire = AsyncMock()
    redis_mock.keys = AsyncMock()
    redis_mock.smembers = AsyncMock()
    redis_mock.sadd = AsyncMock()
    redis_mock.close = AsyncMock()
    redis_mock.info = AsyncMock()
    redis_mock.touch = AsyncMock()

    # Mock pipeline
    pipeline_mock = AsyncMock()
    pipeline_mock.__aenter__ = AsyncMock(return_value=pipeline_mock)
    pipeline_mock.__aexit__ = AsyncMock(return_value=None)
    pipeline_mock.setex = AsyncMock()
    pipeline_mock.sadd = AsyncMock()
    pipeline_mock.expire = AsyncMock()
    pipeline_mock.execute = AsyncMock()
    redis_mock.pipeline = Mock(return_value=pipeline_mock)

    return redis_mock


@pytest.fixture
def mock_memcached():
    """Provide a mock Memcached client for testing."""
    memcached_mock = Mock()
    memcached_mock.version = AsyncMock()
    memcached_mock.get = AsyncMock()
    memcached_mock.set = AsyncMock()
    memcached_mock.delete = AsyncMock()
    memcached_mock.stats = AsyncMock()
    memcached_mock.flush_all = AsyncMock()
    memcached_mock.close = AsyncMock()
    return memcached_mock


@pytest.fixture
def sample_vector_data():
    """Provide sample data for vector search testing."""
    return {
        "doc:python": ("Python is a programming language that lets you work quickly"),
        "doc:java": (
            "Java is a high-level, class-based, object-oriented programming " "language"
        ),
        "doc:javascript": (
            "JavaScript is a programming language that conforms to the "
            "ECMAScript specification"
        ),
        "user:alice": {
            "name": "Alice Smith",
            "skills": ["python", "machine learning"],
        },
        "user:bob": {"name": "Bob Johnson", "skills": ["java", "spring boot"]},
        "post:ml": {
            "title": "Machine Learning Basics",
            "content": "Introduction to ML with Python",
        },
    }


@pytest.fixture
def mock_prometheus_collector():
    """Provide a mock Prometheus collector."""
    with (
        patch("yokedcache.monitoring.Counter"),
        patch("yokedcache.monitoring.Gauge"),
        patch("yokedcache.monitoring.Histogram"),
    ):

        from yokedcache.monitoring import PrometheusCollector

        collector = PrometheusCollector()

        # Mock the metric objects
        collector._get_counter = Mock()
        collector._set_counter = Mock()
        collector._delete_counter = Mock()
        collector._invalidation_counter = Mock()
        collector._cache_size_gauge = Mock()
        collector._cache_keys_gauge = Mock()
        collector._hit_rate_gauge = Mock()
        collector._operation_duration = Mock()

        return collector


@pytest.fixture
def mock_statsd_collector():
    """Provide a mock StatsD collector."""
    with patch("statsd.StatsClient") as mock_client_class:
        mock_client = Mock()
        mock_client.increment = Mock()
        mock_client.gauge = Mock()
        mock_client.histogram = Mock()
        mock_client.timing = Mock()
        mock_client_class.return_value = mock_client

        from yokedcache.monitoring import StatsDCollector

        collector = StatsDCollector()
        collector.client = mock_client

        return collector
