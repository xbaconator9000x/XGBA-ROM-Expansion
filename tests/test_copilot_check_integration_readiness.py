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

    def test_exact_pr_head_sha_is_valid_evidence(self):
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["workflow_runs"][0]["head_sha"] = (
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        )
        snapshot["workflow_runs"][0]["event"] = "pull_request"
        self.assertEqual(validate(self.manifest, snapshot), [])

    def test_unrelated_executed_sha_is_rejected_even_with_matching_pr_refs(self):
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["workflow_runs"][0]["head_sha"] = "d" * 40
        self.assertTrue(
            any("lacks matching current head/base provenance" in issue
                for issue in validate(self.manifest, snapshot))
        )

    def test_merge_sha_requires_verified_exact_parent_head_and_base(self):
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["commit_details"]["c" * 40]["parents"] = [
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "dddddddddddddddddddddddddddddddddddddddd",
        ]
        self.assertTrue(
            any("lacks matching current head/base provenance" in issue
                for issue in validate(self.manifest, snapshot))
        )

    def test_pull_request_target_running_base_code_is_rejected(self):
        snapshot = copy.deepcopy(self.snapshot)
        run = snapshot["workflow_runs"][0]
        run["event"] = "pull_request_target"
        run["head_sha"] = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        self.assertTrue(
            any("lacks matching current head/base provenance" in issue
                for issue in validate(self.manifest, snapshot))
        )

    def test_empty_or_malformed_scopes_fail_closed(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["pull_requests"] = []
        self.assertTrue(any("non-empty list" in issue for issue in validate(manifest, self.snapshot)))

        snapshot = copy.deepcopy(self.snapshot)
        snapshot["pull_requests"] = {}
        self.assertTrue(any("non-empty object" in issue for issue in validate(self.manifest, snapshot)))

        manifest = copy.deepcopy(self.manifest)
        manifest["pull_requests"] = [{}]
        self.assertTrue(any("invalid PR number" in issue for issue in validate(manifest, self.snapshot)))

    def test_duplicate_manifest_and_snapshot_scopes_fail_closed(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["pull_requests"].append(copy.deepcopy(manifest["pull_requests"][0]))
        self.assertTrue(any("duplicate PR #77" in issue for issue in validate(manifest, self.snapshot)))

        snapshot = copy.deepcopy(self.snapshot)
        snapshot["pull_requests"][77] = copy.deepcopy(snapshot["pull_requests"]["77"])
        self.assertTrue(any("duplicate PR #77" in issue for issue in validate(self.manifest, snapshot)))

    def test_dependency_cycles_fail_closed(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["pull_requests"][0]["depends_on"] = [77]
        self.assertTrue(any("dependency cycle" in issue for issue in validate(manifest, self.snapshot)))

    def test_inconsistent_topological_order_fails_closed(self):
        manifest = copy.deepcopy(self.manifest)
        parent = copy.deepcopy(manifest["pull_requests"][0])
        parent.update(
            number=78,
            title="parent",
            head={"ref": "parent", "sha": "f" * 40},
            depends_on=[],
        )
        manifest["pull_requests"][0]["depends_on"] = [78]
        manifest["pull_requests"].append(parent)
        manifest["required_workflow_ids"]["78"] = [43]
        manifest["pull_request_order"] = [77, 78]

        snapshot = copy.deepcopy(self.snapshot)
        snapshot["pull_requests"]["78"] = {
            "head_sha": "f" * 40,
            "base_sha": "b" * 40,
            "base_ref": "main",
            "state": "open",
            "draft": True,
            "merged": False,
        }
        snapshot["workflow_runs"].append({
            "id": 123457,
            "workflow_id": 43,
            "event": "push",
            "status": "completed",
            "conclusion": "success",
            "head_sha": "f" * 40,
            "pull_requests": [78],
        })
        self.assertTrue(
            any("places PR #77 before dependency PR #78" in issue
                for issue in validate(manifest, snapshot))
        )

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
            any("manifest base SHA is malformed" in issue
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
