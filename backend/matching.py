"""
Bharat Tech Atlas v4.00.02 — State Mentor Matching Algorithm
Intelligent matching of startups to mentors based on state, sector, and quality signals.

Features:
- Strong same-state preference (massive score boost)
- Sector expertise overlap scoring
- Quality signals: unicorn experience, funding track record, women-led preference
- Explainable results with clear reasons
- Flexible discovery mode (search mentors without a specific startup)
"""
import logging
from typing import List, Dict, Optional, Tuple
from .database import get_db
from .utils import row_to_dict
from .cache import search_cache

logger = logging.getLogger("bta.matching")


def _calculate_sector_overlap(startup_sectors: List[str], mentor_sectors: List[str]) -> Tuple[float, List[str]]:
    """Calculate overlap between startup and mentor sectors."""
    if not startup_sectors or not mentor_sectors:
        return 0.0, []
    
    startup_set = set(s.lower().strip() for s in startup_sectors)
    mentor_set = set(m.lower().strip() for m in mentor_sectors)
    
    overlap = startup_set & mentor_set
    total_unique = startup_set | mentor_set
    
    if not total_unique:
        return 0.0, []
    
    score = len(overlap) / len(total_unique)
    return score, list(overlap)


def _score_mentor(
    mentor: Dict,
    startup_state: str,
    startup_sectors: List[str],
    startup_stage: Optional[str],
    prefer_women_led: bool = False,
) -> Tuple[float, List[str]]:
    """
    Score a mentor against a startup. Returns (score, reasons).
    
    Scoring:
    - Same state: +100
    - Sector overlap (exact): +50 per match, scaled by overlap ratio
    - Adjacent state: +25
    - Unicorn experience: +40
    - High funding track record: +15
    - Women-led preference match: +25
    - DPIIT recognized: +8
    - Recent activity (2020+): +10
    """
    score = 0.0
    reasons = []
    
    mentor_state = mentor.get("state", "")
    mentor_sectors = mentor.get("sectors", [])
    if isinstance(mentor_sectors, str):
        import json
        try:
            mentor_sectors = json.loads(mentor_sectors)
        except:
            mentor_sectors = []
    
    # State matching
    if mentor_state and startup_state and mentor_state.lower() == startup_state.lower():
        score += 100
        reasons.append(f"Located in {mentor_state}")
    elif mentor_state and startup_state:
        # Check for adjacent states (common state pairs)
        adjacent = {
            "delhi": ["haryana", "uttar pradesh"],
            "haryana": ["delhi", "uttar pradesh"],
            "uttar pradesh": ["delhi", "haryana"],
            "karnataka": ["tamil nadu", "telangana", "andhra pradesh"],
            "tamil nadu": ["karnataka", "kerala", "andhra pradesh"],
            "telangana": ["karnataka", "andhra pradesh"],
            "maharashtra": ["gujarat", "madhya pradesh", "goa"],
            "gujarat": ["maharashtra", "rajasthan"],
            "rajasthan": ["gujarat", "haryana", "delhi"],
        }
        startup_state_lower = startup_state.lower()
        mentor_state_lower = mentor_state.lower()
        if mentor_state_lower in adjacent.get(startup_state_lower, []):
            score += 25
            reasons.append(f"Near {startup_state} ({mentor_state})")
    
    # Sector overlap
    if startup_sectors and mentor_sectors:
        overlap_score, overlaps = _calculate_sector_overlap(startup_sectors, mentor_sectors)
        if overlaps:
            score += 50 * overlap_score + (len(overlaps) * 10)
            reasons.append(f"Sector match: {', '.join(overlaps[:3])}")
    
    # Quality signals
    if mentor.get("unicorn_status") == "unicorn":
        score += 40
        reasons.append("Unicorn founder/leader")
    
    if mentor.get("funding_inr", 0) > 1000000000:  # > 100 Cr
        score += 15
        reasons.append("High funding experience")
    
    if prefer_women_led and mentor.get("is_women_led"):
        score += 25
        reasons.append("Women-led mentor")
    
    if mentor.get("dpiit_recognized"):
        score += 8
        reasons.append("DPIIT recognized")
    
    founded_year = mentor.get("founded_year")
    if founded_year and founded_year >= 2020:
        score += 10
        reasons.append("Recently active")
    
    return score, reasons


def match_mentors_for_startup(
    startup_slug: str,
    limit: int = 10,
    discovery_mode: bool = False,
    state: Optional[str] = None,
    sectors: Optional[List[str]] = None,
    prefer_women_led: bool = False,
) -> Dict:
    """
    Match mentors to a startup or find mentors by criteria.
    
    Args:
        startup_slug: Slug of the startup to match (if discovery_mode=False)
        limit: Max number of matches to return
        discovery_mode: If True, search mentors by state/sectors without a startup
        state: Filter by state (for discovery mode)
        sectors: Filter by sectors (for discovery mode)
        prefer_women_led: Prefer women-led mentors
    
    Returns:
        {
            "startup": "...",
            "startup_state": "...",
            "startup_sectors": [...],
            "matches": [
                {
                    "mentor": {...},
                    "score": 112.5,
                    "match_strength": "Excellent",
                    "reasons": [...]
                }
            ]
        }
    """
    conn = get_db()
    
    # Get startup info if not in discovery mode
    startup = None
    startup_state = state or ""
    startup_sectors = sectors or []
    
    if not discovery_mode:
        row = conn.execute(
            "SELECT * FROM entities WHERE slug = ? AND is_active = 1",
            (startup_slug,)
        ).fetchone()
        
        if not row:
            conn.close()
            return {
                "startup": startup_slug,
                "startup_state": "",
                "startup_sectors": [],
                "matches": [],
                "error": "Startup not found",
            }
        
        startup = row_to_dict(row)
        startup_state = startup.get("state", "")
        startup_sectors = startup.get("sectors", [])
        if isinstance(startup_sectors, str):
            import json
            try:
                startup_sectors = json.loads(startup_sectors)
            except:
                startup_sectors = []
    
    # Build mentor query
    query = """SELECT * FROM entities WHERE is_active = 1 AND (
        entity_type = 'mentor' OR entity_type = 'investor' OR 
        entity_type = 'incubator' OR entity_type = 'accelerator'
    )"""
    params = []
    
    if state:
        query += " AND state = ?"
        params.append(state)
    
    if sectors:
        # Filter mentors by sector overlap
        sector_conditions = []
        for s in sectors:
            sector_conditions.append("sectors LIKE ?")
            params.append(f"%{s}%")
        if sector_conditions:
            query += f" AND ({' OR '.join(sector_conditions)})"
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    # Score each mentor
    scored = []
    for row in rows:
        mentor = row_to_dict(row)
        score, reasons = _score_mentor(
            mentor, startup_state, startup_sectors,
            startup.get("stage") if startup else None,
            prefer_women_led=prefer_women_led,
        )
        
        if score > 0:
            scored.append((mentor, score, reasons))
    
    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)
    
    # Build response
    matches = []
    for mentor, score, reasons in scored[:limit]:
        strength = "Excellent" if score >= 100 else "Strong" if score >= 60 else "Good" if score >= 30 else "Moderate"
        matches.append({
            "mentor": mentor,
            "score": round(score, 1),
            "match_strength": strength,
            "reasons": reasons,
        })
    
    return {
        "startup": startup.get("name", startup_slug) if startup else None,
        "startup_state": startup_state,
        "startup_sectors": startup_sectors,
        "matches": matches,
        "total_available": len(scored),
    }


def match_startups_for_investor(
    investor_slug: str,
    limit: int = 10,
    state: Optional[str] = None,
    sectors: Optional[List[str]] = None,
    stage: Optional[str] = None,
    min_funding: float = 0,
) -> Dict:
    """
    Match startups to an investor based on criteria.
    
    This is the inverse of match_mentors_for_startup - helps investors find
    startups that match their investment thesis.
    """
    conn = get_db()
    
    # Get investor info
    row = conn.execute(
        "SELECT * FROM entities WHERE slug = ? AND is_active = 1",
        (investor_slug,)
    ).fetchone()
    
    if not row:
        conn.close()
        return {
            "investor": investor_slug,
            "matches": [],
            "error": "Investor not found",
        }
    
    investor = row_to_dict(row)
    investor_state = investor.get("state", "")
    investor_sectors = investor.get("sectors", [])
    if isinstance(investor_sectors, str):
        import json
        try:
            investor_sectors = json.loads(investor_sectors)
        except:
            investor_sectors = []
    
    # Build startup query
    query = "SELECT * FROM entities WHERE is_active = 1 AND entity_type = 'startup'"
    params = []
    
    if state or investor_state:
        target_state = state or investor_state
        query += " AND state = ?"
        params.append(target_state)
    
    if sectors or investor_sectors:
        target_sectors = sectors or investor_sectors
        sector_conditions = []
        for s in target_sectors:
            sector_conditions.append("sectors LIKE ?")
            params.append(f"%{s}%")
        if sector_conditions:
            query += f" AND ({' OR '.join(sector_conditions)})"
    
    if stage:
        query += " AND stage = ?"
        params.append(stage)
    
    if min_funding > 0:
        query += " AND funding_inr >= ?"
        params.append(min_funding)
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    # Score startups for this investor
    scored = []
    for row in rows:
        startup = row_to_dict(row)
        score, reasons = _score_mentor(
            startup, investor_state, investor_sectors, None, prefer_women_led=False
        )
        
        # Add startup-specific signals
        if startup.get("unicorn_status") == "unicorn":
            score += 40
            reasons.append("Unicorn startup")
        if startup.get("is_women_led"):
            score += 25
            reasons.append("Women-led startup")
        if startup.get("dpiit_recognized"):
            score += 8
            reasons.append("DPIIT recognized")
        
        if score > 0:
            scored.append((startup, score, reasons))
    
    scored.sort(key=lambda x: x[1], reverse=True)
    
    matches = []
    for startup, score, reasons in scored[:limit]:
        strength = "Excellent" if score >= 100 else "Strong" if score >= 60 else "Good"
        matches.append({
            "startup": startup,
            "score": round(score, 1),
            "match_strength": strength,
            "reasons": reasons,
        })
    
    return {
        "investor": investor.get("name", investor_slug),
        "investor_state": investor_state,
        "investor_sectors": investor_sectors,
        "matches": matches,
        "total_available": len(scored),
    }
