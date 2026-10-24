import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("audit", Path(__file__).with_name("audit_conductor.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AuditTests(unittest.TestCase):
    def test_ca_date_triage(self):
        self.assertEqual(audit.ca_release_status("ca-certificates-20261020-r0"), "flagged")
        self.assertEqual(audit.ca_release_status("2026.10.21"), "review provenance")
        self.assertEqual(audit.ca_release_status("unknown"), "unknown")

    def test_node_security_boundaries(self):
        for version in ("20.20.0", "22.23.3", "24.22.0", "26.12.0", "23.0.0"):
            self.assertEqual(audit.node_status(version), "flagged")
        for version in ("22.23.4", "24.22.1", "26.12.1", "v24.23.0"):
            self.assertEqual(audit.node_status(version), "patched")
        self.assertEqual(audit.node_status("unavailable"), "unknown")

    def test_empty_store_is_unknown(self):
        self.assertEqual(audit.inspect_bundle("")["status"], "unknown")

    def test_parse_failure_is_unknown(self):
        self.assertEqual(audit.inspect_bundle("-----BEGIN CERTIFICATE-----\ninvalid\n-----END CERTIFICATE-----")["status"], "unknown")

    def test_inspect_failure_is_not_omitted(self):
        with patch.object(audit, "run", return_value=None):
            record = audit.inventory_container("container-id")
        self.assertEqual(record["id"], "container-id")
        self.assertEqual(record["status"], "unknown")

    def test_inventory_keeps_identity_without_exposing_environment(self):
        info = [{"Name": "/internal-db", "Image": "sha256:running", "Config": {"Image": "vendor:tag", "Env": ["PASSWORD=private-value"]}, "State": {"Status": "running"}}]
        def fake_run(*args):
            if args[:2] == ("docker", "inspect"):
                return json.dumps(info)
            if args[:3] == ("docker", "image", "inspect"):
                return '[{"RepoDigests":["vendor@sha256:pulled"]}]'
            return None
        with patch.object(audit, "run", side_effect=fake_run):
            record = audit.inventory_container("full-container-id")
        self.assertEqual(record["name"], "internal-db")
        self.assertEqual(record["running_image_id"], "sha256:running")
        self.assertTrue(record["review_required"])
        self.assertNotIn("private-value", json.dumps(record))

    def test_tls_timeout_is_not_clean(self):
        with patch.object(audit.subprocess, "run", side_effect=OSError):
            self.assertEqual(audit.check_tls("example.com")["status"], "unknown")

    def test_invalid_tls_targets_rejected(self):
        for target in ("https://example.com", "-example.com", "example.com:99999", "example.com/path"):
            with self.assertRaises(ValueError):
                audit.check_tls(target)


if __name__ == "__main__":
    unittest.main()
