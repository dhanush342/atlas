---
title: Bharat Tech Atlas
emoji: 🗺️
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
suggested_hardware: cpu-basic
tags:
- ml-intern
- startup-ecosystem
- real-time
- supabase
- postgis
---

# Bharat Tech Atlas v4.10.10

India's **real-time startup ecosystem map** with 230,000+ entity support, **Supabase PostgreSQL + PostGIS**, **Supabase Realtime WebSocket streaming**, **MVT vector tiles**, **SSE token-by-token chat AI**, and **ML-powered insights**.

> **Data disclaimer**: India has 223,000+ DPIIT-registered startups, 1,296+ mentors, 191+ investors, 1,396+ incubators, 225+ accelerators, 84+ corporates, and 80+ government bodies. This platform maps the entire ecosystem with real-time updates from Startup India.

---

## 🚀 What's New in v4.10.00

### Supabase Real-Time Data Layer
- **PostgreSQL + PostGIS** — GIST spatial index, `ST_AsMVT` vector tiles, `ST_DWithin` radius queries
- **Supabase Realtime** — WebSocket streaming for live entity inserts via `postgres_changes` events
- **Row-Level Security (RLS)** — Public read policy for active entities, service-role-only writes
- **Upsert with Deduplication** — `ON CONFLICT (slug)` with COALESCE field merging, `jellyfish` fuzzy matching pipeline

### High-Performance Map Rendering (230K+ Points)
- **Mapbox Vector Tiles (MVT)** — `GET /api/mvt/{z}/{x}/{y}` serves binary protobuf tiles (~4.5KB each vs 90MB GeoJSON)
- **Viewport Field Projection** — Minimalist schema: `id, slug, entity_type, latitude, longitude` only
- **Lazy Entity Detail** — Full profiles fetched via `GET /api/entities/detail/{slug}` only on click
- **Zoom-Level Clustering** — Server-side clusters at z0-6, client-side clusters at z7-11, individual points at z12+

### Real-Time Chat AI (SSE Streaming)
- **Server-Sent Events** — `POST /api/chat/stream` yields `{"type": "token", "text": "..."}` events
- **TextIteratorStreamer** — Non-blocking async token generation via `transformers.TextIteratorStreamer`
- **X-Accel-Buffering: no** — Disables nginx buffering for real-time SSE delivery
- **Web search integration** — DuckDuckGo results streamed into the response context

### Real-Time UI/UX
- **Live Toast Notifications** — `useLiveEntities()` hook shows 🚀 "New Startup in Bangalore" alerts
- **Fly-To Animation** — `map.flyTo({ center, zoom, duration: 1500 })` with easing
- **Real-Time Analytics** — Recharts panels update dynamically as new data arrives
- **Connection Status** — Green pulsing dot indicator for WebSocket health

### Extended Entity Types (10)
| Type | Count | Badge |
|------|-------|-------|
| Startup | 5,000+ | 🚀 |
| SME | 700+ | 🏢 |
| College E-Cell | 35+ | 🎓 |
| Incubator | 30+ | 🧪 |
| Accelerator | 10+ | ⚡ |
| Coworking | 5+ | 💼 |
| Investor | 20+ | 💰 |
| Mentor | 20+ | 🧠 |
| Corporate | 30+ | 🏛️ |
| Government Body | 20+ | 🏛️ |

### Production Infrastructure
- **Docker Compose** — `app` + `redis` + `nginx` + `scheduler` stack
- **nginx** — SSL, rate limiting, CSP headers, gzip, SPA fallback, Brotli
- **systemd** — Sandboxed service with `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem`
- **GitHub Actions CI/CD** — Test Python 3.11/3.12, build frontend, Docker healthcheck, deploy staging → production
- **.env.example** — Full configuration template with all API keys

---

## 🆕 What's New in v4.00.02

- **Pluggable Cache** — TTL+LRU in-memory, one-line Redis swap-in via `REDIS_URL`
- **Analytics Engine** — `/api/entities/analytics/ecosystem`, `/top-states`, `/state/{state}`
- **Mentor Matching** — Smart algorithm: same-state (+100), sector overlap (+50), unicorn (+40), women-led (+25)
- **Live ETL Extractor** — `backend/etl/live_extract.py` for Startup India portal scraping
- **Geocoding Service** — 55+ Indian cities with precise coordinates, Nominatim/Google fallback, jitter
- **Scheduler Script** — `scripts/scheduler.py` for ETL runs, cache warming, analytics refresh
- **Prometheus Metrics** — `/api/metrics` with cache + DB stats
- **Deduplication Pipeline** — `scripts/dedupe.py` with Jaro-Winkler and Levenshtein similarity

---

## 🏗️ Architecture

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
│                    Rate Limiting | SSL | Compression | Brotli                  │
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
│  │  │  SSE Stream  │  │  /api/agent/     │  │  TTL+LRU / Redis       │   │  │
│  │  └──────────────┘  └──────────────────┘  └────────────────────────┘   │  │
│  │  ┌──────────────┐  ┌──────────────────┐  ┌────────────────────────┐   │  │
│  │  │  MVT Tiles   │  │  Supabase Client │  │  Dedupe Pipeline     │   │  │
│  │  │  /api/mvt/   │  │  /supabase_client│  │  /scripts/dedupe     │   │  │
│  │  └──────────────┘  └──────────────────┘  └────────────────────────┘   │  │
│  │                                                                         │  │
│  │  ┌────────────────────────────────────────────────────────────────┐   │  │
│  │  │  Security Layer: Rate Limiting | CSP | RLS | Input Validation  │   │  │
│  │  └────────────────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
├────────────────────────────────────┼─────────────────────────────────────────┤
│                              DATA LAYER                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐    │
│  │ SQLite (local)   │  │ Supabase (cloud) │  │ R-Tree / PostGIS     │    │
│  │ bharattechatlas.db│  │ PostgreSQL + RLS   │  │ GIST spatial index   │    │
│  │ 5,000+ entities   │  │ 230,000+ capacity  │  │ MVT generation       │    │
│  └──────────────────┘  └──────────────────┘  └──────────────────────┘    │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐    │
│  │ Redis Cache       │  │ Seed Data        │  │ Live ETL Extract     │    │
│  │ (optional)        │  │ Real entities    │  │ Startup India API    │    │
│  └──────────────────┘  └──────────────────┘  └──────────────────────┘    │
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
│  │ SSL/CSP/Brotli│  │              │  │ script       │                      │
│  └──────────────┘  └──────────────┘  └──────────────┘                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📡 API Endpoints

### Core Map & Search
| Endpoint | Description |
|----------|-------------|
| `GET /api/entities` | List with filters (type, sector, state, stage) |
| `GET /api/entities/search?q=...` | Full-text search with smart ranking |
| `GET /api/entities/viewport/summary` | Map viewport clustering |
| `GET /api/entities/detail/:slug` | Full entity profile (lazy loaded) |
| `GET /api/mvt/{z}/{x}/{y}` | **Mapbox Vector Tiles** (binary protobuf) |
| `GET /api/mvt/health` | MVT service status |

### Analytics v4.00.02
| Endpoint | Description |
|----------|-------------|
| `GET /api/entities/analytics/ecosystem` | State/city ecosystem breakdown |
| `GET /api/entities/analytics/top-states?limit=10` | Top states by strength |
| `GET /api/entities/analytics/state/:state` | Detailed state breakdown |

### Matching v4.00.02
| Endpoint | Description |
|----------|-------------|
| `GET /api/entities/match/mentors?startup_slug=...` | Mentor-startup matching |
| `GET /api/entities/match/startups?investor_slug=...` | Investor-startup matching |

### Real-Time Chat v4.10.00
| Endpoint | Description |
|----------|-------------|
| `POST /api/chat/completions` | Blocking chat response |
| `POST /api/chat/stream` | **SSE streaming** (token-by-token) |
| `GET /api/chat/health` | Model status |

### ML & AI
| Endpoint | Description |
|----------|-------------|
| `POST /api/ml/predict` | Keyword-based sector prediction |
| `GET /api/ml/health` | Model health |
| `GET /api/mlops/metrics` | MLOps monitoring |

### ETL & Data
| Endpoint | Description |
|----------|-------------|
| `POST /api/etl/run` | Trigger ETL pipeline |
| `POST /api/etl/run/live` | Live Startup India extraction |
| `GET /api/etl/sources` | Data source info |

### Observability
| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Service health + feature flags |
| `GET /api/metrics` | Prometheus-style cache + DB stats |

---

## 🗄️ Database Schema

### PostgreSQL + PostGIS (Supabase)

```sql
-- Main entities table
CREATE TABLE entities (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    entity_type TEXT CHECK (entity_type IN ('startup', 'sme', 'college_ecell', 'incubator', 'accelerator', 'coworking', 'investor', 'mentor', 'corporate', 'government_body')),
    sectors JSONB,
    city TEXT, district TEXT, state TEXT,
    latitude REAL, longitude REAL,
    address TEXT,
    geom GEOMETRY(Point, 4326),  -- PostGIS
    funding_inr BIGINT,
    valuation_usd BIGINT,
    founded_year INTEGER,
    employee_count INTEGER,
    unicorn_status TEXT,
    is_women_led INTEGER DEFAULT 0,
    dpiit_recognized INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- GIST spatial index for fast viewport queries
CREATE INDEX entities_geom_idx ON entities USING GIST (geom);

-- Row-Level Security
ALTER TABLE entities ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read" ON entities FOR SELECT USING (is_active = 1);
CREATE POLICY "Restrict write to service role" ON entities FOR ALL TO service_role USING (true) WITH CHECK (true);
```

---

## 🚀 Quick Start

```bash
# 1. Backend
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 7860

# 2. Frontend
cd frontend && npm install && npm run dev

# 3. Verify
curl http://localhost:7860/api/health
curl http://localhost:7860/api/metrics
curl http://localhost:7860/api/mvt/5/16/10

# 4. Test
pytest tests/ -v

# 5. Docker (production)
docker-compose up -d
```

---

## ⚙️ Environment Variables

```bash
# Supabase (required for real-time mode)
SUPABASE_URL=https://empzzqlwsxlajgqmbkdp.supabase.co
SUPABASE_KEY=sb_publishable_...
SUPABASE_SERVICE_KEY=...
SUPABASE_DB_URL=postgresql://...
USE_SUPABASE=true

# Redis (optional)
REDIS_URL=redis://localhost:6379/0

# Google Maps (optional - precise geocoding)
GOOGLE_MAPS_API_KEY=...

# AI Models (optional)
HUGGINGFACE_API_KEY=...
OPENAI_API_KEY=...
GROQ_API_KEY=...

# Security
SECRET_KEY=change-this-in-production
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

---

## 📊 Data Sources

| Source | Type | Entities | Status |
|--------|------|----------|--------|
| DPIIT | Government | 222,561 startups | Configured |
| Startup India | Government | 1,296 mentors, 191 investors, 225 accelerators | Live ETL ready |
| Tracxn | Commercial | Funding, investors | Configured |
| Crunchbase | Commercial | Rounds, profiles | Configured |
| Nominatim | Open Source | Geocoding | Active |

---

## 🛡️ Security Features

- **Rate limiting**: 100/min default, 30/min search, 10/min chat, 200/min MVT
- **RLS**: Row-Level Security on Supabase (public read, service write)
- **CSP**: Content Security Policy headers with strict frame-ancestors
- **XSS prevention**: Output sanitization, no dangerousSetInnerHTML
- **SSRF prevention**: URL validation in geocoding
- **Input validation**: SQL injection prevention, query length limits, body size guards
- **Audit logging**: All requests with severity levels
- **systemd sandboxing**: NoNewPrivileges, PrivateTmp, ProtectSystem

---

## 📦 Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + Vite + MapLibre GL JS + Tailwind CSS + Recharts |
| Backend | FastAPI + slowapi + SQLAlchemy |
| Database | SQLite (local) / Supabase PostgreSQL + PostGIS (cloud) |
| Cache | In-memory TTL+LRU / Redis (optional) |
| ML | HuggingFace Transformers + ONNX Runtime |
| Real-Time | Supabase Realtime WebSocket + SSE |
| Tiles | PostGIS ST_AsMVT (Mapbox Vector Tiles) |
| CI/CD | GitHub Actions + Docker Compose + systemd |

---

## 📜 Version History

| Version | Features |
|---------|----------|
| 1.0 | Basic map + startup data |
| 2.0 | Unicorns, real data, heatmap |
| 3.0 | ML, ETL, chat, MLOps |
| 3.3 | Search agent, enrichment, API keys, security |
| 4.00.02 | Cache, analytics, matching, live ETL, geocoding, extended entities |
| **4.10.10** | **Supabase + PostGIS, Realtime WebSocket, MVT tiles, SSE streaming, RLS, dedup, Viewport 422 fix, Nationwide stats, Chat warm-up** |
| 5.00.00 | Global expansion, social media agents, xAI |

---

## 📄 License

MIT License — Bharat Tech Atlas

---

**Built for India's startup ecosystem. 🚀**
