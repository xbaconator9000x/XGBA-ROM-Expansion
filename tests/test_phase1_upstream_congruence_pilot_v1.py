import gzip
import io
import json
import tempfile
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import phase1_upstream_congruence_pilot_v1 as pilot
import verify_native_mgba_regressions as native_gate
import verify_phase1_mgba_boundary_evidence as native_evidence
from phase1_upstream_verified_v1 import canonical_bytes, sha256


def archive_jsonl(rows):
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode="wb", mtime=0) as stream:
        stream.write(b"".join(canonical_bytes(row) + b"\n" for row in rows))
    return output.getvalue()


def archive_csv(rows):
    output = io.StringIO(newline="")
    import csv

    writer = csv.DictWriter(output, fieldnames=["repo", "path", "blob_sha", "evidence_sha256"])
    writer.writeheader()
    writer.writerows(rows)
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode="wb", mtime=0) as stream:
        stream.write(output.getvalue().encode())
    return compressed.getvalue()


def reconciled_fixture():
    key = ("mgba-emu/mgba", "src/gba/gba.c")
    dossier = {
        "provenance": {
            "repository": key[0],
            "path": key[1],
            "pinned_revision": "fd9dc5c2cbf234365068855851107e762fc6211b",
            "git_blob_sha": "a" * 40,
            "source_content_sha256": "b" * 64,
            "tracked_bytes": "10",
        },
        "review": {"semantic_signoff": False},
    }
    digest = sha256(canonical_bytes(dossier))
    queue = {
        key: {
            "repo": key[0],
            "path": key[1],
            "blob_sha": "a" * 40,
            "evidence_sha256": digest,
        }
    }
    source_row = {
        "identity": {
            "repository": key[0],
            "path": key[1],
            "git_blob_sha1": "a" * 40,
            "pinned_commit": dossier["provenance"]["pinned_revision"],
            "source_sha256": dossier["provenance"]["source_content_sha256"],
            "source_bytes": 10,
        },
        "machine_dossier": {
            "original_archive_git_blob_sha1": pilot.PR8_DOSSIER_BLOB,
            "sha256": digest,
            "source_content_sha256_present": True,
            "semantic_signoff": False,
        },
        "approval_state": "NOT_APPROVED",
        "semantic_review_state": "NOT_SEMANTICALLY_REVIEWED",
        "source_index_state": "SOURCE_INDEXED",
        "source_index_reason_code": "SOURCE_BLOB_AND_DOSSIER_VERIFIED",
    }
    return key, queue, {key: dossier}, {key: dict(dossier)}, {key: source_row}


def evidence_fixture():
    identity = {
        "repository": "mgba-emu/mgba",
        "path": "src/gba/gba.c",
        "revision": "fd9dc5c2cbf234365068855851107e762fc6211b",
        "git_blob_sha1": "a" * 40,
        "source_sha256": "b" * 64,
        "dossier_archive_sha256": "c" * 64,
        "dossier_sha256": "d" * 64,
        "source_line_count": 10,
    }
    reference = {
        "repository": identity["repository"],
        "path": identity["path"],
        "revision": identity["revision"],
        "git_blob_sha1": identity["git_blob_sha1"],
        "source_sha256": identity["source_sha256"],
    }
    dependencies = [{**reference, "path": "include/mgba/internal/gba/gba.h"}]
    record = {
        "schema": pilot.BEHAVIOR_SCHEMA,
        "identity": identity,
        "scope": {
            "claim_level": "whole_file",
            "line_coverage": [[1, 10]],
            "claim_ids": ["rom-aperture-bounds"],
        },
        "semantic_map": {
            "claim_ids": ["rom-aperture-bounds"],
            "statements": ["ROM aperture mapping is bounded by the pinned loader rules."],
            "source_refs": [reference],
            "specification_refs": [{**reference, "path": "docs/rom-map.md"}],
        },
        "dependency_closure": {
            "complete": True,
            "dependencies": dependencies,
            "consumers": [{**reference, "path": "src/gba/memory.c"}],
            "dependency_digest_sha256": sha256(
                canonical_bytes(
                    {
                        "dependencies": dependencies,
                        "consumers": [{**reference, "path": "src/gba/memory.c"}],
                    }
                )
            ),
            "unresolved": [],
        },
        "tests": {
            "executed": True,
            "exit_code": 0,
            "test_source_refs": [{**reference, "path": "tests/rom-map.c"}],
            "positive_cases": 2,
            "negative_counterexamples": 1,
            "covered_claim_ids": ["rom-aperture-bounds"],
            "counterexample_claim_ids": ["rom-aperture-bounds"],
            "result_sha256": "e" * 64,
            "actions": {
                "head_sha": identity["revision"],
                "conclusion": "success",
                "event": "push",
                "total_jobs": 1,
                "successful_jobs": 1,
                "executed_jobs": 1,
            },
        },
        "licensing": {
            "distribution_clearance": "CLEARED",
            "evidence_refs": [{**reference, "path": "LICENSE"}],
        },
        "unresolved_objections": [],
        "contradictory_evidence": [],
        "risk_controls": [
            {
                "risk_id": risk_id,
                "executed": True,
                "outcome": requirement["outcome"],
                "test_case": requirement["test_case"],
                "result_sha256": "f" * 64,
                "test_source_refs": [{**reference, "path": "tests/negative-controls.c"}],
                "source_refs": [
                    {
                        "repository": pilot.PILOT_REPOSITORY,
                        "path": path,
                        "revision": pilot.PILOT_REVISION,
                        "git_blob_sha1": pilot.PILOT_FILES[path][0],
                        "source_sha256": pilot.PILOT_FILES[path][1],
                    }
                    for path in requirement["paths"]
                ],
            }
            for risk_id, requirement in pilot.PILOT_RISK_CONTROLS.items()
        ],
    }
    record["record_sha256"] = sha256(canonical_bytes(record))
    return record, identity


def refresh_record_digest(record):
    record["record_sha256"] = sha256(
        canonical_bytes({key: value for key, value in record.items() if key != "record_sha256"})
    )


class UpstreamCongruencePilotTests(unittest.TestCase):
    def test_native_semantic_matrix_reconciles_original_source_and_dossier_bytes(self):
        repository_root = Path(__file__).resolve().parents[1]
        matrix_path = repository_root / "docs/PHASE1_MGBA_NATIVE_SEMANTIC_MATRIX_20261101.json"
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        dossier_path = repository_root / "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
        dossier_data = dossier_path.read_bytes()
        self.assertEqual(sha256(dossier_data), pilot.DOSSIER_SHA256)
        self.assertEqual(pilot.git_blob_sha(dossier_data), pilot.DOSSIER_BLOB)
        self.assertEqual(matrix["source"]["dossier_archive"]["sha256"], pilot.DOSSIER_SHA256)
        self.assertEqual(matrix["source"]["dossier_archive"]["git_blob_sha1"], pilot.DOSSIER_BLOB)

        dossiers = {}
        with gzip.open(dossier_path, "rt", encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                path = row.get("provenance", {}).get("path")
                if path in pilot.PILOT_FILES:
                    dossiers[path] = row

        self.assertEqual(set(dossiers), set(pilot.PILOT_FILES))
        files = {row["path"]: row for row in matrix["files"]}
        self.assertEqual(set(files), set(pilot.PILOT_FILES))
        for path, (blob_sha, source_sha) in pilot.PILOT_FILES.items():
            row = files[path]
            dossier = dossiers[path]
            self.assertEqual(row["source_git_blob_sha1"], blob_sha)
            self.assertEqual(row["source_sha256"], source_sha)
            self.assertEqual(dossier["provenance"]["git_blob_sha"], blob_sha)
            self.assertEqual(dossier["provenance"]["source_content_sha256"], source_sha)
            self.assertEqual(row["machine_dossier_sha256"], sha256(canonical_bytes(dossier)))

    def test_native_semantic_matrix_preserves_nonapproval_and_unresolved_boundaries(self):
        repository_root = Path(__file__).resolve().parents[1]
        matrix = json.loads(
            (repository_root / "docs/PHASE1_MGBA_NATIVE_SEMANTIC_MATRIX_20261101.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(matrix["native_run"]["run_status"], "completed")
        self.assertEqual(matrix["native_run"]["run_conclusion"], "success")
        self.assertEqual(matrix["native_run"]["job_status"], "completed")
        self.assertEqual(matrix["native_run"]["job_conclusion"], "success")
        self.assertEqual(matrix["native_run"]["native_assertions_passed"], 34)
        self.assertEqual(matrix["native_run"]["native_assertions_failed"], 0)
        self.assertEqual(matrix["native_run"]["evidence_classification"], "NATIVE_EVIDENCE_ONLY")
        self.assertEqual(matrix["compiler_evidence"]["consumer_closure"], "NOT_ESTABLISHED")
        self.assertEqual(matrix["compiler_evidence"]["unresolved_symbol_references"], "NOT_RECORDED")
        self.assertEqual(matrix["license_assessment"]["project_distribution_clearance"], "NOT_ASSESSED")
        self.assertEqual(matrix["dispositions"]["phase1_gate"], "FAIL_INCOMPLETE")
        self.assertEqual(matrix["dispositions"]["needs_review_count"], 6)
        self.assertEqual(matrix["dispositions"]["upstream_verified_passed_count"], 0)
        self.assertEqual(matrix["dispositions"]["copilot_reviewed_passed_count"], 0)
        self.assertEqual(matrix["dispositions"]["legacy_external_independent_approved"], 0)
        observed = {
            observation
            for row in matrix["files"]
            for observation in row["native_hazard_observations"]
        }
        self.assertEqual(observed, set(matrix["native_run"]["native_hazard_observations"]))
        self.assertEqual(len(observed), 4)

    def test_pinned_candidate_scope_and_zero_approval_boundary(self):
        self.assertEqual(len(pilot.PILOT_FILES), 6)
        self.assertEqual(pilot.INVENTORY_SIZE, 14834)
        self.assertEqual(pilot.P0_CANDIDATES, 338)

    def test_live_index_digest_rejects_tampering(self):
        with self.assertRaises(pilot.EvidenceError):
            pilot._validate_pr8_index(b"not the pinned index")

    def test_pr8_dossier_digest_and_git_blob_are_both_required(self):
        data = b"pinned synthetic archive"
        pilot._verify_pinned_bytes(data, sha256(data), pilot.git_blob_sha(data), "fixture")
        with self.assertRaises(pilot.EvidenceError):
            pilot._verify_pinned_bytes(data + b"x", sha256(data), pilot.git_blob_sha(data), "fixture")
        with self.assertRaises(pilot.EvidenceError):
            pilot._verify_pinned_bytes(data, sha256(data), "0" * 40, "fixture")

    def test_dossier_archive_loader_rejects_duplicate_identity(self):
        key, _, dossiers, _, _ = reconciled_fixture()
        data = archive_jsonl([dossiers[key], dossiers[key]])
        with self.assertRaises(pilot.EvidenceError):
            pilot._load_dossiers(data, "fixture", expected_count=2)

    def test_dossier_archive_loader_rejects_missing_identity(self):
        key, _, dossiers, _, _ = reconciled_fixture()
        with self.assertRaises(pilot.EvidenceError):
            pilot._load_dossiers(archive_jsonl([dossiers[key]]), "fixture", expected_count=2)

    def test_queue_loader_rejects_duplicate_identity(self):
        key, queue, _, _, _ = reconciled_fixture()
        row = queue[key]
        with self.assertRaises(pilot.EvidenceError):
            pilot._load_queue(archive_csv([row, row]), expected_count=2)

    def test_valid_single_identity_reconciles(self):
        _, queue, pr2, pr8, indexed = reconciled_fixture()
        pilot._reconcile_rows(queue, pr2, pr8, indexed, expected_count=1)

    def test_reconciliation_rejects_omitted_index_record(self):
        _, queue, pr2, pr8, indexed = reconciled_fixture()
        indexed.clear()
        with self.assertRaises(pilot.EvidenceError):
            pilot._reconcile_rows(queue, pr2, pr8, indexed, expected_count=1)

    def test_reconciliation_rejects_extra_index_record(self):
        _, queue, pr2, pr8, indexed = reconciled_fixture()
        indexed[("mgba-emu/mgba", "extra.c")] = next(iter(indexed.values()))
        with self.assertRaises(pilot.EvidenceError):
            pilot._reconcile_rows(queue, pr2, pr8, indexed, expected_count=1)

    def test_index_rows_reject_duplicate_source_identity(self):
        _, _, _, _, indexed = reconciled_fixture()
        row = next(iter(indexed.values()))
        with self.assertRaises(pilot.EvidenceError):
            pilot._index_rows([row, row])

    def test_dependency_candidate_graph_finds_connected_targets(self):
        repository = "mgba-emu/mgba"
        rows = {
            (repository, "src/a.c"): {
                "direct_dependencies": [{"candidate_target_paths": ["include/shared.h"]}]
            },
            (repository, "src/b.c"): {
                "direct_dependencies": [{"candidate_target_paths": ["include/shared.h"]}]
            },
        }
        component = pilot._dependency_candidate_component(
            rows, {(repository, "src/a.c")}
        )
        self.assertIn((repository, "src/b.c"), component)

    def test_dependency_candidate_graph_does_not_invent_unconnected_edges(self):
        repository = "mgba-emu/mgba"
        rows = {
            (repository, "src/a.c"): {"direct_dependencies": []},
            (repository, "src/b.c"): {"direct_dependencies": []},
        }
        component = pilot._dependency_candidate_component(
            rows, {(repository, "src/a.c")}
        )
        self.assertNotIn((repository, "src/b.c"), component)

    def test_dossier_canonical_bytes_must_match_between_archives(self):
        key, queue, pr2, pr8, indexed = reconciled_fixture()
        pr8[key]["untrusted_extra"] = True
        with self.assertRaises(pilot.EvidenceError):
            pilot._reconcile_rows(queue, pr2, pr8, indexed, expected_count=1)

    def test_dossier_digest_must_match_index_and_queue(self):
        key, queue, pr2, pr8, indexed = reconciled_fixture()
        indexed[key]["machine_dossier"]["sha256"] = "0" * 64
        with self.assertRaises(pilot.EvidenceError):
            pilot._reconcile_rows(queue, pr2, pr8, indexed, expected_count=1)

    def test_wrong_source_blob_is_blocked(self):
        key, queue, pr2, pr8, indexed = reconciled_fixture()
        indexed[key]["identity"]["git_blob_sha1"] = "0" * 40
        with self.assertRaises(pilot.EvidenceError):
            pilot._reconcile_rows(queue, pr2, pr8, indexed, expected_count=1)

    def test_source_sha_must_match_the_original_dossier(self):
        key, queue, pr2, pr8, indexed = reconciled_fixture()
        indexed[key]["identity"]["source_sha256"] = "0" * 64
        with self.assertRaises(pilot.EvidenceError):
            pilot._reconcile_rows(queue, pr2, pr8, indexed, expected_count=1)

    def test_source_byte_count_must_match_the_original_dossier(self):
        key, queue, pr2, pr8, indexed = reconciled_fixture()
        indexed[key]["identity"]["source_bytes"] = 11
        with self.assertRaises(pilot.EvidenceError):
            pilot._reconcile_rows(queue, pr2, pr8, indexed, expected_count=1)

    def test_index_may_not_claim_semantic_approval(self):
        key, queue, pr2, pr8, indexed = reconciled_fixture()
        indexed[key]["approval_state"] = "APPROVED"
        with self.assertRaises(pilot.EvidenceError):
            pilot._reconcile_rows(queue, pr2, pr8, indexed, expected_count=1)

    def test_positive_behavioral_fixture_has_complete_structural_evidence(self):
        record, identity = evidence_fixture()
        validate_ref = lambda ref: isinstance(ref, dict) and bool(ref.get("git_blob_sha1"))
        validate_actions = lambda actions: actions.get("conclusion") == "success"
        self.assertEqual(
            pilot._validate_candidate_evidence(record, identity, validate_ref, validate_actions), []
        )

    def test_behavioral_fixture_requires_versioned_risk_control_schema(self):
        record, identity = evidence_fixture()
        record["schema"] = "xgba.phase1.behavioral_congruence_evidence.v1"
        refresh_record_digest(record)
        reasons = pilot._validate_candidate_evidence(
            record, identity, lambda _: True, lambda _: True
        )
        self.assertIn("BEHAVIORAL_SCHEMA_MISMATCH", reasons)

    def test_behavioral_fixture_requires_reference_and_actions_reverification(self):
        record, identity = evidence_fixture()
        reasons = pilot._validate_candidate_evidence(record, identity)
        self.assertIn("REFERENCED_ARTIFACTS_NOT_REVERIFIED", reasons)
        self.assertIn("EXACT_HEAD_ACTIONS_PROVENANCE_NOT_REVERIFIED", reasons)

    def test_behavioral_fixture_rejects_digest_and_identity_tampering(self):
        record, identity = evidence_fixture()
        identity = dict(identity)
        record["identity"]["source_sha256"] = "0" * 64
        reasons = pilot._validate_candidate_evidence(record, identity, lambda _: True, lambda _: True)
        self.assertIn("BEHAVIORAL_RECORD_DIGEST_MISMATCH", reasons)
        self.assertIn("SOURCE_OR_DOSSIER_IDENTITY_MISMATCH", reasons)

    def test_behavioral_fixture_rejects_missing_semantic_map(self):
        record, identity = evidence_fixture()
        record["semantic_map"]["statements"] = []
        reasons = pilot._validate_candidate_evidence(record, identity, lambda _: True, lambda _: True)
        self.assertIn("UPSTREAM_SEMANTIC_MAP_OR_SPECIFICATION_MISSING", reasons)

    def test_behavioral_fixture_rejects_dependency_divergence(self):
        record, identity = evidence_fixture()
        record["dependency_closure"]["unresolved"] = ["dynamic include"]
        reasons = pilot._validate_candidate_evidence(record, identity, lambda _: True, lambda _: True)
        self.assertIn("DEPENDENCY_OR_CONSUMER_CLOSURE_INCOMPLETE", reasons)

    def test_behavioral_fixture_rejects_partial_whole_file_scope(self):
        record, identity = evidence_fixture()
        record["scope"]["line_coverage"] = [[1, 9]]
        reasons = pilot._validate_candidate_evidence(record, identity, lambda _: True, lambda _: True)
        self.assertIn("WHOLE_FILE_SCOPE_INCOMPLETE", reasons)

    def test_behavioral_fixture_rejects_unexecuted_or_noncovering_tests(self):
        record, identity = evidence_fixture()
        record["tests"]["executed"] = False
        record["tests"]["negative_counterexamples"] = 0
        record["tests"]["covered_claim_ids"] = []
        reasons = pilot._validate_candidate_evidence(record, identity, lambda _: True, lambda _: True)
        self.assertIn("PINNED_POSITIVE_AND_NEGATIVE_TEST_EXECUTION_MISSING", reasons)

    def test_behavioral_fixture_rejects_malformed_numeric_and_digest_fields(self):
        malformed = (
            ("tests", "positive_cases", "1"),
            ("tests", "positive_cases", True),
            ("tests", "positive_cases", None),
            ("tests", "negative_counterexamples", 1.0),
            ("tests", "negative_counterexamples", False),
            ("tests", "negative_counterexamples", None),
            ("tests", "result_sha256", "e" * 63),
            ("tests", "result_sha256", "g" * 64),
            ("tests", "result_sha256", True),
            ("tests", "result_sha256", None),
            ("tests", "exit_code", False),
            ("tests.actions", "total_jobs", "1"),
            ("tests.actions", "total_jobs", True),
            ("tests.actions", "total_jobs", None),
            ("tests.actions", "successful_jobs", False),
            ("tests.actions", "executed_jobs", "1"),
        )
        for section, field, value in malformed:
            record, identity = evidence_fixture()
            target = record["tests"] if section == "tests" else record["tests"]["actions"]
            target[field] = value
            refresh_record_digest(record)
            reasons = pilot._validate_candidate_evidence(
                record, identity, lambda _: True, lambda _: True
            )
            self.assertIn(
                "PINNED_POSITIVE_AND_NEGATIVE_TEST_EXECUTION_MISSING",
                reasons,
                (section, field, value),
            )

    def test_behavioral_fixture_rejects_stale_actions_head(self):
        record, identity = evidence_fixture()
        record["tests"]["actions"]["head_sha"] = "f" * 40
        record["record_sha256"] = sha256(canonical_bytes({k: v for k, v in record.items() if k != "record_sha256"}))
        reasons = pilot._validate_candidate_evidence(record, identity, lambda _: True, lambda _: True)
        self.assertIn("PINNED_POSITIVE_AND_NEGATIVE_TEST_EXECUTION_MISSING", reasons)

    def test_behavioral_fixture_rejects_unassessed_licensing(self):
        record, identity = evidence_fixture()
        record["licensing"]["distribution_clearance"] = "NOT_ASSESSED"
        reasons = pilot._validate_candidate_evidence(record, identity, lambda _: True, lambda _: True)
        self.assertIn("LICENSING_SCOPE_NOT_CLEARED", reasons)

    def test_behavioral_fixture_rejects_unresolved_or_contradictory_evidence(self):
        record, identity = evidence_fixture()
        record["unresolved_objections"] = ["ROM prefetch lifecycle"]
        record["contradictory_evidence"] = ["test claims differ"]
        reasons = pilot._validate_candidate_evidence(record, identity, lambda _: True, lambda _: True)
        self.assertIn("UNRESOLVED_SUBSTANTIVE_OBJECTIONS", reasons)
        self.assertIn("CONTRADICTORY_EVIDENCE_PRESENT", reasons)

    def test_behavioral_fixture_rejects_unverified_artifact_references(self):
        record, identity = evidence_fixture()
        reasons = pilot._validate_candidate_evidence(
            record, identity, lambda _: False, lambda _: False
        )
        self.assertIn("REFERENCED_ARTIFACTS_NOT_REVERIFIED", reasons)
        self.assertIn("EXACT_HEAD_ACTIONS_PROVENANCE_NOT_REVERIFIED", reasons)

    def test_behavioral_fixture_requires_every_risk_specific_negative_control(self):
        record, identity = evidence_fixture()
        for risk_id in pilot.PILOT_RISK_CONTROLS:
            candidate = json.loads(json.dumps(record))
            candidate["risk_controls"] = [
                control
                for control in candidate["risk_controls"]
                if control["risk_id"] != risk_id
            ]
            refresh_record_digest(candidate)
            reasons = pilot._validate_candidate_evidence(
                candidate, identity, lambda _: True, lambda _: True
            )
            self.assertIn("RISK_SPECIFIC_NEGATIVE_CONTROLS_INCOMPLETE", reasons, risk_id)

    def test_behavioral_fixture_rejects_unsafe_risk_control_claims(self):
        for field, value in (
            ("executed", False),
            ("outcome", "SAFE_WITHOUT_COUNTEREXAMPLE"),
            ("test_case", "unrelated_test"),
            ("result_sha256", "not-a-digest"),
            ("test_source_refs", []),
        ):
            record, identity = evidence_fixture()
            record["risk_controls"][0][field] = value
            refresh_record_digest(record)
            reasons = pilot._validate_candidate_evidence(
                record, identity, lambda _: True, lambda _: True
            )
            self.assertIn("RISK_SPECIFIC_NEGATIVE_CONTROLS_INCOMPLETE", reasons, field)

    def test_behavioral_fixture_rejects_risk_control_source_substitution(self):
        record, identity = evidence_fixture()
        record["risk_controls"][0]["source_refs"][0]["source_sha256"] = "0" * 64
        refresh_record_digest(record)
        reasons = pilot._validate_candidate_evidence(
            record, identity, lambda _: True, lambda _: True
        )
        self.assertIn("RISK_SPECIFIC_NEGATIVE_CONTROLS_INCOMPLETE", reasons)

    def test_behavioral_fixture_rejects_duplicate_or_unknown_risk_controls(self):
        record, identity = evidence_fixture()
        record["risk_controls"].append(dict(record["risk_controls"][0]))
        record["risk_controls"].append(
            {**record["risk_controls"][0], "risk_id": "UNPINNED_RISK"}
        )
        refresh_record_digest(record)
        reasons = pilot._validate_candidate_evidence(
            record, identity, lambda _: True, lambda _: True
        )
        self.assertIn("RISK_SPECIFIC_NEGATIVE_CONTROLS_INCOMPLETE", reasons)

    def test_native_build_report_blocks_when_pinned_checkout_is_absent(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = pilot._native_build_status(Path(temporary))
        self.assertEqual(report["status"], "BLOCKED")
        self.assertFalse(report["required_source_present"])
        self.assertFalse(report["native_probe_executed"])
        self.assertIn("PINNED_MGBA_SOURCE_CHECKOUT_ABSENT", report["reason_codes"])
        self.assertEqual(report["preprocessor_closure"], "NOT_ESTABLISHED")
        self.assertEqual(report["consumer_closure"], "NOT_ESTABLISHED")

    def test_pilot_risk_obligations_are_explicit_and_never_report_executed(self):
        obligations = pilot._risk_obligation_report()
        self.assertEqual(
            {obligation["risk_id"] for obligation in obligations},
            set(pilot.PILOT_RISK_CONTROLS),
        )
        self.assertTrue(all(obligation["reason_code"] for obligation in obligations))
        self.assertNotIn(
            "PASSED", {obligation["evidence_state"] for obligation in obligations}
        )

    def test_native_ingestion_accepts_exact_synthetic_regression_log_only(self):
        source = b"fixture-only native source bytes"
        checks = sorted(native_gate.REQUIRED_TESTS)
        gaps = sorted(native_gate.REQUIRED_NATIVE_GAPS)
        lines = []
        for name in checks:
            lines.extend((f"PASS {name}", f"CASE {name} exit_code=0"))
        for observation in gaps:
            name, value = observation.split("=", 1)
            lines.extend(
                (
                    f"OBSERVATION {observation}",
                    f"CASE_OBSERVATION {name} observed={value} exit_code=0",
                )
            )
        lines.append(
            "SUMMARY hard_failures=0 native_gap_observations=4 "
            "xgba_runtime_implemented=false phase1_mapping_complete=false"
        )
        log = "\n".join(lines) + "\n"
        result = {
            "source_revision": native_evidence.PIN,
            "test_source_sha256": sha256(source),
            "run_kind": "NATIVE_MGBA_SYNTHETIC_CARTRIDGE_ONLY",
            "probe_suite_revision": native_evidence.PROBE_SUITE_REVISION,
            "native_probe_exit_code": 0,
            "external_XGBA_banking_implemented": False,
            "phase1_mapping_complete": False,
            "independent_semantic_reviews_approved": 0,
            "positive_checks_passed": len(checks),
            "positive_checks_failed": 0,
            "native_gap_observations": gaps,
        }
        verified = native_evidence.verify_case_log(log, result, source)
        self.assertEqual(verified["assertions_verified"], len(checks))
        self.assertEqual(verified["native_regression_gate"], "PASS_PINNED_NATIVE_MGBA_REGRESSION_ONLY")
        self.assertEqual(len(verified["case_results"]), len(checks))
        self.assertEqual(len(verified["hazard_observations"]), len(gaps))
        self.assertFalse(any(row["observed"] is False for row in verified["hazard_observations"]))

    def test_native_ingestion_rejects_case_execution_or_source_mismatch(self):
        source = b"fixture-only native source bytes"
        checks = sorted(native_gate.REQUIRED_TESTS)
        gaps = sorted(native_gate.REQUIRED_NATIVE_GAPS)
        lines = []
        for name in checks:
            lines.extend((f"PASS {name}", f"CASE {name} exit_code=0"))
        for observation in gaps:
            name, value = observation.split("=", 1)
            lines.extend(
                (
                    f"OBSERVATION {observation}",
                    f"CASE_OBSERVATION {name} observed={value} exit_code=0",
                )
            )
        lines.append(
            "SUMMARY hard_failures=0 native_gap_observations=4 "
            "xgba_runtime_implemented=false phase1_mapping_complete=false"
        )
        log = "\n".join(lines) + "\n"
        result = {
            "source_revision": native_evidence.PIN,
            "test_source_sha256": sha256(source),
            "run_kind": "NATIVE_MGBA_SYNTHETIC_CARTRIDGE_ONLY",
            "probe_suite_revision": native_evidence.PROBE_SUITE_REVISION,
            "native_probe_exit_code": 0,
            "external_XGBA_banking_implemented": False,
            "phase1_mapping_complete": False,
            "independent_semantic_reviews_approved": 0,
            "positive_checks_passed": len(checks),
            "positive_checks_failed": 0,
            "native_gap_observations": gaps,
        }
        with self.assertRaisesRegex(native_evidence.EvidenceRejected, "NATIVE_CASE_EXIT_CODE_NONZERO"):
            native_evidence.verify_case_log(log.replace("exit_code=0", "exit_code=1", 1), result, source)
        with self.assertRaisesRegex(native_evidence.EvidenceRejected, "differs from executed"):
            native_evidence.verify_case_log(log, result, b"different fixture")

    def test_native_ingestion_binds_run_and_job_to_exact_pr_head(self):
        head = "1" * 40
        run = {
            "id": 12,
            "run_attempt": 1,
            "head_sha": head,
            "name": native_evidence.WORKFLOW_NAME,
            "path": native_evidence.WORKFLOW_PATH,
            "event": "push",
            "status": "in_progress",
            "repository": {"full_name": native_evidence.REPOSITORY},
            "pull_requests": [{"number": 2}],
        }
        jobs = {
            "jobs": [
                {
                    "id": 34,
                    "run_id": 12,
                    "name": native_evidence.JOB_NAME,
                    "head_sha": head,
                    "status": "in_progress",
                    "conclusion": None,
                    "steps": [
                        {"name": name, "status": "completed", "conclusion": "success"}
                        for name in (
                            "Configure headless mGBA C core",
                            "Compile and link unmodified pinned mGBA",
                            "Analyze actual compiler targets and linked symbols",
                        )
                    ],
                }
            ]
        }
        context = {"run_id": 12, "run_attempt": 1, "head_sha": head}
        verified = native_evidence.verify_actions_provenance(run, jobs, context)
        self.assertEqual(verified["job_id"], 34)
        self.assertEqual(verified["head_sha"], head)
        for tamper in (
            {**run, "head_sha": "2" * 40},
            {**run, "status": "completed"},
            {**run, "pull_requests": []},
        ):
            with self.assertRaises(native_evidence.EvidenceRejected):
                native_evidence.verify_actions_provenance(tamper, jobs, context)


if __name__ == "__main__":
    unittest.main()
