#!/usr/bin/env python3
"""Read-only Docker runtime/CA inventory and served TLS checks (run on Conductor).

Never dumps container environments, commands, mounted data, or private keys.
Exit 1 = flagged; 2 = incomplete evidence; 0 = probes passed, manual review remains.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import ssl
import subprocess
import tempfile

BLOCKED = "emSign ECC Root CA - G3"
PEMS = re.compile(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", re.S)
MIN_NODE = {22: (23, 4), 24: (22, 1), 26: (12, 1)}


def ca_release_status(version):
    # Conservative triage only: vendors can backport without changing this date.
    match = re.search(r"(20\d{2})[.-]?(\d{2})[.-]?(\d{2})", version)
    if not match:
        return "unknown"
    return "flagged" if tuple(map(int, match.groups())) < (2026, 10, 21) else "review provenance"


def run(*args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        return result.stdout if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def node_status(version):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", version.strip())
    if not match:
        return "unknown"
    major, minor, patch = map(int, match.groups())
    return "patched" if major in MIN_NODE and (minor, patch) >= MIN_NODE[major] else "flagged"


def inspect_bundle(content):
    certs = PEMS.findall(content)
    if not certs:
        return {"status": "unknown", "reason": "empty or non-PEM store"}
    blocked = 0
    try:
        with tempfile.TemporaryDirectory() as directory:
            cert_path = Path(directory) / "cert.pem"
            for pem in certs:
                cert_path.write_text(pem)
                decoded = ssl._ssl._test_decode_cert(str(cert_path))
                blocked += any(key == "commonName" and value == BLOCKED
                               for rdn in decoded["subject"] for key, value in rdn)
    except (ValueError, ssl.SSLError, OSError):
        return {"status": "unknown", "reason": "certificate parsing failed"}
    return {"status": "flagged" if blocked else "checked", "certificates": len(certs),
            "blocked_roots": blocked, "sha256": hashlib.sha256(content.encode()).hexdigest()}


def inventory_container(container_id):
    raw = run("docker", "inspect", container_id)
    if raw is None:
        return {"id": container_id, "status": "unknown", "reason": "inspect failed"}
    info = json.loads(raw)[0]
    labels = info["Config"].get("Labels") or {}
    image_raw = run("docker", "image", "inspect", info["Image"])
    image = json.loads(image_raw)[0] if image_raw else {}
    record = {
        "id": container_id, "name": info["Name"].lstrip("/"),
        "image_reference": info["Config"]["Image"], "running_image_id": info["Image"],
        "repo_digests": image.get("RepoDigests") or [], "image_created": image.get("Created"),
        # A final image's digest does not identify its parent. Do not infer it.
        "base_image": (image.get("Config", {}).get("Labels") or {}).get("org.opencontainers.image.base.name", "unknown: inspect Dockerfile/build provenance"),
        "compose_project": labels.get("com.docker.compose.project"),
        "compose_service": labels.get("com.docker.compose.service"),
        "state": info["State"]["Status"],
        "health": info["State"].get("Health", {}).get("Status", "not configured"),
        "runtimes": {}, "ca_stores": {}, "review_required": [],
    }
    def execute(*args):
        return run("docker", "exec", container_id, *args)
    node = execute("node", "--version")
    if node:
        record["runtimes"]["node"] = {"version": node.strip(), "status": node_status(node)}
        bundled = execute("node", "-e", "process.stdout.write(require('tls').rootCertificates.join('\\n'))")
        record["ca_stores"]["node:bundled"] = inspect_bundle(bundled or "")
        effective = execute("node", "-e", "process.stdout.write(require('tls').getCACertificates('default').join('\\n'))")
        record["ca_stores"]["node:effective"] = inspect_bundle(effective or "")
    python = None
    for binary in ("python3", "python"):
        probe = execute(binary, "--version")
        if probe:
            python = binary
            record["runtimes"]["python"] = {"version": probe.strip(), "status": "review CA stores"}
            break
    paths = {"/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt", "/etc/ssl/cert.pem"}
    if python:
        probe = execute(python, "-c", "import json,ssl; print(json.dumps(ssl.get_default_verify_paths()._asdict()))")
        if probe:
            config = json.loads(probe)
            paths.update(p for k, p in config.items() if k in ("cafile", "openssl_cafile") and p)
        else:
            record["review_required"].append("Python effective CA paths could not be read")
        for module in ("certifi", "pip._vendor.certifi"):
            location = execute(python, "-c", f"import json; import {module} as c; print(json.dumps(dict(path=c.where(),version=getattr(c,'__version__','unknown'))))")
            if location:
                bundle = json.loads(location)
                paths.add(bundle["path"])
                record.setdefault("ca_releases", {})[module] = {"version": bundle["version"], "status": ca_release_status(bundle["version"])}
    php = execute("php", "-r", "echo PHP_VERSION;")
    if php:
        record["runtimes"]["php"] = {"version": php.strip(), "status": "review vendor security release"}
        record["review_required"].append("PHP present: verify vendor fixes before acceptance")
    for path in sorted(paths):
        content = execute("cat", path)
        if content is not None:
            record["ca_stores"][path] = inspect_bundle(content)
    packages = execute("sh", "-c", "if command -v apk >/dev/null; then apk info -v ca-certificates; elif command -v dpkg-query >/dev/null; then dpkg-query -W ca-certificates; else exit 1; fi")
    record["ca_package"] = packages.strip() if packages else "unknown"
    record.setdefault("ca_releases", {})["system"] = {"version": record["ca_package"], "status": ca_release_status(record["ca_package"])}
    if not record["runtimes"]:
        record["review_required"].append("Node/Python/PHP probes unavailable: classify other runtime from image provenance")
    if not record["ca_stores"]:
        record["review_required"].append("No readable PEM store: inspect custom/bundled stores manually")
    record["review_required"].append("Confirm custom CA stores and base freshness from build/vendor provenance; creation date alone is insufficient")
    return record


def check_tls(target):
    # DNS hostname optionally followed by a port; no URLs, IP literals or paths.
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?(?::[0-9]{1,5})?", target):
        raise ValueError(f"Invalid TLS target: {target}")
    host, _, port = target.partition(":")
    port = int(port or 443)
    if not 1 <= port <= 65535:
        raise ValueError("Invalid TLS port")
    command = ["openssl", "s_client", "-connect", f"{host}:{port}", "-servername", host,
               "-showcerts", "-verify_return_error", "-verify_hostname", host]
    try:
        result = subprocess.run(command, input="", text=True, capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return {"target": target, "status": "unknown", "reason": "TLS probe unavailable/timed out"}
    certs = PEMS.findall(result.stdout)
    if result.returncode or not certs:
        return {"target": target, "status": "unknown", "reason": "TLS chain/hostname verification failed"}
    with tempfile.TemporaryDirectory() as directory:
        leaf = Path(directory) / "leaf.pem"
        intermediates = Path(directory) / "intermediates.pem"
        leaf.write_text(certs[0])
        intermediates.write_text("\n".join(certs[1:]))
        args = ["openssl", "verify", "-show_chain", "-verify_hostname", host]
        if len(certs) > 1:
            args += ["-untrusted", str(intermediates)]
        chain = run(*args, str(leaf))
    if chain is None:
        return {"target": target, "status": "unknown", "reason": "Could not resolve trust anchor"}
    return {"target": target, "status": "flagged" if BLOCKED in chain else "checked",
            "verified_chain": chain.strip(), "leaf_sha256": hashlib.sha256(ssl.PEM_cert_to_DER_cert(certs[0])).hexdigest(),
            "review_required": "Check alternate chains and reconcile target list against all Caddy/Tailscale listeners"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tls-targets", type=Path, required=True, help="One DNS hostname[:port] per line, # comments allowed")
    parser.add_argument("--cert-dir", action="append", type=Path, default=[], help="Actual Caddy/proxy certificate directory; repeat as needed")
    args = parser.parse_args()
    targets = [line.split("#", 1)[0].strip() for line in args.tls_targets.read_text().splitlines()]
    targets = sorted(set(t for t in targets if t))
    ids = run("docker", "ps", "-q", "--no-trunc")
    if ids is None:
        raise SystemExit("Cannot enumerate Docker; no audit performed")
    containers = [inventory_container(cid) for cid in ids.split()]
    tls = [check_tls(target) for target in targets]
    stored = []
    for directory in args.cert_dir:
        if not directory.is_dir():
            stored.append({"directory": str(directory), "status": "unknown", "reason": "directory missing/unreadable"})
            continue
        for cert in sorted(directory.rglob("*")):
            if cert.is_file() and cert.suffix in (".crt", ".pem"):
                try:
                    stored.append({"path": str(cert), **inspect_bundle(cert.read_text())})
                except (OSError, UnicodeError):
                    stored.append({"path": str(cert), "status": "unknown", "reason": "read failed"})
    after = run("docker", "ps", "-q", "--no-trunc")
    stable = after is not None and set(after.split()) == set(ids.split())
    report = {"generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "containers": containers, "tls": tls, "stored_certificates": stored, "stable_inventory": stable,
              "manual_acceptance_required": True,
              "notes": "Read-only probes do not prove base freshness, custom-store coverage, all TLS listeners, or successful redeployment."}
    print(json.dumps(report, indent=2))
    statuses = [r.get("status") for c in containers for r in list(c.get("runtimes", {}).values()) + list(c.get("ca_stores", {}).values()) + list(c.get("ca_releases", {}).values())]
    statuses += [r["status"] for r in tls]
    statuses += [r["status"] for r in stored]
    if "flagged" in statuses:
        return 1
    if not containers or not targets or not stable or "unknown" in statuses or any(c.get("status") == "unknown" or c.get("review_required") for c in containers):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
