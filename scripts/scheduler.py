"""
Bharat Tech Atlas v4.00.02 — ETL Scheduler Script
Run periodic ETL jobs, data refreshes, and cache warming.

Usage:
    python scripts/scheduler.py --run-etl
    python scripts/scheduler.py --warm-cache
    python scripts/scheduler.py --refresh-analytics
    python scripts/scheduler.py --run-all

Can also be run via cron:
    0 */6 * * * cd /path/to/app && python scripts/scheduler.py --run-all
"""
import argparse
import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("bta.scheduler")


async def run_etl_pipeline():
    """Run the full ETL pipeline."""
    from backend.etl.pipeline import ETLPipeline
    from backend.database import DB_PATH

    logger.info("Starting ETL pipeline...")
    pipeline = ETLPipeline({"db_path": DB_PATH})
    try:
        result = await pipeline.run()
        logger.info(f"ETL complete: {result}")
    except Exception as e:
        logger.error(f"ETL failed: {e}")


async def warm_cache():
    """Warm up caches by fetching popular endpoints."""
    import httpx

    logger.info("Warming cache...")
    endpoints = [
        "/api/health",
        "/api/entities/analytics/overview",
        "/api/entities/sectors",
        "/api/entities/facets",
    ]

    async with httpx.AsyncClient(base_url="http://localhost:7860") as client:
        for endpoint in endpoints:
            try:
                resp = await client.get(endpoint, timeout=30)
                logger.info(f"  {endpoint} -> {resp.status_code}")
            except Exception as e:
                logger.warning(f"  {endpoint} -> failed: {e}")

    logger.info("Cache warming complete")


async def refresh_analytics():
    """Refresh analytics materialized views (if any)."""
    from backend.database import get_db

    logger.info("Refreshing analytics...")
    conn = get_db()
    try:
        # Run a simple vacuum to optimize the database
        conn.execute("VACUUM")
        conn.execute("ANALYZE")
        logger.info("Analytics refresh complete (VACUUM + ANALYZE)")
    except Exception as e:
        logger.error(f"Analytics refresh failed: {e}")
    finally:
        conn.close()


async def run_all():
    """Run all scheduled tasks."""
    await run_etl_pipeline()
    await refresh_analytics()
    await warm_cache()
    logger.info("All scheduled tasks complete")


def main():
    parser = argparse.ArgumentParser(description="Bharat Tech Atlas Scheduler")
    parser.add_argument("--run-etl", action="store_true", help="Run ETL pipeline")
    parser.add_argument("--warm-cache", action="store_true", help="Warm caches")
    parser.add_argument("--refresh-analytics", action="store_true", help="Refresh analytics")
    parser.add_argument("--run-all", action="store_true", help="Run all tasks")
    args = parser.parse_args()

    if args.run_all:
        asyncio.run(run_all())
    elif args.run_etl:
        asyncio.run(run_etl_pipeline())
    elif args.warm_cache:
        asyncio.run(warm_cache())
    elif args.refresh_analytics:
        asyncio.run(refresh_analytics())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
