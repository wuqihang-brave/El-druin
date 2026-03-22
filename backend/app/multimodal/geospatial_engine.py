"""Geospatial analysis and entity tracking engine."""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Coordinates:
    """Geographic coordinate pair.

    Attributes:
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.
    """

    lat: float
    lon: float


@dataclass
class LocationInfo:
    """Reverse-geocode result.

    Attributes:
        address: Full formatted address string.
        city: City or town name.
        country: Country name.
        country_code: ISO 3166-1 alpha-2 country code.
        coordinates: Source coordinates.
    """

    address: str
    city: str
    country: str
    country_code: str
    coordinates: Coordinates


@dataclass
class MovementPattern:
    """Tracked entity movement pattern.

    Attributes:
        entity_id: Tracked entity.
        waypoints: Ordered list of ``{lat, lon, timestamp}`` dicts.
        total_distance_km: Total distance travelled in km.
        average_speed_kmh: Estimated average speed.
    """

    entity_id: str
    waypoints: list[dict] = field(default_factory=list)
    total_distance_km: float = 0.0
    average_speed_kmh: float = 0.0


@dataclass
class Hotspot:
    """A geographic cluster of events.

    Attributes:
        center: Cluster center coordinates.
        radius_km: Approximate cluster radius.
        event_count: Number of events in the cluster.
        severity_distribution: Dict mapping severity → count.
    """

    center: Coordinates
    radius_km: float
    event_count: int
    severity_distribution: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class GeospatialEngine:
    """Geospatial analysis and entity tracking.

    Uses Nominatim for geocoding when available, with a fallback to
    coordinate-based distance calculations using the haversine formula.

    Attributes:
        _geocode_cache: In-memory geocode result cache.
    """

    EARTH_RADIUS_KM: float = 6371.0

    def __init__(self) -> None:
        self._geocode_cache: dict[str, Coordinates] = {}

    # ------------------------------------------------------------------
    # Geocoding
    # ------------------------------------------------------------------

    async def geocode(self, address: str) -> Coordinates:
        """Geocode an address string to coordinates.

        Args:
            address: Human-readable address or place name.

        Returns:
            :class:`Coordinates` for the address.
        """
        if address in self._geocode_cache:
            return self._geocode_cache[address]

        try:
            result = await asyncio.to_thread(
                self._nominatim_geocode, address
            )
            self._geocode_cache[address] = result
            return result
        except Exception as exc:
            logger.warning("Geocoding failed for '%s': %s", address, exc)
            return Coordinates(lat=0.0, lon=0.0)

    def _nominatim_geocode(self, address: str) -> Coordinates:
        """Call Nominatim synchronously (run in thread pool).

        Args:
            address: Address string.

        Returns:
            :class:`Coordinates`.

        Raises:
            RuntimeError: If geocoding fails.
        """
        try:
            from geopy.geocoders import Nominatim  # type: ignore
            from geopy.exc import GeocoderTimedOut  # type: ignore

            geolocator = Nominatim(user_agent="eldruin-platform")
            location = geolocator.geocode(address, timeout=10)
            if location:
                return Coordinates(lat=location.latitude, lon=location.longitude)
        except ImportError:
            logger.warning("geopy not installed; using fallback geocode")
        raise RuntimeError(f"Could not geocode '{address}'")

    async def reverse_geocode(self, lat: float, lon: float) -> LocationInfo:
        """Reverse-geocode coordinates to a location description.

        Args:
            lat: Latitude.
            lon: Longitude.

        Returns:
            :class:`LocationInfo`.
        """
        try:
            result = await asyncio.to_thread(
                self._nominatim_reverse_geocode, lat, lon
            )
            return result
        except Exception as exc:
            logger.warning("Reverse geocoding failed (%s, %s): %s", lat, lon, exc)
            return LocationInfo(
                address=f"{lat},{lon}",
                city="Unknown",
                country="Unknown",
                country_code="XX",
                coordinates=Coordinates(lat=lat, lon=lon),
            )

    def _nominatim_reverse_geocode(self, lat: float, lon: float) -> LocationInfo:
        """Synchronous reverse geocode via Nominatim.

        Args:
            lat: Latitude.
            lon: Longitude.

        Returns:
            :class:`LocationInfo`.
        """
        try:
            from geopy.geocoders import Nominatim  # type: ignore

            geolocator = Nominatim(user_agent="eldruin-platform")
            location = geolocator.reverse(f"{lat}, {lon}", timeout=10)
            if location and location.raw:
                raw = location.raw.get("address", {})
                return LocationInfo(
                    address=location.address or "",
                    city=raw.get("city") or raw.get("town") or raw.get("village", ""),
                    country=raw.get("country", ""),
                    country_code=raw.get("country_code", "").upper(),
                    coordinates=Coordinates(lat=lat, lon=lon),
                )
        except ImportError:
            pass
        return LocationInfo(
            address=f"{lat},{lon}",
            city="",
            country="",
            country_code="",
            coordinates=Coordinates(lat=lat, lon=lon),
        )

    # ------------------------------------------------------------------
    # Spatial queries
    # ------------------------------------------------------------------

    async def find_nearby_events(
        self, lat: float, lon: float, radius_km: float
    ) -> list[dict]:
        """Find events within a radius of the given coordinates.

        Uses a bounding box pre-filter followed by exact haversine filtering.

        Args:
            lat: Center latitude.
            lon: Center longitude.
            radius_km: Search radius in km.

        Returns:
            List of event dicts within the radius.
        """
        lat_delta = radius_km / self.EARTH_RADIUS_KM * (180 / math.pi)
        lon_delta = lat_delta / max(math.cos(math.radians(lat)), 1e-6)

        events: list[dict] = []
        try:
            from app.db.postgres import fetch_all

            rows = await fetch_all(
                """
                SELECT id, title, event_type, severity, location, created_at
                FROM events
                WHERE (location->>'lat')::float BETWEEN :min_lat AND :max_lat
                  AND (location->>'lon')::float BETWEEN :min_lon AND :max_lon
                LIMIT 200
                """,
                {
                    "min_lat": lat - lat_delta,
                    "max_lat": lat + lat_delta,
                    "min_lon": lon - lon_delta,
                    "max_lon": lon + lon_delta,
                },
            )
            for row in rows:
                loc = row.get("location") or {}
                if isinstance(loc, dict):
                    e_lat = float(loc.get("lat", 0))
                    e_lon = float(loc.get("lon", 0))
                    dist = await self.calculate_distance(
                        (lat, lon), (e_lat, e_lon)
                    )
                    if dist <= radius_km:
                        events.append({**row, "distance_km": round(dist, 2)})
        except Exception as exc:
            logger.warning("find_nearby_events failed: %s", exc)
        return events

    async def calculate_movement_pattern(
        self, entity_id: str, time_range: tuple[Any, Any]
    ) -> MovementPattern:
        """Calculate movement pattern for a tracked entity.

        Args:
            entity_id: Entity identifier.
            time_range: Tuple of (start, end) datetimes.

        Returns:
            :class:`MovementPattern` with waypoints and statistics.
        """
        # In production, pull from a tracking table.  Return stub for now.
        return MovementPattern(entity_id=entity_id)

    async def identify_hotspots(
        self, events: list[dict], grid_size_km: float = 50.0
    ) -> list[Hotspot]:
        """Identify geographic hotspots by clustering events.

        Uses a simple grid-based aggregation.

        Args:
            events: List of event dicts with ``location.lat`` and
                ``location.lon``.
            grid_size_km: Grid cell size for clustering.

        Returns:
            List of :class:`Hotspot` instances ordered by event count.
        """
        grid: dict[tuple, list[dict]] = {}
        for event in events:
            loc = event.get("location") or {}
            if not isinstance(loc, dict):
                continue
            try:
                lat = float(loc.get("lat", 0))
                lon = float(loc.get("lon", 0))
            except (TypeError, ValueError):
                continue

            cell_lat = round(lat / (grid_size_km / self.EARTH_RADIUS_KM * 180 / math.pi), 0)
            cell_lon = round(lon / (grid_size_km / self.EARTH_RADIUS_KM * 180 / math.pi), 0)
            grid.setdefault((cell_lat, cell_lon), []).append(event)

        hotspots: list[Hotspot] = []
        for (cell_lat, cell_lon), cell_events in grid.items():
            if len(cell_events) < 2:
                continue
            lats = [float((e.get("location") or {}).get("lat", 0)) for e in cell_events]
            lons = [float((e.get("location") or {}).get("lon", 0)) for e in cell_events]
            center = Coordinates(
                lat=sum(lats) / len(lats),
                lon=sum(lons) / len(lons),
            )
            severity_dist: dict[str, int] = {}
            for e in cell_events:
                sev = e.get("severity", "medium")
                severity_dist[sev] = severity_dist.get(sev, 0) + 1

            hotspots.append(
                Hotspot(
                    center=center,
                    radius_km=grid_size_km / 2,
                    event_count=len(cell_events),
                    severity_distribution=severity_dist,
                )
            )

        hotspots.sort(key=lambda h: h.event_count, reverse=True)
        return hotspots

    # ------------------------------------------------------------------
    # Distance
    # ------------------------------------------------------------------

    async def calculate_distance(
        self, point1: tuple[float, float], point2: tuple[float, float]
    ) -> float:
        """Calculate the great-circle distance between two points.

        Uses the haversine formula.

        Args:
            point1: (lat, lon) of first point.
            point2: (lat, lon) of second point.

        Returns:
            Distance in kilometres.
        """
        return self.haversine(point1, point2)

    def haversine(
        self,
        point1: tuple[float, float],
        point2: tuple[float, float],
    ) -> float:
        """Compute haversine distance between two (lat, lon) pairs.

        Args:
            point1: (lat1, lon1) in decimal degrees.
            point2: (lat2, lon2) in decimal degrees.

        Returns:
            Distance in kilometres.
        """
        lat1, lon1 = math.radians(point1[0]), math.radians(point1[1])
        lat2, lon2 = math.radians(point2[0]), math.radians(point2[1])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        return self.EARTH_RADIUS_KM * c


# Module-level singleton
geospatial_engine = GeospatialEngine()
