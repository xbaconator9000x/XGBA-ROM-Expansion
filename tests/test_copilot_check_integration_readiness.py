"""Offline fail-closed fixtures for PR integration provenance."""

import copy
import json
from pathlib import Path
import unittest

from tools.copilot_check_integration_readiness import (
    blocker_triage_report,
    classify_workflow_evidence,
    _format_workflow_blocker,
    recorded_snapshot,
    validate,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures/copilot-integration-readiness/valid_merge_sha.json"
)
CLASSIFICATIONS = (
    Path(__file__).parent
    / "fixtures/copilot-integration-readiness/workflow_classifications.json"
)
BASE_RECONCILIATION = (
    Path(__file__).parent
    / "fixtures/copilot-integration-readiness/base_sha_reconciliation.json"
)
LIVE_OBSERVATIONS = (
    Path(__file__).parent
    / "fixtures/copilot-integration-readiness/live_observations_20261104.json"
)
MANIFEST = (
    Path(__file__).parent.parent / "development/copilot-integration/manifest.json"
)


class IntegrationReadinessTests(unittest.TestCase):
    def setUp(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.manifest = fixture["manifest"]
        self.snapshot = fixture["snapshot"]
        self.classification_fixture = json.loads(
            CLASSIFICATIONS.read_text(encoding="utf-8")
        )

    def test_exact_merge_sha_with_head_and_base_provenance_passes(self):
        self.assertEqual(validate(self.manifest, self.snapshot), [])

    def test_merge_sha_is_distinguished_by_exact_pr_head_and_base(self):
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["workflow_runs"][0]["pull_requests"][0].pop("merge_sha")
        self.assertEqual(validate(self.manifest, snapshot), [])

    def test_exact_pr_head_sha_is_valid_evidence(self):
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["workflow_runs"][0]["head_sha"] = "a" * 40
        snapshot["workflow_runs"][0]["event"] = "pull_request"
        snapshot["workflow_runs"][0]["pull_requests"][0] = {
            "number": 77,
            "head_sha": "a" * 40,
            "base_sha": "b" * 40,
        }
        self.assertEqual(validate(self.manifest, snapshot), [])

    def test_exact_pr_head_without_current_base_provenance_is_rejected(self):
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["workflow_runs"][0]["head_sha"] = "a" * 40
        snapshot["workflow_runs"][0]["event"] = "pull_request"
        snapshot["workflow_runs"][0]["pull_requests"][0] = {
            "number": 77,
            "head_sha": "a" * 40,
        }
        issues = validate(self.manifest, snapshot)
        self.assertTrue(
            any(
                "PR head/base provenance is missing or stale" in issue
                for issue in issues
            )
        )

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

    def test_eight_base_rows_use_verified_full_sha_and_keep_stale_dependency(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        reconciliation = json.loads(
            BASE_RECONCILIATION.read_text(encoding="utf-8")
        )
        expected_numbers = {11, 12, 14, 15, 16, 17, 18, 21}
        rows = {
            pr["number"]: pr
            for pr in manifest["pull_requests"]
            if pr["number"] in expected_numbers
        }
        evidence = {
            pr["number"]: pr for pr in reconciliation["pull_requests"]
        }
        self.assertEqual(set(rows), expected_numbers)
        self.assertEqual(set(evidence), expected_numbers)
        self.assertEqual(
            manifest["base_sha_reconciliation"]["reconciled_at"],
            reconciliation["observed_at"],
        )
        self.assertEqual(
            reconciliation["reported_pr_base_sha"],
            "b76a2b686d4acf4302b9dacfad28494660d9b5f9",
        )
        self.assertEqual(
            reconciliation["observed_base_ref_tip_sha"],
            "995e00904384191170075e8a57d18161ef1a2ec2",
        )
        self.assertNotEqual(
            reconciliation["reported_pr_base_sha"],
            reconciliation["observed_base_ref_tip_sha"],
        )
        for number, pr in rows.items():
            with self.subTest(pr=number):
                self.assertEqual(pr["depends_on"], [8])
                self.assertEqual(pr["base"]["ref"], reconciliation["shared_child_base_ref"])
                self.assertEqual(pr["base"]["sha"], reconciliation["reported_pr_base_sha"])
                self.assertEqual(
                    pr["base"]["reported_sha"],
                    reconciliation["original_malformed_manifest_sha"],
                )
                self.assertEqual(
                    evidence[number]["manifest_head_sha"], pr["head"]["sha"]
                )
                self.assertEqual(evidence[number]["base_ref"], pr["base"]["ref"])
                self.assertEqual(
                    evidence[number]["merge_base_sha"],
                    reconciliation["shared_merge_base_sha"],
                )
                self.assertNotEqual(
                    pr["base"]["sha"], evidence[number]["merge_base_sha"]
                )

        issues = validate(manifest, recorded_snapshot(manifest))
        for number in expected_numbers:
            with self.subTest(stale_dependency=number):
                self.assertTrue(
                    any(
                        "PR #%d base SHA %s does not match dependency PR #8 head"
                        % (number, reconciliation["reported_pr_base_sha"])
                        in issue
                        for issue in issues
                    )
                )

    def test_reconciled_sha_must_match_pr_metadata_not_merge_base(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        snapshot = recorded_snapshot(manifest)
        pr = next(item for item in manifest["pull_requests"] if item["number"] == 11)
        pr["base"]["sha"] = "18dee74bf3042326645eb13ae7df3c551325b5a8"
        issues = validate(manifest, snapshot)
        self.assertTrue(
            any(
                "PR #11 base SHA changed" in issue
                and "observed b76a2b686d4acf4302b9dacfad28494660d9b5f9" in issue
                for issue in issues
            )
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

    def test_workflow_evidence_classification_fixtures(self):
        observed = {
            "head_sha": self.classification_fixture["pull_request"]["head_sha"],
            "base_sha": self.classification_fixture["pull_request"]["base_sha"],
        }
        cases = self.classification_fixture["cases"]
        expected = {
            "executed_success": "executed_success",
            "executed_failure": "executed_failure",
            "action_required_zero_job": "action_required_zero_job",
            "pending": "pending",
            "missing": "missing",
            "stale_head": "stale_head_base",
            "stale_base": "stale_head_base",
        }
        for case_name, expected_status in expected.items():
            with self.subTest(case=case_name):
                result = classify_workflow_evidence(
                    77,
                    42,
                    observed,
                    cases[case_name]["runs"],
                    {},
                )
                self.assertEqual(result["status"], expected_status)

    def test_newer_authorization_blocked_attempt_supersedes_older_success(self):
        observed = {
            "head_sha": self.classification_fixture["pull_request"]["head_sha"],
            "base_sha": self.classification_fixture["pull_request"]["base_sha"],
        }
        cases = self.classification_fixture["cases"]
        older = copy.deepcopy(cases["executed_success"]["runs"][0])
        newer = copy.deepcopy(cases["action_required_zero_job"]["runs"][0])
        older.update(id=200, run_number=20, run_attempt=1, created_at="2026-11-04T10:00:00Z")
        newer.update(id=200, run_number=20, run_attempt=2, created_at="2026-11-04T10:00:00Z")
        result = classify_workflow_evidence(77, 42, observed, [older, newer], {})
        self.assertEqual(result["status"], "action_required_zero_job")
        self.assertEqual(result["run_attempt"], 2)
        blocker = _format_workflow_blocker(result)
        self.assertIn(result["run_url"], blocker)
        self.assertIn("expected_head_sha", result)
        self.assertIn("tested_head=%s" % observed["head_sha"], blocker)
        self.assertIn("tested_base=%s" % observed["base_sha"], blocker)
        self.assertIn("maintainer with write access must approve", blocker)
        self.assertIn("do not retry or count it as green", blocker)

    def test_action_required_is_reported_even_without_head_base_provenance(self):
        observed = {
            "head_sha": self.classification_fixture["pull_request"]["head_sha"],
            "base_sha": self.classification_fixture["pull_request"]["base_sha"],
        }
        run = copy.deepcopy(
            self.classification_fixture["cases"]["action_required_zero_job"]["runs"][0]
        )
        run["pull_requests"] = [77]
        result = classify_workflow_evidence(77, 42, observed, [run], {})
        self.assertEqual(result["status"], "action_required_zero_job")
        self.assertEqual(result["provenance_status"], "stale_head_base")
        self.assertIn("lacks current PR head/base provenance", result["detail"])
        blocker = _format_workflow_blocker(result)
        self.assertIn("maintainer with write access must approve", blocker)
        self.assertIn("provenance", blocker)

    def test_missing_or_incomplete_job_scope_never_counts_as_success(self):
        observed = {
            "head_sha": self.classification_fixture["pull_request"]["head_sha"],
            "base_sha": self.classification_fixture["pull_request"]["base_sha"],
        }
        run = copy.deepcopy(
            self.classification_fixture["cases"]["executed_success"]["runs"][0]
        )
        run["jobs"]["complete"] = False
        result = classify_workflow_evidence(77, 42, observed, [run], {})
        self.assertEqual(result["status"], "missing")

        run = copy.deepcopy(
            self.classification_fixture["cases"]["executed_success"]["runs"][0]
        )
        run["jobs"]["jobs"][0]["run_attempt"] = 1
        result = classify_workflow_evidence(77, 42, observed, [run], {})
        self.assertEqual(result["status"], "missing")

        run["jobs"]["jobs"][0]["run_attempt"] = run["run_attempt"]
        result = classify_workflow_evidence(77, 42, observed, [run], {})
        self.assertEqual(result["status"], "executed_success")

        run["jobs"]["complete"] = True
        run["jobs"]["total_count"] = 0
        run["jobs"]["jobs"] = []
        result = classify_workflow_evidence(77, 42, observed, [run], {})
        self.assertEqual(result["status"], "missing")

    def test_stale_success_and_pull_request_target_base_are_not_counted(self):
        observed = {
            "head_sha": self.classification_fixture["pull_request"]["head_sha"],
            "base_sha": self.classification_fixture["pull_request"]["base_sha"],
        }
        stale = copy.deepcopy(
            self.classification_fixture["cases"]["stale_head"]["runs"][0]
        )
        issue = validate(
            {
                "pull_requests": [{
                    "number": 77,
                    "head": {"ref": "topic", "sha": observed["head_sha"]},
                    "base": {"ref": "main", "sha": observed["base_sha"]},
                    "depends_on": [],
                    "required_evidence": ["evidence"],
                }],
                "main": {"ref": "main", "sha": observed["base_sha"]},
                "required_workflow_ids": {"77": [42]},
                "pull_request_order": [77],
                "integration_order": [{"order": 1, "action": "Integrate"}],
            },
            {
                "main": {"sha": observed["base_sha"]},
                "pull_requests": {
                    "77": {
                        "head_sha": observed["head_sha"],
                        "base_sha": observed["base_sha"],
                        "base_ref": "main",
                        "state": "open",
                        "draft": True,
                        "merged": False,
                    }
                },
                "workflow_runs": [stale],
                "commit_details": {},
            },
        )
        self.assertTrue(any("stale_head_base" in item for item in issue))
        self.assertTrue(any(stale["html_url"] in item for item in issue))

        target = copy.deepcopy(
            self.classification_fixture["cases"]["executed_success"]["runs"][0]
        )
        target["event"] = "pull_request_target"
        target["head_sha"] = observed["base_sha"]
        result = classify_workflow_evidence(77, 42, observed, [target], {})
        self.assertEqual(result["status"], "stale_head_base")

    def test_offline_blocker_triage_is_complete_and_preserves_policy(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        snapshot = recorded_snapshot(manifest)
        issues = validate(manifest, snapshot)
        live_observations = json.loads(LIVE_OBSERVATIONS.read_text(encoding="utf-8"))
        report = blocker_triage_report(
            manifest, snapshot, issues, "f" * 64, live_observations
        )
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["blocker_count"], len(issues))
        self.assertEqual(
            [item["issue"] for item in report["blockers"]],
            issues,
        )
        self.assertEqual(
            report["category_counts"],
            {
                "stale_dependency_base": 9,
                "stale_main_base": 7,
                "stale_workflow_evidence": 9,
                "unverified_workflow_id": 19,
            },
        )
        self.assertEqual(report["policy"]["phase1_gate"], "FAIL_INCOMPLETE")
        self.assertEqual(report["policy"]["independent_approvals"], 0)
        self.assertFalse(report["policy"]["ci_is_semantic_approval"])
        self.assertEqual(len({item["id"] for item in report["blockers"]}), len(issues))
        self.assertTrue(all(item["closure_action"] for item in report["blockers"]))
        self.assertTrue(all(item["source_refs"] for item in report["blockers"]))
        live_runs = {
            run["pr_number"]: run
            for run in report["live_observations"]["workflow_runs"]
        }
        self.assertEqual(live_runs[13]["jobs"]["total"], 1)
        self.assertEqual(len(live_runs[13]["job_urls"]), 1)
        self.assertEqual(live_runs[27]["conclusion"], "action_required")
        self.assertEqual(live_runs[27]["jobs"]["total"], 0)
        self.assertEqual(live_runs[35]["jobs"]["total"], 1)
        self.assertEqual(live_runs[36]["jobs"]["total"], 2)
        self.assertEqual(live_runs[37]["jobs"]["total"], 0)

    def test_triage_remains_serializable_for_malformed_manifest(self):
        report = blocker_triage_report(
            None,
            {},
            ["manifest must be a JSON object"],
        )
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["blockers"][0]["category"], "other_readiness_blocker")
        self.assertIsNone(report["blockers"][0]["pr_number"])


if __name__ == "__main__":
    unittest.main()
