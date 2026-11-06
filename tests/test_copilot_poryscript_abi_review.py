"""Fail-closed tests for the task-scoped Poryscript ABI review record."""
import copy
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.copilot_poryscript_abi_review import (
    DEFAULT_RECORD,
    FILE_INSPECTION_SCHEMAS,
    ROOT,
    validate_closure_record,
    validate_file_inspection_record,
    validate_poryscript_lexer_followup,
    validate_poryscript_parser_emitter_followup,
    git_blob_sha1,
    validate_record,
    verify_file_inspection_sources,
    verify_poryscript_lexer_sources,
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
        cls.poryscript_firered_inspection = json.loads(
            (DEFAULT_RECORD.parent / "poryscript-firered-abi-followup.json").read_text(
                encoding="utf-8"
            )
        )
        cls.preprocessor_inspection = json.loads(
            (DEFAULT_RECORD.parent / "preprocessor-dependency-followup.json").read_text(
                encoding="utf-8"
            )
        )
        cls.lexer_input_followup = json.loads(
            (DEFAULT_RECORD.parent / "poryscript-lexer-input-followup.json").read_text(
                encoding="utf-8"
            )
        )
        cls.parser_emitter_followup = json.loads(
            (DEFAULT_RECORD.parent / "parser-emitter-input-followup.json").read_text(
                encoding="utf-8"
            )
        )

    def test_poryscript_lexer_handoff_is_complete_and_non_approving(self):
        result = validate_poryscript_lexer_followup(
            self.lexer_input_followup, self.closure
        )
        self.assertEqual(result["status"],
                         "PASS_LEXER_SOURCE_RECORD_NOT_SEMANTIC_APPROVAL")
        self.assertEqual(result["source_files_recorded"], 2)
        self.assertEqual(result["whole_file_semantic_reviews"], 0)
        self.assertEqual(self.lexer_input_followup["accounting"]["phase1_gate"],
                         "FAIL_INCOMPLETE")

    def test_poryscript_lexer_handoff_rejects_identity_and_dossier_mutations(self):
        mutations = (
            ("git_blob_sha1", "0" * 40),
            ("sha256", "0" * 64),
            ("dossier_record_line_sha256", "0" * 64),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                changed = copy.deepcopy(self.lexer_input_followup)
                changed["files"][0][field] = value
                with self.assertRaises(ValueError):
                    validate_poryscript_lexer_followup(changed, self.closure)

    def test_poryscript_lexer_handoff_rejects_source_range_mutations(self):
        for field, value in (("end", 491), ("sha256", "0" * 64)):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.lexer_input_followup)
                changed["files"][0]["supplemental_evidence_ranges"][0][field] = value
                with self.assertRaisesRegex(ValueError, "full-file range"):
                    validate_poryscript_lexer_followup(changed, self.closure)

    def test_poryscript_lexer_handoff_rejects_dependency_mutations(self):
        changed = copy.deepcopy(self.lexer_input_followup)
        changed["files"][0]["dependency_links"][0]["path"] = "emitter/emitter.go"
        with self.assertRaisesRegex(ValueError, "dependency links differ"):
            validate_poryscript_lexer_followup(changed, self.closure)

    def test_poryscript_lexer_handoff_rejects_license_and_objection_mutations(self):
        changed = copy.deepcopy(self.lexer_input_followup)
        changed["files"][0]["license_evidence"]["status"] = "APPROVED"
        with self.assertRaisesRegex(ValueError, "license applicability"):
            validate_poryscript_lexer_followup(changed, self.closure)

        changed = copy.deepcopy(self.lexer_input_followup)
        changed["objections"][0]["status"] = "RESOLVED"
        with self.assertRaisesRegex(ValueError, "objections"):
            validate_poryscript_lexer_followup(changed, self.closure)

    def test_poryscript_lexer_handoff_rejects_verdict_attribution_and_gate_mutations(self):
        changed = copy.deepcopy(self.lexer_input_followup)
        changed["files"][0]["verdict"] = "APPROVED"
        with self.assertRaisesRegex(ValueError, "disposition"):
            validate_poryscript_lexer_followup(changed, self.closure)

        changed = copy.deepcopy(self.lexer_input_followup)
        changed["reviewer"]["authenticated_github_review_attribution"] = True
        with self.assertRaisesRegex(ValueError, "attribution"):
            validate_poryscript_lexer_followup(changed, self.closure)

        changed = copy.deepcopy(self.lexer_input_followup)
        changed["accounting"]["phase1_gate"] = "PASS"
        with self.assertRaisesRegex(ValueError, "Phase 1 and non-approving"):
            validate_poryscript_lexer_followup(changed, self.closure)

    def test_poryscript_lexer_source_verification_rejects_modified_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "lexer/lexer.go"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"modified pinned source\n")
            with self.assertRaisesRegex(ValueError, "Git blob mismatch"):
                verify_poryscript_lexer_sources(
                    self.lexer_input_followup, self.closure, root,
                    source_files_only=True,
                )

    def test_parser_emitter_handoff_is_complete_and_non_approving(self):
        result = validate_poryscript_parser_emitter_followup(
            self.parser_emitter_followup, self.closure
        )
        self.assertEqual(
            result["status"],
            "PASS_PARSER_EMITTER_RECORD_NOT_SEMANTIC_APPROVAL",
        )
        self.assertEqual(result["source_files_recorded"], 1)
        self.assertEqual(result["whole_file_semantic_reviews"], 0)
        self.assertEqual(self.parser_emitter_followup["accounting"]["phase1_gate"],
                         "FAIL_INCOMPLETE")
        self.assertEqual(
            set(self.parser_emitter_followup["actual_cli_probe"]["numeric_cases"]),
            {"0", "0x", "0x10000", "-1", "65536"},
        )

    def test_parser_emitter_handoff_rejects_source_identity_mutation(self):
        changed = copy.deepcopy(self.parser_emitter_followup)
        changed["files"][0]["git_blob_sha1"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "source identity"):
            validate_poryscript_parser_emitter_followup(changed, self.closure)

    def test_parser_emitter_handoff_rejects_dependency_mutation(self):
        changed = copy.deepcopy(self.parser_emitter_followup)
        changed["files"][0]["dependency_links"][0]["path"] = "emitter/emitter.go"
        with self.assertRaisesRegex(ValueError, "dependency links differ"):
            validate_poryscript_parser_emitter_followup(changed, self.closure)

    def test_parser_emitter_handoff_rejects_verdict_and_gate_mutations(self):
        changed = copy.deepcopy(self.parser_emitter_followup)
        changed["files"][0]["verdict"] = "APPROVED"
        with self.assertRaisesRegex(ValueError, "source identity or disposition"):
            validate_poryscript_parser_emitter_followup(changed, self.closure)

        changed = copy.deepcopy(self.parser_emitter_followup)
        changed["accounting"]["phase1_gate"] = "PASS"
        with self.assertRaisesRegex(ValueError, "remain non-approving"):
            validate_poryscript_parser_emitter_followup(changed, self.closure)

    def test_parser_emitter_handoff_rejects_probe_mutation(self):
        changed = copy.deepcopy(self.parser_emitter_followup)
        changed["actual_cli_probe"]["numeric_cases"]["0x"]["emitted_assembly_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "CLI probe record differs"):
            validate_poryscript_parser_emitter_followup(changed, self.closure)

    def test_parser_emitter_probe_rejects_source_blob_mutation(self):
        from tools.copilot_poryscript_parser_emitter_probe import (
            SOURCE_BLOBS,
            verify_sources,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for path in SOURCE_BLOBS:
                source = root / path
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text("mutated pinned source\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source blob mismatch"):
                verify_sources(root, source_files_only=True)

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

    def test_poryscript_firered_handoff_is_pinned_and_non_approving(self):
        result = validate_file_inspection_record(
            self.poryscript_firered_inspection, self.closure
        )
        self.assertEqual(result["files_with_full_source_text_retrieved"], 16)
        self.assertEqual(result["complete_source_files_read"], 0)
        self.assertEqual(result["whole_file_semantic_reviews"], 0)
        self.assertEqual(result["new_qualifying_copilot_receipts"], 0)
        self.assertEqual(result["phase1_gate"], "FAIL_INCOMPLETE")
        self.assertEqual(len(self.poryscript_firered_inspection["files"]), 16)
        self.assertTrue(all(
            item["full_source_bytes_retrieved"] is True and
            item["whole_file_semantic_disposition"] is False and
            item["verdict"] == "NEEDS_EVIDENCE" and
            item["license_evidence"]["status"] == "UNRESOLVED"
            for item in self.poryscript_firered_inspection["files"]
        ))

    def test_followup_rejects_source_dossier_and_dimension_mutations(self):
        for index in range(len(self.poryscript_firered_inspection["files"])):
            for field in ("git_blob_sha1", "sha256", "dossier_record_line_sha256"):
                with self.subTest(index=index, field=field):
                    changed = copy.deepcopy(self.poryscript_firered_inspection)
                    changed["files"][index][field] = "0" * (
                        40 if field == "git_blob_sha1" else 64
                    )
                    with self.assertRaisesRegex(
                        ValueError, "source/dossier identity differs"
                    ):
                        validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.poryscript_firered_inspection)
        changed["files"][0]["byte_length"] += 1
        with self.assertRaisesRegex(ValueError, "pinned source-byte identity"):
            validate_file_inspection_record(changed, self.closure)

    def test_followup_rejects_range_and_scope_mutations(self):
        changed = copy.deepcopy(self.poryscript_firered_inspection)
        changed["files"][0]["supplemental_evidence_ranges"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(
            ValueError, "supplemental source evidence differs"
        ):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.poryscript_firered_inspection)
        changed["files"][0]["dependency_links"][0]["path"] = "missing.c"
        with self.assertRaisesRegex(ValueError, "dependency lacks a pinned endpoint"):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.poryscript_firered_inspection)
        changed["summary"]["selected_source_files"] -= 1
        with self.assertRaisesRegex(ValueError, "source-byte count is incomplete"):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.poryscript_firered_inspection)
        changed["validation"]["targeted_tests_passed"] = 0
        with self.assertRaisesRegex(ValueError, "validation provenance is incomplete"):
            validate_file_inspection_record(changed, self.closure)

    def test_followup_rejects_verdict_license_and_attribution_mutations(self):
        changed = copy.deepcopy(self.poryscript_firered_inspection)
        changed["files"][0]["verdict"] = "COPILOT_REVIEWED"
        with self.assertRaisesRegex(ValueError, "must not claim whole-file disposition"):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.poryscript_firered_inspection)
        changed["files"][0]["license_evidence"]["status"] = "CLEARED"
        with self.assertRaisesRegex(ValueError, "unresolved license review"):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.poryscript_firered_inspection)
        changed["license_sources"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "license-source identity differs"):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.poryscript_firered_inspection)
        changed["reviewer"]["authenticated_github_review_attribution"] = True
        with self.assertRaisesRegex(ValueError, "missing authenticated attribution"):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.poryscript_firered_inspection)
        changed["objections"][0]["status"] = "RESOLVED"
        with self.assertRaisesRegex(ValueError, "objections must remain explicit"):
            validate_file_inspection_record(changed, self.closure)

    def test_preprocessor_handoff_is_disjoint_and_non_approving(self):
        result = validate_file_inspection_record(
            self.preprocessor_inspection, self.closure
        )
        expected = {
            "asm/macros.inc",
            "include/characters.h",
            "tools/preproc/Makefile",
            "tools/preproc/c_file.cpp",
            "tools/preproc/c_file.h",
            "tools/preproc/char_util.h",
            "tools/preproc/charmap.cpp",
            "tools/preproc/charmap.h",
            "tools/preproc/io.cpp",
            "tools/preproc/io.h",
            "tools/preproc/string_parser.cpp",
            "tools/preproc/string_parser.h",
            "tools/preproc/utf8.cpp",
            "tools/preproc/utf8.h",
        }
        self.assertEqual(
            {item["path"] for item in self.preprocessor_inspection["files"]},
            expected,
        )
        prior_files = set().union(*(
            config["expected_files"]
            for schema, config in FILE_INSPECTION_SCHEMAS.items()
            if schema != self.preprocessor_inspection["schema"]
        ))
        self.assertTrue(all(
            ("pret/pokefirered", path) not in prior_files for path in expected
        ))
        self.assertEqual(result["complete_source_files_read"], 14)
        self.assertEqual(result["whole_file_semantic_reviews"], 0)
        self.assertEqual(result["new_qualifying_copilot_receipts"], 0)
        self.assertEqual(result["phase1_gate"], "FAIL_INCOMPLETE")
        self.assertTrue(all(
            item["verdict"] == "NEEDS_EVIDENCE" and
            item["whole_file_semantic_disposition"] is False
            for item in self.preprocessor_inspection["files"]
        ))

    def test_preprocessor_handoff_rejects_source_and_dossier_mutations(self):
        for index in range(len(self.preprocessor_inspection["files"])):
            for field in ("git_blob_sha1", "sha256", "dossier_record_line_sha256"):
                with self.subTest(index=index, field=field):
                    changed = copy.deepcopy(self.preprocessor_inspection)
                    changed["files"][index][field] = "0" * (
                        40 if field == "git_blob_sha1" else 64
                    )
                    with self.assertRaisesRegex(
                        ValueError, "source/dossier identity differs"
                    ):
                        validate_file_inspection_record(changed, self.closure)

            changed = copy.deepcopy(self.preprocessor_inspection)
            changed["files"][index]["byte_length"] += 1
            with self.subTest(index=index, field="byte_length"):
                with self.assertRaisesRegex(
                    ValueError, "complete pinned source-byte identity"
                ):
                    validate_file_inspection_record(changed, self.closure)

    def test_preprocessor_handoff_rejects_full_file_range_mutation(self):
        changed = copy.deepcopy(self.preprocessor_inspection)
        changed["files"][0]["supplemental_evidence_ranges"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "whole-file evidence differs"):
            validate_file_inspection_record(changed, self.closure)

    def test_preprocessor_handoff_rejects_dependency_mutation(self):
        changed = copy.deepcopy(self.preprocessor_inspection)
        changed["files"][0]["dependency_links"][0]["path"] = "missing.inc"
        with self.assertRaisesRegex(ValueError, "dependency lacks a pinned endpoint"):
            validate_file_inspection_record(changed, self.closure)

    def test_preprocessor_handoff_rejects_license_and_objection_mutations(self):
        changed = copy.deepcopy(self.preprocessor_inspection)
        changed["license_sources"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "license-source identity differs"):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.preprocessor_inspection)
        changed["objections"][0]["status"] = "RESOLVED"
        with self.assertRaisesRegex(ValueError, "source objections must remain explicit"):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.preprocessor_inspection)
        changed["license_search"]["status"] = "FOUND"
        with self.assertRaisesRegex(
            ValueError, "license or governing-protocol provenance changed"
        ):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.preprocessor_inspection)
        changed["basis"]["protocol_document_status"] = "AVAILABLE"
        with self.assertRaisesRegex(
            ValueError, "baseline or governing-protocol blocker"
        ):
            validate_file_inspection_record(changed, self.closure)

    def test_preprocessor_handoff_rejects_verdict_attribution_and_scope_mutations(self):
        changed = copy.deepcopy(self.preprocessor_inspection)
        changed["files"][0]["verdict"] = "COPILOT_REVIEWED"
        with self.assertRaisesRegex(ValueError, "must not claim whole-file disposition"):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.preprocessor_inspection)
        changed["reviewer"]["authenticated_github_review_attribution"] = True
        with self.assertRaisesRegex(ValueError, "missing authenticated attribution"):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.preprocessor_inspection)
        changed["accounting"]["approved_total"] = 1
        with self.assertRaisesRegex(ValueError, "non-approving"):
            validate_file_inspection_record(changed, self.closure)

        changed = copy.deepcopy(self.preprocessor_inspection)
        changed["review_handoff"]["pending_requirements"].pop()
        with self.assertRaisesRegex(ValueError, "handoff omits independent-review blockers"):
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


class PinnedFireRedPreprocessorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preprocessor_inspection = json.loads(
            (DEFAULT_RECORD.parent / "preprocessor-dependency-followup.json").read_text(
                encoding="utf-8"
            )
        )
        cls.closure = json.loads(
            (DEFAULT_RECORD.parent / "closure-review.json").read_text(
                encoding="utf-8"
            )
        )
        source_root = Path(os.environ.get(
            "XGBA_PINNED_FIRERED_ROOT", ROOT / "upstream-firered"
        ))
        source_dir = source_root / "tools/preproc"
        if not (source_dir / "Makefile").is_file():
            raise unittest.SkipTest("pinned FireRed checkout is unavailable")
        cls.temp_dir = tempfile.TemporaryDirectory()
        temp_root = Path(cls.temp_dir.name)
        cls.preproc_dir = temp_root / "tools/preproc"
        cls.preproc_dir.parent.mkdir(parents=True)
        shutil.copytree(
            source_dir,
            cls.preproc_dir,
            ignore=shutil.ignore_patterns("preproc", "preproc.exe"),
        )
        include_dir = temp_root / "include"
        include_dir.mkdir()
        shutil.copyfile(
            source_root / "include/characters.h",
            include_dir / "characters.h",
        )
        subprocess.run(
            ["make", "-C", str(cls.preproc_dir), "-j2"],
            check=True,
            capture_output=True,
            text=True,
        )

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temp_dir"):
            cls.temp_dir.cleanup()

    def run_preproc(self, source, charmap=b"'A' = BB\n"):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_path = root / "input.s"
            charmap_path = root / "charmap.txt"
            source_path.write_bytes(source)
            charmap_path.write_bytes(charmap)
            return subprocess.run(
                [str(self.preproc_dir / "preproc"), str(source_path),
                 str(charmap_path)],
                capture_output=True,
                text=False,
            )

    def test_pinned_preprocessor_emits_mapped_string_byte(self):
        result = self.run_preproc(b'.string "A"\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"\t.byte 0xBB\n", result.stdout)

    def test_pinned_preprocessor_rejects_unknown_character(self):
        result = self.run_preproc(b'.string "Z"\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"unknown character U+5A", result.stderr)

    def test_pinned_preprocessor_rejects_truncated_utf8(self):
        result = self.run_preproc(b'.string "\xc3"\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"invalid encoding in UTF-8 string", result.stderr)

    def test_pinned_preprocessor_rejects_oversized_charmap_sequence(self):
        charmap = b"'A' = " + b"A" * 34 + b"\n"
        result = self.run_preproc(b'.string "A"\n', charmap)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"byte sequence too long (max is 16 bytes)", result.stderr)

    def test_pinned_source_mutation_is_rejected(self):
        source_root = Path(os.environ.get(
            "XGBA_PINNED_FIRERED_ROOT", ROOT / "upstream-firered"
        ))
        source = self.preprocessor_inspection["files"][0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for item in self.preprocessor_inspection["files"]:
                path = root / item["path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source_root / item["path"], path)
            result = verify_file_inspection_sources(
                self.preprocessor_inspection,
                self.closure,
                {
                    "pret/pokefirered": root,
                    "huderlem/poryscript": root / "unused-pinned-root",
                },
                source_files_only=True,
            )
            self.assertEqual(result["source_files_verified"], 14)
            changed_path = root / source["path"]
            changed_path.write_bytes(changed_path.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "Git blob mismatch"):
                verify_file_inspection_sources(
                    self.preprocessor_inspection,
                    self.closure,
                    {
                        "pret/pokefirered": root,
                        "huderlem/poryscript": root / "unused-pinned-root",
                    },
                    source_files_only=True,
                )


if __name__ == "__main__":
    unittest.main()
