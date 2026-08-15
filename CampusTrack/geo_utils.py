"""
Geolocation helpers for the geo-fence check at scan time.
"""
import math


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Great-circle distance between two lat/lng points, in meters.
    Accurate enough for a geofence radius check (we're comparing tens
    to low-hundreds of meters, not doing surveying).
    """
    r = 6371000  # Earth's mean radius, meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c
