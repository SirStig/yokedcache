## [0.2.4] - 2025-11-02

### 🐛 Critical Bug Fixes

#### Fixed Missing Implementation
- **Fixed missing `_handle_tags` method**: Implemented proper tag management method that was referenced but not defined, fixing tag handling for cache operations

#### Fixed Exception Handling
- **Fixed incorrect exception name**: Replaced all instances of non-existent `CircuitBreakerOpenError` with correct `CircuitBreakerError` from circuit_breaker module, preventing runtime failures

#### Code Structure Fixes
- **Removed duplicate method definitions**: Eliminated multiple duplicate definitions of `_direct_get`, `_direct_set`, `_direct_delete`, `_direct_exists`, and `_direct_expire` methods
- **Fixed incorrect method nesting**: Moved `add_backend_route` and `remove_backend_route` methods from incorrectly nested position inside `setup_prefix_routing` to proper class level
- **Fixed incorrect self references**: Corrected `self._cache` references (which don't exist) to proper `self` references in method implementations

#### Metrics API Fixes
- **Fixed metrics method calls**: Replaced calls to non-existent methods (`record_miss`, `record_hit`, `record_set`, `record_delete`, `record_error`) with proper `record_operation()` calls using `OperationMetric` objects
- **Added null safety checks**: Added proper null checks for `self._metrics` before performing metrics operations to prevent crashes when metrics are disabled

#### Circuit Breaker Enhancements
- **Added context manager support**: Implemented `__aenter__` and `__aexit__` methods in `CircuitBreaker` class to support proper async context manager usage (`async with self._circuit_breaker`)

### Impact
These fixes resolve critical runtime errors that would have prevented the library from functioning correctly. All fixes maintain backward compatibility and improve code quality and reliability.

## [0.3.0] - 2025-08-26

### 🚀 Major Features

#### Advanced Caching Patterns
- **HTTP Response Middleware**: ETag/Cache-Control headers with 304 Not Modified responses for FastAPI applications
- **Single-Flight Protection**: Prevents cache stampede by deduplicating concurrent requests for the same key
- **Stale-While-Revalidate**: Serve stale cached data while refreshing in background for improved performance
- **Stale-If-Error**: Fallback to cached data during service failures for enhanced resilience

#### Multi-Backend Architecture
- **DiskCache Backend**: Local disk-based persistent caching using the `diskcache` library
- **SQLite Backend**: Embedded database caching with TTL support for offline scenarios
- **Per-Prefix Routing**: Route cache keys to different backends based on key prefixes for data sharding

#### Observability & Tracing
- **OpenTelemetry Integration**: Distributed tracing with automatic span creation for cache operations
- **Cache Metrics**: Hit/miss tracking, timing metrics, and backend performance monitoring
- **Global Tracer Configuration**: Service-wide tracing setup with configurable sampling rates

### 🔧 Technical Enhancements
- **SWR Scheduler**: Background refresh scheduling with task management and cleanup
- **Prefix Router**: Intelligent backend selection based on key patterns
- **Enhanced Configuration**: New config options for advanced features with backward compatibility
- **Optional Dependencies**: Graceful handling of missing optional packages (diskcache, opentelemetry)

### 📦 Installation
```bash
# New optional dependencies
pip install yokedcache[disk]          # DiskCache backend
pip install yokedcache[tracing]       # OpenTelemetry tracing
pip install yokedcache[full]          # All features including new ones
```

### 🧪 Testing
- Comprehensive test suite for all new features
- Integration tests for advanced caching patterns
- Mock-based testing for optional dependencies

## [0.2.3] - 2025-08-25


_Changes since v0.2.0_


### Features
- feat: update manual release workflow to include prerelease option and version verification (
74e17d)

### Fixes
- fix: improve version retrieval method and enhance error handling for CacheConfig (6581eb7)
- fix: improve type annotations and enhance error handling in FastAPI example (
8e8680)

### Chores
- chore: remove flake8 linting step from test workflow (
a52e34)
- chore: ensure newline at EOF in pre-commit config (
ffd948)
- chore: release version 0.2.1 with enhanced resilience and performance features (
e04b78)
- chore: update Codecov action in CI workflow (
ab4405)
- chore: enhance documentation and streamline project structure (
9e5470)
- chore: update dependencies and enhance configuration options (
29d7ec)

### Other
- Add extensive test 2 (
33ed60)
- Add extensive test coverage (
4f3a62)
- Add comprehensive tests, configuration files, and Prometheus setup for YokedCache (
43ec50)

# Changelog

All notable changes to the YokedCache project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] - 2025-08-23

### Added

- **Circuit Breaker Pattern**: Advanced resilience pattern to prevent cascading failures during Redis outages
- **Connection Pool Management**: Enhanced Redis connection configuration with custom pool parameters
- **Async/Sync Context Detection**: Smart handling to prevent Task object returns in mixed async/sync environments
- **Comprehensive Metrics System**: Real-time performance tracking with hit rates, error rates, and response times
- **Enhanced Error Handling**: Graceful fallback mechanisms when cache operations fail
- **Health Check Endpoint**: Detailed cache status monitoring including connection pool stats and performance metrics
- **Retry Mechanism**: Exponential backoff retry logic for transient Redis failures
- **Improved Configuration**: Extended `CacheConfig` with circuit breaker, retry, and resilience settings
- **FastAPI Dependency Enhancement**: Better support for generator-based dependencies and database session handling
- **Comprehensive Test Suite**: 240+ tests with 64% coverage including circuit breaker, configuration, and utilities
- **Production-Ready Features**: Implementation of all critical priority items from real-world testing feedback

### Changed

- **Enhanced `CacheConfig`**: Added `connection_pool_kwargs`, circuit breaker settings, and error handling options
- **Improved Cache Methods**: Added explicit async (`aget`, `aset`) and sync (`get_sync`, `set_sync`) method variants
- **Better Dependency Injection**: Enhanced `cached_dependency` decorator to properly handle FastAPI generator patterns
- **Upgraded Serialization**: Fixed datetime handling to use timezone-aware `datetime.now(timezone.utc)`
- **Performance Optimizations**: Improved cache key generation and data serialization efficiency

### Fixed

- **Critical Issue**: `CacheConfig` now properly accepts and validates `connection_pool_kwargs` parameter
- **Async/Sync Handling**: Fixed Task object returns when sync methods called from async contexts
- **FastAPI Integration**: Resolved generator dependency wrapping to return proper database session objects
- **Environment Variables**: Enhanced parsing and validation of configuration overrides
- **MyPy Compatibility**: Resolved all type checking errors for better code quality
- **Test Stability**: Fixed file permission issues in Windows testing environment

### Security

- **Error Resilience**: Circuit breaker prevents system overload during Redis failures
- **Connection Management**: Proper connection pool configuration prevents resource exhaustion
- **Graceful Degradation**: Fallback mechanisms ensure application stability during cache issues

### Performance

- **64% Test Coverage**: Significantly improved from 55% with comprehensive testing of critical paths
- **Circuit Breaker Efficiency**: 92% test coverage for resilience patterns
- **Configuration Validation**: 98% test coverage for robust configuration management
- **Utility Functions**: 72% test coverage for core helper functions

### Documentation

- **Star request button prominently displayed in README**
- **Documentation build verification with `mkdocs build --strict`**
- **Updated documentation dependencies to latest versions**
- **Enhanced CONTRIBUTING.md with documentation build requirements**
- **Updated development setup to include docs dependencies**

## [0.2.0] - 2024-01-15

### Added

- **Multi-Backend Architecture**: Support for Redis, Memcached, and in-memory backends with abstract interface
- **Vector-Based Similarity Search**: Advanced semantic search using TF-IDF and cosine/euclidean/manhattan similarity
- **Production Monitoring**: Prometheus and StatsD metrics integration for real-time monitoring and alerting
- **CSV Export**: CLI support for exporting cache statistics to CSV format for analysis and reporting
- **Enhanced CLI**: Improved command-line interface with file output, format options, and advanced search
- **Professional Templates**: Pull request template and code of conduct for better project governance
- **Memory Backend**: In-memory caching with LRU eviction, TTL support, and thread-safe operations
- **Testing Infrastructure**: Comprehensive test suite with 200+ tests covering all features and edge cases
- **Testing Guide**: Complete documentation for testing methodology and best practices

### Changed

- **Modular Backend System**: Refactored cache implementation to support pluggable backends with consistent API
- **Enhanced Configuration**: Extended configuration options for multi-backend setup and monitoring integration
- **Improved Documentation**: Updated README with comprehensive examples, feature descriptions, and testing info
- **Development Workflow**: Added pre-commit hooks with black, isort, mypy, and pytest for code quality
- **Professional Standards**: Removed emojis from documentation for enterprise-ready appearance

### Fixed

- **DateTime Warnings**: Replaced deprecated `datetime.utcnow()` with timezone-aware alternatives
- **Import Handling**: Improved graceful degradation when optional dependencies are not available
- **Vector Search**: Corrected Manhattan distance calculation using proper sklearn functions
- **Test Reliability**: Enhanced async test mocking and fixture management for consistent results

### Security

- **Dependency Management**: Updated and categorized optional dependencies for better security and maintenance

## [0.1.3] - 2025-08-22

### Added

- CLI module execution support via `python -m yokedcache`
- Full CLI command suite: ping, stats, list, flush, search, export-config, warm
- Comprehensive documentation updates with accurate CLI examples

### Changed

- Improved CLI architecture with proper command registration
- Enhanced GitHub Actions workflow for better CI/CD reliability
- Updated all documentation files for accuracy and completeness

### Fixed

- Redis connection method: changed from `aclose()` to `close()` for proper async connection handling
- CLI command registration issue with async decorators using `functools.wraps`
- CLI parameter conflict with double context passing in async commands
- Black code formatting compliance across all source files
- isort import sorting compliance (added proper blank lines)
- MyPy type checking errors for Redis client methods
- GitHub Actions integration test failures with CLI module execution

### Removed

- Codecov integration temporarily disabled due to rate limiting issues

## [0.1.2] - 2025-08-22

### Added

- Initial project structure and core architecture
- Basic caching functionality with Redis backend
- Automatic cache invalidation on database writes
- Tag-based cache grouping and invalidation
- Pattern-based cache invalidation with wildcards
- Fuzzy search capabilities for cached data
- FastAPI integration with dependency injection
- Database wrapper for automatic query caching
- Comprehensive CLI tool for cache management
- Configuration system with YAML support
- Performance metrics and statistics tracking
- Multiple serialization methods (JSON, Pickle, MessagePack)
- Async/await support throughout the library
- Connection pooling and health checks
- Error handling and graceful fallbacks
- Comprehensive test suite with pytest
- Documentation and usage examples
- Development tooling (pre-commit, Makefile, CI/CD)

## [0.1.0] - 2024-MM-DD

### Added

- Initial release of YokedCache
- Core caching functionality with Redis
- FastAPI integration support
- CLI tool for cache management
- Configuration system
- Basic documentation and examples

[Unreleased]: https://github.com/sirstig/yokedcache/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/sirstig/yokedcache/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/sirstig/yokedcache/compare/v0.1.0...v0.1.2
[0.1.0]: https://github.com/sirstig/yokedcache/releases/tag/v0.1.0
