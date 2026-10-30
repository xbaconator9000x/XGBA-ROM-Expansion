import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import phase1_mapping_gate as gate


class LegacyDispositionTests(unittest.TestCase):
    def setUp(self):
        self.repository = "xbaconator9000x/XGBA-ROM-Expansion"
        self.sha = "a" * 40
        self.source = {"blob_sha": "b" * 40}
        self.review = {"evidence_sha256": "c" * 64}
        self.disposition = {
            "repo": "pret/pokefirered",
            "path": "src/example.c",
            "git_blob_sha": self.source["blob_sha"],
            "evidence_sha256": self.review["evidence_sha256"],
            "status": "mapped_dependencies",
            "reviewer": "reviewer",
            "semantic_rationale": "Reviewed source behavior and dependency contracts in full.",
            "contract_ids": "FIRERED_SCRIPT_NATIVE_CALLBACK",
        }
        self.disposition["reviewer_provenance"] = json.dumps({
            "repository": self.repository,
            "pull_number": 8,
            "review_id": 321,
            "head_sha": self.sha,
            "reviewer_login": "reviewer",
            "disposition_sha256": "",
        }, sort_keys=True, separators=(",", ":"))
        provenance = json.loads(self.disposition["reviewer_provenance"])
        provenance["disposition_sha256"] = gate.legacy_disposition_digest(self.disposition)
        self.disposition["reviewer_provenance"] = json.dumps(
            provenance, sort_keys=True, separators=(",", ":")
        )
        self.api = {
            f"https://api.github.com/repos/{self.repository}/pulls/8": {
                "user": {"login": "pr-author"},
            },
            f"https://api.github.com/repos/{self.repository}/pulls/8/reviews?per_page=100&page=1": [{
                "id": 321,
                "user": {"login": "reviewer"},
                "commit_id": self.sha,
                "state": "COMMENTED",
                "submitted_at": "2026-10-30T00:00:00Z",
                "body": (
                    gate.LEGACY_RECEIPT_MARKER
                    + provenance["disposition_sha256"]
                    + "\n"
                    + gate.DECISION_MARKER
                ),
            }],
            f"https://api.github.com/repos/{self.repository}/pulls/8/reviews?per_page=100&page=2": [],
        }

    def test_attributed_legacy_receipt_remains_valid(self):
        self.assertEqual(
            gate.disposition_problems(self.disposition, self.source, self.review), []
        )
        self.assertEqual(
            gate.verify_legacy_provenance(
                self.disposition, self.repository, self.api.__getitem__
            ),
            [],
        )

    def test_forged_reviewer_name_without_provenance_is_rejected(self):
        forged = dict(self.disposition)
        forged["reviewer"] = "independent-reviewer"
        forged.pop("reviewer_provenance")
        self.assertTrue(gate.disposition_problems(forged, self.source, self.review))

    def test_forged_or_stale_github_review_is_rejected(self):
        self.api[
            f"https://api.github.com/repos/{self.repository}/pulls/8/reviews?per_page=100&page=1"
        ][0]["body"] = "No matching disposition receipt."
        self.assertTrue(
            gate.verify_legacy_provenance(
                self.disposition, self.repository, self.api.__getitem__
            )
        )

    def test_reviewer_cannot_be_pull_request_author(self):
        self.api[f"https://api.github.com/repos/{self.repository}/pulls/8"]["user"]["login"] = "reviewer"
        self.assertTrue(
            gate.verify_legacy_provenance(
                self.disposition, self.repository, self.api.__getitem__
            )
        )


if __name__ == "__main__":
    unittest.main()
