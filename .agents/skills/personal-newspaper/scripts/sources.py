"""Source envelopes and bounded public feed/forecast adapters. No account writes."""
from datetime import datetime
import hashlib
from html import unescape
import json
from pathlib import Path
import re
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo


def need(condition, message):
    if not condition:
        raise ValueError(message)


def collect(workspace, day=None):
    import newspaper as n
    from operations import lock
    root = Path(workspace)
    with lock(root):
        profile = n.load(root / ".local/profile.json")
        at = datetime.now(ZoneInfo(profile["timezone"]))
        day = day or at.date().isoformat()
        snapshot = {"schema_version": 1, "mode": "live", "date": day, "timezone": profile["timezone"],
                    "sources": {s["id"]: {"status": "unavailable", "complete": False, "observed_at": None,
                                "reason": "Not collected. Read the configured scope with an available adapter.", "items": []}
                                for s in profile["sources"]}}
        path = root / "work" / day / "snapshot.json"
        need(not path.exists(), "A snapshot exists; resume/import it instead of resetting collection.")
        n.save(path, snapshot)
    return {"snapshot": str(path.resolve()), "sources": len(snapshot["sources"]), "status": "awaiting_collection"}


def import_source(workspace, snapshot_path, envelope):
    import newspaper as n
    from operations import lock
    root = Path(workspace)
    with lock(root):
        profile, snapshot = n.load(root / ".local/profile.json"), n.load(snapshot_path)
        configs = {s["id"]: s for s in profile["sources"]}
        key = envelope.get("source")
        need(key in configs and key in snapshot["sources"], "Import only a configured source.")
        need(envelope.get("date") == snapshot["date"] and envelope.get("timezone") == snapshot["timezone"], "Imported date/time zone differs from the edition.")
        need(envelope.get("schema_version", 1) == 1 and isinstance(envelope.get("items"), list), "Invalid source envelope.")
        need(envelope.get("status") in {"current", "partial", "stale", "unavailable"} and envelope.get("reason"), "Give the source status, scope and limits.")
        evidence = envelope.get("evidence", {})
        need(not envelope["items"] or all(evidence.get(k) for k in ("tool", "reference", "scope")), "Items require actual observation evidence.")
        if envelope["status"] == "current":
            now = datetime.now(ZoneInfo(profile["timezone"]))
            need(envelope.get("complete") is True and envelope.get("method") in n.LIVE_METHODS
                 and all(evidence.get(k) for k in ("tool", "reference", "scope")), "Current imports require complete live evidence.")
            age = (now - n.timestamp(envelope["observed_at"])).total_seconds()
            need(0 <= age <= configs[key].get("max_age_minutes", 60) * 60, "Current import is stale or future-dated.")
        outside_ids = {i["id"] for s, data in snapshot["sources"].items() if s != key for i in data["items"]}
        own_ids = [i.get("id") for i in envelope["items"]]
        need(all(isinstance(x, str) and x for x in own_ids) and len(set(own_ids)) == len(own_ids) and not set(own_ids) & outside_ids, "Source item IDs must be stable and globally unique.")
        snapshot["sources"][key] = {k: v for k, v in envelope.items() if k not in {"source", "date", "timezone"}}
        n.save(snapshot_path, snapshot)
    return {"source": key, "status": envelope["status"], "items": len(own_ids)}


def fetch(url):
    need(urlparse(url).scheme == "https", "Public source URLs must use HTTPS.")
    with urlopen(Request(url, headers={"User-Agent": "PersonalNewspaper/2.0 (read-only public source collector)"}), timeout=25) as response:
        data = response.read(8 * 1024 * 1024 + 1)
    need(len(data) <= 8 * 1024 * 1024, "Public response exceeded the eight-megabyte collection bound.")
    return data


def plain(text):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def public_envelope(config, profile, day, fetcher=fetch):
    at = datetime.now(ZoneInfo(profile["timezone"]))
    url = config["url"]
    data = fetcher(url)
    format_name = config.get("format", "jsonfeed")
    items, complete = [], True
    if format_name == "nws":
        points = json.loads(data)
        forecast_url = points["properties"]["forecast"]
        forecast = json.loads(fetcher(forecast_url))
        for period in forecast["properties"]["periods"]:
            items.append({"id": config["id"] + ":" + str(period["number"]), "title": period["name"],
                          "summary": period["detailedForecast"], "source_label": "National Weather Service",
                          "source_url": forecast_url, "published_at": forecast["properties"].get("updated"),
                          "temperature": period["temperature"], "temperature_unit": period["temperatureUnit"]})
    elif format_name == "jsonfeed":
        feed = json.loads(data)
        complete = not bool(feed.get("next_url"))
        for item in feed.get("items", []):
            canonical = item.get("url") or item.get("external_url") or item.get("id")
            need(canonical, "A JSON Feed item lacks an identity.")
            items.append({"id": config["id"] + ":" + hashlib.sha256(canonical.encode()).hexdigest()[:20],
                          "title": plain(item.get("title", "Untitled feed entry")),
                          "summary": plain(item.get("summary") or item.get("content_text") or item.get("content_html"))[:8000] or "Title-only entry; read the original before summarizing.",
                          "source_label": feed.get("title", config["id"]), "source_url": item.get("url") or item.get("external_url") or url,
                          "published_at": item.get("date_published"), "content_scope": "feed_entry"})
    elif format_name in {"rss", "atom"}:
        document = ET.fromstring(data)
        atom = "{http://www.w3.org/2005/Atom}"
        entries = document.findall(".//item") if format_name == "rss" else document.findall(f".//{atom}entry")
        for entry in entries:
            prefix = atom if format_name == "atom" else ""
            title = entry.findtext(prefix + "title") or "Untitled feed entry"
            link = entry.findtext("link") if format_name == "rss" else next((node.get("href") for node in entry.findall(atom + "link") if node.get("rel", "alternate") == "alternate"), url)
            identity = entry.findtext(prefix + "id") or entry.findtext("guid") or link or title
            summary = entry.findtext(prefix + "summary") or entry.findtext("description") or entry.findtext(prefix + "content") or "Title-only entry."
            items.append({"id": config["id"] + ":" + hashlib.sha256(identity.encode()).hexdigest()[:20], "title": plain(title),
                          "summary": plain(summary)[:8000], "source_url": link or url, "source_label": config.get("label", config["id"]),
                          "published_at": entry.findtext(prefix + "published") or entry.findtext("pubDate") or entry.findtext(prefix + "updated"),
                          "content_scope": "title_description" if format_name == "atom" else "feed_entry"})
    else:
        raise ValueError("Supported public adapters: jsonfeed, rss, atom, nws.")
    if len(items) > config.get("max_items", 200):
        items = items[:config.get("max_items", 200)]
        complete = False
    return {"schema_version": 1, "source": config["id"], "date": day, "timezone": profile["timezone"],
            "status": "current" if complete else "partial", "complete": complete, "method": "public_api", "observed_at": at.isoformat(),
            "reason": "Read the configured public index/forecast. Linked originals or video footage are not established by feed descriptions." + (" Pagination or item limits remain." if not complete else ""),
            "evidence": {"tool": "Bounded HTTPS public adapter", "reference": url, "scope": format_name + " configured source"}, "items": items}


def refresh_public(workspace, snapshot_path):
    import newspaper as n
    root = Path(workspace)
    profile, snapshot = n.load(root / ".local/profile.json"), n.load(snapshot_path)
    results = []
    for config in profile["sources"]:
        if config.get("adapter") != "public":
            continue
        try:
            envelope = public_envelope(config, profile, snapshot["date"])
        except (OSError, ValueError, KeyError, ET.ParseError) as exc:
            envelope = {"schema_version": 1, "source": config["id"], "date": snapshot["date"], "timezone": snapshot["timezone"],
                        "status": "unavailable", "complete": False, "observed_at": None, "reason": str(exc)[:500], "items": []}
        results.append(import_source(workspace, snapshot_path, envelope))
    return {"sources": results}


def record_discovery(workspace, observation):
    import newspaper as n
    from operations import lock
    with lock(workspace):
        root = Path(workspace)
        profile = n.load(root / ".local/profile.json")
        need(observation.get("id") in {s["id"] for s in profile["sources"]}, "Select/approve a source in the profile before remembering it.")
        need(all(observation.get(k) for k in ("discovery_path", "last_verified_at", "scope", "evidence", "page_ids")), "Source discovery needs actual provenance and page assignments.")
        n.timestamp(observation["last_verified_at"])
        need(set(observation["page_ids"]).issubset({s["id"] for s in profile["sections"]}), "Unknown discovery page assignment.")
        path = root / ".local/source-registry.json"
        data = n.load(path)
        data["sources"] = [s for s in data["sources"] if s["id"] != observation["id"]] + [observation]
        n.save(path, data)
    return observation
