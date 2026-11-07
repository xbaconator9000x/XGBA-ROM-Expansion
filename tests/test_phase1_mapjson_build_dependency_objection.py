"""Fail-closed tests for the pinned mapjson build-dependency objection."""

import copy
import json
from pathlib import Path
import unittest

from tools.phase1_mapjson_build_dependency_objection import (
    ROOT,
    load_reference,
    validate_source_objection,
)


EVIDENCE_PATH = (
    ROOT
    / "development/copilot-integration/"
    "mapjson-build-dependency-objection-20261107.json"
)


class MapjsonBuildDependencyObjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
        cls.reference = load_reference()

    def test_exact_pins_validate_without_semantic_promotion(self):
        self.assertEqual(validate_source_objection(self.evidence, self.reference), [])
        self.assertEqual(self.evidence["objection"]["status"], "NEEDS_EVIDENCE")
        self.assertEqual(
            self.evidence["related_integration_blocker"]["disposition"], "BLOCKED"
        )
        self.assertEqual(self.evidence["phase1"]["gate"], "FAIL_INCOMPLETE")
        self.assertEqual(self.evidence["phase1"]["approved_dispositions"], 0)

    def test_wrong_blob_or_dossier_sha_is_rejected(self):
        for field in ("git_blob_sha", "dossier_sha256", "source_sha256"):
            altered = copy.deepcopy(self.evidence)
            altered["source_files"][0][field] = "0" * (40 if field == "git_blob_sha" else 64)
            with self.subTest(field=field):
                findings = validate_source_objection(altered, self.reference)
                self.assertTrue(any("differs from pinned registry" in item for item in findings))

    def test_missing_or_duplicate_dependency_identity_is_rejected(self):
        altered = copy.deepcopy(self.evidence)
        altered["source_files"] = [
            row for row in altered["source_files"]
            if row["path"] != "tools/mapjson/json11.h"
        ]
        findings = validate_source_objection(altered, self.reference)
        self.assertTrue(any("closure is incomplete" in item for item in findings))

        altered = copy.deepcopy(self.evidence)
        altered["source_files"].append(copy.deepcopy(altered["source_files"][0]))
        findings = validate_source_objection(altered, self.reference)
        self.assertTrue(any("contain duplicates" in item for item in findings))

    def test_blocker_and_license_cannot_be_promoted(self):
        mutations = (
            (
                "resolved blocker",
                lambda value: value["related_integration_blocker"].update(
                    disposition="RESOLVED"
                ),
            ),
            (
                "approved disposition",
                lambda value: value["objection"].update(status="APPROVED"),
            ),
            (
                "license cleared",
                lambda value: value["licensing"].update(
                    distribution_clearance="CLEARED"
                ),
            ),
            (
                "false phase gate",
                lambda value: value["phase1"].update(gate="PASS"),
            ),
            (
                "fabricated native build",
                lambda value: value["unverified"].update(arm_target_build=False),
            ),
        )
        for name, mutate in mutations:
            altered = copy.deepcopy(self.evidence)
            with self.subTest(mutation=name):
                mutate(altered)
                self.assertTrue(validate_source_objection(altered, self.reference))

    def test_host_transcript_tampering_is_rejected(self):
        altered = copy.deepcopy(self.evidence)
        altered["host_synthetic_validation"]["transcript"][0] = "invented compiler"
        findings = validate_source_objection(altered, self.reference)
        self.assertTrue(any("transcript is incomplete" in item for item in findings))

    def test_registry_hash_tampering_is_rejected(self):
        altered = copy.deepcopy(self.evidence)
        altered["source_registry"]["dossiers_sha256"] = "0" * 64
        findings = validate_source_objection(altered, self.reference)
        self.assertTrue(any("dossier archive hash mismatch" in item for item in findings))


if __name__ == "__main__":
    unittest.main()
