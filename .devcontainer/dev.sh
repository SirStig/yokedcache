#!/bin/bash

# YokedCache Development Helper Script
# Usage: ./dev.sh [command]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Activate conda environment if not already active
activate_env() {
    if [ "$CONDA_DEFAULT_ENV" != "yokedcache" ]; then
        source /opt/conda/etc/profile.d/conda.sh
        conda activate yokedcache
    fi
}

# Development commands
case "$1" in
    "setup"|"install")
        log_info "Installing YokedCache in development mode..."
        activate_env
        pip install -e .
        log_success "Development installation complete"
        ;;

    "test"|"tests")
        log_info "Running tests..."
        activate_env
        if [ -n "$2" ]; then
            pytest "$2" -v
        else
            pytest -v
        fi
        ;;

    "test-cov"|"coverage")
        log_info "Running tests with coverage..."
        activate_env
        pytest --cov=yokedcache --cov-report=html --cov-report=term-missing
        log_success "Coverage report generated in htmlcov/"
        ;;

    "format"|"fmt")
        log_info "Formatting code..."
        activate_env
        black src tests
        isort src tests
        log_success "Code formatting complete"
        ;;

    "lint")
        log_info "Running linting checks..."
        activate_env
        flake8 src tests
        mypy src
        log_success "Linting complete"
        ;;

    "quality"|"qa")
        log_info "Running all quality checks..."
        activate_env
        black --check src tests
        isort --check-only src tests
        flake8 src tests
        mypy src
        log_success "All quality checks passed"
        ;;

    "docs"|"doc")
        log_info "Building documentation..."
        activate_env
        mkdocs build
        log_success "Documentation built in site/"
        ;;

    "docs-serve")
        log_info "Starting documentation server..."
        activate_env
        mkdocs serve --dev-addr=0.0.0.0:58080
        ;;

    "redis-cli")
        log_info "Connecting to Redis CLI..."
        redis-cli -h redis -p 56379
        ;;

    "ping")
        log_info "Testing cache connection..."
        activate_env
        yokedcache ping
        ;;

    "stats")
        log_info "Showing cache statistics..."
        activate_env
        yokedcache stats
        ;;

    "clear")
        log_warning "Clearing cache..."
        activate_env
        yokedcache clear --confirm
        log_success "Cache cleared"
        ;;

    "logs")
        service="${2:-yokedcache-dev}"
        log_info "Showing logs for $service..."
        docker logs -f "$service"
        ;;

    "shell")
        log_info "Starting development shell..."
        activate_env
        exec bash
        ;;

    "jupyter")
        log_info "Starting Jupyter Lab..."
        activate_env
        jupyter lab --ip=0.0.0.0 --port=58888 --allow-root --no-browser
        ;;

    "monitor")
        log_info "Starting monitoring stack..."
        docker-compose --profile monitoring up -d
        log_success "Monitoring stack started:"
        log_info "  • Prometheus: http://localhost:59090"
        log_info "  • Grafana: http://localhost:53000 (admin/admin)"
        ;;

    "tools")
        log_info "Starting development tools..."
        docker-compose --profile tools up -d
        log_success "Tools started:"
        log_info "  • Redis Insight: http://localhost:58001"
        ;;

    "status")
        log_info "Service status:"
        docker-compose ps
        ;;

    "restart")
        service="${2:-all}"
        if [ "$service" = "all" ]; then
            log_info "Restarting all services..."
            docker-compose restart
        else
            log_info "Restarting $service..."
            docker-compose restart "$service"
        fi
        log_success "Restart complete"
        ;;

    "clean")
        log_info "Cleaning up development environment..."
        docker-compose down -v
        docker system prune -f
        log_success "Cleanup complete"
        ;;

    "help"|""|"-h"|"--help")
        echo "YokedCache Development Helper"
        echo ""
        echo "Usage: ./dev.sh [command]"
        echo ""
        echo "Setup Commands:"
        echo "  setup, install    Install package in development mode"
        echo "  clean            Clean up containers and volumes"
        echo ""
        echo "Development Commands:"
        echo "  test [file]      Run tests (optionally specify test file)"
        echo "  test-cov         Run tests with coverage report"
        echo "  format, fmt      Format code with black and isort"
        echo "  lint             Run linting checks"
        echo "  quality, qa      Run all quality checks"
        echo ""
        echo "Documentation:"
        echo "  docs, doc        Build documentation"
        echo "  docs-serve       Serve documentation with live reload"
        echo ""
        echo "Cache Operations:"
        echo "  ping             Test cache connection"
        echo "  stats            Show cache statistics"
        echo "  clear            Clear cache data"
        echo "  redis-cli        Connect to Redis CLI"
        echo ""
        echo "Services:"
        echo "  status           Show service status"
        echo "  restart [svc]    Restart service (or all services)"
        echo "  logs [service]   Show service logs"
        echo "  monitor          Start monitoring stack (Prometheus/Grafana)"
        echo "  tools            Start development tools (Redis Insight)"
        echo ""
        echo "Development Environment:"
        echo "  shell            Start development shell"
        echo "  jupyter          Start Jupyter Lab"
        echo ""
        ;;

    *)
        log_error "Unknown command: $1"
        echo "Run './dev.sh help' for available commands"
        exit 1
        ;;
esac
