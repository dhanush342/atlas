"""
Bharat Tech Atlas v4.00.02 — Ecosystem Analytics Engine
State & city breakdowns for startups, mentors, investors, incubators, accelerators, corporates, government bodies.

APIs:
    GET /api/entities/analytics/ecosystem — Full ecosystem breakdown by state
    GET /api/entities/analytics/top-states — Quick top states summary
"""
import logging
from typing import List, Dict, Optional
from .database import get_db
from .utils import row_to_dict

logger = logging.getLogger("bta.analytics")


def get_ecosystem_breakdown(
    entity_types: Optional[List[str]] = None,
    min_startups: int = 0,
) -> Dict:
    """
    Return full ecosystem breakdown by state and city.
    
    Args:
        entity_types: Filter by entity types (e.g., ['startup', 'mentor'])
        min_startups: Minimum number of startups for a state to be included
    
    Returns:
        {
            "states": [
                {
                    "state": "Karnataka",
                    "total": 1240,
                    "startups": 980,
                    "mentors": 85,
                    "investors": 42,
                    "incubators": 65,
                    "accelerators": 28,
                    "corporates": 25,
                    "government_bodies": 15,
                    "unicorns": 42,
                    "women_led": 120,
                    "top_cities": ["Bangalore", "Mysore", ...]
                }
            ],
            "total_nationwide": {...}
        }
    """
    conn = get_db()
    
    # Build filter for entity types
    type_filter = ""
    params = []
    if entity_types:
        placeholders = ",".join("?" * len(entity_types))
        type_filter = f" AND entity_type IN ({placeholders})"
        params = entity_types[:]
    
    # Query by state
    query = f"""
        SELECT 
            state,
            entity_type,
            COUNT(*) as count,
            SUM(CASE WHEN unicorn_status = 'unicorn' THEN 1 ELSE 0 END) as unicorns,
            SUM(CASE WHEN is_women_led = 1 THEN 1 ELSE 0 END) as women_led
        FROM entities
        WHERE is_active = 1 {type_filter}
        GROUP BY state, entity_type
        ORDER BY count DESC
    """
    
    rows = conn.execute(query, params).fetchall()
    
    # Aggregate by state
    states_data = {}
    nationwide = {
        "total": 0,
        "startups": 0,
        "mentors": 0,
        "investors": 0,
        "incubators": 0,
        "accelerators": 0,
        "corporates": 0,
        "government_bodies": 0,
        "unicorns": 0,
        "women_led": 0,
    }
    
    for row in rows:
        state = row["state"]
        entity_type = row["entity_type"]
        count = row["count"]
        unicorns = row["unicorns"] or 0
        women_led = row["women_led"] or 0
        
        if state not in states_data:
            states_data[state] = {
                "state": state,
                "total": 0,
                "startups": 0,
                "mentors": 0,
                "investors": 0,
                "incubators": 0,
                "accelerators": 0,
                "corporates": 0,
                "government_bodies": 0,
                "unicorns": 0,
                "women_led": 0,
                "top_cities": [],
            }
        
        states_data[state]["total"] += count
        states_data[state]["unicorns"] += unicorns
        states_data[state]["women_led"] += women_led
        
        nationwide["total"] += count
        nationwide["unicorns"] += unicorns
        nationwide["women_led"] += women_led
        
        # Map entity_type to our aggregation key
        if entity_type in nationwide:
            states_data[state][entity_type] += count
            nationwide[entity_type] += count
        elif entity_type in ["sme", "college_ecell"]:
            states_data[state]["startups"] += count  # Group SMEs under startups for simplicity
            nationwide["startups"] += count
        else:
            states_data[state]["startups"] += count
            nationwide["startups"] += count
    
    # Get top cities per state
    city_query = f"""
        SELECT state, city, COUNT(*) as count
        FROM entities
        WHERE is_active = 1 {type_filter}
        GROUP BY state, city
        ORDER BY count DESC
    """
    city_rows = conn.execute(city_query, params).fetchall()
    
    city_by_state = {}
    for row in city_rows:
        state = row["state"]
        city = row["city"]
        count = row["count"]
        if state not in city_by_state:
            city_by_state[state] = []
        city_by_state[state].append({"city": city, "count": count})
    
    for state, cities in city_by_state.items():
        if state in states_data:
            states_data[state]["top_cities"] = [c["city"] for c in cities[:5]]
    
    # Filter by minimum startups
    filtered_states = [
        s for s in states_data.values()
        if s["startups"] >= min_startups or s["total"] >= min_startups
    ]
    
    # Sort by total count descending
    filtered_states.sort(key=lambda x: x["total"], reverse=True)
    
    conn.close()
    
    return {
        "states": filtered_states,
        "total_nationwide": nationwide,
        "count": len(filtered_states),
    }


def get_top_states(limit: int = 10) -> List[Dict]:
    """Quick summary of top states by ecosystem strength."""
    conn = get_db()
    
    query = """
        SELECT 
            state,
            COUNT(*) as total,
            SUM(CASE WHEN entity_type = 'startup' THEN 1 ELSE 0 END) as startups,
            SUM(CASE WHEN unicorn_status = 'unicorn' THEN 1 ELSE 0 END) as unicorns,
            SUM(CASE WHEN is_women_led = 1 THEN 1 ELSE 0 END) as women_led
        FROM entities
        WHERE is_active = 1
        GROUP BY state
        ORDER BY total DESC
        LIMIT ?
    """
    
    rows = conn.execute(query, (limit,)).fetchall()
    conn.close()
    
    return [
        {
            "state": row["state"],
            "total": row["total"],
            "startups": row["startups"] or 0,
            "unicorns": row["unicorns"] or 0,
            "women_led": row["women_led"] or 0,
        }
        for row in rows
    ]


def get_state_detail(state: str) -> Dict:
    """Detailed breakdown for a single state."""
    conn = get_db()
    
    # Overall stats
    query = """
        SELECT 
            entity_type,
            COUNT(*) as count,
            SUM(CASE WHEN unicorn_status = 'unicorn' THEN 1 ELSE 0 END) as unicorns,
            SUM(CASE WHEN is_women_led = 1 THEN 1 ELSE 0 END) as women_led,
            SUM(CASE WHEN dpiit_recognized = 1 THEN 1 ELSE 0 END) as dpiit
        FROM entities
        WHERE is_active = 1 AND state = ?
        GROUP BY entity_type
    """
    
    rows = conn.execute(query, (state,)).fetchall()
    
    breakdown = {}
    for row in rows:
        breakdown[row["entity_type"]] = {
            "count": row["count"],
            "unicorns": row["unicorns"] or 0,
            "women_led": row["women_led"] or 0,
            "dpiit": row["dpiit"] or 0,
        }
    
    # Top cities
    city_rows = conn.execute(
        """SELECT city, COUNT(*) as count FROM entities
           WHERE is_active = 1 AND state = ? GROUP BY city ORDER BY count DESC LIMIT 10""",
        (state,)
    ).fetchall()
    
    # Top sectors
    sector_rows = conn.execute(
        """SELECT sectors FROM entities WHERE is_active = 1 AND state = ?""",
        (state,)
    ).fetchall()
    
    import json
    sector_counts = {}
    for row in sector_rows:
        try:
            sectors = json.loads(row["sectors"])
            for s in sectors:
                sector_counts[s] = sector_counts.get(s, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass
    
    top_sectors = sorted(sector_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Funding stats
    funding_row = conn.execute(
        """SELECT SUM(funding_inr) as total, AVG(funding_inr) as avg,
                  COUNT(CASE WHEN funding_inr > 0 THEN 1 END) as funded_count
           FROM entities WHERE is_active = 1 AND state = ?""",
        (state,)
    ).fetchone()
    
    conn.close()
    
    return {
        "state": state,
        "entity_breakdown": breakdown,
        "top_cities": [{"city": r["city"], "count": r["count"]} for r in city_rows],
        "top_sectors": [{"sector": s, "count": c} for s, c in top_sectors],
        "funding": {
            "total_inr": funding_row["total"] or 0,
            "avg_inr": round(funding_row["avg"] or 0, 2),
            "funded_count": funding_row["funded_count"] or 0,
        },
    }
