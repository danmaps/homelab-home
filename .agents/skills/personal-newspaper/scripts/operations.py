"""Private workflow state, verified email evidence and optional guarded CUPS printing."""
from contextlib import contextmanager
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
import re
import subprocess
from zoneinfo import ZoneInfo


def need(condition, message):
    if not condition:
        raise ValueError(message)


@contextmanager
def lock(workspace):
    path = Path(workspace) / ".local" / "operation.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.mkdir()
    except FileExistsError as exc:
        raise ValueError("Another newspaper operation is active; resolve an abandoned lock before retrying.") from exc
    try:
        yield
    finally:
        path.rmdir()


def configure(workspace, answers):
    import newspaper as n
    from onboarding import build_profile, registry
    root = Path(workspace)
    need(not answers.get("example_only"), "The sample answers are fictional. Ask the new user, adapt the answers, then remove example_only.")
    profile = build_profile(answers)
    need(not (root / ".local/profile.json").exists(), "Preserve the existing profile; edit its reviewed settings instead.")
    root.mkdir(parents=True, exist_ok=True)
    with lock(root):
        for folder in ("work", "outputs", "deliverables"):
            (root / folder).mkdir(exist_ok=True)
        n.save(root / ".local/profile.json", profile)
        n.save(root / ".local/source-registry.json", registry(profile))
        n.save(root / ".local/edition-history.json", {"schema_version": 1, "editions": []})
        n.save(root / ".local/pilot-runs.json", {"runs": []})
    return {"profile": str((root / '.local/profile.json').resolve()), "pages": len(profile["sections"]),
            "setup_confirmed": True, "printing_enabled": False, "schedule_enabled": False}


def checked(folder):
    import newspaper as n
    folder = Path(folder)
    qa, receipt = n.load(folder / "qa.json"), n.load(folder / "receipt.json")
    need(qa.get("passed") and qa.get("visual_review") and receipt.get("visual_review"), "Mechanical and visual QA must both pass.")
    need(n.sha256(folder / "newspaper.pdf") == receipt["pdf_sha256"], "The PDF changed after review.")
    for name, digest in receipt["input_sha256"].items():
        need(n.sha256(folder / name) == digest, "The reviewed input changed.")
    return receipt


def remember(workspace, folder, receipt):
    import newspaper as n
    path = Path(workspace) / ".local/edition-history.json"
    history = n.load(path) if path.exists() else {"schema_version": 1, "editions": []}
    record = {**receipt.get("novelty", {}), "edition_id": receipt["edition_id"], "folder": str(Path(folder).resolve()),
              "pdf_sha256": receipt["pdf_sha256"], "delivery": receipt["delivery"], "reviewed": True}
    history["editions"] = [x for x in history["editions"] if x.get("edition_id") != record["edition_id"]] + [record]
    n.save(path, history)


def record_local(workspace, folder):
    import newspaper as n
    with lock(workspace):
        profile = n.load(Path(workspace) / ".local/profile.json")
        receipt = checked(folder)
        need(profile["delivery"]["channel"] == "local_pdf", "This user's delivery preference requires verified email.")
        receipt["delivery"] = {"status": "local_ready", "recorded_at": datetime.now(timezone.utc).isoformat()}
        n.save(Path(folder) / "receipt.json", receipt)
        remember(workspace, folder, receipt)
    return receipt["delivery"]


def validate_email(email, receipt, profile, at=None):
    import newspaper as n
    at = at or datetime.now(timezone.utc)
    expected = sorted(a.casefold() for a in profile["delivery"].get("recipients", []))
    need(profile["delivery"].get("channel") == "email" and expected and profile["delivery"].get("authorization"), "Configure this user's authorized email delivery first.")
    need(receipt.get("mode") != "demo", "A fictional sample cannot establish live newspaper email delivery.")
    need(email.get("status") == "sent" and email.get("edition_id") == receipt["edition_id"], "Require sent evidence for this edition, not a draft or outbox item.")
    need(sorted(a.casefold() for a in email.get("to", [])) == expected and not email.get("cc") and not email.get("bcc"), "Email recipients differ from the authorized profile.")
    need(all(email.get(k) for k in ("message_id", "provider", "sent_at")), "Record the actual provider, sent message ID and time.")
    sent = n.timestamp(email["sent_at"])
    need(sent <= at + timedelta(minutes=2) and sent >= n.timestamp(receipt["created_at"]) - timedelta(minutes=2), "Email timestamp is inconsistent with the checked PDF.")
    attachment = email.get("attachment", {})
    readback = Path(attachment.get("readback_path", ""))
    need(attachment.get("sha256") == receipt["pdf_sha256"] and readback.is_file() and n.sha256(readback) == receipt["pdf_sha256"],
         "Download/read back the sent PDF attachment and verify its actual bytes.")
    verify = email.get("verification", {})
    need(verify.get("method") == "sent_message_readback" and verify.get("message_id") == email["message_id"]
         and sorted(a.casefold() for a in verify.get("to", [])) == expected and verify.get("attachment_sha256") == receipt["pdf_sha256"]
         and all(verify.get(k) for k in ("tool", "reference", "verified_at")), "Save actual sent-message recipient and attachment verification evidence.")
    verified = n.timestamp(verify["verified_at"])
    need(sent - timedelta(minutes=2) <= verified <= at + timedelta(minutes=2), "Sent-message readback time is inconsistent.")
    return email


def record_email(workspace, folder, email):
    import newspaper as n
    with lock(workspace):
        receipt = checked(folder)
        if receipt["delivery"]["status"] == "emailed":
            return {**receipt["delivery"], "duplicate_skipped": True}
        profile = n.load(Path(workspace) / ".local/profile.json")
        validate_email(email, receipt, profile)
        receipt["email"] = email
        receipt["delivery"] = {"status": "emailed", "message_id": email["message_id"], "sent_at": email["sent_at"], "to": email["to"]}
        n.save(Path(folder) / "receipt.json", receipt)
        remember(workspace, folder, receipt)
    return receipt["delivery"]


def state(workspace, day=None):
    import newspaper as n
    root = Path(workspace)
    profile = n.load(root / ".local/profile.json")
    day = day or datetime.now(ZoneInfo(profile["timezone"])).date().isoformat()
    records = []
    for path in (root / "outputs").rglob("receipt.json"):
        receipt = n.load(path)
        if receipt.get("date") == day:
            receipt["folder"] = str(path.parent.resolve())
            receipt["pdf_intact"] = (path.parent / "newspaper.pdf").is_file() and n.sha256(path.parent / "newspaper.pdf") == receipt["pdf_sha256"]
            records.append(receipt)
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    delivered = next((r for r in records if r["delivery"]["status"] in {"emailed", "local_ready"} and r["pdf_intact"]), None)
    latest = delivered or (records[0] if records else None)
    stage = "not_started" if latest is None else "delivered" if delivered else "needs_review" if not latest.get("visual_review") else "email_delivery_pending" if profile["delivery"]["channel"] == "email" else "local_handoff_pending"
    return {"date": day, "stage": stage, "latest": latest, "printing": profile["printing"], "schedule": profile["schedule"]}


def print_gate(profile, receipt, snapshot, at, scheduled=False):
    import newspaper as n
    settings = profile["printing"]
    if receipt.get("mode") == "demo":
        return "Fictional samples are not automatically printed."
    if scheduled and not settings.get("enabled"):
        return "Automatic printing is off."
    if not settings.get("test_passed") or not settings.get("physical_output_verified"):
        return "The printer test needs physical confirmation."
    if settings.get("test_printer") != settings.get("printer"):
        return "The selected queue needs its own physical test."
    if profile["delivery"]["channel"] == "email" and receipt["delivery"]["status"] != "emailed":
        return "Verify email delivery before printing."
    if profile["delivery"]["channel"] == "email":
        try:
            validate_email(receipt.get("email", {}), receipt, profile, at)
        except (ValueError, KeyError, OSError):
            return "Email verification evidence is incomplete."
    elif receipt["delivery"]["status"] != "local_ready":
        return "Record the configured local handoff before printing."
    if not receipt.get("qa_passed") or not receipt.get("visual_review"):
        return "The newspaper requires mechanical and visual review."
    if receipt.get("coverage", {}).get("feature_gaps"):
        return "Family or academic coverage remains incomplete."
    for config in profile["sources"]:
        if not config.get("required_for_print", config.get("required", True)):
            continue
        source = snapshot["sources"].get(config["id"], {})
        if source.get("status") != "current" or source.get("complete") is not True or source.get("method") not in n.LIVE_METHODS or not source.get("observed_at"):
            return "Required source coverage is incomplete."
        if not 0 <= (at - n.timestamp(source["observed_at"])).total_seconds() <= config.get("max_age_minutes", 60) * 60:
            return "Required source coverage is stale."
    local = at.astimezone(ZoneInfo(profile["timezone"]))
    if scheduled and (local.date().isoformat() != receipt["date"] or local.time() >= time.fromisoformat(profile["schedule"]["deadline"])):
        return "The scheduled printing deadline has passed."
    return None


def printer_args(profile, pdf, title):
    settings = profile["printing"]
    queue = settings.get("printer", "")
    need(isinstance(queue, str) and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", queue), "Choose a valid pinned CUPS queue.")
    need(settings.get("color") in {"Gray", "RGB"} and settings.get("duplex") in {"None", "DuplexNoTumble", "DuplexTumble"}, "Unsupported printer color/duplex option.")
    return ["lp", "-d", queue, "-n", "1", "-t", title, "-o", "PageSize=" + profile["paper"],
            "-o", "ColorModel=" + settings["color"], "-o", "Duplex=" + settings["duplex"],
            "-o", "scaling=100", "-o", "print-scaling=none", str(pdf)]


def submit_print(workspace, folder, scheduled=False, reprint=False, runner=subprocess.run, at=None):
    import newspaper as n
    root, folder = Path(workspace), Path(folder)
    at = at or datetime.now(timezone.utc)
    with lock(root):
        profile = n.load(root / ".local/profile.json")
        receipt = checked(folder)
        snapshot = n.load(folder / "snapshot.json")
        reason = print_gate(profile, receipt, snapshot, at, scheduled)
        if reason:
            return {"status": "skipped", "reason": reason}
        ledger_path = root / ".local/print-ledger.json"
        ledger = n.load(ledger_path) if ledger_path.exists() else {"jobs": []}
        prior = [x for x in ledger["jobs"] if x["date"] == receipt["date"] and x["status"] in {"submitting", "submitted", "unverified", "queue_completed"}]
        if prior and not reprint:
            return {"status": "skipped", "duplicate_skipped": True, "reason": "A print attempt for this date already exists."}
        args = printer_args(profile, folder / "newspaper.pdf", "Newspaper-" + receipt["edition_id"])
        queue = runner(["lpstat", "-p", profile["printing"]["printer"]], capture_output=True, text=True, timeout=30)
        if queue.returncode or "disabled" in queue.stdout.lower():
            return {"status": "skipped", "reason": "The pinned printer is unavailable."}
        record = {"date": receipt["date"], "edition_id": receipt["edition_id"], "status": "submitting", "attempted_at": at.isoformat()}
        ledger["jobs"].append(record)
        n.save(ledger_path, ledger)  # Persist before the non-idempotent submission.
        try:
            result = runner(args, capture_output=True, text=True, timeout=30)
            match = re.search(r"request id is ([A-Za-z0-9_.-]+-\d+)", result.stdout)
            record.update(status="submitted" if result.returncode == 0 and match else "unverified", job_id=match.group(1) if match else None,
                          stdout=result.stdout[:1000], stderr=result.stderr[:1000])
        except (OSError, subprocess.SubprocessError) as error:
            record.update(status="unverified", error=str(error))
        receipt["printing"] = record
        n.save(ledger_path, ledger)
        n.save(folder / "receipt.json", receipt)
    return record


def printing_preference(workspace, enabled):
    import newspaper as n
    with lock(workspace):
        path = Path(workspace) / ".local/profile.json"
        profile = n.load(path)
        need(not enabled or (profile["printing"].get("test_passed") and profile["printing"].get("physical_output_verified")),
             "Submit and physically confirm a printer test before enabling automatic printing.")
        profile["printing"]["enabled"] = enabled
        n.save(path, profile)
    return profile["printing"]


def printer_test(workspace, submit=False, runner=subprocess.run):
    import newspaper as n
    from weasyprint import HTML
    root = Path(workspace)
    with lock(root):
        profile = n.load(root / ".local/profile.json")
        pdf = root / "work/printer-test.pdf"
        record_path = root / ".local/printer-test.json"
        record = n.load(record_path) if record_path.exists() else {}
        if record.get("status") in {"submitted", "submitting", "unverified"}:
            return {**record, "duplicate_skipped": True}
        HTML(string='<style>@page{size:' + profile["paper"] + ';margin:.5in} .r{width:6in;border-bottom:1pt solid} .b{width:1in;height:1in;border:1pt solid} h2{break-before:page}</style><h1>Newspaper printer test</h1><p>This line should measure six inches.</p><div class="r"></div><p>This square should measure one inch.</p><div class="b"></div><h2>Reverse side</h2><p>Check orientation, legibility and paper alignment.</p>').write_pdf(pdf)
        record = {"status": "ready", "pdf": str(pdf.resolve()), "pdf_sha256": n.sha256(pdf), "printer": profile["printing"].get("printer")}
        if submit:
            args = printer_args(profile, pdf, "Newspaper-Printer-Test")
            record["status"] = "submitting"
            n.save(record_path, record)
            try:
                result = runner(args, capture_output=True, text=True, timeout=30)
                match = re.search(r"request id is ([A-Za-z0-9_.-]+-\d+)", result.stdout)
                record.update(status="submitted" if result.returncode == 0 and match else "unverified", job_id=match.group(1) if match else None)
            except (OSError, subprocess.SubprocessError) as error:
                record.update(status="unverified", error=str(error))
        n.save(record_path, record)
    return record


def confirm_printer(workspace, job_id, user_confirmation):
    import newspaper as n
    with lock(workspace):
        root = Path(workspace)
        record = n.load(root / ".local/printer-test.json")
        need(record.get("status") == "submitted" and record.get("job_id") == job_id and bool(user_confirmation.strip()),
             "Record the new user's actual physical test confirmation for the submitted job.")
        profile = n.load(root / ".local/profile.json")
        need(record["printer"] == profile["printing"].get("printer"), "The selected printer changed; test the newly selected queue.")
        profile["printing"].update(test_passed=True, physical_output_verified=True, test_job_id=job_id,
                                   test_printer=record["printer"], user_confirmation=user_confirmation)
        n.save(root / ".local/profile.json", profile)
    return profile["printing"]


def pilot(workspace, run):
    import newspaper as n
    root = Path(workspace)
    need(all(k in run for k in ("date", "started_at", "finished_at", "delivery_status", "coverage_complete", "print_status")), "Pilot record is incomplete.")
    need(isinstance(run["coverage_complete"], bool), "Pilot coverage_complete must be a JSON boolean.")
    started, finished = n.timestamp(run["started_at"]), n.timestamp(run["finished_at"])
    elapsed = (finished - started).total_seconds() / 60
    need(elapsed >= 0, "Pilot finish precedes start.")
    if run["delivery_status"] in {"emailed", "local_ready"}:
        need(run.get("delivered_at"), "A delivered pilot run needs the actual verified delivery time.")
        delivered = n.timestamp(run["delivered_at"])
        need(started <= delivered <= finished, "Pilot delivery time must fall within the run.")
    with lock(root):
        profile = n.load(root / ".local/profile.json")
        zone = ZoneInfo(profile["timezone"])
        local_delivery = n.timestamp(run["delivered_at"]).astimezone(zone) if run.get("delivered_at") else None
        deadline_met = bool(local_delivery and local_delivery.date().isoformat() == run["date"] and local_delivery.time() <= time.fromisoformat(profile["schedule"]["deadline"]))
        path = root / ".local/pilot-runs.json"
        data = n.load(path)
        data["runs"] = [r for r in data["runs"] if r["date"] != run["date"]] + [{**run, "elapsed_minutes": elapsed, "deadline_met": deadline_met}]
        n.save(path, data)
    return {"runs": len(data["runs"]), "elapsed_minutes": elapsed, "start_adjustment_minutes": max(0, elapsed - 45),
            "pilot_complete": len(data["runs"]) >= 3, "full_coverage_accepted": len(data["runs"]) >= 3 and all(r["coverage_complete"] and r.get("deadline_met") and r["delivery_status"] in {"emailed", "local_ready"} for r in data["runs"][-3:])}
