"""
Geographic scoring for job-resume matching based on location preferences
"""

import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from geopy.distance import geodesic
from geopy.geocoders import Nominatim

logger = logging.getLogger(__name__)


@dataclass
class Location:
    """Container for location data"""

    city: Optional[str]
    state: Optional[str]
    country: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    formatted_address: Optional[str]


@dataclass
class GeoScore:
    """Container for geographic scoring results"""

    distance_km: float
    distance_miles: float
    is_remote: bool
    is_hybrid: bool
    location_match: bool  # Same city/metro area
    score: float  # Normalized 0-1 score


class GeoScorer:
    """Score job-resume matches based on geographic factors"""

    def __init__(
        self, geocoder_user_agent: str = "career-jobs-app", cache_geocoding: bool = True
    ):
        """
        Initialize geographic scorer

        Args:
            geocoder_user_agent: User agent for geocoding service
            cache_geocoding: Whether to cache geocoding results
        """
        self.geocoder = Nominatim(user_agent=geocoder_user_agent)
        self.geocoding_cache: Dict[str, Location] = {} if cache_geocoding else None

        # Distance thresholds for scoring (in km)
        self.SAME_CITY_THRESHOLD = 25  # ~15 miles
        self.COMMUTABLE_THRESHOLD = 80  # ~50 miles
        self.REGIONAL_THRESHOLD = 160  # ~100 miles
        self.MAX_PREFERRED_DISTANCE = 500  # ~310 miles

    def parse_location_string(self, location_str: str) -> Location:
        """
        Parse a location string into structured format

        Args:
            location_str: Location string (e.g., "San Francisco, CA, USA")

        Returns:
            Location object with parsed components
        """
        if not location_str:
            return Location(None, None, None, None, None, None)

        # Check for remote indicators
        location_lower = location_str.lower()
        if any(
            term in location_lower for term in ["remote", "anywhere", "distributed"]
        ):
            return Location(
                city="Remote",
                state=None,
                country=None,
                latitude=None,
                longitude=None,
                formatted_address="Remote",
            )

        # Parse location components
        parts = [p.strip() for p in location_str.split(",")]

        city = parts[0] if len(parts) > 0 else None
        state = parts[1] if len(parts) > 1 else None
        country = parts[2] if len(parts) > 2 else "USA"  # Default to USA

        # Handle common abbreviations
        if state:
            state = self._normalize_state(state)

        return Location(
            city=city,
            state=state,
            country=country,
            latitude=None,
            longitude=None,
            formatted_address=location_str,
        )

    def _normalize_state(self, state: str) -> str:
        """Normalize state abbreviations and names"""
        state = state.strip().upper()

        # Common US state abbreviations
        us_states = {
            "CALIFORNIA": "CA",
            "NEW YORK": "NY",
            "TEXAS": "TX",
            "FLORIDA": "FL",
            "ILLINOIS": "IL",
            "PENNSYLVANIA": "PA",
            "OHIO": "OH",
            "GEORGIA": "GA",
            "NORTH CAROLINA": "NC",
            "MICHIGAN": "MI",
            "NEW JERSEY": "NJ",
            "VIRGINIA": "VA",
            "WASHINGTON": "WA",
            "ARIZONA": "AZ",
            "MASSACHUSETTS": "MA",
            "TENNESSEE": "TN",
            "INDIANA": "IN",
            "MISSOURI": "MO",
            "MARYLAND": "MD",
            "WISCONSIN": "WI",
            "COLORADO": "CO",
            "MINNESOTA": "MN",
            "SOUTH CAROLINA": "SC",
            "ALABAMA": "AL",
            "LOUISIANA": "LA",
            "KENTUCKY": "KY",
            "OREGON": "OR",
            "OKLAHOMA": "OK",
            "CONNECTICUT": "CT",
            "UTAH": "UT",
            "IOWA": "IA",
            "NEVADA": "NV",
            "ARKANSAS": "AR",
            "MISSISSIPPI": "MS",
            "KANSAS": "KS",
            "NEW MEXICO": "NM",
            "NEBRASKA": "NE",
            "IDAHO": "ID",
            "WEST VIRGINIA": "WV",
            "HAWAII": "HI",
            "NEW HAMPSHIRE": "NH",
            "MAINE": "ME",
            "RHODE ISLAND": "RI",
            "MONTANA": "MT",
            "DELAWARE": "DE",
            "SOUTH DAKOTA": "SD",
            "NORTH DAKOTA": "ND",
            "ALASKA": "AK",
            "VERMONT": "VT",
            "WYOMING": "WY",
        }

        # If it's a full state name, convert to abbreviation
        if state in us_states:
            return us_states[state]

        # If it's already an abbreviation, return as is
        if len(state) == 2:
            return state

        return state

    def geocode_location(self, location: Location) -> Location:
        """
        Get coordinates for a location using geocoding

        Args:
            location: Location object to geocode

        Returns:
            Location object with coordinates filled in
        """
        # TEMPORARILY DISABLED: Geocoding service is unavailable
        # Return location without coordinates to use default scoring
        # TODO: Re-enable when OpenStreetMap service is available or implement alternative geocoding
        return location

    def calculate_distance(self, loc1: Location, loc2: Location) -> Tuple[float, float]:
        """
        Calculate distance between two locations

        Args:
            loc1: First location
            loc2: Second location

        Returns:
            Tuple of (distance_km, distance_miles)
        """
        if not all([loc1.latitude, loc1.longitude, loc2.latitude, loc2.longitude]):
            return (float("inf"), float("inf"))

        coords1 = (loc1.latitude, loc1.longitude)
        coords2 = (loc2.latitude, loc2.longitude)

        distance_km = geodesic(coords1, coords2).kilometers
        distance_miles = geodesic(coords1, coords2).miles

        return (distance_km, distance_miles)

    def score_distance(self, distance_km: float) -> float:
        """
        Convert distance to a score (0-1, higher is better)

        Args:
            distance_km: Distance in kilometers

        Returns:
            Score between 0 and 1
        """
        if distance_km <= self.SAME_CITY_THRESHOLD:
            return 1.0  # Perfect score for same city
        elif distance_km <= self.COMMUTABLE_THRESHOLD:
            # Linear decay from 1.0 to 0.8
            return 1.0 - 0.2 * (distance_km - self.SAME_CITY_THRESHOLD) / (
                self.COMMUTABLE_THRESHOLD - self.SAME_CITY_THRESHOLD
            )
        elif distance_km <= self.REGIONAL_THRESHOLD:
            # Linear decay from 0.8 to 0.5
            return 0.8 - 0.3 * (distance_km - self.COMMUTABLE_THRESHOLD) / (
                self.REGIONAL_THRESHOLD - self.COMMUTABLE_THRESHOLD
            )
        elif distance_km <= self.MAX_PREFERRED_DISTANCE:
            # Linear decay from 0.5 to 0.2
            return 0.5 - 0.3 * (distance_km - self.REGIONAL_THRESHOLD) / (
                self.MAX_PREFERRED_DISTANCE - self.REGIONAL_THRESHOLD
            )
        else:
            # Exponential decay for very long distances
            return 0.2 * (0.5 ** ((distance_km - self.MAX_PREFERRED_DISTANCE) / 1000))

    def calculate_geo_score(
        self,
        resume_location: str,
        job_location: str,
        job_remote_type: Optional[str] = None,
        willing_to_relocate: bool = False,
    ) -> GeoScore:
        """
        Calculate geographic score for job-resume match

        Args:
            resume_location: Resume location string
            job_location: Job location string
            job_remote_type: Remote work type ('Remote', 'Hybrid', 'On Site')
            willing_to_relocate: Whether candidate is willing to relocate

        Returns:
            GeoScore with detailed location scoring
        """
        # Parse locations
        resume_loc = self.parse_location_string(resume_location)
        job_loc = self.parse_location_string(job_location)

        # Check for remote work
        is_remote = job_remote_type and job_remote_type.lower() == "remote"
        is_hybrid = job_remote_type and job_remote_type.lower() == "hybrid"

        # If job is fully remote, perfect score
        if is_remote or job_loc.city == "Remote":
            return GeoScore(
                distance_km=0,
                distance_miles=0,
                is_remote=True,
                is_hybrid=False,
                location_match=True,
                score=1.0,
            )

        # Geocode locations if needed
        resume_loc = self.geocode_location(resume_loc)
        job_loc = self.geocode_location(job_loc)

        # Calculate distance
        distance_km, distance_miles = self.calculate_distance(resume_loc, job_loc)

        # Check for same city/metro area
        location_match = distance_km <= self.SAME_CITY_THRESHOLD

        # Calculate base score
        base_score = self.score_distance(distance_km)

        # Apply modifiers
        if is_hybrid:
            # Hybrid gets a boost for longer distances
            if distance_km > self.COMMUTABLE_THRESHOLD:
                base_score = min(1.0, base_score + 0.2)

        if willing_to_relocate:
            # Willing to relocate reduces distance penalty
            base_score = min(1.0, base_score + 0.3)

        # Handle case where geocoding failed
        if distance_km == float("inf"):
            # Default to neutral score if we can't determine distance
            base_score = 0.5
            distance_km = -1
            distance_miles = -1

        return GeoScore(
            distance_km=distance_km,
            distance_miles=distance_miles,
            is_remote=is_remote,
            is_hybrid=is_hybrid,
            location_match=location_match,
            score=base_score,
        )

    def rank_locations_by_preference(
        self,
        resume_location: str,
        job_locations: List[Tuple[str, str]],  # List of (job_id, location)
        max_results: int = 10,
    ) -> List[Tuple[str, GeoScore]]:
        """
        Rank multiple job locations by geographic preference

        Args:
            resume_location: Resume location string
            job_locations: List of (job_id, location) tuples
            max_results: Maximum number of results to return

        Returns:
            Sorted list of (job_id, GeoScore) tuples
        """
        scored_locations = []

        for job_id, job_location in job_locations:
            geo_score = self.calculate_geo_score(resume_location, job_location)
            scored_locations.append((job_id, geo_score))

        # Sort by score (descending)
        scored_locations.sort(key=lambda x: x[1].score, reverse=True)

        return scored_locations[:max_results]

    def get_location_insights(self, geo_score: GeoScore) -> Dict[str, str]:
        """
        Get human-readable insights about location match

        Args:
            geo_score: Geographic score object

        Returns:
            Dictionary of insights
        """
        insights = {}

        if geo_score.is_remote:
            insights["match_type"] = "Remote Position"
            insights["commute"] = "No commute required"
        elif geo_score.location_match:
            insights["match_type"] = "Same City"
            insights["commute"] = "Short commute likely"
        elif geo_score.distance_km <= self.COMMUTABLE_THRESHOLD:
            insights["match_type"] = "Commutable Distance"
            insights["commute"] = f"~{geo_score.distance_miles:.0f} miles"
        elif geo_score.distance_km <= self.REGIONAL_THRESHOLD:
            insights["match_type"] = "Regional"
            insights["commute"] = "May require relocation or long commute"
        else:
            insights["match_type"] = "Different Region"
            insights["commute"] = "Relocation likely required"

        if geo_score.is_hybrid:
            insights["work_arrangement"] = "Hybrid (reduced commute frequency)"

        return insights
