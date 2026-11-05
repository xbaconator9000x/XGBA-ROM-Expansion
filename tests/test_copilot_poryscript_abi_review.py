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
    validate_file_inspection_record,
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
        cls.inspection = json.loads(
            (DEFAULT_RECORD.parent / "file-inspection-followup.json").read_text(
                encoding="utf-8"
            )
        )
        cls.dispatch_inspection = json.loads(
            (DEFAULT_RECORD.parent / "fire-red-script-dispatch-followup.json").read_text(
                encoding="utf-8"
            )
        )
        cls.map_header_inspection = json.loads(
            (DEFAULT_RECORD.parent / "map-header-review-followup.json").read_text(
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

    def test_file_inspection_records_are_linked_and_non_approving(self):
        result = validate_file_inspection_record(self.inspection, self.closure)
        self.assertEqual(result["files_with_full_source_text_retrieved"], 4)
        self.assertEqual(result["whole_file_semantic_reviews"], 0)
        self.assertEqual(result["new_qualifying_copilot_receipts"], 0)
        self.assertEqual(result["phase1_gate"], "FAIL_INCOMPLETE")
        self.assertTrue(all(
            item["verdict"] == "NEEDS_EVIDENCE" and
            item["whole_file_semantic_disposition"] is False
            for item in self.inspection["files"]
        ))

    def test_file_inspection_rejects_identity_verdict_and_attribution_mutations(self):
        changed = copy.deepcopy(self.inspection)
        changed["files"][0]["git_blob_sha1"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "source/dossier identity differs"):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.inspection)
        changed["files"][0]["verdict"] = "APPROVED"
        with self.assertRaisesRegex(ValueError, "must not claim whole-file disposition"):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.inspection)
        changed["reviewer"]["authenticated_github_review_attribution"] = True
        with self.assertRaisesRegex(ValueError, "missing authenticated attribution"):
            validate_file_inspection_record(changed, self.closure)

    def test_fire_red_dispatch_inspection_is_pinned_and_non_approving(self):
        result = validate_file_inspection_record(
            self.dispatch_inspection, self.closure
        )
        self.assertEqual(result["files_with_full_source_text_retrieved"], 4)
        self.assertEqual(result["whole_file_semantic_reviews"], 0)
        self.assertEqual(result["new_qualifying_copilot_receipts"], 0)
        self.assertEqual(result["phase1_gate"], "FAIL_INCOMPLETE")
        self.assertEqual(
            {item["path"] for item in self.dispatch_inspection["files"]},
            {
                "asm/macros/map.inc",
                "data/script_cmd_table.inc",
                "src/scrcmd.c",
                "src/overworld.c",
            },
        )

    def test_fire_red_dispatch_receipt_rejects_dossier_and_dependency_mutations(self):
        changed = copy.deepcopy(self.dispatch_inspection)
        changed["files"][0]["dossier_record_line_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source/dossier identity differs"):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.dispatch_inspection)
        changed["files"][0]["dependency_links"][0]["path"] = "missing.c"
        with self.assertRaisesRegex(ValueError, "dependency lacks a pinned endpoint"):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.dispatch_inspection)
        changed["files"][0]["evidence_ranges"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "line evidence differs from closure"):
            validate_file_inspection_record(changed, self.closure)

    def test_map_header_handoff_is_complete_and_non_approving(self):
        result = validate_file_inspection_record(
            self.map_header_inspection, self.closure
        )
        self.assertEqual(result["files_with_full_source_text_retrieved"], 7)
        self.assertEqual(result["complete_source_files_read"], 7)
        self.assertEqual(result["whole_file_semantic_reviews"], 0)
        self.assertEqual(result["new_qualifying_copilot_receipts"], 0)
        self.assertEqual(result["phase1_gate"], "FAIL_INCOMPLETE")
        self.assertEqual(
            {item["path"] for item in self.map_header_inspection["files"]},
            {
                "tools/mapjson/mapjson.cpp",
                "map_data_rules.mk",
                "data/maps.s",
                "include/global.fieldmap.h",
                "data/event_scripts.s",
                "data/maps/Route18/scripts.inc",
                "include/constants/map_scripts.h",
            },
        )
        self.assertTrue(all(
            item["complete_source_inspection"] is True and
            item["whole_file_semantic_disposition"] is False and
            item["verdict"] == "NEEDS_EVIDENCE"
            for item in self.map_header_inspection["files"]
        ))

    def test_map_header_handoff_rejects_source_and_dossier_mutations(self):
        for index in range(len(self.map_header_inspection["files"])):
            for field in ("git_blob_sha1", "sha256", "dossier_record_line_sha256"):
                with self.subTest(index=index, field=field):
                    changed = copy.deepcopy(self.map_header_inspection)
                    changed["files"][index][field] = "0" * (
                        40 if field == "git_blob_sha1" else 64
                    )
                    with self.assertRaisesRegex(
                        ValueError, "source/dossier identity differs"
                    ):
                        validate_file_inspection_record(changed, self.closure)

    def test_map_header_handoff_rejects_range_and_dependency_mutations(self):
        changed = copy.deepcopy(self.map_header_inspection)
        changed["files"][0]["evidence_ranges"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "line evidence differs from closure"):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.map_header_inspection)
        changed["files"][0]["supplemental_evidence_ranges"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "supplemental source evidence differs"):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.map_header_inspection)
        changed["files"][0]["dependency_links"][0]["path"] = "missing.c"
        with self.assertRaisesRegex(ValueError, "dependency lacks a pinned endpoint"):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.map_header_inspection)
        changed["files"][0]["complete_source_inspection"] = False
        with self.assertRaisesRegex(ValueError, "complete source identity"):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.map_header_inspection)
        changed["files"][0]["line_count"] += 1
        with self.assertRaisesRegex(ValueError, "complete source identity"):
            validate_file_inspection_record(changed, self.closure)

    def test_map_header_handoff_rejects_verdict_and_review_claim_mutations(self):
        changed = copy.deepcopy(self.map_header_inspection)
        changed["files"][0]["verdict"] = "COPILOT_REVIEWED"
        with self.assertRaisesRegex(ValueError, "must not claim whole-file disposition"):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.map_header_inspection)
        changed["files"][0]["whole_file_semantic_disposition"] = True
        with self.assertRaisesRegex(ValueError, "must not claim whole-file disposition"):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.map_header_inspection)
        changed["reviewer"]["authenticated_github_review_attribution"] = True
        with self.assertRaisesRegex(ValueError, "missing authenticated attribution"):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.map_header_inspection)
        changed["negative_controls"].pop()
        with self.assertRaisesRegex(ValueError, "negative-control set is incomplete"):
            validate_file_inspection_record(changed, self.closure)

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
