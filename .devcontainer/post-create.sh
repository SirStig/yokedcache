#!/bin/bash

# YokedCache Development Environment Setup Script
set -e

echo "🚀 Setting up YokedCache development environment..."

# Ensure we're in the workspace directory
cd /workspace

# Activate conda environment
source /opt/conda/etc/profile.d/conda.sh
conda activate yokedcache

# Install the package in development mode
echo "📦 Installing YokedCache in development mode..."
pip install -e .

# Install pre-commit hooks
echo "🔧 Setting up pre-commit hooks..."
pre-commit install || echo "⚠️  Pre-commit installation failed (this is ok if .pre-commit-config.yaml doesn't exist)"

# Wait for Redis to be ready
echo "🔄 Waiting for Redis to be ready..."
max_attempts=30
attempt=0
while ! redis-cli -h redis -p 56379 ping > /dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ $attempt -ge $max_attempts ]; then
        echo "❌ Redis failed to start within expected time"
        break
    fi
    echo "   Waiting for Redis... (attempt $attempt/$max_attempts)"
    sleep 2
done

if redis-cli -h redis -p 56379 ping > /dev/null 2>&1; then
    echo "✅ Redis is ready!"
else
    echo "⚠️  Redis may not be ready, but continuing..."
fi

# Wait for Memcached to be ready
echo "🔄 Waiting for Memcached to be ready..."
max_attempts=15
attempt=0
while ! nc -z memcached 11211 > /dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ $attempt -ge $max_attempts ]; then
        echo "❌ Memcached failed to start within expected time"
        break
    fi
    echo "   Waiting for Memcached... (attempt $attempt/$max_attempts)"
    sleep 1
done

if nc -z memcached 11211 > /dev/null 2>&1; then
    echo "✅ Memcached is ready!"
else
    echo "⚠️  Memcached may not be ready, but continuing..."
fi

# Test the installation
echo "🧪 Testing YokedCache installation..."
python -c "
import yokedcache
print(f'✅ YokedCache version: {yokedcache.__version__}')

# Test basic import
from yokedcache import YokedCache, CacheConfig
print('✅ Core imports successful')

# Test CLI
import subprocess
result = subprocess.run(['yokedcache', '--version'], capture_output=True, text=True)
if result.returncode == 0:
    print(f'✅ CLI working: {result.stdout.strip()}')
else:
    print('⚠️  CLI test failed')
"

# Test Redis connection
echo "🧪 Testing Redis connection..."
python -c "
import asyncio
from yokedcache import YokedCache, CacheConfig

async def test_redis():
    try:
        config = CacheConfig(redis_url='redis://redis:56379/0')
        cache = YokedCache(config=config)
        await cache.connect()
        health = await cache.health_check()
        await cache.disconnect()
        if health:
            print('✅ Redis connection test successful')
        else:
            print('⚠️  Redis health check failed')
    except Exception as e:
        print(f'⚠️  Redis connection test failed: {e}')

asyncio.run(test_redis())
"

# Run basic tests to ensure everything is working
echo "🧪 Running basic tests..."
if [ -d "tests" ]; then
    python -m pytest tests/test_cache.py -v --tb=short || echo "⚠️  Some tests failed (this might be expected in development)"
else
    echo "⚠️  No tests directory found"
fi

# Create development cache config
echo "📝 Creating development cache configuration..."
cat > cache_config_dev.yaml << EOF
# YokedCache Development Configuration
redis_url: redis://redis:56379/0
default_ttl: 300
key_prefix: dev_yokedcache
max_connections: 25
enable_fuzzy: true
fuzzy_threshold: 80
log_level: DEBUG

# Development-specific settings
enable_metrics: true
prometheus_port: 58000

# Table configurations for testing
tables:
  users:
    ttl: 600
    tags: ["user_data"]
    enable_fuzzy: true

  products:
    ttl: 1800
    tags: ["product_data"]

  sessions:
    ttl: 300
    tags: ["session_data"]

monitoring:
  enable_metrics: true
  prometheus_port: 58000
EOF

echo "📋 Development environment ready!"
echo ""
echo "🎯 Quick Start Commands:"
echo "   • Test Redis:     yokedcache ping"
echo "   • Run tests:      pytest"
echo "   • Format code:    black src tests"
echo "   • Type check:     mypy src"
echo "   • Run linting:    flake8 src tests"
echo "   • Start Jupyter:  jupyter lab --ip=0.0.0.0 --port=8888 --allow-root"
echo ""
echo "🔗 Available Services:"
echo "   • Redis:          redis://redis:56379"
echo "   • Memcached:      memcached:11211"
echo "   • Redis Insight:  http://localhost:58001 (if enabled)"
echo "   • Prometheus:     http://localhost:59090 (if enabled)"
echo "   • Grafana:        http://localhost:53000 (if enabled)"
echo ""
echo "📖 Documentation: https://sirstig.github.io/yokedcache"
echo "🎉 Happy coding!"
