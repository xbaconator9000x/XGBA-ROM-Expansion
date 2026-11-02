"""Adversarial controls for the unchanged v6 current-head rejection."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import phase1_copilot_receipts_v6_adapter as v6
from phase1_copilot_receipts_v6_stale_head_negative import (
    STALE_BLOCKER, verify_stale_head_rejection,
)


def rows():
    return [
        {"source": f"{repo}:{path}", "status": "BLOCKED", "blocker": STALE_BLOCKER}
        for repo, path in v6.EXPECTED_ORDER
    ]


def encode(items):
    return "\n".join(json.dumps(item) for item in items)


class StaleHeadNegativeTests(unittest.TestCase):
    def test_exact_seven_rejections(self):
        self.assertEqual(verify_stale_head_rejection(2, encode(rows())), 7)

    def test_successful_validator_is_not_stale_negative(self):
        with self.assertRaises(ValueError):
            verify_stale_head_rejection(0, encode(rows()))

    def test_infrastructure_error_is_not_stale_negative(self):
        with self.assertRaises(ValueError):
            verify_stale_head_rejection(2, '{"status":"BLOCKED","blocker":"HTTP 403"}')

    def test_missing_record_rejected(self):
        with self.assertRaises(ValueError):
            verify_stale_head_rejection(2, encode(rows()[:-1]))

    def test_duplicate_record_rejected(self):
        altered = rows()
        altered[-1] = altered[0].copy()
        with self.assertRaises(ValueError):
            verify_stale_head_rejection(2, encode(altered))

    def test_unexpected_blocker_rejected(self):
        altered = rows()
        altered[0]["blocker"] = "GitHub API unavailable"
        with self.assertRaises(ValueError):
            verify_stale_head_rejection(2, encode(altered))

    def test_fake_validated_receipt_rejected(self):
        altered = rows()
        altered[0]["status"] = "COPILOT_RECEIPT_VALIDATED"
        with self.assertRaises(ValueError):
            verify_stale_head_rejection(2, encode(altered))

    def test_extra_field_rejected(self):
        altered = rows()
        altered[0]["approved"] = True
        with self.assertRaises(ValueError):
            verify_stale_head_rejection(2, encode(altered))

    def test_malformed_json_rejected(self):
        with self.assertRaises(ValueError):
            verify_stale_head_rejection(2, encode(rows()) + "\nnot json")


if __name__ == "__main__":
    unittest.main()
