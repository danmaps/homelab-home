"""Solo Strava: private Apple Health workout ingestion and route viewer."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import os
import sqlite3
from datetime import datetime
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent


def metric(value, expected):
    """Normalize Health Auto Export quantity+units to canonical units."""
    if isinstance(value, dict):
        n, unit = value.get("qty"), str(value.get("units", "")).lower()
    else:
        n, unit = value, ""
    try:
        n = float(n)
    except (ValueError, TypeError):
        return None
    if not math.isfinite(n):
        return None
    if expected == "distance":
        return n * {"mi": 1609.344, "km": 1000, "m": 1, "meter": 1, "meters": 1}.get(unit, 1)
    if expected == "elevation":
        return n * ({"ft": 0.3048, "m": 1}.get(unit, 1))
    return n


def valid_route(route):
    if not isinstance(route, list):
        return []
    points = []
    for p in route[:100000]:
        if not isinstance(p, dict):
            continue
        try:
            lat = float(p.get("latitude", p.get("lat")))
            lon = float(p.get("longitude", p.get("lon")))
            if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue
        except (ValueError, TypeError):
            continue
        point = {"lat": lat, "lon": lon}
        for incoming, outgoing in [("altitude", "ele"), ("timestamp", "time"), ("speed", "speed_mps")]:
            v = p.get(incoming)
            if outgoing == "time" and isinstance(v, str):
                point[outgoing] = v
            elif outgoing != "time" and isinstance(v, (float, int)) and math.isfinite(v):
                point[outgoing] = v
        points.append(point)
    return points


def normalize(item):
    if not isinstance(item, dict):
        raise ValueError("workout must be an object")
    name, start, end = item.get("name"), item.get("start"), item.get("end")
    if not all(isinstance(s, str) and s.strip() for s in [name, start, end]):
        raise ValueError("workout missing name/start/end")
    wid = str(item.get("id") or hashlib.sha256(f"{name}|{start}|{end}".encode()).hexdigest())
    if len(wid) > 250:
        raise ValueError("invalid workout id")
    route = valid_route(item.get("route"))
    try:
        duration = float(item.get("duration") or 0)
    except (ValueError, TypeError):
        duration = 0
    if not math.isfinite(duration) or duration < 0:
        duration = 0
    return {
        "id": wid, "name": name, "start": start, "end": end,
        "duration_s": duration,
        "distance_m": metric(item.get("distance"), "distance"),
        "elevation_up_m": metric(item.get("elevationUp"), "elevation"),
        "energy_kcal": metric(item.get("activeEnergyBurned", item.get("activeEnergy")), "energy"),
        "route": route, "raw": item,
    }


def workouts_from_payload(payload):
    # HAE JSON export v1/v2 uses {data:{workouts:[...]}}; also accept {workouts:[...]}.
    if not isinstance(payload, dict):
        raise ValueError("expected JSON object")
    data = payload.get("data", payload)
    if not isinstance(data, dict) or not isinstance(data.get("workouts"), list):
        raise ValueError("expected data.workouts array")
    if len(data["workouts"]) > 3000:
        raise ValueError("too many workouts in one export")
    return [normalize(w) for w in data["workouts"]]


@contextmanager
def connect_db(path):
    db = sqlite3.connect(path, timeout=30)
    try:
        with db:
            yield db
    finally:
        db.close()


def init_db(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect_db(path) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("""CREATE TABLE IF NOT EXISTS workouts (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL,
            duration_s REAL, distance_m REAL, elevation_up_m REAL, energy_kcal REAL,
            route_json TEXT NOT NULL, raw_json TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")


def save_workouts(path, workouts):
    with connect_db(path) as db:
        for w in workouts:
            db.execute("""INSERT INTO workouts
                (id,name,start,end,duration_s,distance_m,elevation_up_m,energy_kcal,route_json,raw_json)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                  name=excluded.name,start=excluded.start,end=excluded.end,
                  duration_s=excluded.duration_s,
                  distance_m=COALESCE(excluded.distance_m,workouts.distance_m),
                  elevation_up_m=COALESCE(excluded.elevation_up_m,workouts.elevation_up_m),
                  energy_kcal=COALESCE(excluded.energy_kcal,workouts.energy_kcal),
                  route_json=CASE WHEN excluded.route_json='[]' THEN workouts.route_json ELSE excluded.route_json END,
                  raw_json=excluded.raw_json, updated_at=CURRENT_TIMESTAMP
            """, (w["id"], w["name"], w["start"], w["end"], w["duration_s"],
                  w["distance_m"], w["elevation_up_m"], w["energy_kcal"],
                  json.dumps(w["route"], separators=(',', ':')),
                  json.dumps(w["raw"], separators=(',', ':'))))
    return len(workouts)


def load_workouts(path, include_routes=False):
    cols = "id,name,start,end,duration_s,distance_m,elevation_up_m,energy_kcal"
    if include_routes:
        cols += ",route_json"
    with connect_db(path) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(f"SELECT {cols} FROM workouts ORDER BY start DESC LIMIT 500").fetchall()
    result = []
    for row in rows:
        item = dict(row)
        if include_routes:
            item["route"] = json.loads(item.pop("route_json"))
        result.append(item)
    return result


def get_workout(path, workout_id):
    with connect_db(path) as db:
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT id,name,start,end,duration_s,distance_m,elevation_up_m,energy_kcal,route_json FROM workouts WHERE id=?", (workout_id,)).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["route"] = json.loads(result.pop("route_json"))
    return result


def to_geojson(workout):
    coordinates = []
    times = []
    for p in workout["route"]:
        coords = [p["lon"], p["lat"]]
        if p.get("ele") is not None:
            coords.append(p["ele"])
        coordinates.append(coords)
        times.append(p.get("time"))
    return {"type": "FeatureCollection", "features": [{
        "type": "Feature", "properties": {
            "id": workout["id"], "name": workout["name"], "start": workout["start"],
            "timestamps": times},
        "geometry": {"type": "LineString", "coordinates": coordinates}
    }]}


def to_gpx(workout):
    def timestamp(v):
        if not v:
            return None
        try:
            return datetime.strptime(v, "%Y-%m-%d %H:%M:%S %z").isoformat()
        except ValueError:
            return v
    chunks = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<gpx version="1.1" creator="Solo Strava" xmlns="http://www.topografix.com/GPX/1/1">',
              f'<trk><name>{escape(workout["name"])}</name><trkseg>']
    for point in workout["route"]:
        s = f'<trkpt lat="{point["lat"]}" lon="{point["lon"]}">'
        if point.get("ele") is not None:
            s += f'<ele>{point["ele"]}</ele>'
        t = timestamp(point.get("time"))
        if t:
            s += f'<time>{escape(t)}</time>'
        chunks.append(s + '</trkpt>')
    chunks += ['</trkseg></trk></gpx>']
    return ''.join(chunks).encode('utf-8')


class Handler(BaseHTTPRequestHandler):
    server_version = "SoloStrava/0.1"

    def log_message(self, fmt, *args):
        # Avoid recording tokens or sensitive URL query strings.
        return

    def send_json(self, status, value):
        body = json.dumps(value, separators=(',', ':')).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def auth_read(self):
        value = self.headers.get("Authorization", "")
        if not value.startswith("Basic "):
            return False
        try:
            userpass = base64.b64decode(value[6:], validate=True).decode()
            user, password = userpass.split(":", 1)
        except (ValueError, UnicodeError):
            return False
        return hmac.compare_digest(user, self.server.read_user) and hmac.compare_digest(password, self.server.read_password)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/healthz":
            return self.send_json(200, {"status": "ok"})
        if not self.auth_read():
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Solo Strava"')
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if path == "/api/workouts":
            return self.send_json(200, {"workouts": load_workouts(self.server.db_path)})
        if path == "/api/workouts/geo":
            return self.send_json(200, {"workouts": load_workouts(self.server.db_path, True)})
        if path.startswith('/api/workouts/') and (path.endswith('.gpx') or path.endswith('.geojson')):
            is_gpx = path.endswith('.gpx')
            suffix = '.gpx' if is_gpx else '.geojson'
            workout_id = unquote(path[len('/api/workouts/'):-len(suffix)])
            workout = get_workout(self.server.db_path, workout_id)
            if not workout:
                return self.send_json(404, {"error": "not found"})
            body = to_gpx(workout) if is_gpx else json.dumps(to_geojson(workout)).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/gpx+xml' if is_gpx else 'application/geo+json')
            self.send_header('Content-Disposition', 'attachment; filename="workout.' + ('gpx' if is_gpx else 'geojson') + '"')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path in ("/", "/index.html"):
            body = (ROOT / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline' https://unpkg.com; script-src 'self' 'unsafe-inline' https://unpkg.com; img-src 'self' data: https://*.tile.openstreetmap.org; connect-src 'self';")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/api/ingest":
            return self.send_json(404, {"error": "not found"})
        if not hmac.compare_digest(self.headers.get("X-Ingest-Key", ""), self.server.ingest_key):
            return self.send_json(401, {"error": "unauthorized"})
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            return self.send_json(415, {"error": "JSON required"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > self.server.max_bytes:
                return self.send_json(413, {"error": "invalid or oversized payload"})
            payload = json.loads(self.rfile.read(length))
            workouts = workouts_from_payload(payload)
        except (ValueError, json.JSONDecodeError):
            return self.send_json(400, {"error": "invalid workout JSON"})
        n = save_workouts(self.server.db_path, workouts)
        return self.send_json(200, {"ok": True, "accepted": n})


def build_server(host, port, db_path, ingest_key, read_user, read_password, max_bytes=25 * 1024 * 1024):
    if len(ingest_key) < 20 or len(read_password) < 16 or not read_user:
        raise ValueError("Set a strong ingest token and read password in .env")
    init_db(db_path)
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.db_path = str(db_path)
    srv.ingest_key = ingest_key
    srv.read_user = read_user
    srv.read_password = read_password
    srv.max_bytes = max_bytes
    return srv


if __name__ == "__main__":
    host = os.getenv("SOLO_HOST", "0.0.0.0")
    port = int(os.getenv("SOLO_PORT", "8787"))
    srv = build_server(host, port, os.getenv("SOLO_DB", "/data/workouts.db"),
                       os.environ.get("SOLO_INGEST_KEY", ""),
                       os.getenv("SOLO_READ_USER", "runner"),
                       os.environ.get("SOLO_READ_PASSWORD", ""),
                       int(os.getenv("SOLO_MAX_MB", "25")) * 1024 * 1024)
    print(f"Solo Strava listening on {host}:{port} (bind to tailnet or loopback only)", flush=True)
    srv.serve_forever()