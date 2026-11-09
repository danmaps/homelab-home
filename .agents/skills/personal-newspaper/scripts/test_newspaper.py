"""Behavioral checks for the portable starter, using fictional inputs only."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

import newspaper


class NewspaperTests(unittest.TestCase):
    def setUp(self):
        self.profile = newspaper.load(newspaper.ASSETS / "profile.example.json")
        self.snapshot = newspaper.load(newspaper.ASSETS / "demo.snapshot.json")
        self.edition = newspaper.load(newspaper.ASSETS / "demo.edition.json")

    def check(self):
        return newspaper.validate(self.profile, self.snapshot, self.edition, newspaper.ASSETS)

    def make_live(self):
        self.snapshot["mode"] = self.edition["mode"] = "live"
        for source in self.snapshot["sources"].values():
            source.update(status="current", complete=True, method="connector")

    def test_fictional_sample_never_claims_current_coverage(self):
        result = self.check()
        self.assertTrue(result["passed"])
        self.assertFalse(result["coverage"]["complete"])

    def test_missing_secondary_newsletter_topic_is_rejected(self):
        self.edition["pages"][2]["articles"].pop()
        with self.assertRaisesRegex(ValueError, "Mandatory topic missing.*community:sky"):
            self.check()

    def test_topic_on_wrong_page_does_not_satisfy_coverage(self):
        moved = self.edition["pages"][2]["articles"].pop()
        self.edition["pages"][0]["articles"].append(moved)
        with self.assertRaisesRegex(ValueError, "Mandatory topic missing"):
            self.check()

    def test_unknown_citation_is_rejected(self):
        self.edition["pages"][0]["articles"][0]["source_ids"] = ["invented:reference"]
        with self.assertRaisesRegex(ValueError, "Unknown cited"):
            self.check()

    def test_future_observation_is_rejected(self):
        self.snapshot["sources"]["calendar"]["observed_at"] = "2026-10-24T08:00:00+00:00"
        with self.assertRaisesRegex(ValueError, "after compilation"):
            self.check()

    def test_calendar_window_crosses_month_using_days(self):
        self.snapshot["date"] = self.edition["date"] = "2026-10-31"
        self.edition["as_of"] = "2026-10-31T07:15:00+00:00"
        page = self.edition["pages"][1]
        page.update(start_date="2026-11-01", end_date="2026-11-01")
        page["articles"][0]["event_date"] = "2026-11-01"
        self.assertTrue(self.check()["passed"])
        page["articles"][0]["event_date"] = "2026-10-31"
        with self.assertRaisesRegex(ValueError, "outside its planning"):
            self.check()

    def test_stale_evidence_blocks_strict_coverage(self):
        self.make_live()
        self.profile["allow_partial"] = False
        self.snapshot["sources"]["calendar"]["observed_at"] = "2026-10-23T07:00:00+00:00"
        with self.assertRaisesRegex(ValueError, "coverage is incomplete"):
            self.check()

    def test_cache_cannot_claim_live_complete_status(self):
        self.make_live()
        self.snapshot["sources"]["calendar"]["method"] = "local_cache"
        with self.assertRaisesRegex(ValueError, "complete live observation"):
            self.check()

    def test_missing_calendar_remains_an_explicit_gap(self):
        self.make_live()
        self.snapshot["sources"]["calendar"].update(status="unavailable", complete=False,
                                                     observed_at=None, items=[])
        self.edition["pages"][0]["articles"][0]["source_ids"] = ["community:seed"]
        self.edition["pages"][1]["articles"][0]["source_ids"] = ["community:repair"]
        result = self.check()
        self.assertFalse(result["coverage"]["complete"])
        self.assertEqual(result["coverage"]["sources"][0]["status"], "unavailable")

    def test_duplicate_facts_need_an_explicit_reason(self):
        article = deepcopy(self.edition["pages"][0]["articles"][0])
        article.pop("event_date")
        self.edition["pages"][1]["articles"].append(article)
        with self.assertRaisesRegex(ValueError, "Duplicate fact"):
            self.check()
        self.edition["duplicate_exceptions"] = [{"fact_id": "demo:walk", "page_ids": ["today", "tomorrow"],
                                                  "reason": "Explicit planning recap for this test."}]
        self.assertTrue(self.check()["passed"])

    def test_unsafe_link_and_image_escape_are_rejected(self):
        item = self.snapshot["sources"]["calendar"]["items"][0]
        item["source_url"] = "javascript:alert(1)"
        with self.assertRaisesRegex(ValueError, "Unsupported source URL"):
            self.check()
        item.pop("source_url")
        with self.assertRaisesRegex(ValueError, "stay under"):
            newspaper.image_path({"path": "../../outside.png"}, newspaper.ASSETS)

    def test_review_checks_pdf_bytes_and_preserves_outbound_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / "newspaper.pdf").write_bytes(b"checked fixture bytes")
            (folder / "page-1.png").write_bytes(b"preview fixture bytes")
            newspaper.save(folder / "profile.json", self.profile)
            newspaper.save(folder / "qa.json", {"passed": True, "physical_pages": 1,
                "preview_sha256": {"page-1.png": newspaper.sha256(folder / "page-1.png")}})
            newspaper.save(folder / "receipt.json", {"qa_passed": True,
                "pdf_sha256": newspaper.sha256(folder / "newspaper.pdf"),
                "input_sha256": {"profile.json": newspaper.sha256(folder / "profile.json")},
                "delivery": {"status": "not_requested"}, "printing": {"status": "not_requested"}})
            reviewed = newspaper.review(folder, "Inspected the fixture in this isolated integrity test.")
            self.assertTrue(reviewed["visual_review"])
            self.assertEqual(reviewed["delivery"]["status"], "not_requested")
            self.assertEqual(reviewed["printing"]["status"], "not_requested")
            (folder / "newspaper.pdf").write_bytes(b"changed bytes")
            with self.assertRaisesRegex(ValueError, "PDF changed"):
                newspaper.review(folder, "Cannot approve modified bytes.")


if __name__ == "__main__":
    unittest.main()
