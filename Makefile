# Makefile for YokedCache development

.PHONY: install install-dev venv test test-cov lint format type-check clean docs build publish help

# Default target
help:
	@echo "YokedCache Development Commands"
	@echo "==============================="
	@echo "install      Install package in current environment"
	@echo "install-dev  Install package with development dependencies"
	@echo "venv         Create .venv and install package with dev dependencies"
	@echo "test         Run test suite"
	@echo "test-cov     Run tests with coverage report"
	@echo "lint         Run linting checks"
	@echo "format       Format code with black and isort"
	@echo "type-check   Run mypy type checking"
	@echo "clean        Clean build artifacts"
	@echo "build        Build package for distribution"
	@echo "test-build   Build and check package"
	@echo "publish-test Publish to Test PyPI"
	@echo "publish      Publish package to PyPI"
	@echo "setup-remote Show commands to setup GitHub remote"

# Installation
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	pre-commit install

venv:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev]"
	@echo "Activate: source .venv/bin/activate   (or use Cursor’s Python interpreter: .venv/bin/python)"

install-dev-req:
	pip install -r requirements-dev.txt
	pre-commit install

install-minimal:
	pip install -r requirements-minimal.txt

install-full:
	pip install -r requirements-full.txt

# Testing
test:
	pytest

test-cov:
	pytest --cov=yokedcache --cov-report=html --cov-report=term-missing

# Code quality
lint:
	flake8 src tests
	mypy src

format:
	black src tests
	isort src tests

type-check:
	mypy src

# Development
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name __pycache__ -delete
	find . -name "*.pyc" -delete

# Documentation
docs:
	python3 -m pip install -q -e ".[docs]"
	YOKEDCACHE_SITE_PATH_PREFIX= python3 scripts/build_docs_site.py
	cp CHANGELOG.md site/changelog.md
	python3 -m pdoc yokedcache -o site/api --template-directory site-src/pdoc-template
	@echo "Output in site/ — run: cd site && python3 -m http.server 8000"

# Distribution
build: clean
	python -m build

test-build: build
	python -m twine check dist/*

publish-test: test-build
	python -m twine upload --repository testpypi dist/*

publish: test-build
	python -m twine upload dist/*

# GitHub repository setup
setup-remote:
	@echo "Run this command to add your GitHub remote:"
	@echo "git remote add origin https://github.com/sirstig/yokedcache.git"
	@echo "git push -u origin main"

# Utilities
redis-start:
	@echo "Starting Redis server (requires Docker)..."
	docker run -d --name yokedcache-redis -p 6379:6379 redis:7-alpine

redis-stop:
	@echo "Stopping Redis server..."
	docker stop yokedcache-redis || true
	docker rm yokedcache-redis || true

# CI/CD helpers
ci-test: install-dev test lint type-check

# Quick development checks
check: format lint test

# Setup for new contributors
setup: install-dev
	@echo "Development environment setup complete!"
	@echo "Run 'make test' to verify everything works."
