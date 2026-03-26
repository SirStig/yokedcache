# Contributing

Contributions are welcome. Here's how to get up and running.

## Setup

```bash
git clone https://github.com/sirstig/yokedcache.git
cd yokedcache
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e ".[dev,docs]"
pre-commit install
```

For Redis-backed tests, start a local server:

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

## Running tests

```bash
pytest                                         # all tests
pytest tests/test_cache.py                    # single file
pytest --cov=yokedcache --cov-report=html     # with coverage
```

Maintain coverage above 90%. Use `fakeredis` for Redis mocking in unit tests.

## Code style

We use Black, isort, flake8, and mypy. Pre-commit handles these automatically on commit, or run them manually:

```bash
black src tests && isort src tests
flake8 src tests
mypy src --ignore-missing-imports
```

## Documentation

Source lives under `site-src/pages/`. To preview locally:

```bash
python scripts/build_docs_site.py
cp CHANGELOG.md site/changelog.md
python -m pdoc yokedcache -o site/api --template-directory site-src/pdoc-template
cd site && python -m http.server 8000
```

Update `site-src/pages/` for any user-facing behavior changes, and docstrings for public API changes (Google-style format).

## Submitting changes

1. Fork and create a feature branch: `git checkout -b feature/your-thing`
2. Make changes, add or update tests
3. Run the full test suite and linters
4. Open a PR—one maintainer review required; tests and coverage must pass

**Commit style:** we use [conventional commits](https://www.conventionalcommits.org/)—`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `perf:`, `chore:`.

## Reporting issues

Open an issue using the provided templates. Include a minimal reproduction case and your environment (Python version, Redis version, OS).

For features: open an issue first to discuss before building. Consider backward compatibility.

## Security

Report vulnerabilities through [GitHub Security Advisories](https://github.com/sirstig/yokedcache/security/advisories/new), not public issues. See [SECURITY.md](SECURITY.md).

## Release process

1. Update version in `src/yokedcache/__init__.py`
2. Update `CHANGELOG.md`
3. Open a release PR; after merge, tag: `git tag -a v1.x.x -m "Release v1.x.x" && git push origin v1.x.x`
4. GitHub Actions publishes to PyPI automatically
