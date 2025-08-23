# Changelog

All notable changes to the YokedCache project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Star request button prominently displayed in README
- Documentation build verification with `mkdocs build --strict`

### Changed

- Updated documentation dependencies to latest versions
- Enhanced CONTRIBUTING.md with documentation build requirements
- Updated development setup to include docs dependencies

### Fixed

- Fixed mkdocs navigation configuration to include all existing documentation files
- Resolved relative link issues in documentation
- Fixed missing file warnings in mkdocs build

### Removed

- Acknowledgments section from README.md (streamlined for professional appearance)

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
