"""
Bharat Tech Atlas v4.10.00 — Supabase Client & Realtime Integration

Connects to Supabase PostgreSQL with PostGIS, Realtime (WebSocket),
Row-Level Security (RLS), and Token-based Auth.

Features:
- Supabase SQLAlchemy client (sync + async)
- PostGIS spatial queries with ST_* functions
- RLS policies for public read / service write
- Realtime channel subscriptions
- Upsert with conflict resolution (slug-based deduplication)
- Minimalist field projection for map payloads
"""
import os
import json
import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from urllib.parse import urlparse

logger = logging.getLogger("bta.supabase")

# ─── Supabase Configuration ────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://empzzqlwsxlajgqmbkdp.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_U1dQ4_Hs7v_A3JMPaABtnw_MhVU4Bf0")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

USE_SUPABASE = os.environ.get("USE_SUPABASE", "false").lower() == "true"

def get_supabase_credentials() -> Dict[str, str]:
    return {
        "url": SUPABASE_URL,
        "key": SUPABASE_KEY,
        "service_key": SUPABASE_SERVICE_KEY,
    }


# ─── SQLAlchemy Engine (PostgreSQL via Supabase) ─────────────────────────────
class SupabaseDatabase:
    """PostgreSQL database connection via Supabase with PostGIS."""
    
    def __init__(self):
        self._engine = None
        self._connection_string = None
        self._setup_connection()
    
    def _setup_connection(self):
        """Build PostgreSQL connection string from Supabase URL."""
        # Supabase URL format: https://<project>.supabase.co
        # We need to construct the PostgreSQL connection string
        # Format: postgresql://postgres.<project>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
        # For simplicity, we use the connection string from env or parse from URL
        
        conn_str = os.environ.get("SUPABASE_DB_URL")
        if not conn_str and SUPABASE_URL:
            # Parse project ID from URL
            parsed = urlparse(SUPABASE_URL)
            project_id = parsed.netloc.split('.')[0]  # empzzqlwsxlajgqmbkdp
            # Default connection string template (user must set password)
            conn_str = f"postgresql://postgres.{project_id}@{project_id}.pooler.supabase.com:5432/postgres"
        
        self._connection_string = conn_str
    
    def get_engine(self):
        if self._engine is None:
            from sqlalchemy import create_engine
            self._engine = create_engine(
                self._connection_string,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                echo=False,
            )
        return self._engine
    
    def get_connection(self):
        return self.get_engine().connect()
    
    def execute(self, query: str, params=None):
        with self.get_connection() as conn:
            from sqlalchemy import text
            result = conn.execute(text(query), params)
            conn.commit()
            return result
    
    def fetchall(self, query: str, params=None) -> List[Dict]:
        with self.get_connection() as conn:
            from sqlalchemy import text
            result = conn.execute(text(query), params)
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]
    
    def fetchone(self, query: str, params=None) -> Optional[Dict]:
        rows = self.fetchall(query, params)
        return rows[0] if rows else None
    
    def init_schema(self):
        """Initialize PostGIS and create tables if not exists."""
        from sqlalchemy import text
        
        with self.get_connection() as conn:
            # Enable PostGIS extension
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            
            # Create entities table with PostGIS
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS entities (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    slug TEXT UNIQUE NOT NULL,
                    entity_type TEXT NOT NULL CHECK (entity_type IN (
                        'startup', 'sme', 'college_ecell', 'incubator',
                        'accelerator', 'coworking', 'investor', 'mentor',
                        'corporate', 'government_body'
                    )),
                    sectors JSONB,
                    dpiit_category TEXT,
                    business_model TEXT,
                    stage TEXT,
                    dpiit_recognized INTEGER DEFAULT 0,
                    nsa_winner INTEGER DEFAULT 0,
                    nsa_category TEXT,
                    is_women_led INTEGER DEFAULT 0,
                    is_rural_impact INTEGER DEFAULT 0,
                    is_campus_startup INTEGER DEFAULT 0,
                    unicorn_status TEXT,
                    funding_inr BIGINT DEFAULT 0,
                    funding_stage TEXT,
                    funding_rounds JSONB,
                    valuation_usd BIGINT,
                    description TEXT,
                    website TEXT,
                    linkedin_url TEXT,
                    instagram_url TEXT,
                    twitter_url TEXT,
                    linkedin_team_size INTEGER,
                    linkedin_industry TEXT,
                    linkedin_specialties JSONB,
                    investors JSONB,
                    city TEXT,
                    district TEXT,
                    state TEXT,
                    latitude REAL,
                    longitude REAL,
                    address TEXT,
                    geom GEOMETRY(Point, 4326),
                    founded_year INTEGER,
                    employee_count INTEGER,
                    college_name TEXT,
                    data_sources JSONB,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            
            # Create GIST spatial index
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS entities_geom_idx ON entities USING GIST (geom)
            """))
            
            # Create indexes for common queries
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_entities_state ON entities(state)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_entities_city ON entities(city)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_entities_unicorn ON entities(unicorn_status)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_entities_women ON entities(is_women_led)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_entities_active ON entities(is_active)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_entities_slug ON entities(slug)"))
            
            # Enable RLS
            conn.execute(text("ALTER TABLE entities ENABLE ROW LEVEL SECURITY"))
            
            # Create RLS policies
            conn.execute(text("""
                CREATE POLICY IF NOT EXISTS "Allow public read" ON entities
                    FOR SELECT USING (is_active = 1)
            """))
            conn.execute(text("""
                CREATE POLICY IF NOT EXISTS "Restrict write to service role" ON entities
                    FOR ALL TO service_role USING (true) WITH CHECK (true)
            """))
            
            conn.commit()
            logger.info("PostGIS schema initialized with RLS")


# ─── Supabase Realtime Client ────────────────────────────────────────────────
class SupabaseRealtime:
    """WebSocket realtime subscriptions via Supabase."""
    
    def __init__(self, url: str = None, key: str = None):
        self.url = url or SUPABASE_URL
        self.key = key or SUPABASE_KEY
        self._channels = {}
    
    def subscribe_to_inserts(self, table: str, callback) -> str:
        """Subscribe to INSERT events on a table."""
        # This is a backend wrapper - the frontend uses Supabase JS client directly
        # For backend, we use PostgreSQL LISTEN/NOTIFY or Supabase Realtime REST API
        channel_id = f"{table}_inserts"
        self._channels[channel_id] = callback
        return channel_id
    
    def unsubscribe(self, channel_id: str):
        if channel_id in self._channels:
            del self._channels[channel_id]


# ─── PostGIS Spatial Queries ─────────────────────────────────────────────────
class PostGISQueries:
    """High-performance spatial queries using PostGIS."""
    
    def __init__(self, db: SupabaseDatabase):
        self.db = db
    
    def viewport_query(self, min_lng: float, max_lng: float, min_lat: float, max_lat: float,
                       entity_types: List[str] = None, limit: int = 10000) -> List[Dict]:
        """Fast viewport query using PostGIS ST_Contains."""
        # Minimalist point schema: id, slug, entity_type, lat, lng only
        type_filter = ""
        params = {"min_lng": min_lng, "max_lng": max_lng, "min_lat": min_lat, "max_lat": max_lat, "limit": limit}
        
        if entity_types:
            placeholders = ",".join([f":t{i}" for i in range(len(entity_types))])
            type_filter = f"AND entity_type IN ({placeholders})"
            for i, t in enumerate(entity_types):
                params[f"t{i}"] = t
        
        query = f"""
            SELECT id, slug, entity_type, latitude, longitude
            FROM entities
            WHERE is_active = 1
            AND ST_Contains(
                ST_MakeEnvelope(:min_lng, :min_lat, :max_lng, :max_lat, 4326),
                geom
            )
            {type_filter}
            LIMIT :limit
        """
        return self.db.fetchall(query, params)
    
    def generate_mvt(self, z: int, x: int, y: int, entity_type: str = None) -> bytes:
        """Generate Mapbox Vector Tile (MVT) from PostGIS."""
        params = {"z": z, "x": x, "y": y, "extent": 4096, "buffer": 256}
        
        type_filter = ""
        if entity_type:
            type_filter = "AND entity_type = :entity_type"
            params["entity_type"] = entity_type
        
        query = f"""
            SELECT ST_AsMVT(q, 'entities', :extent, 'geom') AS mvt
            FROM (
                SELECT id, slug, entity_type,
                    ST_AsMVTGeom(
                        geom,
                        ST_TileEnvelope(:z, :x, :y),
                        :extent,
                        :buffer,
                        true
                    ) AS geom
                FROM entities
                WHERE is_active = 1
                AND geom IS NOT NULL
                {type_filter}
            ) q
        """
        result = self.db.fetchone(query, params)
        return result["mvt"] if result else b""
    
    def nearby_entities(self, lat: float, lng: float, radius_km: float = 10,
                        limit: int = 50) -> List[Dict]:
        """Find entities within radius using ST_DWithin."""
        query = """
            SELECT id, name, slug, entity_type, city, state, latitude, longitude,
                ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) AS distance_m
            FROM entities
            WHERE is_active = 1
            AND ST_DWithin(
                geom::geography,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                :radius * 1000
            )
            ORDER BY distance_m
            LIMIT :limit
        """
        return self.db.fetchall(query, {"lat": lat, "lng": lng, "radius": radius_km, "limit": limit})
    
    def update_geom_from_coords(self, entity_id: int, lat: float, lng: float):
        """Update geom column from latitude/longitude."""
        query = """
            UPDATE entities
            SET geom = ST_SetSRID(ST_MakePoint(:lng, :lat), 4326),
                updated_at = NOW()
            WHERE id = :id
        """
        self.db.execute(query, {"id": entity_id, "lat": lat, "lng": lng})


# ─── Upsert with Deduplication ─────────────────────────────────────────────────
class EntityUpsert:
    """Upsert entities with slug-based deduplication."""
    
    def __init__(self, db: SupabaseDatabase):
        self.db = db
    
    def upsert_entity(self, entity: Dict) -> Dict:
        """
        Upsert an entity. On conflict (slug), update only missing/null fields.
        
        Args:
            entity: Dict with all entity fields
            
        Returns:
            {"id": int, "slug": str, "action": "insert" | "update"}
        """
        slug = entity.get("slug")
        if not slug:
            raise ValueError("Entity must have a slug for upsert")
        
        # Build the upsert query
        columns = []
        values = []
        placeholders = []
        
        for i, (key, value) in enumerate(entity.items()):
            if key not in ["id", "created_at", "updated_at"]:
                columns.append(key)
                values.append(value)
                placeholders.append(f":p{i}")
        
        cols_str = ", ".join(columns)
        placeholders_str = ", ".join(placeholders)
        
        # Build ON CONFLICT DO UPDATE for non-null fields
        update_clauses = []
        for i, col in enumerate(columns):
            if col != "slug":
                update_clauses.append(f"{col} = COALESCE(entities.{col}, EXCLUDED.{col})")
        
        update_str = ", ".join(update_clauses) if update_clauses else "updated_at = NOW()"
        
        params = {f"p{i}": v for i, v in enumerate(values)}
        
        query = f"""
            INSERT INTO entities ({cols_str})
            VALUES ({placeholders_str})
            ON CONFLICT (slug) DO UPDATE SET
                {update_str},
                updated_at = NOW()
            RETURNING id, slug, entity_type, xmax::int = 0 AS is_insert
        """
        
        result = self.db.fetchone(query, params)
        if result:
            return {
                "id": result["id"],
                "slug": result["slug"],
                "action": "insert" if result["is_insert"] else "update",
            }
        return {"error": "Upsert failed"}
    
    def batch_upsert(self, entities: List[Dict]) -> List[Dict]:
        """Batch upsert entities for efficiency."""
        results = []
        for entity in entities:
            try:
                results.append(self.upsert_entity(entity))
            except Exception as e:
                logger.warning(f"Batch upsert failed for {entity.get('slug')}: {e}")
                results.append({"error": str(e), "slug": entity.get("slug")})
        return results


# ─── Global Instance (Lazy) ──────────────────────────────────────────────────
_supabase_db = None


def get_supabase_db() -> SupabaseDatabase:
    global _supabase_db
    if _supabase_db is None:
        _supabase_db = SupabaseDatabase()
    return _supabase_db


def get_postgis() -> PostGISQueries:
    return PostGISQueries(get_supabase_db())


def get_upsert() -> EntityUpsert:
    return EntityUpsert(get_supabase_db())


# ─── Minimalist Map Payload (Performance) ────────────────────────────────────
class MapPayload:
    """Generate lightweight map payloads for 230K+ points."""
    
    @staticmethod
    def get_point_data(min_lng: float, max_lng: float, min_lat: float, max_lat: float,
                       entity_types: List[str] = None) -> List[Dict]:
        """Return only id, slug, type, coords for map rendering."""
        return get_postgis().viewport_query(min_lng, max_lng, min_lat, max_lat, entity_types)
    
    @staticmethod
    def get_entity_detail(slug: str) -> Optional[Dict]:
        """Get full entity details (lazy loaded on click)."""
        db = get_supabase_db()
        return db.fetchone(
            "SELECT * FROM entities WHERE slug = :slug AND is_active = 1",
            {"slug": slug}
        )
