import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import phase1_copilot_receipts as receipts
from phase1_bulk_triage import canonical, digest, git_blob


class CopilotReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source_root = self.root / "upstream"
        self.checkout = self.source_root / "pokefirered"
        self.checkout.mkdir(parents=True)
        subprocess.run(["git", "-C", str(self.checkout), "init", "-q"], check=True)
        (self.checkout / "src").mkdir()
        self.source = b"static int add(int a, int b)\n{\n    return a + b;\n}\n"
        self.license = b"Copyright and license terms for the pinned fixture.\n"
        (self.checkout / "src" / "sample.c").write_bytes(self.source)
        (self.checkout / "LICENSE").write_bytes(self.license)
        subprocess.run(["git", "-C", str(self.checkout), "add", "."], check=True)
        subprocess.run([
            "git", "-C", str(self.checkout), "-c", "user.name=Fixture",
            "-c", "user.email=fixture@example.test", "commit", "-qm", "fixture",
        ], check=True)
        self.pin = subprocess.check_output(
            ["git", "-C", str(self.checkout), "rev-parse", "HEAD"], text=True
        ).strip()
        self.old_pin = receipts.PINS["pret/pokefirered"]
        receipts.PINS["pret/pokefirered"] = self.pin
        self.addCleanup(self._restore_pin)
        self.head = "c" * 40
        self.repository = "xbaconator9000x/XGBA-ROM-Expansion"
        self.key = ("pret/pokefirered", "src/sample.c")
        self.dossier = {
            "provenance": {
                "repository": self.key[0],
                "pinned_revision": self.pin,
                "path": self.key[1],
                "git_blob_sha": git_blob(self.source),
                "source_content_sha256": hashlib.sha256(self.source).hexdigest(),
            },
            "review": {"semantic_signoff": False, "reviewer": None},
        }
        self.dossier_hash = digest(canonical(self.dossier))
        self.queue = {
            self.key: {
                "repo": self.key[0], "path": self.key[1],
                "blob_sha": git_blob(self.source), "evidence_sha256": self.dossier_hash,
            }
        }
        self.dossiers = {self.key: self.dossier}
        self.receipt = self._make_receipt()
        self.github_responses = {}

    def _restore_pin(self):
        receipts.PINS["pret/pokefirered"] = self.old_pin

    def _source_ref(self, path, data):
        return {
            "repository": "pret/pokefirered",
            "revision": self.pin,
            "path": path,
            "git_blob_sha1": git_blob(data),
            "source_sha256": hashlib.sha256(data).hexdigest(),
        }

    def _make_receipt(self):
        lines = len(self.source.splitlines())
        return {
            "schema": receipts.SCHEMA,
            "source": self._source_ref("src/sample.c", self.source),
            "machine_dossier_sha256": self.dossier_hash,
            "review": {
                "decision": "APPROVED",
                "semantic_rationale": "The complete pinned implementation and its call contract were reviewed.",
                "findings": [{
                    "claim": "The helper returns the sum of its two integer arguments.",
                    "source_lines": [1, 3],
                }],
                "whole_file_coverage": {
                    "scope": "WHOLE_FILE",
                    "source_sha256": hashlib.sha256(self.source).hexdigest(),
                    "source_lines": lines,
                    "reviewed_line_ranges": [[1, lines]],
                },
                "dependency_closure": {
                    "status": "COMPLETE",
                    "rationale": "The translation unit has no external declarations or includes.",
                    "dependencies": [],
                },
                "licensing": {
                    "status": "CLEARED",
                    "rationale": "The pinned repository license terms were reviewed for this item.",
                    "evidence": [self._source_ref("LICENSE", self.license)],
                },
                "evidence_distinctions": {
                    "source": {
                        "status": "VERIFIED",
                        "source_sha256": hashlib.sha256(self.source).hexdigest(),
                    },
                    "synthetic": {"status": "NOT_CLAIMED", "reason": "No synthetic result is claimed."},
                    "compiled_native": {"status": "NOT_RUN", "reason": "No native build result is claimed."},
                    "runtime_gameplay": {"status": "NOT_RUN", "reason": "No runtime result is claimed."},
                    "save_restart": {"status": "NOT_APPLICABLE", "reason": "This fixture has no save behavior."},
                    "physical_flash": {"status": "NOT_CLAIMED", "reason": "No hardware result is claimed."},
                },
                "objections": [],
            },
            "target": {
                "repository": self.repository,
                "pull_number": 8,
                "head_sha": self.head,
            },
        }

    def _seal(self, receipt=None):
        receipt = self.receipt if receipt is None else receipt
        body_hash = receipts.receipt_digest(receipt)
        receipt["attestation"] = {
            "receipt_sha256": body_hash,
        }
        self.github_responses = {
            f"https://api.github.com/repos/{self.repository}/pulls/8": {
                "user": {"login": "xbaconator9000x"},
                "head": {"sha": self.head},
            },
            f"https://api.github.com/repos/{self.repository}/pulls/8/reviews?per_page=100": [{
                "user": {"login": "Copilot"},
                "commit_id": self.head,
                "state": "COMMENTED",
                "submitted_at": "2026-10-30T00:00:00Z",
                "body": receipts.RECEIPT_MARKER + body_hash + "\n" + receipts.DECISION_MARKER,
            }],
            f"https://api.github.com/repos/{self.repository}/actions/runs?head_sha={self.head}&per_page=100": {
                "workflow_runs": [{
                    "name": "Phase 1 pinned source census and review dossiers",
                    "event": "pull_request",
                    "head_sha": self.head,
                    "status": "completed",
                    "conclusion": "success",
                    "pull_requests": [{
                        "number": 8,
                        "head": {"sha": self.head},
                    }],
                }],
            },
        }
        return receipt

    def _validate(self, receipt=None):
        return receipts.validate_receipt(
            self.receipt if receipt is None else receipt,
            queue=self.queue,
            dossiers=self.dossiers,
            source_root=self.source_root,
            expected_head=self.head,
            repository=self.repository,
            github_api=self.github_responses.__getitem__,
        )

    def test_valid_attributed_receipt_passes(self):
        self._seal()
        key, problems = self._validate()
        self.assertEqual(key, self.key)
        self.assertEqual(problems, [])

    def test_missing_or_forged_signature_is_rejected(self):
        self._seal()
        missing = copy.deepcopy(self.receipt)
        del missing["attestation"]
        self.assertTrue(self._validate(missing)[1])
        forged = copy.deepcopy(self.receipt)
        forged["attestation"]["receipt_sha256"] = "0" * 64
        self.assertTrue(self._validate(forged)[1])

    def test_stale_source_dossier_and_head_hashes_are_rejected(self):
        self._seal()
        for field, value in (("source_sha256", "0" * 64),):
            bad = copy.deepcopy(self.receipt)
            bad["source"][field] = value
            self._seal(bad)
            self.assertTrue(self._validate(bad)[1])
        bad = copy.deepcopy(self.receipt)
        bad["machine_dossier_sha256"] = "0" * 64
        self._seal(bad)
        self.assertTrue(self._validate(bad)[1])
        bad = copy.deepcopy(self.receipt)
        bad["target"]["head_sha"] = "d" * 40
        self._seal(bad)
        self.assertTrue(self._validate(bad)[1])

    def test_incomplete_scope_and_dependencies_are_rejected(self):
        self._seal()
        bad = copy.deepcopy(self.receipt)
        bad["review"]["whole_file_coverage"]["reviewed_line_ranges"] = [[1, 2]]
        self._seal(bad)
        self.assertTrue(self._validate(bad)[1])
        bad = copy.deepcopy(self.receipt)
        bad["review"]["dependency_closure"]["status"] = "INCOMPLETE"
        self._seal(bad)
        self.assertTrue(self._validate(bad)[1])

    def test_author_conflict_is_rejected(self):
        self._seal()
        pull_url = f"https://api.github.com/repos/{self.repository}/pulls/8"
        self.github_responses[pull_url]["user"]["login"] = "copilot"
        self.assertTrue(self._validate()[1])

    def test_missing_reviewer_identity_is_rejected(self):
        self._seal()
        review_url = f"https://api.github.com/repos/{self.repository}/pulls/8/reviews?per_page=100"
        self.github_responses[review_url][0]["user"] = {}
        self.assertTrue(self._validate()[1])

    def test_malformed_source_identity_is_rejected(self):
        self._seal()
        bad = copy.deepcopy(self.receipt)
        bad["source"]["repository"] = []
        self._seal(bad)
        key, problems = self._validate(bad)
        self.assertIsNone(key)
        self.assertTrue(problems)

    def test_unpinned_dependency_bytes_are_rejected(self):
        self._seal()
        bad = copy.deepcopy(self.receipt)
        dependency = self._source_ref("LICENSE", self.license)
        dependency["git_blob_sha1"] = "0" * 40
        bad["review"]["dependency_closure"]["dependencies"] = [dependency]
        self._seal(bad)
        self.assertTrue(self._validate(bad)[1])

    def test_unresolved_licensing_or_objections_are_rejected(self):
        self._seal()
        bad = copy.deepcopy(self.receipt)
        bad["review"]["licensing"]["status"] = "PENDING"
        self._seal(bad)
        self.assertTrue(self._validate(bad)[1])
        bad = copy.deepcopy(self.receipt)
        bad["review"]["objections"] = [{"status": "OPEN", "resolution": ""}]
        self._seal(bad)
        self.assertTrue(self._validate(bad)[1])

    def test_ci_only_and_unsupported_runtime_claims_are_rejected(self):
        self._seal()
        bad = copy.deepcopy(self.receipt)
        bad["review"]["evidence_distinctions"]["runtime_gameplay"] = {
            "status": "CI_ONLY", "reason": "CI passed."
        }
        self._seal(bad)
        self.assertTrue(self._validate(bad)[1])
        bad = copy.deepcopy(self.receipt)
        bad["review"]["evidence_distinctions"]["runtime_gameplay"] = {
            "status": "VERIFIED",
            "artifacts": [{
                "kind": "synthetic_test",
                "uri": "https://example.test/test.log",
                "sha256": "a" * 64,
            }],
        }
        self._seal(bad)
        self.assertTrue(self._validate(bad)[1])

    def test_unsuccessful_exact_head_validation_is_rejected(self):
        self._seal()
        run_url = f"https://api.github.com/repos/{self.repository}/actions/runs?head_sha={self.head}&per_page=100"
        self.github_responses[run_url]["workflow_runs"][0]["conclusion"] = "failure"
        self.assertTrue(self._validate()[1])
        self._seal()
        self.github_responses[run_url]["workflow_runs"][0]["pull_requests"][0]["number"] = 9
        self.assertTrue(self._validate()[1])

    def test_hash_without_explicit_review_decision_is_rejected(self):
        self._seal()
        review_url = f"https://api.github.com/repos/{self.repository}/pulls/8/reviews?per_page=100"
        self.github_responses[review_url][0]["body"] = (
            receipts.RECEIPT_MARKER + receipts.receipt_digest(self.receipt)
        )
        self.assertTrue(self._validate()[1])


if __name__ == "__main__":
    unittest.main()
