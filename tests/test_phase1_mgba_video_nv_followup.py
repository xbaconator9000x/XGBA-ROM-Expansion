import unittest

from tools import phase1_mgba_video_nv_followup as followup


def valid_report():
    return followup.compose_report(
        {
            path: {
                "git_blob_sha1": source["blob"],
                "source_sha256": source["sha256"],
                "dossier_row_sha256": source["dossier"],
                "dossier_archive_sha256": followup.ARCHIVE_SHA256,
                "line_anchors": [
                    {"line": line, "text": text} for line, text in source["anchors"]
                ],
            }
            for path, source in followup.FOCUS_SOURCES.items()
        }
    )


class VideoNVFollowupTests(unittest.TestCase):
    def test_exact_nonapproving_report_passes(self):
        followup.validate_report(valid_report())

    def test_source_blob_drift_fails(self):
        report = valid_report()
        path = "include/mgba/internal/gba/video.h"
        report["source_records"][path]["git_blob_sha1"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "source/dossier identity or anchor drift"):
            followup.validate_report(report)

    def test_source_sha_drift_fails(self):
        report = valid_report()
        path = "src/arm/arm.c"
        report["source_records"][path]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source/dossier identity or anchor drift"):
            followup.validate_report(report)

    def test_dossier_row_drift_fails(self):
        report = valid_report()
        path = "src/arm/debugger/debugger.c"
        report["source_records"][path]["dossier_row_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source/dossier identity or anchor drift"):
            followup.validate_report(report)

    def test_dossier_archive_drift_fails(self):
        report = valid_report()
        report["dossier_archive_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Dossier archive identity mismatch"):
            followup.validate_report(report)

    def test_anchor_drift_fails(self):
        report = valid_report()
        report["source_records"]["src/gba/memory.c"]["line_anchors"][0]["text"] = "unsupported"
        with self.assertRaisesRegex(ValueError, "source/dossier identity or anchor drift"):
            followup.validate_report(report)

    def test_effective_type_cannot_be_resolved_by_host_alignment(self):
        report = valid_report()
        report["video_backing"]["effective_type"] = "RESOLVED"
        with self.assertRaisesRegex(ValueError, "Effective-type conclusion cannot be promoted"):
            followup.validate_report(report)

    def test_alignment_controls_cannot_be_overstated(self):
        report = valid_report()
        report["video_backing"]["alignment_control"]["alignment_variants"] = 1
        with self.assertRaisesRegex(ValueError, "Unsupported video alignment control claim"):
            followup.validate_report(report)

    def test_arm_nv_disposition_cannot_be_approved(self):
        report = valid_report()
        report["arm_condition_f"]["disposition"] = "APPROVED"
        with self.assertRaisesRegex(ValueError, "ARM condition-F disposition"):
            followup.validate_report(report)

    def test_armv4t_oracle_claim_fails_closed(self):
        report = valid_report()
        report["arm_condition_f"]["independent_armv4t_oracle"] = "PASSED"
        with self.assertRaisesRegex(ValueError, "Unsupported ARMv4T oracle"):
            followup.validate_report(report)

    def test_license_clearance_cannot_be_claimed(self):
        report = valid_report()
        report["license_evidence"]["distribution_clearance"] = True
        with self.assertRaisesRegex(ValueError, "Unsupported license or distribution-clearance"):
            followup.validate_report(report)

    def test_gate_and_approval_mutations_fail(self):
        for key, value in (("independent_approvals_added", 1), ("gate_contribution", 1)):
            with self.subTest(key=key):
                report = valid_report()
                report[key] = value
                with self.assertRaisesRegex(ValueError, "cannot add approvals or gate contribution"):
                    followup.validate_report(report)

    def test_gate_cannot_be_changed(self):
        report = valid_report()
        report["gate"] = "PASS"
        with self.assertRaisesRegex(ValueError, "cannot change the gate"):
            followup.validate_report(report)

    def test_unrecognized_report_claim_fails_closed(self):
        report = valid_report()
        report["independent_armv4t_oracle_passed"] = True
        with self.assertRaisesRegex(ValueError, "Unsupported report fields or evidence claims"):
            followup.validate_report(report)

    def test_source_scope_cannot_be_rewritten(self):
        report = valid_report()
        report["video_backing"]["source_scope"] = ["effective-type proved safe"]
        with self.assertRaisesRegex(ValueError, "Unsupported report fields or evidence claims"):
            followup.validate_report(report)


if __name__ == "__main__":
    unittest.main()
