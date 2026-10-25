"""Bounded Docker readiness probe for Open WebUI."""

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    port = os.environ.get("PORT", "8080")
    host = os.environ.get("OPEN_WEBUI_HEALTH_HOST") or os.environ.get("HOST", "127.0.0.1")
    if host in {"0.0.0.0", "::", "[::]"}:
        host = "127.0.0.1"
    url = f"http://{host}:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=4) as response:
            if response.status != 200:
                return 1
            payload = json.load(response)
    except (OSError, ValueError, urllib.error.URLError):
        return 1
    return 0 if payload.get("status") is True else 1


if __name__ == "__main__":
    sys.exit(main())
