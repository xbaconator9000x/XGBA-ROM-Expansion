"""Offline fail-closed fixtures for PR integration provenance."""

import copy
import json
from pathlib import Path
import unittest

from tools.copilot_check_integration_readiness import validate


FIXTURE = (
    Path(__file__).parent
    / "fixtures/copilot-integration-readiness/valid_merge_sha.json"
)


class IntegrationReadinessTests(unittest.TestCase):
    def setUp(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.manifest = fixture["manifest"]
        self.snapshot = fixture["snapshot"]

    def test_exact_merge_sha_with_head_and_base_provenance_passes(self):
        self.assertEqual(validate(self.manifest, self.snapshot), [])

    def test_merge_sha_is_distinguished_by_exact_pr_head_and_base(self):
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["workflow_runs"][0]["pull_requests"][0].pop("merge_sha")
        self.assertEqual(validate(self.manifest, snapshot), [])

    def test_missing_dependency_fails_closed(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["pull_requests"][0]["depends_on"] = [76]
        self.assertTrue(
            any("missing dependency PR #76" in issue
                for issue in validate(manifest, self.snapshot))
        )

    def test_closed_or_non_draft_pr_fails_closed(self):
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["pull_requests"]["77"]["draft"] = False
        self.assertTrue(
            any("open-draft state" in issue
                for issue in validate(self.manifest, snapshot))
        )

    def test_missing_required_workflow_id_fails_closed(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["required_workflow_ids"].pop("77")
        self.assertTrue(
            any("workflow ID is unverified" in issue
                for issue in validate(manifest, self.snapshot))
        )

    def test_malformed_pinned_sha_fails_closed(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["pull_requests"][0]["base"]["sha"] = "b" * 37
        self.assertTrue(
            any("not a full 40-character Git SHA" in issue
                for issue in validate(manifest, self.snapshot))
        )

    def test_changed_head_or_base_sha_fails_closed(self):
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["pull_requests"]["77"]["head_sha"] = "dddddddddddddddddddddddddddddddddddddddd"
        self.assertTrue(
            any("head SHA changed" in issue for issue in validate(self.manifest, snapshot))
        )
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["pull_requests"]["77"]["base_sha"] = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
        self.assertTrue(
            any("base SHA changed" in issue for issue in validate(self.manifest, snapshot))
        )

    def test_absent_required_evidence_fails_closed(self):
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["workflow_runs"] = []
        self.assertTrue(
            any("required evidence absent" in issue
                for issue in validate(self.manifest, snapshot))
        )

    def test_green_run_on_different_sha_is_not_evidence(self):
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["workflow_runs"][0]["event"] = "push"
        snapshot["workflow_runs"][0]["head_sha"] = "dddddddddddddddddddddddddddddddddddddddd"
        self.assertTrue(
            any("lacks matching current head/base provenance" in issue
                for issue in validate(self.manifest, snapshot))
        )

    def test_merge_sha_without_actual_base_provenance_is_not_evidence(self):
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["workflow_runs"][0]["pull_requests"][0].pop("base_sha")
        self.assertTrue(
            any("lacks matching current head/base provenance" in issue
                for issue in validate(self.manifest, snapshot))
        )


if __name__ == "__main__":
    unittest.main()
