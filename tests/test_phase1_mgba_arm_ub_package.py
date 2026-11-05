import unittest

from tools import phase1_mgba_arm_ub_package as package


def valid_report():
    identities = {
        item["path"]: {
            "git_blob_sha1": item["blob"],
            "source_sha256": item["source_sha256"],
            "dossier_row_sha256": item["dossier_sha256"],
            "dossier_archive_sha256": package.ARCHIVE_SHA256,
            "line_anchors": [
                {"line": line, "text": text}
                for line, text in package.ANCHOR_LINES[key]
            ],
        }
        for key, item in package.SOURCES.items()
    }
    return package.compose_report(
        {
            item["path"]: {
                "row_sha256": item["dossier_sha256"],
                "archive_sha256": package.ARCHIVE_SHA256,
            }
            for item in package.SOURCES.values()
        },
        {
            key: [{"line": line, "text": text} for line, text in anchors]
            for key, anchors in package.ANCHOR_LINES.items()
        },
        "gcc test",
    )


class ARMUBPackageTests(unittest.TestCase):
    def test_exact_nonapproving_package_passes(self):
        package.validate_report(valid_report())

    def test_source_blob_drift_fails(self):
        report = valid_report()
        path = package.SOURCES["isa_inlines"]["path"]
        report["source_identities"][path]["git_blob_sha1"] = "0" * 40
        report["objections"][0]["source"] = report["source_identities"][path]
        with self.assertRaisesRegex(ValueError, "source or dossier identity drift"):
            package.validate_report(report)

    def test_source_sha256_drift_fails(self):
        report = valid_report()
        path = package.SOURCES["decoder_thumb"]["path"]
        report["source_identities"][path]["source_sha256"] = "0" * 64
        report["objections"][1]["source"] = report["source_identities"][path]
        with self.assertRaisesRegex(ValueError, "source or dossier identity drift"):
            package.validate_report(report)

    def test_dossier_row_drift_fails(self):
        report = valid_report()
        path = package.SOURCES["decoder"]["path"]
        report["source_identities"][path]["dossier_row_sha256"] = "0" * 64
        report["objections"][2]["source"] = report["source_identities"][path]
        with self.assertRaisesRegex(ValueError, "source or dossier identity drift"):
            package.validate_report(report)

    def test_dossier_archive_drift_fails(self):
        report = valid_report()
        report["dossier_archive_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "dossier archive identity mismatch"):
            package.validate_report(report)

    def test_resolved_disposition_fails(self):
        report = valid_report()
        report["objections"][0]["disposition"] = "RESOLVED"
        with self.assertRaisesRegex(ValueError, "Invalid or unsupported disposition"):
            package.validate_report(report)

    def test_approval_or_gate_mutation_fails(self):
        report = valid_report()
        report["gate_contribution"] = 1
        with self.assertRaisesRegex(ValueError, "cannot change gate"):
            package.validate_report(report)

    def test_native_or_arm_oracle_claim_fails(self):
        report = valid_report()
        report["sanitizer_evidence"]["armv4t_hardware_oracle"] = True
        with self.assertRaisesRegex(ValueError, "Unsupported compiler, runtime, ABI, or oracle"):
            package.validate_report(report)

    def test_complete_dependency_clearance_claim_fails(self):
        report = valid_report()
        report["dependency_evidence"]["complete_project_closure"] = True
        with self.assertRaisesRegex(ValueError, "Unsupported complete project dependency closure"):
            package.validate_report(report)

    def test_dependency_identity_drift_fails(self):
        report = valid_report()
        report["dependency_evidence"]["verified_input_identities"]["include/mgba/internal/arm/arm.h"][
            "source_sha256"
        ] = "0" * 64
        with self.assertRaisesRegex(ValueError, "dependency identity drift"):
            package.validate_report(report)

    def test_distribution_license_clearance_claim_fails(self):
        report = valid_report()
        report["license_evidence"]["distribution_clearance"] = True
        with self.assertRaisesRegex(ValueError, "distribution-license clearance"):
            package.validate_report(report)

    def test_complete_abi_claim_fails(self):
        report = valid_report()
        report["sanitizer_evidence"]["whole_api_abi_established"] = True
        with self.assertRaisesRegex(ValueError, "Unsupported compiler, runtime, ABI, or oracle"):
            package.validate_report(report)

    def test_native_execution_claim_fails(self):
        report = valid_report()
        report["sanitizer_evidence"]["native_mgba_execution"] = True
        with self.assertRaisesRegex(ValueError, "Unsupported compiler, runtime, ABI, or oracle"):
            package.validate_report(report)

    def test_unrecognized_claim_fails(self):
        report = valid_report()
        report["sanitizer_evidence"]["independent_oracle_passed"] = True
        with self.assertRaisesRegex(ValueError, "Unsupported compiler, runtime, ABI, or oracle"):
            package.validate_report(report)

    def test_anchor_drift_fails(self):
        report = valid_report()
        report["source_identities"][package.SOURCES["isa_inlines"]["path"]]["line_anchors"][0][
            "text"
        ] = "unsupported source claim"
        with self.assertRaisesRegex(ValueError, "source anchor drift"):
            package.validate_report(report)

    def test_changed_ubsan_case_fails(self):
        report = valid_report()
        report["objections"][1]["controls"][0]["expected_diagnostic"] = "no failure"
        with self.assertRaisesRegex(ValueError, "Invalid or unsupported disposition"):
            package.validate_report(report)


if __name__ == "__main__":
    unittest.main()
