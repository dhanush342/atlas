# Bharat Tech Atlas v4.00.02 — Architecture & Deployment Guide

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER LAYER                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │ Web Browser  │  │ Mobile App   │  │ API Clients  │  │ Admin Dashboard  │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘ │
│         │                 │                 │                    │           │
│         └─────────────────┴─────────────────┴────────────────────┘           │
│                                    │                                         │
│                              HTTPS / WSS                                     │
│                                    │                                         │
├────────────────────────────────────┼─────────────────────────────────────────┤
│                         NGINX (Reverse Proxy)                                │
│                    Rate Limiting | SSL | Compression                         │
│                                    │                                         │
├────────────────────────────────────┼─────────────────────────────────────────┤
│                              FASTAPI BACKEND                                 │
│  ┌─────────────────────────────────┼──────────────────────────────────────┐  │
│  │                                 │                                      │  │
│  │  ┌──────────────┐  ┌───────────┴──────────┐  ┌──────────────────┐   │  │
│  │  │  API Routes  │  │  Analytics Engine    │  │  Matching Engine │   │  │
│  │  │  /api/...    │  │  /analytics/ecosystem│  │  /match/mentors  │   │  │
│  │  └──────────────┘  └──────────────────────┘  └──────────────────┘   │  │
│  │  ┌──────────────┐  ┌──────────────────┐  ┌────────────────────────┐   │  │
│  │  │  ML Routes   │  │  ETL Pipeline    │  │  Geocoding Service   │   │  │
│  │  │  /api/ml/    │  │  /api/etl/       │  │  /geocoding.py       │   │  │
│  │  └──────────────┘  └──────────────────┘  └────────────────────────┘   │  │
│  │  ┌──────────────┐  ┌──────────────────┐  ┌────────────────────────┐   │  │
│  │  │  Chat AI     │  │  Search Agent    │  │  Cache Layer           │   │  │
│  │  │  /api/chat/  │  │  /api/agent/     │  │  TTL+LRU / Redis       │   │  │
│  │  └──────────────┘  └──────────────────┘  └────────────────────────┘   │  │
│  │                                                                         │  │
│  │  ┌────────────────────────────────────────────────────────────────┐   │  │
│  │  │  Security Layer: Rate Limiting | CSP | Input Validation | Audit │   │  │
│  │  └────────────────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
├────────────────────────────────────┼─────────────────────────────────────────┤
│                              DATA LAYER                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐    │
│  │ SQLite Database    │  │ Redis Cache        │  │ R-Tree Spatial Index │    │
│  │ bharattechatlas.db │  │ (Optional)         │  │ entities_rtree       │    │
│  │ 5,000+ entities    │  │ REDIS_URL          │  │ Fast geo queries     │    │
│  │ 10 entity types     │  │ 4 cache instances  │  │                     │    │
│  └──────────────────┘  └──────────────────┘  └──────────────────────┘    │
│  ┌──────────────────┐  ┌──────────────────┐                            │
│  │ Seed Data         │  │ Live ETL Extract │                            │
│  │ 118+ unicorns     │  │ Startup India API │                            │
│  │ Real addresses    │  │ Nominatim geocode  │                            │
│  └──────────────────┘  └──────────────────┘                            │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│                         INFRASTRUCTURE                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Docker       │  │ GitHub       │  │ systemd      │  │ cron/        │   │
│  │ docker-      │  │ Actions      │  │ service      │  │ scheduler    │   │
│  │ compose.yml  │  │ CI/CD        │  │ bharat-tech- │  │ scripts/     │   │
│  │              │  │ pipeline     │  │ atlas.service│  │ scheduler.py │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │
│  │ nginx/       │  │ .env         │  │ deploy.sh    │                      │
│  │ nginx.conf   │  │ config       │  │ deployment   │                      │
│  │ SSL/CSP      │  │              │  │ script       │                      │
│  └──────────────┘  └──────────────┘  └──────────────┘                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Entity Types (10)

| Type | Count | Color | Description |
|------|-------|-------|-------------|
| startup | 5,000+ | 🔵 #3B82F6 | DPIIT-recognized startups, unicorns, funded |
| sme | 700+ | 🟢 #10B981 | Small & Medium Enterprises |
| college_ecell | 35+ | 🟡 #FBBF24 | College Entrepreneurship Cells |
| incubator | 30+ | 🟣 #A855F7 | Startup incubators (T-Hub, SINE, etc.) |
| accelerator | 10+ | 🩷 #EC4899 | Accelerators (Google, Techstars, YC) |
| coworking | 5+ | 🟢 #14B8A6 | Coworking spaces |
| investor | 20+ | 🔴 #EF4444 | VC firms, angel networks |
| mentor | 20+ | 🟣 #8B5CF6 | Industry mentors and advisors |
| corporate | 30+ | 🔵 #0EA5E9 | Large companies working with startups |
| government_body | 20+ | 🟠 #D97706 | Government bodies and policies |

## API Endpoints

### Core Map & Search
- `GET /api/entities` — List entities with filters
- `GET /api/entities/search?q=...` — Full-text search with smart ranking
- `GET /api/entities/viewport/summary` — Map viewport clustering
- `GET /api/entities/:slug` — Entity detail

### Analytics v4.00.02
- `GET /api/entities/analytics/ecosystem` — State/city breakdown
- `GET /api/entities/analytics/top-states?limit=10` — Top states
- `GET /api/entities/analytics/state/:state` — State detail

### Matching v4.00.02
- `GET /api/entities/match/mentors?startup_slug=...` — Mentor matching
- `GET /api/entities/match/startups?investor_slug=...` — Investor-startup matching

### ML & AI
- `POST /api/ml/predict` — Keyword-based sector prediction (production-ready)
- `GET /api/ml/health` — Model health
- `GET /api/mlops/metrics` — MLOps monitoring
- `GET /api/mlops/predictions` — Prediction logs

### Chat & Agent
- `POST /api/chat/completions` — AI chat with web search
- `GET /api/agent/search` — Search agent with DuckDuckGo
- `GET /api/agent/enrich` — Entity enrichment

### ETL & Data
- `GET /api/etl/run` — Trigger ETL pipeline
- `POST /api/etl/run/live` — Live Startup India extraction
- `GET /api/etl/sources` — Data source info
- `GET /api/etl/history` — ETL run history

### Observability
- `GET /api/health` — Service health
- `GET /api/metrics` — Prometheus-style metrics + cache stats

## Database Schema

### entities (main table)
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| name | TEXT | Entity name |
| slug | TEXT UNIQUE | URL-safe identifier |
| entity_type | TEXT CHECK | One of 10 types |
| sectors | JSON | Array of sector strings |
| city | TEXT | City name |
| district | TEXT | District name |
| state | TEXT | State name |
| latitude | REAL | Precise latitude |
| longitude | REAL | Precise longitude |
| address | TEXT | Full address string |
| geocode_source | TEXT | cache/nominatim/google |
| geocode_confidence | TEXT | high/medium/low |
| funding_inr | INTEGER | Funding in INR |
| valuation_usd | INTEGER | Valuation in USD |
| founded_year | INTEGER | Year founded |
| employee_count | INTEGER | Team size |
| unicorn_status | TEXT | unicorn / null |
| is_women_led | INTEGER | 0/1 flag |
| is_rural_impact | INTEGER | 0/1 flag |
| dpiit_recognized | INTEGER | 0/1 flag |
| ... | ... | ... |

### entities_rtree (spatial index)
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | FK to entities |
| min_lng, max_lng | REAL | Longitude bounds |
| min_lat, max_lat | REAL | Latitude bounds |

## Deployment Options

### Option 1: Docker Compose (Recommended)
```bash
docker-compose up -d
# Access: http://localhost
```

Services: app (FastAPI), redis (cache), nginx (proxy), scheduler (ETL)

### Option 2: systemd Service (Production Linux)
```bash
sudo cp systemd/bharat-tech-atlas.service /etc/systemd/system/
sudo systemctl enable --now bharat-tech-atlas
```

### Option 3: Direct Python
```bash
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 7860
```

## Environment Variables

See `.env.example` for full configuration. Key variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| REDIS_URL | - | Redis caching (optional) |
| GOOGLE_MAPS_API_KEY | - | Precise geocoding |
| SECRET_KEY | - | Session/security |
| ENV | development | runtime mode |

## CI/CD Pipeline

```
Git Push → GitHub Actions
  ├── test-backend (Python 3.11, 3.12)
  ├── test-frontend (Node 20)
  ├── docker-build + healthcheck
  ├── deploy-staging (on main)
  └── deploy-production (manual gate)
```

## Data Sources

| Source | Type | Update Frequency | Status |
|--------|------|-------------------|--------|
| DPIIT | Government | Weekly | Configured |
| Startup India | Government | Weekly | Live ETL ready |
| Tracxn | Commercial | Daily | Configured |
| Crunchbase | Commercial | Daily | Configured |
| Nominatim | Open Source | On-demand | Geocoding |

## Cache Architecture

```
┌────────────────────────────────────────┐
│         CACHE LAYER                    │
│  ┌──────────┐ ┌──────────┐            │
│  │ entity   │ │ search   │  TTL: 5min  │
│  │ 50K max  │ │ 10K max  │             │
│  └──────────┘ └──────────┘            │
│  ┌──────────┐ ┌──────────┐            │
│  │ ml       │ │ facet    │  TTL: 2min  │
│  │ 5K max   │ │ 5K max   │             │
│  └──────────┘ └──────────┘            │
│                                        │
│  REDIS_URL set → Redis backend        │
│  REDIS_URL unset → Memory backend     │
│  One-line switch: export REDIS_URL=...│
└────────────────────────────────────────┘
```

## Security Features

- Rate limiting: 100/minute default, 30/minute search, 10/minute chat
- Input validation: Strict regex, SQL LIKE escaping, body size limits
- XSS prevention: Content Security Policy headers, chat sanitization
- SQL injection: Parameterized queries only
- CORS: Configured origin whitelist
- Audit logging: All requests logged with severity levels
- Systemd sandboxing: NoNewPrivileges, PrivateTmp, ProtectSystem

## Version History

| Version | Date | Features |
|---------|------|----------|
| 1.0 | 2024 | Basic map + startup data |
| 2.0 | 2024 | Unicorns, real data, heatmap |
| 3.0 | 2025 | ML, ETL, chat, MLOps |
| 3.3 | 2025 | Search agent, enrichment, API keys |
| 4.00.02 | 2025 | Cache, analytics, matching, live ETL, extended entities, CI/CD, deployment |
| 5.00.00 | Future | Global expansion, social media agents, xAI |

## License

MIT License — Bharat Tech Atlas
