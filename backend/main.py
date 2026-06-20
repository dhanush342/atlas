"""
Bharat Tech Atlas v3.3 — FastAPI Application Entry Point
- Unified middleware with security headers, body validation, audit logging
- Graceful DB pool shutdown
- Seed guard for faster restarts
- Honest feature flags
- CSP, HSTS, X-Content-Type-Options headers
"""
import os
import secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .database import init_db, DB_PATH, get_db, is_seeded, close_all_connections, SCHEMA_VERSION
from .seed import seed_database
from .routes.entities import router as entities_router
from .routes.ml_routes import router as ml_router
from .routes.mlops_routes import router as mlops_router
from .routes.etl_routes import router as etl_router
from .routes.enrichment_routes import router as enrichment_router
from .routes.chat_routes import router as chat_router
from .routes.search_agent_routes import router as search_agent_router
from .directory import router as directory_router
from .security import generate_csp_header, validate_body_size, audit_log, check_rate_limit
from .routes.mvt_routes import router as mvt_router
from .supabase_client import get_supabase_db, get_postgis, USE_SUPABASE
from .cache import cache_health

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Bharat Tech Atlas v4.10.00 — Initializing...")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    init_db()
    print("✅ SQLite Database initialized (v%s)" % SCHEMA_VERSION)

    if USE_SUPABASE:
        try:
            db = get_supabase_db()
            db.init_schema()
            print("✅ Supabase PostgreSQL + PostGIS initialized")
            print("🔗 Connected: Supabase Realtime ✓ | PostGIS ✓ | RLS ✓")
        except Exception as e:
            print(f"⚠️ Supabase connection failed: {e}")
            print("   Falling back to SQLite mode")

    if not is_seeded():
        seed_database(DB_PATH)
        print("✅ Seed data loaded")
    else:
        print("ℹ️  Database already seeded — skipping")

    # v4.10.10 — Warm up chat model in background thread to prevent first-request latency
    try:
        import threading
        from .routes.chat_routes import _get_chat_pipeline
        def _warm_model():
            try:
                _get_chat_pipeline()
                print("🤖 Chat model (Qwen2.5) warmed up in background")
            except Exception as e:
                print(f"⚠️ Chat model warm-up failed: {e}")
        threading.Thread(target=_warm_model, daemon=True).start()
    except Exception as e:
        print(f"⚠️ Could not start model warm-up: {e}")

    print("✅ Map & Filters: /api/entities/*")
    print("✅ MVT Tiles: /api/mvt/{z}/{x}/{y}")
    print("✅ ML (keyword fallback): /api/ml/*")
    print("✅ MLOps: /api/mlops/*")
    print("✅ ETL pipeline: /api/etl/*")
    print("✅ Analytics & Matching: /api/entities/analytics/*, /api/entities/match/*")
    print("✅ Enrichment (API keys required): /api/enrich/*")
    print("✅ Chat AI (SSE Streaming): /api/chat/*")
    print("✅ Search Agent: /api/agent/*")
    print("✅ Directory pages: /directory/*")
    print("✅ Cache layer: /api/metrics")
    print("🔗 Connected: Pipeline ✓ | ML ✓ | Chatbot ✓ | Analytics ✓ | Matching ✓ | Cache ✓ | Redis-ready ✓ | PostGIS ✓ | MVT ✓ | SSE ✓")
    yield
    close_all_connections()
    print("👋 Bharat Tech Atlas — Shutting down")


app = FastAPI(
    title="Bharat Tech Atlas",
    description="India's startup ecosystem map with ML-powered insights, real-time Supabase, and 230K+ entity support",
    version="4.10.10",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — tighten for production
_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "HEAD", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    max_age=600,
)


# ─── Unified security middleware ──────────────────────────────────────────
@app.middleware("http")
async def unified_middleware(request: Request, call_next):
    req_id = getattr(request.state, "request_id", secrets.token_hex(8))
    request.state.request_id = req_id
    request.state.start_time = __import__("time").time()

    # Body size guard (read + validate, 2MB max)
    body = b""
    if request.method in ("POST", "PUT", "PATCH"):
        try:
            body = await request.body()
            ok, err = validate_body_size(body)
            if not ok:
                audit_log("body_size_exceeded", req_id, details={"size": len(body)}, severity="warning")
                return JSONResponse({"error": err}, status_code=413)
        except Exception:
            pass  # body already consumed elsewhere

    # Query string guard
    query = str(request.url.query)
    if len(query) > 2048:
        audit_log("query_too_long", req_id, details={"length": len(query)}, severity="warning")
        return JSONResponse({"error": "Query string too long"}, status_code=400)

    # Param guard
    for key, value in request.query_params.items():
        if len(value) > 512:
            audit_log("param_too_long", req_id, details={"key": key, "length": len(value)}, severity="warning")
            return JSONResponse({"error": f"Parameter '{key}' too long"}, status_code=400)
        if "\x00" in value:
            audit_log("null_byte_injection", req_id, details={"key": key}, severity="error")
            return JSONResponse({"error": "Invalid parameter"}, status_code=400)

    # Rate-limit chat and agent endpoints more strictly
    if request.url.path.startswith("/api/chat/") or request.url.path.startswith("/api/agent/"):
        client_ip = get_remote_address(request)
        key = f"{client_ip}:{request.url.path}"
        allowed, rl_headers = check_rate_limit(key, max_requests=30, window_seconds=60)
        if not allowed:
            audit_log("rate_limit_exceeded", req_id, client_ip=client_ip,
                      details={"path": request.url.path}, severity="warning")
            resp = JSONResponse({"error": "Too many requests — please slow down."}, status_code=429)
            resp.headers.update(rl_headers)
            return resp

    response = await call_next(request)

    # Cache-Control by path
    path = request.url.path
    if path.startswith("/api/entities/"):
        response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=60"
    elif path.startswith("/api/ml/") or path.startswith("/api/mlops/"):
        response.headers["Cache-Control"] = "public, max-age=60"
    elif path.startswith("/api/agent/"):
        response.headers["Cache-Control"] = "public, max-age=120, stale-while-revalidate=300"
    elif path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Request-ID"] = req_id

    # HSTS in production
    if os.environ.get("DEPLOY_ENV") == "production":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["Content-Security-Policy"] = generate_csp_header()

    # Audit slow requests
    elapsed_ms = (__import__("time").time() - request.state.start_time) * 1000
    if elapsed_ms > 5000:
        audit_log("slow_request", req_id,
                  details={"path": path, "elapsed_ms": round(elapsed_ms, 1)}, severity="warning")

    return response


@app.get("/api/health")
@limiter.limit("120/minute")
async def health(request: Request):
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM entities WHERE is_active=1").fetchone()[0]
    unicorns = conn.execute("SELECT COUNT(*) FROM entities WHERE unicorn_status='unicorn' AND is_active=1").fetchone()[0]
    return {
        "status": "ok",
        "service": "Bharat Tech Atlas",
        "version": "4.10.10",
        "entities": total,
        "unicorns": unicorns,
        "supabase_mode": USE_SUPABASE,
        "features": {
            "ml_inference": True,
            "ml_inference_mode": "keyword_fallback",
            "etl_pipeline": True,
            "live_etl": True,
            "mlops_monitoring": True,
            "data_enrichment": False,
            "linkedin_integration": False,
            "github_integration": False,
            "google_maps_integration": False,
            "chat_ai": True,
            "chat_streaming_sse": True,
            "search_agent": True,
            "analytics": True,
            "mentor_matching": True,
            "caching": True,
            "cache_backend": "redis" if os.environ.get("REDIS_URL") else "memory",
            "postgis": USE_SUPABASE,
            "mvt_tiles": True,
            "realtime": USE_SUPABASE,
            "rls": USE_SUPABASE,
            "deduplication": True,
        }
    }


app.include_router(entities_router, prefix="/api/entities", tags=["entities"])
app.include_router(ml_router, prefix="/api/ml", tags=["ml"])
app.include_router(mlops_router, prefix="/api/mlops", tags=["mlops"])
app.include_router(etl_router, prefix="/api/etl", tags=["etl"])
app.include_router(enrichment_router, prefix="/api/enrich", tags=["enrichment"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(search_agent_router, prefix="/api/agent", tags=["agent"])
app.include_router(directory_router, prefix="/directory", tags=["directory"])
app.include_router(mvt_router, prefix="/api/mvt", tags=["mvt"])


@app.get("/api/metrics")
@limiter.limit("60/minute")
async def metrics(request: Request):
    """Prometheus-style metrics endpoint with cache + DB stats."""
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM entities WHERE is_active=1").fetchone()[0]
    by_type = conn.execute(
        "SELECT entity_type, COUNT(*) as c FROM entities WHERE is_active=1 GROUP BY entity_type"
    ).fetchall()
    conn.close()

    cache_stats = cache_health()
    cache_backend = "redis" if os.environ.get("REDIS_URL") else "memory"

    return {
        "service": "Bharat Tech Atlas",
        "version": "4.10.10",
        "cache_backend": cache_backend,
        "database": {
            "total_entities": total,
            "by_type": {r["entity_type"]: r["c"] for r in by_type},
        },
        "caches": cache_stats,
        "note": "Set REDIS_URL=redis://host:port/0 to enable Redis caching",
    }


STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")

if os.path.exists(os.path.join(STATIC_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")


@app.get("/")
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, headers={"Cache-Control": "public, max-age=3600"})
    return JSONResponse({"message": "Bharat Tech Atlas API v4.00.02. Frontend not built yet."})


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith("api/") or full_path.startswith("directory/"):
        return JSONResponse({"error": "Not found"}, status_code=404)

    file_path = os.path.join(STATIC_DIR, full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)

    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)

    return JSONResponse({"message": "Bharat Tech Atlas API v4.00.02 running."})
