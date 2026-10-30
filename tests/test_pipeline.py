import csv
import os
import tempfile
import unittest

import config
from pipeline import (
    NOT_FOUND,
    _fallback_copy,
    process_and_filter_influencers,
    run_sending_and_tracking_layer,
)


class PipelineTests(unittest.TestCase):
    def test_filter_marks_pass_and_failure_with_reasons(self):
        records = [
            {
                "name": "Creator",
                "followers": 25_000,
                "engagement_rate": "2.50%",
                "_niche_text": "beauty makeup tutorials",
            },
            {
                "name": "Out of range",
                "followers": 110_000,
                "_niche_text": "fashion style",
            },
            {
                "name": "Unverified",
                "followers": 20_000,
                "_niche_text": "general news",
            },
        ]

        result = process_and_filter_influencers(
            records, "Fashion & Beauty", min_engagement_rate=1.0
        )

        self.assertEqual([row["filter_status"] for row in result], [
            "PASSED",
            "FAILED",
            "FAILED",
        ])
        self.assertIn("within 5,000-100,000", result[0]["filter_reason"])
        self.assertIn("outside 5,000-100,000", result[1]["filter_reason"])
        self.assertIn("relevance", result[2]["filter_reason"])

    def test_filter_marks_unavailable_contact_and_metrics(self):
        record = {
            "name": "Creator",
            "followers": "Not Found",
            "_niche_text": "fashion creator",
        }
        result = process_and_filter_influencers([record], "Fashion & Beauty")[0]
        self.assertEqual(result["contact_email"], "Not Found")
        self.assertEqual(result["filter_status"], "FAILED")
        self.assertIn("follower count is unavailable", result["filter_reason"])

    def test_engagement_floor_is_an_explicit_filter(self):
        creator = {
            "name": "Creator",
            "followers": 20_000,
            "engagement_rate": "0.5%",
            "_niche_text": "fashion creator",
        }
        result = process_and_filter_influencers(
            [creator], "Fashion & Beauty", min_engagement_rate=1.0
        )[0]
        self.assertEqual(result["filter_status"], "FAILED")
        self.assertIn("below 1% minimum", result["filter_reason"])

    def test_local_fixture_has_exactly_50_labeled_synthetic_profiles(self):
        self.assertEqual(len(config.MOCK_INFLUENCERS), 50)
        self.assertEqual(
            sum(row["niche"] == "Fashion & Beauty" for row in config.MOCK_INFLUENCERS),
            25,
        )
        self.assertEqual(
            sum(row["niche"] == "Technology" for row in config.MOCK_INFLUENCERS),
            25,
        )
        self.assertEqual(
            len({row["profile_url"] for row in config.MOCK_INFLUENCERS}), 50
        )
        self.assertTrue(
            all(creator["is_synthetic"] for creator in config.MOCK_INFLUENCERS)
        )
        self.assertEqual(
            {creator["niche"] for creator in config.MOCK_INFLUENCERS},
            {"Fashion & Beauty", "Technology"},
        )
        self.assertTrue(
            all(creator["profile_url"].endswith(".invalid/" + creator["handle"][1:])
                for creator in config.MOCK_INFLUENCERS)
        )
        self.assertTrue(
            all(not creator["contact_email"] for creator in config.MOCK_INFLUENCERS)
        )
        self.assertTrue(
            all(3_000 <= creator["followers"] <= 120_000
                for creator in config.MOCK_INFLUENCERS)
        )

    def test_local_fixture_runs_filter_for_complete_niche(self):
        result = process_and_filter_influencers(
            config.MOCK_INFLUENCERS, "Fashion & Beauty"
        )
        self.assertEqual(len(result), 50)
        self.assertTrue(any(row["filter_status"] == "PASSED" for row in result))
        self.assertTrue(any(row["filter_status"] == "FAILED" for row in result))
        self.assertTrue(
            all(row["contact_email"] == NOT_FOUND for row in result)
        )

    def test_fallback_copy_is_personalized_and_meets_word_counts(self):
        copy = _fallback_copy(
            {
                "name": "Beauty Creator",
                "niche": "Fashion & Beauty",
                "recent_content": "Everyday skincare routine | Other video",
            }
        )
        self.assertIn("Everyday skincare routine", copy["email_pitch"])
        self.assertIn("Everyday skincare routine", copy["instagram_dm"])
        self.assertGreaterEqual(len(copy["email_pitch"].split()), 60)
        self.assertLessEqual(len(copy["email_pitch"].split()), 90)
        self.assertGreaterEqual(len(copy["instagram_dm"].split()), 15)
        self.assertLessEqual(len(copy["instagram_dm"].split()), 30)

    def test_tracker_simulates_and_prevents_duplicate_profiles(self):
        creator = {
            "name": "Creator",
            "profile_url": "https://www.youtube.com/channel/channel-id",
            "contact_email": "creator@example.invalid",
            "filter_status": "PASSED",
            "email_pitch": "A personalized email.",
            "instagram_dm": "A personalized DM.",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "tracker.csv")
            first = run_sending_and_tracking_layer([creator], path)
            second = run_sending_and_tracking_layer([creator], path)
            with open(path, newline="", encoding="utf-8") as tracker_file:
                rows = list(csv.DictReader(tracker_file))

        self.assertEqual(first["simulated_sent"], 1)
        self.assertEqual(second["duplicates_skipped"], 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["delivery_status"], "SIMULATED_SENT")

    def test_tracker_skips_missing_email_without_guessing(self):
        creator = {
            "name": "Creator",
            "profile_url": "https://www.youtube.com/channel/missing-email",
            "contact_email": "Not Found",
            "filter_status": "PASSED",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "tracker.csv")
            result = run_sending_and_tracking_layer([creator], path)
            with open(path, newline="", encoding="utf-8") as tracker_file:
                row = next(csv.DictReader(tracker_file))
        self.assertEqual(result["missing_email"], 1)
        self.assertEqual(row["contact_email"], "Not Found")
        self.assertEqual(
            row["delivery_status"], "SIMULATED_SKIPPED_MISSING_OR_INVALID_EMAIL"
        )


if __name__ == "__main__":
    unittest.main()
