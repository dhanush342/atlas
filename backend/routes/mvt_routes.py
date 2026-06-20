"""
Bharat Tech Atlas v4.10.00 — Mapbox Vector Tile (MVT) Server

Serves PostGIS-generated MVT tiles for 230K+ point rendering.
Endpoint: GET /api/mvt/{z}/{x}/{y}?entity_type=startup

Protocol: Z/X/Y standard slippy map tile format.
Content-Type: application/x-protobuf

Benefits:
- Only downloads visible tiles (~4.5KB each vs 90MB GeoJSON)
- Binary Protocol Buffers format (smaller than JSON)
- PostGIS ST_AsMVT handles clipping and simplification
"""
import io
import logging
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from typing import Optional

from ..supabase_client import get_postgis
from ..security import check_rate_limit, audit_log
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger("bta.mvt")
router = APIRouter(prefix="/api/mvt", tags=["mvt"])

limiter = Limiter(key_func=get_remote_address)


@router.get("/{z}/{x}/{y}")
@limiter.limit("200/minute")
async def get_mvt_tile(
    request: Request,
    z: int, x: int, y: int,
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
):
    """
    Serve a Mapbox Vector Tile for a given Z/X/Y tile coordinate.
    
    Args:
        z: Zoom level (0-14)
        x: Tile X coordinate
        y: Tile Y coordinate
        entity_type: Optional filter (startup, mentor, investor, etc.)
    
    Returns:
        Binary MVT payload (application/x-protobuf)
    """
    req_id = getattr(request.state, "request_id", "unknown")
    
    # Validate zoom level
    if z < 0 or z > 14:
        raise HTTPException(status_code=400, detail="Zoom level must be 0-14")
    
    try:
        postgis = get_postgis()
        mvt_bytes = postgis.generate_mvt(z, x, y, entity_type)
        
        if not mvt_bytes:
            # Empty tile - return 204 or minimal valid MVT
            return Response(
                content=b"",
                media_type="application/x-protobuf",
                headers={"X-Empty-Tile": "true"}
            )
        
        audit_log("mvt_tile", req_id,
                  details={"z": z, "x": x, "y": y, "type": entity_type, "size": len(mvt_bytes)},
                  severity="info")
        
        return Response(
            content=bytes(mvt_bytes) if isinstance(mvt_bytes, memoryview) else mvt_bytes,
            media_type="application/x-protobuf",
            headers={
                "Cache-Control": "public, max-age=86400",
                "Content-Encoding": "identity",
                "X-Tile-Z": str(z),
                "X-Tile-Count": "1",
            }
        )
    
    except Exception as e:
        logger.error(f"MVT generation failed for {z}/{x}/{y}: {e}")
        raise HTTPException(status_code=500, detail="MVT generation failed")


@router.get("/health")
@limiter.limit("60/minute")
async def mvt_health(request: Request):
    """MVT service health check."""
    return {
        "status": "ok",
        "service": "MVT Tile Server",
        "version": "4.10.10",
        "format": "Mapbox Vector Tile (MVT)",
        "encoding": "Protocol Buffers",
        "content_type": "application/x-protobuf",
        "max_zoom": 14,
    }
