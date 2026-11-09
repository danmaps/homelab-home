"""Portable local newspaper validation/rendering. No account or outbound actions."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.parse import urlparse
from urllib.request import url2pathname
from zoneinfo import ZoneInfo

ASSETS = Path(__file__).resolve().parents[1] / "assets"
LIVE_METHODS = {"connector", "native_ui_verified", "public_api", "web_fetch"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        os.chmod(temporary, 0o600)
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def timestamp(value):
    require(nonempty(value), "Expected an ISO timestamp with UTC offset.")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.tzinfo is not None, "Timestamps require a UTC offset.")
    return result


def valid_url(value):
    if not value:
        return True
    parts = urlparse(value)
    return parts.scheme in {"http", "https", "mailto"} and bool(parts.netloc or parts.path)


def ids(rows, label):
    require(isinstance(rows, list) and rows, f"{label} must be a nonempty list.")
    values = [row.get("id") for row in rows]
    require(all(nonempty(x) for x in values) and len(set(values)) == len(values),
            f"{label} require unique, nonempty IDs.")
    return values


def image_path(image, edition_dir):
    raw = Path(image["path"])
    path = (Path(edition_dir) / raw).resolve()
    require(not raw.is_absolute() and path.is_relative_to(Path(edition_dir).resolve()),
            "Image paths must stay under the edition input directory.")
    require(path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"},
            f"A supported raster image is missing: {raw}")
    return path


def validate(profile, snapshot, edition, edition_dir, history=None):
    for obj in (profile, snapshot, edition):
        require(obj.get("schema_version") == 1, "Unsupported schema_version.")
    require(nonempty(profile.get("title")), "The newspaper needs a title.")
    zone = ZoneInfo(profile["timezone"])
    require(profile.get("paper") in {"Letter", "A4"}, "Paper must be Letter or A4.")
    day = date.fromisoformat(edition["date"])
    at = timestamp(edition["as_of"])
    require(at.astimezone(zone).date() == day, "as_of must fall on the edition's local date.")
    require(edition["title"] == profile["title"], "Edition title differs from the profile.")
    require(snapshot["date"] == edition["date"], "Snapshot and edition dates differ.")
    require(snapshot["timezone"] == edition["timezone"] == profile["timezone"], "Time zones differ.")
    mode = edition.get("mode")
    require(mode in {"live", "demo"} and snapshot.get("mode") == mode, "Inputs need matching live/demo modes.")
    sections = profile["sections"]
    section_ids = ids(sections, "Sections")
    require(all(nonempty(x.get("title")) for x in sections), "Every section needs a title.")
    require(ids(edition["pages"], "Pages") == section_ids, "Pages must match profile section order exactly.")
    settings = profile["sources"]
    source_ids = ids(settings, "Sources")
    require(set(snapshot["sources"]).issubset(source_ids), "Snapshot has an unconfigured source.")
    index, coverage, topic_pages = {}, [], {}
    for config in settings:
        key = config["id"]
        require(config.get("coverage") in {"selective", "all_topics"}, f"Invalid coverage mode: {key}")
        targets = config.get("page_ids", [])
        require(isinstance(targets, list) and set(targets).issubset(section_ids), f"Unknown target page: {key}")
        require(config["coverage"] != "all_topics" or targets, f"all_topics needs target pages: {key}")
        max_age = config.get("max_age_minutes", 60)
        require(isinstance(max_age, (int, float)) and max_age > 0, "Source age limit must be positive.")
        source = snapshot["sources"].get(key, {"status": "unavailable", "complete": False,
                                               "reason": "Not collected.", "items": []})
        status = source.get("status")
        require(status in {"current", "partial", "stale", "unavailable", "demo"}, f"Invalid source status: {key}")
        require(nonempty(source.get("reason")), f"Source needs a scope/limitation reason: {key}")
        require(mode == "demo" or status != "demo", "Demo evidence cannot support a live edition.")
        require(mode != "demo" or status == "demo", "Demo snapshots use demo sources only.")
        observed = timestamp(source["observed_at"]) if source.get("observed_at") else None
        require(observed is None or observed <= at, f"Observation is after compilation: {key}")
        evidence = source.get("evidence", {})
        has_evidence = isinstance(evidence, dict) and all(nonempty(evidence.get(x)) for x in ("tool", "reference", "scope"))
        live = source.get("method") in LIVE_METHODS
        if status == "current":
            require(source.get("complete") is True and live and has_evidence and observed is not None,
                    f"Current source needs complete live observation evidence: {key}")
        current = bool(status == "current" and observed and 0 <= (at - observed).total_seconds() <= max_age * 60)
        coverage.append({"id": key, "required": bool(config.get("required", True)), "current": current,
                         "status": "stale" if status == "current" and not current else status,
                         "reason": source["reason"]})
        require(isinstance(source.get("items"), list), f"Source items must be a list: {key}")
        if source["items"]:
            require(has_evidence, f"Source items need observation evidence: {key}")
        for item in source["items"]:
            identity = item.get("id")
            require(nonempty(identity) and identity not in index, "Source item IDs must be globally unique.")
            require(all(nonempty(item.get(x)) for x in ("title", "summary", "source_label")), f"Incomplete source item: {identity}")
            require(valid_url(item.get("source_url")), f"Unsupported source URL: {identity}")
            index[identity] = item
            if config["coverage"] == "all_topics":
                topic_pages[identity] = set(targets)
    complete = mode == "live" and all(x["current"] for x in coverage if x["required"])
    require(complete or profile.get("allow_partial", True) or mode == "demo", "Required-source coverage is incomplete.")
    artwork = profile.get("artwork", {}).get("mode", "none")
    require(artwork in {"none", "optional", "one_per_page"}, "Invalid artwork mode.")
    cited, facts, images = defaultdict(set), defaultdict(set), {}
    for page, section in zip(edition["pages"], sections):
        page_id = page["id"]
        require(nonempty(page.get("deck")), f"Page needs a deck: {page_id}")
        window = section.get("window")
        require(window in {None, "tomorrow", "week", "month"}, f"Unknown planning window: {window}")
        if window:
            start = day + timedelta(days=1) if window == "tomorrow" else day
            end = start if window == "tomorrow" else day + timedelta(days=6 if window == "week" else 29)
            require(page.get("start_date") == str(start) and page.get("end_date") == str(end),
                    f"Incorrect inclusive planning dates: {page_id}")
        articles = page.get("articles")
        require(isinstance(articles, list) and (articles or section.get("kind") == "games"), f"A page needs articles: {page_id}")
        for article in articles:
            require(nonempty(article.get("headline")), "Every article needs a headline.")
            require(isinstance(article.get("paragraphs"), list) and article["paragraphs"] and
                    all(nonempty(x) for x in article["paragraphs"]), "Every article needs nonempty paragraphs.")
            for field in ("source_ids", "fact_ids"):
                require(isinstance(article.get(field), list) and article[field] and all(nonempty(x) for x in article[field]),
                        f"Every article needs {field}.")
            for identity in article["source_ids"]:
                require(identity in index, f"Unknown cited source item: {identity}")
                cited[identity].add(page_id)
            for identity in article["fact_ids"]:
                facts[identity].add(page_id)
            if article.get("event_date"):
                event = date.fromisoformat(article["event_date"])
                require(not window or start <= event <= end, f"Event falls outside its planning page: {page_id}")
        image = page.get("image")
        require(artwork != "one_per_page" or image, f"Missing full-width image: {page_id}")
        require(artwork != "none" or not image, "Profile has disabled artwork.")
        if image:
            require(nonempty(image.get("alt")), "Images require meaningful alt text.")
            require(image.get("origin") in {"generated", "source", "licensed"}, "Image origin is required.")
            if image["origin"] == "generated":
                require(image.get("generated_for_date") == edition["date"] and image.get("generation_evidence"),
                        "Generated images need the edition date and generation evidence.")
            else:
                require(image.get("source_url") and valid_url(image["source_url"]), "Image provenance is required.")
            path = image_path(image, edition_dir)
            images[page_id] = {"path": str(path), "sha256": sha256(path)}
    for identity, targets in topic_pages.items():
        require(bool(cited[identity] & targets), f"Mandatory topic missing from target pages: {identity}")
    exceptions = edition.get("duplicate_exceptions", [])
    for identity, pages in facts.items():
        if len(pages) > 1:
            require(any(x.get("fact_id") == identity and pages.issubset(x.get("page_ids", [])) and nonempty(x.get("reason"))
                        for x in exceptions), f"Duplicate fact needs a reason and explicit page exception: {identity}")
    result = {"passed": True, "intended_pages": len(sections), "mode": mode,
              "coverage": {"complete": complete, "sources": coverage}, "images": images}
    from features import validate_features, novelty_record, check_novelty
    result.update(validate_features(profile, snapshot, edition, result))
    if result.get("feature_gaps"):
        result["coverage"].update(complete=False, feature_gaps=result["feature_gaps"])
        require(profile.get("allow_partial", True) or mode == "demo", "Family coverage is incomplete.")
    result["novelty"] = novelty_record(edition, result, index)
    if profile.get("feature_version", 1) >= 2 and mode == "live":
        require(history is not None, "Full live editions require the workspace history, including an empty first-run history.")
        check_novelty(result["novelty"], history, edition)
    return result


def render(profile_path, snapshot_path, edition_path, output, workspace=None):
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
    from pypdf import PdfReader
    from weasyprint import HTML, default_url_fetcher

    profile, snapshot, edition = (load(x) for x in (profile_path, snapshot_path, edition_path))
    history = load(Path(workspace) / ".local/edition-history.json") if workspace else None
    result = validate(profile, snapshot, edition, Path(edition_path).parent, history)
    require(shutil.which("pdftoppm"), "Poppler pdftoppm is required for page previews.")
    folder = Path(output).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    if result["images"]:
        (folder / "artwork").mkdir()
        for page in edition["pages"]:
            if page["id"] in result["images"]:
                source = Path(result["images"][page["id"]]["path"])
                safe_id = hashlib.sha256(page["id"].encode()).hexdigest()[:12]
                copied = folder / "artwork" / (safe_id + source.suffix)
                shutil.copyfile(source, copied)
                page["image"]["path"] = str(copied.relative_to(folder))
                result["images"][page["id"]]["path"] = str(copied)
    for name, obj in (("profile", profile), ("snapshot", snapshot), ("edition", edition)):
        save(folder / f"{name}.json", obj)
    index = {item["id"]: item for source in snapshot["sources"].values() for item in source["items"]}
    env = Environment(loader=FileSystemLoader(ASSETS), autoescape=True, undefined=StrictUndefined)
    env.globals["citations"] = lambda values: [index[x] for x in dict.fromkeys(values)]
    env.globals["image_uri"] = lambda page_id: Path(result["images"][page_id]["path"]).as_uri()
    env.globals["source_item"] = lambda identity: index[identity]
    env.globals["parent_label"] = lambda identity: index.get(identity, {}).get("title", "Subtask") if identity else ""
    html = env.get_template("edition.html").render(p=profile, e=edition, qa=result,
                                                  font_base=(ASSETS / "fonts").as_uri())
    html_path, pdf = folder / "newspaper.html", folder / "newspaper.pdf"
    html_path.write_text(html, encoding="utf-8")
    allowed = {path.resolve() for path in (ASSETS / "fonts").glob("*") if path.suffix in {".ttf", ".otf"}}
    allowed.update(Path(x["path"]) for x in result["images"].values())

    def local_assets_only(url, *args, **kwargs):
        parts = urlparse(url)
        decoded = url2pathname(("//" + parts.netloc if parts.netloc else "") + parts.path)
        require(parts.scheme == "file" and Path(decoded).resolve() in allowed,
                "PDF rendering only loads the approved local fonts and artwork.")
        return default_url_fetcher(url, *args, **kwargs)

    messages = []

    class Capture(logging.Handler):
        def emit(self, record):
            messages.append(record.getMessage())

    logger = logging.getLogger("weasyprint")
    handler = Capture(level=logging.WARNING)
    logger.addHandler(handler)
    try:
        document = HTML(string=html, url_fetcher=local_assets_only).render()
        errors = []
        for number, page in enumerate(document.pages, 1):
            for box in page._page_box.descendants():
                if getattr(box, "text", ""):
                    if box.position_x < 24 or box.position_x + box.width > page.width - 24:
                        errors.append(f"Page {number}: text crosses a horizontal boundary.")
                    if box.position_y < 20 or box.position_y + box.height > page.height - 20:
                        errors.append(f"Page {number}: text crosses a vertical boundary.")
                element = getattr(box, "element", None)
                if getattr(element, "tag", None) == "img" and hasattr(box, "replacement"):
                    if abs(box.position_x - 46.08) > 1 or abs(box.width - (page.width - 92.16)) > 1:
                        errors.append(f"Page {number}: artwork is not full printable width.")
        document.write_pdf(pdf)
    finally:
        logger.removeHandler(handler)
    reader = PdfReader(pdf)
    if len(reader.pages) != result["intended_pages"]:
        errors.append(f"Expected {result['intended_pages']} pages, rendered {len(reader.pages)}; shorten overflowing content.")
    expected_size = (612, 792) if profile["paper"] == "Letter" else (595.276, 841.89)
    for number, page in enumerate(reader.pages, 1):
        if any(abs(float(value) - expected) > 1 for value, expected in zip((page.mediabox.width, page.mediabox.height), expected_size)):
            errors.append(f"Page {number}: wrong paper size.")
        text = page.extract_text() or ""
        if len(text.strip()) < 100 or f"PAGE {number} OF {result['intended_pages']}" not in text:
            errors.append(f"Page {number}: nearly blank page or missing folio.")
        for font_ref in page.get("/Resources", {}).get("/Font", {}).values():
            font = font_ref.get_object()
            for target in font.get("/DescendantFonts") or [font]:
                descriptor = target.get_object().get("/FontDescriptor")
                descriptor = descriptor.get_object() if descriptor else {}
                if not any(x in descriptor for x in ("/FontFile", "/FontFile2", "/FontFile3")):
                    errors.append(f"Page {number}: a font is not embedded.")
    if any("Failed to load" in x or "cannot be loaded" in x for x in messages):
        errors.append("A font or artwork asset could not be loaded.")
    previews = subprocess.run(["pdftoppm", "-r", "110", "-png", str(pdf), str(folder / "page")],
                              capture_output=True, text=True, timeout=120)
    if previews.returncode:
        errors.append("Preview generation failed: " + previews.stderr[:300])
    preview_files = sorted(folder.glob("page-*.png"))
    if len(preview_files) != len(reader.pages):
        errors.append("Preview count differs from the PDF page count.")
    result.update(passed=not errors, errors=sorted(set(errors)), warnings=messages,
                  physical_pages=len(reader.pages), visual_review=False,
                  preview_sha256={path.name: sha256(path) for path in preview_files})
    save(folder / "qa.json", result)
    receipt = {"schema_version": 1, "title": edition["title"], "date": edition["date"], "mode": edition["mode"],
               "edition_id": edition["date"] + "-" + folder.name, "created_at": datetime.now(timezone.utc).isoformat(),
               "pdf_sha256": sha256(pdf), "qa_passed": result["passed"], "visual_review": False,
               "input_sha256": {f"{name}.json": sha256(folder / f"{name}.json") for name in ("profile", "snapshot", "edition")},
               "coverage": result["coverage"], "delivery": {"status": "not_requested"},
               "printing": {"status": "not_requested"}, "novelty": result["novelty"]}
    if edition["mode"] == "live" and profile.get("feature_version", 1) >= 2:
        receipt["delivery"]["status"] = "email_delivery_pending" if profile["delivery"]["channel"] == "email" else "local_handoff_pending"
    save(folder / "receipt.json", receipt)
    return {"folder": str(folder), "pdf": str(pdf), "qa": result}


def review(folder, note):
    folder = Path(folder)
    qa, receipt = load(folder / "qa.json"), load(folder / "receipt.json")
    require(qa.get("passed") and receipt.get("qa_passed"), "Mechanical QA must pass before review.")
    require(nonempty(note), "Record observations from inspecting every page.")
    require(sha256(folder / "newspaper.pdf") == receipt["pdf_sha256"], "PDF changed after QA.")
    for name, expected in receipt["input_sha256"].items():
        require(sha256(folder / name) == expected, "Input changed after QA.")
    require(len(qa["preview_sha256"]) == qa["physical_pages"], "Every page needs a preview.")
    for name, expected in qa["preview_sha256"].items():
        require(sha256(folder / name) == expected, "A preview changed after QA.")
    reviewed_at = datetime.now(timezone.utc).isoformat()
    qa.update(visual_review=True, visual_review_note=note, visual_reviewed_at=reviewed_at)
    receipt.update(visual_review=True, visual_reviewed_at=reviewed_at)
    save(folder / "qa.json", qa)
    save(folder / "receipt.json", receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "render"):
        command = commands.add_parser(name)
        for field in ("profile", "snapshot", "edition"):
            command.add_argument(f"--{field}", required=True, type=Path)
        command.add_argument("--workspace", type=Path)
        if name == "render":
            command.add_argument("--output", required=True, type=Path)
    command = commands.add_parser("review")
    command.add_argument("folder", type=Path)
    command.add_argument("--note", required=True)
    command.add_argument("--workspace", type=Path)
    commands.add_parser("setup-questions")
    command = commands.add_parser("configure")
    command.add_argument("--workspace", type=Path, required=True)
    command.add_argument("--answers", type=Path, required=True)
    for name in ("state", "preflight", "printing", "record-local", "record-email", "print", "printer-test", "printer-confirm", "pilot", "collect", "source-import", "public-refresh", "record-discovery"):
        command = commands.add_parser(name)
        command.add_argument("--workspace", type=Path, required=True)
        if name in {"record-local", "record-email", "print"}:
            command.add_argument("folder", type=Path)
        if name in {"record-email", "pilot", "source-import", "record-discovery"}:
            command.add_argument("--input", type=Path, required=True)
        if name in {"source-import", "public-refresh"}:
            command.add_argument("--snapshot", type=Path, required=True)
        if name in {"collect", "state"}:
            command.add_argument("--date")
        if name == "printing":
            command.add_argument("preference", choices=["on", "off"])
        if name == "print":
            command.add_argument("--scheduled", action="store_true")
            command.add_argument("--reprint", action="store_true")
        if name == "printer-test":
            command.add_argument("--submit", action="store_true")
        if name == "printer-confirm":
            command.add_argument("--job-id", required=True)
            command.add_argument("--user-confirmation", required=True)
    command = commands.add_parser("puzzles")
    command.add_argument("--date", required=True)
    command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        import operations as ops
        if args.command == "render":
            if args.workspace:
                with ops.lock(args.workspace):
                    result = render(args.profile, args.snapshot, args.edition, args.output, args.workspace)
            else:
                result = render(args.profile, args.snapshot, args.edition, args.output)
        elif args.command == "review":
            result = review(args.folder, args.note)
            if args.workspace:
                with ops.lock(args.workspace):
                    ops.remember(args.workspace, args.folder, result)
        elif args.command == "validate":
            history = load(args.workspace / ".local/edition-history.json") if args.workspace else None
            result = validate(load(args.profile), load(args.snapshot), load(args.edition), args.edition.parent, history)
        elif args.command == "setup-questions":
            from onboarding import QUESTION_GROUPS
            result = {"groups": QUESTION_GROUPS}
        elif args.command == "configure":
            result = ops.configure(args.workspace, load(args.answers))
        elif args.command == "state":
            result = ops.state(args.workspace, args.date)
        elif args.command == "preflight":
            from importlib.metadata import version
            result = {"libraries": {key: version(key) for key in ("weasyprint", "Jinja2", "pypdf", "chess")},
                      "pdftoppm": shutil.which("pdftoppm"), "lp": shutil.which("lp"), "lpstat": shutil.which("lpstat"),
                      "profile_present": (args.workspace / ".local/profile.json").is_file()}
        elif args.command == "record-local":
            result = ops.record_local(args.workspace, args.folder)
        elif args.command == "record-email":
            result = ops.record_email(args.workspace, args.folder, load(args.input))
        elif args.command == "printing":
            result = ops.printing_preference(args.workspace, args.preference == "on")
        elif args.command == "print":
            result = ops.submit_print(args.workspace, args.folder, args.scheduled, args.reprint)
        elif args.command == "printer-test":
            result = ops.printer_test(args.workspace, args.submit)
        elif args.command == "printer-confirm":
            result = ops.confirm_printer(args.workspace, args.job_id, args.user_confirmation)
        elif args.command == "pilot":
            result = ops.pilot(args.workspace, load(args.input))
        elif args.command == "puzzles":
            from games import daily_sudoku, daily_chess
            require(not args.output.exists(), "Preserve the existing puzzle file; choose a new output path.")
            result = {"sudoku": daily_sudoku(args.date), "chess": daily_chess(args.date)}
            save(args.output, result)
            result = {"output": str(args.output), "checked": ["sudoku", "chess"]}
        else:
            import sources
            if args.command == "collect":
                result = sources.collect(args.workspace, args.date)
            elif args.command == "source-import":
                result = sources.import_source(args.workspace, args.snapshot, load(args.input))
            elif args.command == "public-refresh":
                result = sources.refresh_public(args.workspace, args.snapshot)
            else:
                result = sources.record_discovery(args.workspace, load(args.input))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("qa", result).get("passed", True) else 1
    except (ValueError, KeyError, TypeError, OSError, ImportError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"newspaper: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
