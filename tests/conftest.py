"""
Pytest configuration and fixtures for YokedCache tests.
"""

import asyncio
from unittest.mock import AsyncMock, Mock

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
    return CacheConfig(
        redis_url="redis://localhost:6379/0",
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


@pytest.fixture
def sample_data():
    """Provide sample data for testing."""
    return {
        "users": [
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
            {"id": 2, "name": "Bob", "email": "bob@example.com"},
        ],
        "posts": [
            {"id": 1, "title": "Test Post", "user_id": 1, "content": "Test content"},
            {"id": 2, "title": "Another Post", "user_id": 2, "content": "More content"},
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
