"""
Bharat Tech Atlas v4.00.02 — Live ETL Extractor for Startup India
Respectful scraping with rate limiting and error handling.

Supports:
- Mentors
- Investors
- Incubators
- Accelerators
- Corporates
- Government Bodies

Usage:
    from backend.etl.live_extract import StartupIndiaLiveExtractor
    extractor = StartupIndiaLiveExtractor()
    results = await extractor.extract_all(roles=["mentor"], max_pages=2)
"""
import asyncio
import logging
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger("bta.etl.live")


@dataclass
class RawStartupRecord:
    """Standardized record from any source."""
    name: str
    entity_type: str
    city: str
    state: str
    sectors: List[str]
    description: str
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    latitude: float = 0.0
    longitude: float = 0.0
    founded_year: Optional[int] = None
    is_active: bool = True


class StartupIndiaLiveExtractor:
    """Extract data from Startup India portal with respectful rate limiting."""
    
    BASE_URL = "https://www.startupindia.gov.in/content/sih/en/search.html"
    
    ROLE_MAP = {
        "mentor": "Mentor",
        "investor": "Investor",
        "incubator": "Incubator",
        "accelerator": "Accelerator",
        "corporate": "Corporate",
        "government_body": "GovernmentBody",
    }
    
    def __init__(self, delay_seconds: float = 1.5, timeout: int = 30):
        self.delay = delay_seconds
        self.timeout = timeout
        self._session = None
    
    async def _get_session(self):
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession(
                headers={
                    "User-Agent": "BharatTechAtlas/4.00.02 (Research Bot; contact@bharattechatlas.dev)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            )
        return self._session
    
    async def _fetch_page(self, role: str, page: int) -> Optional[str]:
        """Fetch a single page of results."""
        await asyncio.sleep(self.delay)
        
        session = await self._get_session()
        role_param = self.ROLE_MAP.get(role, role)
        url = f"{self.BASE_URL}?roles={role_param}&page={page}"
        
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.text()
                elif resp.status == 429:
                    logger.warning(f"Rate limited on Startup India (role={role}, page={page}). Backing off...")
                    await asyncio.sleep(5)
                    return None
                else:
                    logger.warning(f"Startup India returned {resp.status} for {role} page {page}")
                    return None
        except Exception as e:
            logger.warning(f"Failed to fetch {role} page {page}: {e}")
            return None
    
    def _parse_html(self, html: str, role: str) -> List[RawStartupRecord]:
        """Parse HTML to extract records."""
        records = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            
            # Look for result cards - Startup India uses various class names
            cards = soup.find_all("div", class_=lambda x: x and ("result" in x.lower() or "card" in x.lower() or "item" in x.lower()))
            
            if not cards:
                # Try broader selectors
                cards = soup.find_all(["div", "article", "li"], class_=lambda x: x and ("search" in x.lower() if x else False))
            
            for card in cards[:20]:  # Max 20 per page
                try:
                    # Extract name
                    name_elem = (card.find("h3") or card.find("h2") or card.find("h4") or 
                                card.find("a", class_=lambda x: x and "title" in x.lower() if x else False))
                    name = name_elem.get_text(strip=True) if name_elem else "Unknown"
                    
                    # Extract location info
                    text = card.get_text(separator=" ", strip=True)
                    city, state = self._extract_location(text)
                    
                    # Extract description
                    desc_elem = card.find("p") or card.find("div", class_=lambda x: x and "desc" in x.lower() if x else False)
                    description = desc_elem.get_text(strip=True)[:500] if desc_elem else ""
                    
                    # Extract website
                    website = None
                    link = card.find("a", href=True)
                    if link and link["href"].startswith("http"):
                        website = link["href"]
                    
                    # Extract sectors from text
                    sectors = self._extract_sectors(text)
                    
                    # Get coordinates for known cities
                    lat, lng = self._get_city_coords(city, state)
                    
                    records.append(RawStartupRecord(
                        name=name,
                        entity_type=role,
                        city=city,
                        state=state,
                        sectors=sectors,
                        description=description,
                        website=website,
                        latitude=lat,
                        longitude=lng,
                    ))
                except Exception as e:
                    logger.debug(f"Failed to parse card: {e}")
                    continue
        except ImportError:
            logger.warning("beautifulsoup4 not installed. Install with: pip install beautifulsoup4")
        except Exception as e:
            logger.warning(f"HTML parsing failed: {e}")
        
        return records
    
    def _extract_location(self, text: str) -> Tuple[str, str]:
        """Extract city and state from text."""
        # Known cities and states mapping
        cities = {
            "Bangalore": "Karnataka", "Mumbai": "Maharashtra", "Delhi": "Delhi",
            "Gurgaon": "Haryana", "Noida": "Uttar Pradesh", "Hyderabad": "Telangana",
            "Chennai": "Tamil Nadu", "Pune": "Maharashtra", "Ahmedabad": "Gujarat",
            "Kolkata": "West Bengal", "Kochi": "Kerala", "Jaipur": "Rajasthan",
            "Chandigarh": "Chandigarh", "Indore": "Madhya Pradesh", "Coimbatore": "Tamil Nadu",
            "Surat": "Gujarat", "Lucknow": "Uttar Pradesh", "Bhubaneswar": "Odisha",
            "Thiruvananthapuram": "Kerala", "Nagpur": "Maharashtra", "Visakhapatnam": "Andhra Pradesh",
            "Vadodara": "Gujarat", "Mysore": "Karnataka", "Mangalore": "Karnataka",
            "Guwahati": "Assam", "Patna": "Bihar", "Ranchi": "Jharkhand",
            "Dehradun": "Uttarakhand", "Raipur": "Chhattisgarh", "Vijayawada": "Andhra Pradesh",
            "Madurai": "Tamil Nadu", "Jodhpur": "Rajasthan", "Goa": "Goa",
            "Tiruchirappalli": "Tamil Nadu", "Hubli": "Karnataka", "Amritsar": "Punjab",
            "Warangal": "Telangana", "Agra": "Uttar Pradesh", "Kanpur": "Uttar Pradesh",
            "Varanasi": "Uttar Pradesh", "Shillong": "Meghalaya", "Imphal": "Manipur",
            "Gangtok": "Sikkim", "Shimla": "Himachal Pradesh", "Ludhiana": "Punjab",
            "Bhopal": "Madhya Pradesh", "Udaipur": "Rajasthan", "Aurangabad": "Maharashtra",
            "Rajkot": "Gujarat", "Jammu": "Jammu & Kashmir", "Faridabad": "Haryana",
            "Mohali": "Punjab", "Nashik": "Maharashtra", "Thane": "Maharashtra",
            "Navi Mumbai": "Maharashtra", "Gandhinagar": "Gujarat",
        }
        
        text_lower = text.lower()
        for city, state in cities.items():
            if city.lower() in text_lower:
                return city, state
        
        # Check for state names alone
        states = ["Karnataka", "Maharashtra", "Delhi", "Tamil Nadu", "Telangana",
                 "Gujarat", "Kerala", "Rajasthan", "Uttar Pradesh", "West Bengal",
                 "Haryana", "Punjab", "Madhya Pradesh", "Bihar", "Odisha", "Assam",
                 "Goa", "Andhra Pradesh", "Chhattisgarh", "Jharkhand", "Uttarakhand",
                 "Jammu & Kashmir", "Chandigarh", "Meghalaya", "Manipur", "Sikkim",
                 "Himachal Pradesh", "Tripura", "Nagaland", "Mizoram", "Arunachal Pradesh"]
        for state in states:
            if state.lower() in text_lower:
                return "Unknown", state
        
        return "Unknown", "Unknown"
    
    def _extract_sectors(self, text: str) -> List[str]:
        """Extract industry/sector mentions from text."""
        text_lower = text.lower()
        sector_keywords = {
            "fintech": ["fintech", "financial", "payments", "banking", "lending"],
            "saas": ["saas", "software", "cloud", "enterprise software"],
            "ecommerce": ["ecommerce", "e-commerce", "retail", "marketplace"],
            "healthcare": ["healthcare", "health", "medical", "pharma"],
            "edtech": ["edtech", "education", "learning", "training"],
            "agritech": ["agritech", "agriculture", "farming", "crop"],
            "ai_ml": ["ai", "artificial intelligence", "machine learning", "ml"],
            "cleantech": ["cleantech", "clean energy", "renewable", "solar"],
            "logistics": ["logistics", "supply chain", "delivery", "transport"],
            "foodtech": ["foodtech", "food", "restaurant", "kitchen"],
            "proptech": ["proptech", "real estate", "property", "construction"],
            "biotech": ["biotech", "biotechnology", "genomics", "life sciences"],
            "gaming": ["gaming", "games", "esports", "entertainment"],
            "cybersecurity": ["cybersecurity", "security", "privacy", "encryption"],
            "mobility": ["mobility", "transportation", "ride", "vehicle"],
            "social_impact": ["social impact", "ngo", "non-profit", "community"],
        }
        
        found = []
        for sector, keywords in sector_keywords.items():
            if any(kw in text_lower for kw in keywords):
                found.append(sector)
        
        return found[:3] if found else ["other"]
    
    def _get_city_coords(self, city: str, state: str) -> Tuple[float, float]:
        """Get approximate coordinates for known cities."""
        coords = {
            "Bangalore": (12.9716, 77.5946), "Mumbai": (19.076, 72.8777),
            "Delhi": (28.6139, 77.209), "Gurgaon": (28.4595, 77.0266),
            "Noida": (28.5355, 77.391), "Hyderabad": (17.385, 78.4867),
            "Chennai": (13.0827, 80.2707), "Pune": (18.5204, 73.8567),
            "Ahmedabad": (23.0225, 72.5714), "Kolkata": (22.5726, 88.3639),
            "Kochi": (9.9312, 76.2673), "Jaipur": (26.9124, 75.7873),
            "Chandigarh": (30.7333, 76.7794), "Indore": (22.7196, 75.8577),
            "Coimbatore": (11.0168, 76.9558), "Surat": (21.1702, 72.8311),
            "Lucknow": (26.8467, 80.9462), "Bhubaneswar": (20.2961, 85.8245),
        }
        return coords.get(city, (0.0, 0.0))
    
    async def extract_role(self, role: str, max_pages: int = 2) -> List[RawStartupRecord]:
        """Extract all records for a single role."""
        all_records = []
        for page in range(max_pages):
            html = await self._fetch_page(role, page)
            if html is None:
                continue
            records = self._parse_html(html, role)
            all_records.extend(records)
            logger.info(f"Extracted {len(records)} {role} records from page {page}")
        return all_records
    
    async def extract_all(
        self,
        roles: Optional[List[str]] = None,
        max_pages: int = 2,
    ) -> Dict[str, List[RawStartupRecord]]:
        """Extract records for all requested roles."""
        if roles is None:
            roles = list(self.ROLE_MAP.keys())
        
        results = {}
        for role in roles:
            logger.info(f"Starting extraction for role: {role}")
            records = await self.extract_role(role, max_pages)
            results[role] = records
            logger.info(f"Completed {role}: {len(records)} records")
        
        return results
    
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None
