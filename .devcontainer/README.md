# YokedCache Development Container

This directory contains a complete containerized development environment for YokedCache using VS Code Dev Containers.

## 🚀 Quick Start

1. **Prerequisites**:
   - Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
   - Install [VS Code](https://code.visualstudio.com/)
   - Install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

2. **Open in Container**:
   - Open this project in VS Code
   - Press `F1` and select "Dev Containers: Reopen in Container"
   - Or click the notification popup to reopen in container

3. **Wait for Setup**: The first time will take a few minutes to build and configure everything.

## 🏗️ What's Included

### Core Services
- **Python 3.11** with conda environment
- **Redis 7** for caching backend
- **Memcached 1.6** for alternative backend testing
- All project dependencies pre-installed

### Development Tools
- **VS Code Extensions**: Python, Pylance, Black, isort, flake8, mypy, pytest
- **Code Quality**: Pre-commit hooks, linting, type checking
- **Testing**: pytest with coverage reporting
- **Documentation**: Static site via `scripts/build_docs_site.py` and pdoc (`./dev.sh docs`)

### Optional Monitoring Stack
- **Redis Insight** (GUI for Redis) - Port 8001
- **Prometheus** (Metrics collection) - Port 9090
- **Grafana** (Metrics visualization) - Port 3000

## 🔧 Configuration

### Environment Variables
The container is pre-configured with:
```bash
YOKEDCACHE_REDIS_URL=redis://redis:56379/0
YOKEDCACHE_DEFAULT_TTL=300
YOKEDCACHE_KEY_PREFIX=dev_yokedcache
YOKEDCACHE_LOG_LEVEL=DEBUG
YOKEDCACHE_ENABLE_METRICS=true
YOKEDCACHE_PROMETHEUS_PORT=58000
PYTHONPATH=/workspace/src
```

### Service URLs
- **Redis**: `redis://redis:56379`
- **Memcached**: `memcached:11211`
- **Redis Insight**: http://localhost:58001
- **Prometheus**: http://localhost:59090
- **Grafana**: http://localhost:53000 (admin/admin)

## 🧪 Development Workflow

### Running Tests
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_cache.py

# Run with coverage
pytest --cov=yokedcache --cov-report=html
```

### Code Quality
```bash
# Format code
black src tests

# Sort imports
isort src tests

# Type checking
mypy src

# Linting
flake8 src tests

# Run all quality checks
pre-commit run --all-files
```

### Using YokedCache CLI
```bash
# Test Redis connection
yokedcache ping

# Monitor cache metrics
yokedcache stats

# Clear cache
yokedcache clear --confirm
```

### Development Cache Config
A development configuration file is created at `cache_config_dev.yaml`:
```yaml
redis_url: redis://redis:56379/0
default_ttl: 300
key_prefix: dev_yokedcache
enable_fuzzy: true
log_level: DEBUG
enable_metrics: true
prometheus_port: 58000
```

## 🎛️ Optional Services

### Enable Monitoring Stack
To start Prometheus and Grafana:
```bash
docker-compose --profile monitoring up -d
```

### Enable Redis Insight
To start Redis GUI:
```bash
docker-compose --profile tools up -d
```

## 🔍 Troubleshooting

### Container Won't Start
1. Ensure Docker Desktop is running
2. Check Docker has enough resources (4GB+ RAM recommended)
3. Try rebuilding: `F1` → "Dev Containers: Rebuild Container"

### Redis Connection Issues
```bash
# Check Redis status
redis-cli -h redis -p 56379 ping

# View Redis logs
docker logs yokedcache-redis
```

### Python Environment Issues
```bash
# Verify environment
conda info
python --version
pip list | grep yokedcache

# Reinstall in development mode
pip install -e .
```

### Performance Issues
The container includes performance monitoring:
```bash
# Check resource usage
htop

# Monitor Redis performance
redis-cli -h redis --latency

# View container stats
docker stats
```

## 📁 Directory Structure

```
.devcontainer/
├── devcontainer.json       # VS Code Dev Container configuration
├── docker-compose.yml      # Multi-service Docker setup
├── Dockerfile              # Python development environment
├── post-create.sh          # Environment setup script
├── redis.conf              # Redis configuration
├── prometheus.yml          # Prometheus configuration
├── grafana-datasources.yml # Grafana data sources
└── README.md               # This file
```

## 🚀 Advanced Usage

### Custom Python Packages
Add packages to `requirements-dev.txt` and rebuild the container.

### Environment Customization
Modify `devcontainer.json` to add VS Code extensions or change settings.

### Service Configuration
Edit `docker-compose.yml` to modify service configurations or add new services.

### Persistent Data
Data in Redis and other services persists between container rebuilds via Docker volumes.

## 📚 Resources

- [YokedCache Documentation](https://sirstig.github.io/yokedcache)
- [VS Code Dev Containers](https://code.visualstudio.com/docs/remote/containers)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [Redis Configuration](https://redis.io/topics/config)
