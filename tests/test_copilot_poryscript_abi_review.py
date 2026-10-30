"""Fail-closed tests for the task-scoped Poryscript ABI review record."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.copilot_poryscript_abi_review import (
    DEFAULT_RECORD,
    git_blob_sha1,
    validate_record,
    verify_source_entry,
)


class PoryscriptAbiReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads(DEFAULT_RECORD.read_text(encoding="utf-8"))

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


if __name__ == "__main__":
    unittest.main()
