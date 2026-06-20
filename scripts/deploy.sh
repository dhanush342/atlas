#!/bin/bash
# Bharat Tech Atlas Production Deployment Script
# Usage: ./deploy.sh [staging|production]

set -euo pipefail

ENVIRONMENT=${1:-staging}
APP_DIR="/opt/bharat-tech-atlas"
USER="bta"
SERVICE="bharat-tech-atlas"

echo "=========================================="
echo "  Bharat Tech Atlas Deployment"
echo "  Environment: $ENVIRONMENT"
echo "  Version: $(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
echo "=========================================="

# 1. Pre-deployment checks
echo "[1/8] Running pre-deployment checks..."
if ! command -v docker &> /dev/null; then
    echo "Error: Docker not installed"
    exit 1
fi
if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose not installed"
    exit 1
fi

# 2. Pull latest code
echo "[2/8] Pulling latest code..."
git pull origin main

# 3. Install/update dependencies
echo "[3/8] Installing dependencies..."
if [ -d "$APP_DIR/venv" ]; then
    source "$APP_DIR/venv/bin/activate"
    pip install -r requirements.txt --quiet
fi

# 4. Run database migrations (if any)
echo "[4/8] Running database checks..."
cd "$APP_DIR"
python -c "from backend.database import init_db; init_db()"

# 5. Run tests
echo "[5/8] Running tests..."
pytest tests/ -q --tb=line || { echo "Tests failed! Aborting deployment."; exit 1; }

# 6. Build Docker images
echo "[6/8] Building Docker images..."
docker-compose build --no-cache

# 7. Deploy
echo "[7/8] Deploying..."
docker-compose down
docker-compose up -d

# 8. Health check
echo "[8/8] Running health checks..."
sleep 10
for i in {1..5}; do
    if curl -sf http://localhost:7860/api/health > /dev/null; then
        echo "  Health check passed!"
        break
    fi
    echo "  Health check attempt $i/5..."
    sleep 5
    if [ $i -eq 5 ]; then
        echo "  Health check failed! Rolling back..."
        docker-compose logs --tail=50
        exit 1
    fi
done

echo "=========================================="
echo "  Deployment Complete!"
echo "  Health: http://localhost:7860/api/health"
echo "  Metrics: http://localhost:7860/api/metrics"
echo "=========================================="
