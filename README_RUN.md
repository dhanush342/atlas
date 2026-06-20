# Bharat Tech Atlas v4.00.02 — Quick Start Guide

## Network-Ready Setup (Any IDE)

### 1. Backend (Python)

```bash
cd my
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 7860
```

### 2. Frontend (React + Vite)

```bash
cd my/frontend
npm install
npm run dev
```

### 3. Verify Everything Works

```bash
# Health check
curl http://localhost:7860/api/health

# Metrics & cache status
curl http://localhost:7860/api/metrics

# Mentor matching
curl "http://localhost:7860/api/entities/match/mentors?startup_slug=flipkart"

# Ecosystem analytics
curl http://localhost:7860/api/entities/analytics/ecosystem
```

### 4. Optional: Enable Redis Cache

```bash
# Install redis package
pip install redis

# Set env var (one-line switch)
export REDIS_URL="redis://localhost:6379/0"

# Restart server — it auto-detects Redis
uvicorn backend.main:app --reload --port 7860
```

### 5. Run Tests

```bash
cd my
pytest tests/ -v
```

### 6. Run ETL Scheduler

```bash
# Run all scheduled tasks
python scripts/scheduler.py --run-all

# Or individual tasks
python scripts/scheduler.py --run-etl
python scripts/scheduler.py --warm-cache
python scripts/scheduler.py --refresh-analytics
```

## Database Location

The SQLite database is auto-created at:
```
my/data/bharattechatlas.db
```

## What's New in v4.00.02

- **Pluggable Cache**: TTL+LRU in-memory, one-line Redis swap-in
- **Analytics**: State/city ecosystem breakdowns, top states, state detail
- **Mentor Matching**: Smart algorithm matching startups to mentors by state + sector
- **Live ETL**: Startup India live extraction support
- **Extended Entities**: Mentors, Investors, Corporates, Government Bodies on map
- **UI Polish**: Production button system, typography scale, extended filters
- **Observability**: `/api/metrics` endpoint with cache + DB stats

## Troubleshooting

**Import errors?** Make sure you're running from the project root and `backend/` is in the Python path.

**Frontend not connecting?** Check that the backend is running on port 7860 and CORS is configured.

**Database not seeding?** Delete `data/bharattechatlas.db` and restart — it will auto-seed.
