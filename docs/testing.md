# Testing Guide

This guide covers testing YokedCache, including running the test suite, writing custom tests, and validating new features.

## Table of Contents

- [Quick Start](#quick-start)
- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Writing Tests](#writing-tests)
- [Testing New Features](#testing-new-features)
- [Continuous Integration](#continuous-integration)
- [Troubleshooting](#troubleshooting)

## Quick Start

### Prerequisites

Install the development dependencies:

```bash
# Install with development dependencies
pip install -e ".[dev]"

# Or install manually
pip install pytest pytest-asyncio pytest-cov fakeredis
```

### Quick Verification

Run the quick verification script to test all features:

```bash
python test_quick_verification.py
```

This script tests:
- ✅ Basic YokedCache functionality
- ✅ Memory backend operations
- ✅ Vector similarity search
- ✅ Monitoring integrations
- ✅ Backend imports and availability

### Full Test Suite

Run the complete test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=yokedcache

# Run specific test modules
pytest tests/test_backends.py
pytest tests/test_vector_search.py
pytest tests/test_monitoring.py
```

## Test Structure

The test suite is organized by functionality:

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── test_cache.py            # Core cache functionality tests
├── test_backends.py         # Backend implementation tests
├── test_decorators.py       # Decorator tests
├── test_vector_search.py    # Vector search tests
├── test_monitoring.py       # Monitoring and metrics tests
└── test_cli.py             # CLI functionality tests
```

### Test Categories

#### Unit Tests
- Individual component testing
- Mock external dependencies
- Fast execution (< 1 second per test)

#### Integration Tests
- Cross-component functionality
- Real backend connections (when available)
- End-to-end workflows

#### Feature Tests
- New feature validation
- Edge case coverage
- Performance benchmarks

## Running Tests

### Basic Test Execution

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_backends.py

# Run specific test class
pytest tests/test_backends.py::TestMemoryBackend

# Run specific test method
pytest tests/test_backends.py::TestMemoryBackend::test_memory_backend_connection
```

### Test Configuration

```bash
# Run with coverage reporting
pytest --cov=yokedcache --cov-report=html

# Run with specific markers
pytest -m "not slow"

# Run with parallel execution
pytest -n auto

# Stop on first failure
pytest -x

# Show local variables on failure
pytest -l --tb=long
```

### Environment-Specific Testing

#### Testing with Redis

```bash
# Start Redis (Docker)
docker run -d -p 6379:6379 redis:alpine

# Run Redis-dependent tests
pytest tests/test_backends.py::TestRedisBackend
```

#### Testing with Memcached

```bash
# Start Memcached (Docker)
docker run -d -p 11211:11211 memcached:alpine

# Run Memcached tests
pytest tests/test_backends.py::TestMemcachedBackend
```

#### Testing Optional Dependencies

```bash
# Test vector search features
pytest tests/test_vector_search.py

# Test monitoring features
pytest tests/test_monitoring.py

# Skip tests for missing dependencies
pytest --disable-warnings
```

## Writing Tests

### Test Structure

Follow this structure for new tests:

```python
import pytest
from unittest.mock import Mock, AsyncMock, patch

from yokedcache import YokedCache
from yokedcache.backends import MemoryBackend


class TestNewFeature:
    """Test new feature functionality."""

    @pytest.fixture
    async def setup_feature(self):
        """Setup test environment."""
        # Setup code
        yield test_object
        # Cleanup code

    @pytest.mark.asyncio
    async def test_basic_functionality(self, setup_feature):
        """Test basic feature operation."""
        # Arrange
        test_data = {"key": "value"}

        # Act
        result = await setup_feature.method(test_data)

        # Assert
        assert result is not None
        assert isinstance(result, expected_type)

    @pytest.mark.asyncio
    async def test_error_handling(self, setup_feature):
        """Test error conditions."""
        with pytest.raises(ExpectedException):
            await setup_feature.method(invalid_data)
```

### Async Testing

Use `pytest.mark.asyncio` for async tests:

```python
@pytest.mark.asyncio
async def test_async_operation():
    """Test asynchronous operation."""
    backend = MemoryBackend()
    await backend.connect()

    result = await backend.set("key", "value")
    assert result is True

    await backend.disconnect()
```

### Mocking External Dependencies

Mock external services and dependencies:

```python
@pytest.mark.asyncio
async def test_with_mocked_redis():
    """Test with mocked Redis."""
    with patch('redis.asyncio.Redis') as mock_redis_class:
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        mock_redis_class.return_value = mock_redis

        backend = RedisBackend()
        await backend.connect()

        mock_redis.ping.assert_called_once()
```

### Testing Optional Features

Handle optional dependencies gracefully:

```python
@pytest.mark.skipif(
    not pytest.importorskip("numpy", reason="numpy not available"),
    reason="Vector search dependencies not available"
)
def test_vector_search_feature():
    """Test vector search when dependencies are available."""
    from yokedcache.vector_search import VectorSimilaritySearch

    search = VectorSimilaritySearch()
    # Test implementation
```

## Testing New Features

### Backend Testing

When adding a new backend:

1. **Create backend tests** in `tests/test_backends.py`
2. **Test interface compliance** - ensure all abstract methods are implemented
3. **Test error handling** - connection failures, timeouts, etc.
4. **Test performance** - basic benchmarks for operations

```python
class TestNewBackend:
    """Test new backend implementation."""

    @pytest.fixture
    async def backend(self):
        """Create backend instance."""
        backend = NewBackend(config_params)
        await backend.connect()
        yield backend
        await backend.disconnect()

    @pytest.mark.asyncio
    async def test_interface_compliance(self, backend):
        """Test that backend implements required interface."""
        # Test all CacheBackend methods
        assert await backend.health_check()
        assert await backend.set("key", "value")
        assert await backend.get("key") == "value"
        assert await backend.delete("key")
```

### Feature Testing

For new cache features:

1. **Unit tests** - individual components
2. **Integration tests** - feature interaction with cache
3. **Edge case tests** - boundary conditions
4. **Performance tests** - ensure no regression

### CLI Testing

Test CLI functionality with Click's test runner:

```python
from click.testing import CliRunner
from yokedcache.cli import cli

def test_cli_command():
    """Test CLI command execution."""
    runner = CliRunner()
    result = runner.invoke(cli, ['stats', '--format', 'json'])

    assert result.exit_code == 0
    assert 'total_hits' in result.output
```

## Continuous Integration

### Pre-commit Hooks

Install and configure pre-commit hooks:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

The `.pre-commit-config.yaml` includes:
- **Black** - Code formatting
- **isort** - Import sorting
- **MyPy** - Type checking
- **Pytest** - Test execution

### CI Pipeline

The CI pipeline runs:

1. **Code Quality Checks**
   - Black formatting
   - Import sorting
   - Type checking
   - Linting

2. **Test Execution**
   - Unit tests
   - Integration tests
   - Coverage reporting

3. **Feature Validation**
   - Optional dependency tests
   - Cross-platform testing
   - Performance benchmarks

### Test Matrix

Tests run across:
- **Python versions**: 3.8, 3.9, 3.10, 3.11, 3.12
- **Operating systems**: Ubuntu, Windows, macOS
- **Dependency sets**: minimal, full, optional features

## Troubleshooting

### Common Issues

#### Test Hanging

If tests hang indefinitely:

```bash
# Run with timeout
pytest --timeout=30

# Run single test to isolate
pytest tests/test_specific.py::test_method -v

# Check for resource leaks
pytest --capture=no
```

#### Import Errors

For missing dependencies:

```bash
# Check installed packages
pip list

# Install missing dependencies
pip install -r requirements-dev.txt

# Verify imports
python -c "import yokedcache; print('OK')"
```

#### Mock Issues

For async mocking problems:

```python
# Use AsyncMock for async methods
mock_method = AsyncMock()

# Proper async context manager mocking
mock_context = AsyncMock()
mock_context.__aenter__ = AsyncMock(return_value=mock_context)
mock_context.__aexit__ = AsyncMock(return_value=None)
```

#### Redis Connection Issues

For Redis-related test failures:

```bash
# Check Redis availability
redis-cli ping

# Use fake Redis for tests
pip install fakeredis

# Skip Redis tests if not available
pytest -k "not redis"
```

### Debugging Tests

#### Verbose Output

```bash
# Show print statements
pytest -s

# Show local variables on failure
pytest -l

# Full traceback
pytest --tb=long

# Show warnings
pytest -W ignore::DeprecationWarning
```

#### Test Selection

```bash
# Run only failed tests
pytest --lf

# Run failed tests first
pytest --ff

# Run tests matching pattern
pytest -k "test_memory"

# Run specific markers
pytest -m "slow"
```

#### Coverage Analysis

```bash
# Generate HTML coverage report
pytest --cov=yokedcache --cov-report=html

# Show missing lines
pytest --cov=yokedcache --cov-report=term-missing

# Fail if coverage below threshold
pytest --cov=yokedcache --cov-fail-under=80
```

## Performance Testing

### Benchmarking

Run performance tests to ensure no regression:

```bash
# Basic performance test
python -m pytest tests/test_performance.py

# With profiling
python -m pytest tests/test_performance.py --profile

# Memory usage analysis
python -m pytest tests/test_performance.py --memray
```

### Load Testing

Test with high concurrency:

```python
import asyncio
import pytest
from yokedcache.backends import MemoryBackend

@pytest.mark.asyncio
async def test_concurrent_operations():
    """Test high concurrency operations."""
    backend = MemoryBackend()
    await backend.connect()

    # Simulate 100 concurrent operations
    tasks = []
    for i in range(100):
        tasks.append(backend.set(f"key_{i}", f"value_{i}"))

    results = await asyncio.gather(*tasks)
    assert all(results)

    await backend.disconnect()
```

## Best Practices

### Test Organization

1. **Group related tests** in classes
2. **Use descriptive names** for test methods
3. **Follow AAA pattern** (Arrange, Act, Assert)
4. **Keep tests independent** - no shared state
5. **Use fixtures** for common setup

### Test Data

1. **Use realistic data** that represents actual usage
2. **Test edge cases** - empty data, large data, special characters
3. **Parameterize tests** for multiple input scenarios
4. **Mock external services** to ensure test reliability

### Maintenance

1. **Update tests** when adding features
2. **Remove obsolete tests** when refactoring
3. **Keep tests fast** - use mocks for slow operations
4. **Document complex test scenarios**
5. **Review test coverage** regularly

---

For more information about specific testing scenarios, see the individual test files in the `tests/` directory. Each file contains comprehensive examples and documentation for testing specific components.
