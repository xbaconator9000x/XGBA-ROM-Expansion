"""Fail-closed tests for the task-scoped Poryscript ABI review record."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.copilot_poryscript_abi_review import (
    DEFAULT_RECORD,
    ROOT,
    validate_closure_record,
    git_blob_sha1,
    validate_record,
    verify_source_entry,
)
from tools.copilot_poryscript_abi_review_probes import expected_rodata


class PoryscriptAbiReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads(DEFAULT_RECORD.read_text(encoding="utf-8"))
        cls.closure = json.loads(
            (DEFAULT_RECORD.parent / "closure-review.json").read_text(
                encoding="utf-8"
            )
        )

    def test_record_is_pinned_and_non_approving(self):
        sources = validate_record(self.record)
        self.assertGreater(len(sources), 0)
        self.assertEqual(self.record["accounting"]["new_approvals"], 0)
        self.assertEqual(self.record["accounting"]["phase1_gate"], "FAIL_INCOMPLETE")

    def test_false_approval_is_rejected(self):
        changed = copy.deepcopy(self.record)
        changed["accounting"]["new_approvals"] = 1
        with self.assertRaisesRegex(ValueError, "zero approval total"):
            validate_record(changed)

    def test_legacy_witness_artifact_digest_is_pinned(self):
        changed = copy.deepcopy(self.record)
        changed["actual_cli_witness"]["artifact_zip_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "exact successful result"):
            validate_record(changed)

        changed = copy.deepcopy(self.record)
        changed["original_evidence"]["actual_cli_workflow"]["artifact_zip_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "original PR #20 witness provenance changed"):
            validate_record(changed)

    def test_reused_reviewer_identity_is_rejected(self):
        changed = copy.deepcopy(self.record)
        changed["reviewer"]["identity"] = changed["reviewer"]["source_interpreter_identity"]
        with self.assertRaisesRegex(ValueError, "distinct"):
            validate_record(changed)

    def test_pinned_file_and_line_hashes_are_checked(self):
        data = b"first line\nsecond line\n"
        entry = {
            "repository": "huderlem/poryscript",
            "path": "fixture.go",
            "git_blob_sha1": git_blob_sha1(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "evidence_ranges": [{
                "start": 2,
                "end": 2,
                "sha256": hashlib.sha256(b"second line\n").hexdigest(),
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.go"
            source.write_bytes(data)
            verify_source_entry(entry, root)
            changed = data.replace(b"second", b"changed")
            source.write_bytes(changed)
            with self.assertRaisesRegex(ValueError, "Git blob mismatch"):
                verify_source_entry(entry, root)
            entry["git_blob_sha1"] = git_blob_sha1(changed)
            entry["sha256"] = hashlib.sha256(changed).hexdigest()
            with self.assertRaisesRegex(ValueError, "line-range SHA-256 mismatch"):
                verify_source_entry(entry, root)

    def test_closure_links_all_file_rows_to_original_dossiers(self):
        files, ranges = validate_closure_record(self.closure)
        self.assertEqual(len(files), 81)
        self.assertEqual(len(ranges), 58)
        self.assertTrue(all(
            row[-1] == "NEEDS_EVIDENCE"
            for row in self.closure["coverage"]["file_rows"]
        ))
        self.assertEqual(self.closure["accounting"]["phase1_gate"],
                         "FAIL_INCOMPLETE")
        self.assertFalse(self.closure["reviewer"]["authenticated_github_review_attribution"])

    def test_closure_rejects_approval_and_source_mutations(self):
        changed = copy.deepcopy(self.closure)
        changed["coverage"]["file_rows"][0][-1] = "APPROVED"
        with self.assertRaisesRegex(ValueError, "only NEEDS_EVIDENCE"):
            validate_closure_record(changed)

        changed = copy.deepcopy(self.closure)
        script_row = next(
            row for row in changed["coverage"]["file_rows"]
            if row[0] == "f" and row[1] == "src/script.c"
        )
        script_row[3] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source SHA-256 differs"):
            validate_closure_record(changed)

        changed = copy.deepcopy(self.closure)
        changed["original_machine_evidence"]["dossiers"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "identity differs from pinned dossiers"):
            validate_closure_record(changed)

        changed = copy.deepcopy(self.closure)
        changed["historical_witness"]["artifact_zip_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "historical exact-head witness provenance changed"):
            validate_closure_record(changed)

        changed = copy.deepcopy(self.closure)
        changed["local_actual_cli_probe"]["fixture_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "local actual CLI probe digest changed"):
            validate_closure_record(changed)

    def test_closure_rejects_archive_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp)
            for archive in self.closure["original_machine_evidence"].values():
                link = archive_root / archive["path"]
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(ROOT / archive["path"])
            with self.assertRaisesRegex(ValueError, "escapes archive root"):
                validate_closure_record(self.closure, archive_root)

    def test_closure_rejects_missing_dependency_endpoint(self):
        changed = copy.deepcopy(self.closure)
        changed["coverage"]["dependency_edges"][0][1] = "missing.c"
        with self.assertRaisesRegex(ValueError, "endpoint lacks"):
            validate_closure_record(changed)

    def test_probe_expected_object_mutations_are_sensitive(self):
        raw, _, relocations = expected_rodata()
        zero_changed, _, _ = expected_rodata(zero_operand=1)
        overflow_changed, _, _ = expected_rodata(overflow_operand=1)
        self.assertEqual(raw[41:43], b"\0\0")
        self.assertEqual(raw[67:69], b"\0\0")
        self.assertEqual(zero_changed[41:43], b"\x01\0")
        self.assertEqual(overflow_changed[67:69], b"\x01\0")
        self.assertEqual(relocations, (1, 6, 11, 16, 21, 26, 35, 45, 53, 63, 71))


if __name__ == "__main__":
    unittest.main()
