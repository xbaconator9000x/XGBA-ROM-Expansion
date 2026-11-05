import unittest

from tools import phase1_arm_six_file_eligibility as eligibility
from tools import phase1_mgba_arm_decode_emit_review_verify as arm_review


def valid_report():
    targets = []
    for index, item in arm_review.TARGETS.items():
        path = item["path"]
        targets.append({
            "packet_index": index,
            "source": {
                "repository": eligibility.REPOSITORY,
                "revision": eligibility.PIN,
                "path": path,
                "line_count": eligibility.SOURCE_LINE_COUNTS[path],
                "git_blob_sha1": item["blob"],
                "source_sha256": item["sha256"],
            },
            "original_dossier_sha256": item["dossier"],
            "machine_triage": {
                "reviewer": None,
                "semantic_signoff": False,
                "status": "CANDIDATE_ONLY_SOURCE_HASH_VERIFIED",
            },
            "license": {
                "file_notice": "MPL-2.0_VERIFIED",
                "root_license_git_blob_sha1": arm_review.SUPPORT["LICENSE"][0],
                "root_license_sha256": arm_review.SUPPORT["LICENSE"][1],
                "combined_distribution_clearance": False,
            },
            "review": {
                "eligibility": "NEEDS_EVIDENCE",
                "prior_source_status": eligibility.PRIOR_DISPOSITIONS[path],
                "semantic_disposition": "NOT_PERFORMED",
                "whole_file_coverage": {"status": "NOT_PERFORMED", "reviewed_line_ranges": []},
                "canonical_receipt_rows": 0,
                "durable_copilot_attestation": "ABSENT",
                "reviewer_independence": "BLOCKED_AUTHOR_CONFLICT",
                "blockers": eligibility.BLOCKERS[path],
            },
        })
    dependencies = []
    for path in eligibility.CLOSURE_SOURCES:
        blob, source_sha = arm_review.SUPPORT[path]
        dependencies.append({
            "repository": eligibility.REPOSITORY,
            "revision": eligibility.PIN,
            "path": path,
            "role": eligibility.CLOSURE_SOURCES[path]["role"],
            "git_blob_sha1": blob,
            "source_sha256": source_sha,
            "original_dossier_sha256": eligibility.CLOSURE_SOURCES[path]["dossier"],
            "anchors": [
                {"line": line, "text": text}
                for line, text in eligibility.CLOSURE_SOURCES[path]["anchors"]
            ],
            "license_notice": "MPL-2.0_VERIFIED",
        })
    return {
        "schema": eligibility.SCHEMA,
        "repository_head": "1" * 40,
        "upstream": {"repository": eligibility.REPOSITORY, "revision": eligibility.PIN},
        "original_dossier_archive": {
            "git_blob_sha1": eligibility.ARCHIVE_BLOB,
            "sha256": eligibility.ARCHIVE_SHA256,
        },
        "copilot_authorship_conflict_evidence": {
            "path": eligibility.ANALYSIS_PATH,
            "sha256": eligibility.ANALYSIS_SHA256,
            "commit": eligibility.ANALYSIS_COMMIT,
            "author": {"login": eligibility.COPILOT_LOGIN, "id": eligibility.COPILOT_ID},
        },
        "candidate_copilot_reviewer_identity": {
            "login": eligibility.COPILOT_LOGIN,
            "id": eligibility.COPILOT_ID,
        },
        "targets": targets,
        "bounded_dependency_closure": {
            "status": "PARTIAL_NOT_COMPLETE",
            "verified_dependency_count": len(dependencies),
            "dependencies": dependencies,
            "remaining_scope": (
                "These three cross-cutting sources do not constitute a complete per-file dependency, "
                "caller, native ABI, runtime, or distribution-license closure."
            ),
        },
        "evidence_limits": {
            "compiled_native": "NOT_CLAIMED",
            "host_probes": "PREVIOUSLY_RECORDED_ONLY_NOT_REPEATED",
            "armv4t_oracle": "NOT_RUN",
            "combined_distribution_license_clearance": False,
            "independent_semantic_reviews_added": 0,
            "independent_approvals_added": 0,
            "gate_contribution": 0,
            "gate": "FAIL_INCOMPLETE",
        },
    }


class ARMSixFileEligibilityTests(unittest.TestCase):
    def test_wrapped_mpl_notice_is_recognized(self):
        self.assertTrue(
            eligibility._has_mpl_2_notice(
                b"Mozilla Public\nLicense, v. 2.0."
            )
        )
        self.assertFalse(eligibility._has_mpl_2_notice(b"Mozilla Public License"))

    def test_analysis_authorship_is_pinned_to_original_commit(self):
        self.assertEqual(
            eligibility._copilot_analysis_authorship(eligibility.ROOT),
            {
                "path": eligibility.ANALYSIS_PATH,
                "sha256": eligibility.ANALYSIS_SHA256,
                "commit": eligibility.ANALYSIS_COMMIT,
                "author": {"login": eligibility.COPILOT_LOGIN, "id": eligibility.COPILOT_ID},
            },
        )

    def test_exact_nonapproving_matrix_passes(self):
        eligibility.validate_report(valid_report())

    def test_source_hash_drift_fails(self):
        report = valid_report()
        report["targets"][0]["source"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Stale source or dossier identity"):
            eligibility.validate_report(report)

    def test_dossier_archive_drift_fails(self):
        report = valid_report()
        report["original_dossier_archive"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Original dossier archive identity"):
            eligibility.validate_report(report)

    def test_dependency_hash_drift_fails(self):
        report = valid_report()
        report["bounded_dependency_closure"]["dependencies"][0]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Stale dependency source identity"):
            eligibility.validate_report(report)

    def test_dossier_row_drift_fails(self):
        report = valid_report()
        report["targets"][0]["original_dossier_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Stale source or dossier identity"):
            eligibility.validate_report(report)

    def test_partial_target_coverage_fails(self):
        report = valid_report()
        report["targets"].pop()
        with self.assertRaisesRegex(ValueError, "Six-file target coverage is incomplete"):
            eligibility.validate_report(report)

    def test_partial_semantic_coverage_cannot_qualify(self):
        report = valid_report()
        review = report["targets"][0]["review"]
        review["semantic_disposition"] = "COPILOT_REVIEWED/PASSED"
        review["whole_file_coverage"] = {
            "status": "WHOLE_FILE",
            "reviewed_line_ranges": [[1, 10]],
        }
        with self.assertRaisesRegex(ValueError, "Partial semantic coverage"):
            eligibility.validate_report(report)

    def test_combined_distribution_license_ambiguity_fails(self):
        report = valid_report()
        report["targets"][0]["license"]["combined_distribution_clearance"] = True
        with self.assertRaisesRegex(ValueError, "license claim"):
            eligibility.validate_report(report)

    def test_dependency_license_ambiguity_fails(self):
        report = valid_report()
        report["bounded_dependency_closure"]["dependencies"][0]["license_notice"] = "CLEARED"
        with self.assertRaisesRegex(ValueError, "Dependency licensing"):
            eligibility.validate_report(report)

    def test_unsupported_native_oracle_claim_fails(self):
        report = valid_report()
        report["evidence_limits"]["armv4t_oracle"] = "PASSED"
        with self.assertRaisesRegex(ValueError, "Unsupported native, oracle"):
            eligibility.validate_report(report)

    def test_reviewer_dossier_author_conflict_fails(self):
        with self.assertRaisesRegex(ValueError, "Reviewer and dossier/substantive-evidence author conflict"):
            eligibility.validate_reviewer_independence(198982749, [198982749])

    def test_separate_reviewer_passes_independence_check(self):
        eligibility.validate_reviewer_independence(7, [198982749])

    def test_author_conflict_cannot_be_removed_from_matrix(self):
        report = valid_report()
        report["candidate_copilot_reviewer_identity"] = {"login": "someone-else", "id": 7}
        with self.assertRaisesRegex(ValueError, "Candidate reviewer identity provenance"):
            eligibility.validate_report(report)

    def test_receipt_or_approval_claim_fails(self):
        report = valid_report()
        report["targets"][0]["review"]["canonical_receipt_rows"] = 1
        with self.assertRaisesRegex(ValueError, "Unsupported receipt or attestation"):
            eligibility.validate_report(report)

    def test_unknown_evidence_claim_fails(self):
        report = valid_report()
        report["evidence_limits"]["hardware_oracle"] = "PASS"
        with self.assertRaisesRegex(ValueError, "Unsupported native, oracle"):
            eligibility.validate_report(report)

    def test_malformed_repository_head_fails(self):
        report = valid_report()
        report["repository_head"] = "not-a-commit"
        with self.assertRaisesRegex(ValueError, "Repository head identity"):
            eligibility.validate_report(report)


if __name__ == "__main__":
    unittest.main()
