"""Read-only route tools for local MCP agents. No sensitive data is persisted."""
import math
import re

from server import UUID, config, safe_config, upstream


def list_route_workouts(limit: int = 30):
    """Discover workouts that have GPS tracks (unlike all workouts)."""
    cfg = safe_config(config())
    limit = max(1, min(100, int(limit)))
    return upstream(cfg["ingest"], cfg["ingest_token"], f"/v1/routes?limit={limit}&offset=0")


def get_workout_route(uuid: str, max_points: int = 500):
    """Return the stored route from HealthKit, downsampled for LLM consumption.

    Full detail stays available in the private Solo Strava web UI and upstream
    service. The tool never generates a fake line between points.
    """
    if not UUID.fullmatch(uuid):
        raise ValueError("Expected a HealthKit workout UUID")
    cfg = safe_config(config())
    limit = max(2, min(2500, int(max_points)))
    data = upstream(cfg["ingest"], cfg["ingest_token"], f"/v1/routes/{uuid}")
    points = data.get("points", data.get("route", {}).get("points", [])) if isinstance(data, dict) else []
    if not isinstance(points, list):
        raise ValueError("Unexpected upstream route response; needs real-device validation")
    valid = []
    for p in points:
        if not isinstance(p, dict):
            continue
        lat = p.get("lat", p.get("latitude"))
        lon = p.get("lon", p.get("longitude"))
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            continue
        if math.isfinite(lat) and math.isfinite(lon) and abs(lat) <= 90 and abs(lon) <= 180:
            valid.append([lon, lat])
    if len(valid) > limit:
        # Retain both endpoints; perform an evenly spaced visual decimation.
        valid = [valid[round(i * (len(valid) - 1) / (limit - 1))] for i in range(limit)]
    return {"uuid": uuid, "geometry": {"type":"LineString", "coordinates":valid}, "returned_points":len(valid), "note":"Decimated geometry if source exceeded max_points. Consult the private web UI for the full track."}