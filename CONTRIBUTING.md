# Contributing to YokedCache

We welcome contributions to YokedCache! This document provides guidelines for contributing to the project.

## Development Setup

### Prerequisites

- Python 3.9 or higher
- Redis server
- Git

### Setting up the development environment

1. **Clone the repository:**
   ```bash
   git clone https://github.com/sirstig/yokedcache.git
   cd yokedcache
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies:**
   ```bash
   pip install -e ".[dev,docs]"
   ```

4. **Install pre-commit hooks:**
   ```bash
   pre-commit install
   ```

5. **Set up Redis for testing:**
   ```bash
   # Using Docker
   docker run -d -p 6379:6379 redis:7-alpine

   # Or install Redis locally
   # Follow instructions at https://redis.io/download
   ```

## Development Workflow

### Code Style

We use several tools to maintain code quality:

- **Black** for code formatting
- **isort** for import sorting
- **flake8** for linting
- **mypy** for type checking

Run all checks before committing:

```bash
# Format code
black src tests examples
isort src tests examples

# Check linting
flake8 src tests examples

# Type checking
mypy src --ignore-missing-imports
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=yokedcache --cov-report=html

# Run specific test file
pytest tests/test_cache.py

# Run specific test
pytest tests/test_cache.py::TestYokedCache::test_basic_get_set
```

### Testing Guidelines

- Write tests for all new features
- Maintain test coverage above 90%
- Use `fakeredis` for Redis mocking in tests
- Include both unit and integration tests
- Test error conditions and edge cases

### Documentation

- Update docstrings for all public functions and classes
- Follow Google-style docstring format
- Update README.md for new features
- Add examples to the `examples/` directory
- Update documentation in `docs/` directory as needed
- Run `mkdocs build --strict` to verify documentation builds correctly
- Test documentation locally with `mkdocs serve`

## Contribution Guidelines

### Reporting Issues

Before creating an issue, please:

1. Check if the issue already exists
2. Use the issue templates provided
3. Include a minimal reproduction case
4. Specify your environment (Python version, Redis version, OS)

### Feature Requests

For new features:

1. Open an issue first to discuss the feature
2. Explain the use case and benefits
3. Consider backward compatibility
4. Be willing to implement or help implement

### Pull Requests

1. **Fork the repository** and create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the code style guidelines

3. **Add or update tests** for your changes

4. **Update documentation** as needed

5. **Run the test suite** and ensure all tests pass:
   ```bash
   pytest
   black src tests examples
   flake8 src tests examples
   mypy src --ignore-missing-imports
   mkdocs build --strict
   ```

6. **Commit your changes** with a clear commit message:
   ```bash
   git commit -m "Add fuzzy search timeout configuration"
   ```

7. **Push to your fork** and create a pull request:
   ```bash
   git push origin feature/your-feature-name
   ```

### Commit Message Guidelines

Use conventional commit format:

- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation changes
- `test:` for test additions/modifications
- `refactor:` for code refactoring
- `perf:` for performance improvements
- `chore:` for maintenance tasks

Examples:
```
feat: add Redis cluster support
fix: handle connection timeouts gracefully
docs: update installation instructions
test: add fuzzy search integration tests
```

### Code Review Process

1. All changes must be reviewed by at least one maintainer
2. Automated tests must pass
3. Code coverage must not decrease
4. Documentation must be updated for user-facing changes

## Project Structure

```
yokedcache/
├── src/yokedcache/          # Main package source
│   ├── __init__.py          # Package exports
│   ├── cache.py             # Core cache implementation
│   ├── config.py            # Configuration management
│   ├── decorators.py        # Caching decorators
│   ├── models.py            # Data models
│   ├── utils.py             # Utility functions
│   ├── exceptions.py        # Custom exceptions
│   └── cli.py               # Command-line interface
├── tests/                   # Test suite
├── examples/                # Usage examples
├── docs/                    # Documentation
└── pyproject.toml           # Project configuration
```

## Release Process

1. Update version in `src/yokedcache/__init__.py`
2. Update `CHANGELOG.md` with new features and fixes
3. Create a release PR
4. After merge, tag the release:
   ```bash
   git tag -a v0.1.0 -m "Release version 0.1.0"
   git push origin v0.1.0
   ```
5. GitHub Actions will automatically publish to PyPI

## Getting Help

- **Documentation:** Check the README and examples
- **Issues:** Search existing issues or create a new one
- **Discussions:** Use GitHub Discussions for questions
- **Chat:** Join our community chat (link TBD)

## Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct:

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on constructive feedback
- Respect different viewpoints and experiences

## Recognition

Contributors will be recognized in:

- The project README
- Release notes
- The CONTRIBUTORS file

Thank you for contributing to YokedCache!
