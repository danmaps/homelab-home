"""Solo Strava atlas. Read-only web BFF over a private PulsHealth install.

No Apple Health data, authorization tokens, or GPS routes are ever written to disk.
"""
import base64
import hmac
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn

UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
INDEX = Path(__file__).with_name("index.html")


def env(name, fallback=""):
    return os.environ.get(name, fallback).strip()


def config():
    return {
        "username": env("ATLAS_USERNAME", "runner"),
        "password": env("ATLAS_PASSWORD"),
        "api": env("PULS_API_URL", "http://127.0.0.1:8081").rstrip("/"),
        "api_token": env("PULS_API_TOKEN"),
        "ingest": env("PULS_INGEST_URL", "http://127.0.0.1:8080").rstrip("/"),
        "ingest_token": env("PULS_INGEST_TOKEN"),
    }


def safe_config(cfg):
    if not cfg["password"] or len(cfg["password"]) < 18:
        raise ValueError("ATLAS_PASSWORD must be at least 18 characters")
    if not cfg["api_token"] or not cfg["ingest_token"]:
        raise ValueError("PULS_API_TOKEN and PULS_INGEST_TOKEN are required")
    for key in ("api", "ingest"):
        parsed = urllib.parse.urlsplit(cfg[key])
        if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost"):
            raise ValueError(f"{key} must use loopback HTTP only, not a user-supplied remote host")
    return cfg


def upstream(url, token, path, *, timeout=12):
    req = urllib.request.Request(
        url + path,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status != 200:
                raise ValueError("Unexpected upstream response")
            size = 0
            blocks = []
            while True:
                block = r.read(1024 * 512)
                if not block:
                    break
                size += len(block)
                if size > 16 * 1024 * 1024:
                    raise ValueError("Upstream response larger than 16 MB")
                blocks.append(block)
            return json.loads(b"".join(blocks))
    except urllib.error.HTTPError as e:
        raise ValueError(f"PulsHealth returned HTTP {e.code}") from None
    except (urllib.error.URLError, TimeoutError):
        raise ValueError("PulsHealth service unavailable") from None


class AtlasHandler(BaseHTTPRequestHandler):
    cfg = {}

    def log_message(self, format, *args):
        # No URL or GPS coordinates in access logs.
        print("Atlas request", self.client_address[0], flush=True)

    def _send(self, code, body, media="application/json; charset=utf-8", headers=None):
        self.send_response(code)
        self.send_header("Content-Type", media)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data: https://*.tile.openstreetmap.org; style-src 'self' 'unsafe-inline' https://unpkg.com; script-src 'self' 'unsafe-inline' https://unpkg.com; connect-src 'self'")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, value):
        self._send(code, json.dumps(value, separators=(",", ":")).encode())

    def _authorized(self):
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            payload = base64.b64decode(header[6:], validate=True).decode()
            name, password = payload.split(":", 1)
        except (ValueError, UnicodeError):
            return False
        return hmac.compare_digest(name, self.cfg["username"]) and hmac.compare_digest(password, self.cfg["password"])

    def do_GET(self):
        if not self._authorized():
            self._send(
                401, b"Authorization required", "text/plain; charset=utf-8",
                {"WWW-Authenticate": 'Basic realm="Solo Strava"'}
            )
            return
        try:
            parsed = urllib.parse.urlsplit(self.path)
            route = parsed.path
            if route in ("/", "/index.html"):
                self._send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
            elif route == "/api/status":
                self._json(200, upstream(self.cfg["api"], self.cfg["api_token"], "/v1/users"))
            elif route == "/api/workouts":
                params = urllib.parse.parse_qs(parsed.query)
                n = min(max(int(params.get("limit", ["60"])[0]), 1), 100)
                self._json(200, upstream(self.cfg["api"], self.cfg["api_token"], f"/v1/workouts?limit={n}&offset=0"))
            elif route == "/api/summary":
                params = urllib.parse.parse_qs(parsed.query)
                period = params.get("range", ["30d"])[0]
                if period not in ("7d", "14d", "30d", "90d"):
                    return self._json(400, {"error": "Invalid range"})
                self._json(200, upstream(self.cfg["api"], self.cfg["api_token"], f"/v1/summary?range={period}&format=json"))
            else:
                match = re.fullmatch(r"/api/(workouts|routes|series)/([^/]+)", route)
                if not match or not UUID.fullmatch(match.group(2)):
                    return self._json(404, {"error": "Not found"})
                section, uuid = match.groups()
                if section == "routes":
                    host, token, target = self.cfg["ingest"], self.cfg["ingest_token"], f"/v1/routes/{uuid}"
                else:
                    host, token = self.cfg["api"], self.cfg["api_token"]
                    target = f"/v1/workouts/{uuid}" + ("/series?maxPoints=500" if section == "series" else "")
                self._json(200, upstream(host, token, target))
        except (ValueError, TypeError) as e:
            self._json(502, {"error": str(e)})
        except Exception:
            self._json(500, {"error": "Unexpected server error"})

    def do_POST(self):
        if not self._authorized():
            return self._send(401, b"Authorization required", "text/plain; charset=utf-8", {"WWW-Authenticate": 'Basic realm="Solo Strava"'})
        self._json(405, {"error": "Read-only service"})


def main():
    cfg = safe_config(config())
    AtlasHandler.cfg = cfg
    # Loopback-only, reachable by an approved TLS private proxy (Tailscale Serve).
    ThreadingHTTPServer(("127.0.0.1", int(env("ATLAS_PORT", "3498"))), AtlasHandler).serve_forever()


if __name__ == "__main__":
    main()