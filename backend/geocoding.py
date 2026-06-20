"""
Bharat Tech Atlas v4.00.02 — Geocoding & Address Enrichment Service

Converts city/state names to precise lat/lng coordinates.
Supports multiple providers with fallback:
1. Nominatim (OpenStreetMap) — free, no API key
2. Google Maps (if API key provided)
3. Local coordinate cache (fastest)

Usage:
    from backend.geocoding import geocode_address, enrich_entity_location
    coords = geocode_address("Bangalore, Karnataka, India")
    # => {"lat": 12.9716, "lng": 77.5946, "source": "cache"}
"""
import json
import logging
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger("bta.geocoding")

# ─── Local Coordinate Cache (India's major startup cities) ───────────────────
INDIA_CITY_COORDS: Dict[str, Tuple[float, float]] = {
    # Tier 1
    "Bangalore": (12.9716, 77.5946), "Bengaluru": (12.9716, 77.5946),
    "Mumbai": (19.0760, 72.8777), "Bombay": (19.0760, 72.8777),
    "Delhi": (28.6139, 77.2090), "New Delhi": (28.6139, 77.2090),
    "Gurgaon": (28.4595, 77.0266), "Gurugram": (28.4595, 77.0266),
    "Noida": (28.5355, 77.3910),
    "Hyderabad": (17.3850, 78.4867),
    "Chennai": (13.0827, 80.2707), "Madras": (13.0827, 80.2707),
    "Pune": (18.5204, 73.8567),
    "Ahmedabad": (23.0225, 72.5714),
    "Kolkata": (22.5726, 88.3639), "Calcutta": (22.5726, 88.3639),
    # Tier 2
    "Kochi": (9.9312, 76.2673), "Cochin": (9.9312, 76.2673),
    "Jaipur": (26.9124, 75.7873),
    "Chandigarh": (30.7333, 76.7794),
    "Indore": (22.7196, 75.8577),
    "Coimbatore": (11.0168, 76.9558),
    "Surat": (21.1702, 72.8311),
    "Lucknow": (26.8467, 80.9462),
    "Bhubaneswar": (20.2961, 85.8245),
    "Thiruvananthapuram": (8.5241, 76.9366), "Trivandrum": (8.5241, 76.9366),
    "Nagpur": (21.1458, 79.0882),
    "Visakhapatnam": (17.6868, 83.2185), "Vizag": (17.6868, 83.2185),
    "Vadodara": (22.3072, 73.1812), "Baroda": (22.3072, 73.1812),
    "Mysore": (12.2958, 76.6394), "Mysuru": (12.2958, 76.6394),
    "Mangalore": (12.9141, 74.8560), "Mangaluru": (12.9141, 74.8560),
    "Guwahati": (26.1445, 91.7362),
    "Patna": (25.5941, 85.1376),
    "Ranchi": (23.3441, 85.3096),
    "Dehradun": (30.3165, 78.0322),
    "Raipur": (21.2514, 81.6296),
    "Vijayawada": (16.5062, 80.6480),
    "Madurai": (9.9252, 78.1198),
    "Jodhpur": (26.2389, 73.0243),
    "Goa": (15.2993, 74.1240), "Panaji": (15.4909, 73.8278),
    "Tiruchirappalli": (10.7905, 78.7047), "Trichy": (10.7905, 78.7047),
    "Hubli": (15.3647, 75.1240), "Hubballi": (15.3647, 75.1240),
    "Amritsar": (31.6340, 74.8723),
    "Warangal": (17.9784, 79.5941),
    "Agra": (27.1767, 78.0081),
    "Kanpur": (26.4499, 80.3319),
    "Varanasi": (25.3176, 82.9739),
    "Shillong": (25.5788, 91.8933),
    "Imphal": (24.8170, 93.9368),
    "Gangtok": (27.3316, 88.6138),
    "Shimla": (31.1048, 77.1734),
    "Ludhiana": (30.9010, 75.8573),
    "Bhopal": (23.2599, 77.4126),
    "Udaipur": (24.5854, 73.7125),
    "Aurangabad": (19.8762, 75.3433),
    "Rajkot": (22.3039, 70.8022),
    "Jammu": (32.7266, 74.8570),
    "Faridabad": (28.4089, 77.3178),
    "Mohali": (30.7046, 76.7179), "SAS Nagar": (30.7046, 76.7179),
    "Nashik": (19.9975, 73.7898),
    "Thane": (19.2183, 72.9781),
    "Navi Mumbai": (19.0330, 73.0297),
    "Gandhinagar": (23.2156, 72.6369),
    "Greater Noida": (28.4744, 77.5030),
    "Ghaziabad": (28.6692, 77.4538),
    "Meerut": (28.9845, 77.7064),
    "Dhanbad": (23.7957, 86.4304),
    "Allahabad": (25.4358, 81.8463), "Prayagraj": (25.4358, 81.8463),
    "Jabalpur": (23.1815, 79.9864),
    "Gwalior": (26.2183, 78.1828),
    "Srinagar": (34.0837, 74.7973),
    "Puducherry": (11.9416, 79.8083), "Pondicherry": (11.9416, 79.8083),
    "Itanagar": (27.0844, 93.6053),
    "Kohima": (25.6751, 94.1086),
    "Agartala": (23.8315, 91.2868),
    "Port Blair": (11.6234, 92.7265),
    "Silvassa": (20.2763, 73.0083),
    "Kavaratti": (10.5593, 72.6358),
    "Leh": (34.1526, 77.5770),
    "Kargil": (34.5539, 76.1349),
}

# State capitals for fallback
STATE_CAPITALS = {
    "Karnataka": "Bangalore", "Maharashtra": "Mumbai", "Delhi": "Delhi",
    "Tamil Nadu": "Chennai", "Telangana": "Hyderabad", "Gujarat": "Gandhinagar",
    "Kerala": "Thiruvananthapuram", "Rajasthan": "Jaipur", "Uttar Pradesh": "Lucknow",
    "West Bengal": "Kolkata", "Haryana": "Chandigarh", "Punjab": "Chandigarh",
    "Madhya Pradesh": "Bhopal", "Bihar": "Patna", "Odisha": "Bhubaneswar",
    "Assam": "Dispur", "Goa": "Panaji", "Andhra Pradesh": "Amaravati",
    "Chhattisgarh": "Raipur", "Jharkhand": "Ranchi", "Uttarakhand": "Dehradun",
    "Jammu & Kashmir": "Srinagar", "Himachal Pradesh": "Shimla", "Tripura": "Agartala",
    "Nagaland": "Kohima", "Mizoram": "Aizawl", "Manipur": "Imphal",
    "Meghalaya": "Shillong", "Sikkim": "Gangtok", "Arunachal Pradesh": "Itanagar",
}


@dataclass
class GeocodeResult:
    lat: float
    lng: float
    source: str
    address: Optional[str] = None
    confidence: str = "medium"  # high, medium, low


def geocode_address(
    city: str,
    state: str,
    country: str = "India",
    use_nominatim: bool = False,
    google_api_key: Optional[str] = None,
) -> GeocodeResult:
    """
    Geocode a city/state to precise lat/lng coordinates.
    
    Priority:
    1. Local cache (fastest, most reliable for India)
    2. Nominatim (if use_nominatim=True)
    3. State capital fallback (lowest confidence)
    """
    # 1. Check local cache by city name
    city_key = city.strip()
    if city_key in INDIA_CITY_COORDS:
        lat, lng = INDIA_CITY_COORDS[city_key]
        return GeocodeResult(lat=lat, lng=lng, source="cache", address=f"{city}, {state}", confidence="high")
    
    # Try alternate spellings
    for alt_name, coords in INDIA_CITY_COORDS.items():
        if alt_name.lower() == city_key.lower():
            return GeocodeResult(lat=coords[0], lng=coords[1], source="cache", address=f"{city}, {state}", confidence="high")
    
    # 2. Try Nominatim (OpenStreetMap)
    if use_nominatim:
        try:
            result = _nominatim_geocode(city, state, country)
            if result:
                return result
        except Exception as e:
            logger.warning(f"Nominatim geocoding failed for {city}: {e}")
    
    # 3. Try Google Maps (if API key provided)
    if google_api_key:
        try:
            result = _google_geocode(city, state, country, google_api_key)
            if result:
                return result
        except Exception as e:
            logger.warning(f"Google geocoding failed for {city}: {e}")
    
    # 4. Fallback to state capital
    state_capital = STATE_CAPITALS.get(state.strip())
    if state_capital and state_capital in INDIA_CITY_COORDS:
        lat, lng = INDIA_CITY_COORDS[state_capital]
        return GeocodeResult(
            lat=lat + 0.05, lng=lng + 0.05,  # Slight offset to avoid overlap
            source="state_capital_fallback",
            address=f"{state} (capital approximated)",
            confidence="low"
        )
    
    # 5. Ultimate fallback: approximate by state region
    region_coords = _get_region_approx(state)
    return GeocodeResult(
        lat=region_coords[0], lng=region_coords[1],
        source="region_approximation",
        address=f"{state} (region approximated)",
        confidence="low"
    )


def _nominatim_geocode(city: str, state: str, country: str) -> Optional[GeocodeResult]:
    """Use Nominatim (OpenStreetMap) for geocoding."""
    import urllib.request
    import urllib.parse
    
    query = urllib.parse.quote(f"{city}, {state}, {country}")
    url = f"https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=1"
    
    req = urllib.request.Request(url, headers={
        "User-Agent": "BharatTechAtlas/4.00.02 (contact@bharattechatlas.dev)"
    })
    
    with urllib.request.urlopen(req, timeout=10) as response:
        data = json.loads(response.read().decode())
        if data:
            result = data[0]
            return GeocodeResult(
                lat=float(result["lat"]),
                lng=float(result["lon"]),
                source="nominatim",
                address=result.get("display_name"),
                confidence="high" if result.get("importance", 0) > 0.5 else "medium"
            )
    return None


def _google_geocode(city: str, state: str, country: str, api_key: str) -> Optional[GeocodeResult]:
    """Use Google Maps Geocoding API."""
    import urllib.request
    import urllib.parse
    
    address = urllib.parse.quote(f"{city}, {state}, {country}")
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={api_key}"
    
    with urllib.request.urlopen(url, timeout=10) as response:
        data = json.loads(response.read().decode())
        if data.get("status") == "OK" and data["results"]:
            result = data["results"][0]
            loc = result["geometry"]["location"]
            return GeocodeResult(
                lat=loc["lat"], lng=loc["lng"],
                source="google_maps",
                address=result.get("formatted_address"),
                confidence="high" if result["geometry"]["location_type"] == "ROOFTOP" else "medium"
            )
    return None


def _get_region_approx(state: str) -> Tuple[float, float]:
    """Get approximate coordinates for a state region."""
    region_approx = {
        "North": (28.6, 77.2), "South": (12.9, 77.6),
        "East": (22.5, 88.3), "West": (19.0, 72.8),
        "Central": (23.2, 77.4), "Northeast": (26.1, 91.7),
    }
    
    state_regions = {
        "Karnataka": "South", "Maharashtra": "West", "Delhi": "North",
        "Tamil Nadu": "South", "Telangana": "South", "Gujarat": "West",
        "Kerala": "South", "Rajasthan": "West", "Uttar Pradesh": "North",
        "West Bengal": "East", "Haryana": "North", "Punjab": "North",
        "Madhya Pradesh": "Central", "Bihar": "East", "Odisha": "East",
        "Assam": "Northeast", "Goa": "West", "Andhra Pradesh": "South",
        "Chhattisgarh": "Central", "Jharkhand": "East", "Uttarakhand": "North",
        "Jammu & Kashmir": "North", "Himachal Pradesh": "North", "Tripura": "Northeast",
        "Nagaland": "Northeast", "Mizoram": "Northeast", "Manipur": "Northeast",
        "Meghalaya": "Northeast", "Sikkim": "Northeast", "Arunachal Pradesh": "Northeast",
        "Chandigarh": "North", "Puducherry": "South", "Andaman and Nicobar Islands": "East",
        "Dadra and Nagar Haveli": "West", "Daman and Diu": "West", "Lakshadweep": "South",
        "Ladakh": "North",
    }
    
    region = state_regions.get(state, "Central")
    return region_approx.get(region, (23.2, 77.4))


def enrich_entity_location(entity: dict) -> dict:
    """
    Enrich an entity dict with precise geocoded coordinates.
    
    Input: {"name": "...", "city": "Bangalore", "state": "Karnataka", ...}
    Output: {"name": "...", "city": "Bangalore", "state": "Karnataka", 
             "latitude": 12.9716, "longitude": 77.5946, 
             "address": "Bangalore, Karnataka", "geocode_confidence": "high", ...}
    """
    city = entity.get("city", "")
    state = entity.get("state", "")
    
    if not city or not state:
        return entity
    
    result = geocode_address(city, state)
    
    entity["latitude"] = result.lat
    entity["longitude"] = result.lng
    entity["address"] = result.address or f"{city}, {state}, India"
    entity["geocode_source"] = result.source
    entity["geocode_confidence"] = result.confidence
    
    return entity


def batch_geocode(entities: list) -> list:
    """Geocode a batch of entities efficiently."""
    enriched = []
    for entity in entities:
        enriched.append(enrich_entity_location(entity.copy()))
    return enriched
