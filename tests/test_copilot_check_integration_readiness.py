"""Offline fail-closed fixtures for PR integration provenance."""

import copy
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import unittest

from tools.copilot_check_integration_readiness import (
    blocker_action_closure_report,
    blocker_triage_report,
    classify_main_base_ancestry,
    classify_stacked_dependency_observation,
    classify_workflow_evidence,
    dependency_readiness_report,
    _format_workflow_blocker,
    closure_index_report,
    closure_package_linkage_report,
    main,
    missing_required_workflow_events,
    recorded_snapshot,
    validate,
    workflow_id_correction_report,
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
WORKFLOW_ID_RECONCILIATION = (
    Path(__file__).parent
    / "fixtures/copilot-integration-readiness/workflow_id_reconciliation_20261104.json"
)
STALE_WORKFLOW_RECONCILIATION = (
    Path(__file__).parent
    / "fixtures/copilot-integration-readiness/stale_workflow_evidence_20261104.json"
)
STALE_MAIN_RECONCILIATION = (
    Path(__file__).parent
    / "fixtures/copilot-integration-readiness/stale_main_base_evidence_20261105.json"
)
DEPENDENCY_RECONCILIATION = (
    Path(__file__).parent.parent
    / "development/copilot-integration/dependency-base-reconciliation-20261105.json"
)
CLOSURE_INDEX = (
    Path(__file__).parent.parent
    / "development/copilot-integration/closure-index-20261105.json"
)
ACTION_CLOSURE = (
    Path(__file__).parent.parent
    / "development/copilot-integration/action-closure-20261105.json"
)
WORKFLOW_ID_CORRECTION = (
    Path(__file__).parent.parent
    / "development/copilot-integration/workflow-id-correction-20261105.json"
)
PACKAGE_LINKAGE = (
    Path(__file__).parent.parent
    / "development/copilot-integration/package-linkage-20261105.json"
)
MANIFEST = (
    Path(__file__).parent.parent / "development/copilot-integration/manifest.json"
)
BLOCKER_TRIAGE = (
    Path(__file__).parent.parent
    / "development/copilot-integration/blocker-triage-20261104.json"
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

    def test_nineteen_workflow_ids_are_pinned_to_observed_run_job_evidence(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        reconciliation = json.loads(
            WORKFLOW_ID_RECONCILIATION.read_text(encoding="utf-8")
        )
        expected_prs = {
            3, 4, 5, 6, 7, 10, 12, 14, 16, 17, 18, 22, 23,
            25, 26, 27, 28, 35, 36,
        }
        rows = {row["pr"]: row for row in reconciliation["rows"]}
        self.assertEqual(set(rows), expected_prs)
        manifest_prs = {pr["number"]: pr for pr in manifest["pull_requests"]}
        for number, row in rows.items():
            with self.subTest(pr=number):
                pr = manifest_prs[number]
                self.assertEqual(
                    manifest["required_workflow_ids"][str(number)],
                    [row["workflow_id"]],
                )
                self.assertEqual(row["manifest"]["head"], pr["head"]["sha"])
                self.assertEqual(row["manifest"]["base_ref"], pr["base"]["ref"])
                self.assertEqual(row["manifest"]["base"], pr["base"]["sha"])
                self.assertEqual(row["live"]["base_ref"], row["manifest"]["base_ref"])
                self.assertEqual(row["live"]["base"], row["manifest"]["base"])
                self.assertEqual(row["run"]["head"], row["live"]["head"])
                self.assertEqual(
                    row["run"]["event"],
                    "push" if number in {25, 26, 28} else "pull_request",
                )
                self.assertEqual(
                    row["run"]["id"],
                    int(row["run"]["url"].rsplit("/", 1)[1]),
                )
                jobs = row["jobs"]
                self.assertEqual(jobs["count"], len(jobs["job_ids"]))
                self.assertEqual(jobs["success"], jobs["count"])
                self.assertEqual(jobs["successful_steps"], jobs["steps"])
                if row["run"]["conclusion"] == "success":
                    self.assertGreater(jobs["count"], 0)
                else:
                    self.assertEqual(row["run"]["conclusion"], "action_required")
                    self.assertEqual(jobs["count"], 0)
                    self.assertEqual(jobs["steps"], 0)

        self.assertIn("not the run-time PR base SHA", reconciliation["base_provenance_limit"])
        for number in (27, 28, 35, 36):
            self.assertNotEqual(rows[number]["manifest"]["head"], rows[number]["live"]["head"])
        self.assertEqual(manifest["policy"]["phase1_gate"], "FAIL_INCOMPLETE")
        self.assertEqual(manifest["policy"]["independent_approvals"], 0)

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
                "incomplete_workflow_evidence": 19,
                "stale_dependency_base": 9,
                "stale_main_base": 7,
                "stale_workflow_evidence": 9,
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

    def test_nine_stale_workflow_rows_have_source_linked_live_reconciliation(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        triage = json.loads(BLOCKER_TRIAGE.read_text(encoding="utf-8"))
        reconciliation = json.loads(
            STALE_WORKFLOW_RECONCILIATION.read_text(encoding="utf-8")
        )
        expected_prs = {2, 8, 11, 13, 15, 19, 20, 21, 24}
        manifest_prs = {pr["number"]: pr for pr in manifest["pull_requests"]}
        blockers = {
            blocker["id"]: blocker
            for blocker in triage["blockers"]
            if blocker["category"] == "stale_workflow_evidence"
        }
        rows = {row["pr_number"]: row for row in reconciliation["rows"]}

        self.assertEqual(set(rows), expected_prs)
        self.assertEqual(len(blockers), len(expected_prs))
        self.assertEqual(reconciliation["policy"]["phase1_gate"], "FAIL_INCOMPLETE")
        self.assertEqual(reconciliation["policy"]["independent_approvals"], 0)
        self.assertFalse(reconciliation["policy"]["ci_is_semantic_approval"])
        for path, digest in reconciliation["source_sha256"].items():
            self.assertEqual(
                hashlib.sha256(
                    (Path(__file__).parent.parent / path).read_bytes()
                ).hexdigest(),
                digest,
            )
        for number, row in rows.items():
            pinned = manifest_prs[number]
            self.assertEqual(row["manifest"]["head_sha"], pinned["head"]["sha"])
            self.assertEqual(row["manifest"]["base_ref"], pinned["base"]["ref"])
            self.assertEqual(row["manifest"]["base_sha"], pinned["base"]["sha"])
            self.assertEqual(
                row["manifest"]["required_workflow_id"],
                manifest["required_workflow_ids"][str(number)][0],
            )
            self.assertIn(row["blocker_id"], blockers)
            self.assertEqual(blockers[row["blocker_id"]]["pr_number"], number)
            self.assertEqual(
                row["live_pr"]["url"],
                "https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/%d"
                % number,
            )
            self.assertEqual(len(row["workflow"]["blob_sha"]), 40)
            int(row["workflow"]["blob_sha"], 16)
            self.assertTrue(row["workflow"]["required_events"])
            self.assertNotEqual(row["classification"], "executed_success")
            for run in row["observed_runs"]:
                self.assertIn(run["event"], row["workflow"]["required_events"])
                self.assertGreaterEqual(run["attempt"], 1)
                self.assertEqual(
                    len(run["jobs"]["ids"]), run["jobs"]["count"]
                )
                self.assertEqual(len(run["jobs"]["urls"]), run["jobs"]["count"])
                self.assertEqual(
                    run["jobs"]["successful"], run["jobs"]["count"]
                )
                self.assertTrue(
                    run["url"].startswith(
                        "https://github.com/xbaconator9000x/"
                        "XGBA-ROM-Expansion/actions/runs/"
                    )
                )

        self.assertEqual(
            rows[8]["live_compare"]["status"], "diverged"
        )
        self.assertEqual(rows[8]["live_compare"]["behind_by"], 49)
        self.assertEqual(rows[13]["classification"], "action_required_zero_job")
        self.assertEqual(rows[13]["observed_runs"][0]["jobs"]["count"], 0)
        self.assertEqual(rows[20]["observed_runs"][0]["id"], 40795259266)
        self.assertEqual(rows[20]["observed_runs"][0]["jobs"]["count"], 5)

    def test_nine_row_run_provenance_never_promotes_head_only_success(self):
        reconciliation = json.loads(
            STALE_WORKFLOW_RECONCILIATION.read_text(encoding="utf-8")
        )
        for row in reconciliation["rows"]:
            for run in row["observed_runs"]:
                job_data = run["jobs"]
                jobs = [
                    {
                        "id": job_id,
                        "status": "completed",
                        "conclusion": (
                            "success"
                            if index < job_data["successful"]
                            else "failure"
                        ),
                        "run_attempt": run["attempt"],
                        "html_url": job_data["urls"][index],
                    }
                    for index, job_id in enumerate(job_data["ids"])
                ]
                evidence = {
                    "id": run["id"],
                    "workflow_id": row["manifest"]["required_workflow_id"],
                    "run_attempt": run["attempt"],
                    "event": run["event"],
                    "status": "completed",
                    "conclusion": run["conclusion"],
                    "head_sha": run["head_sha"],
                    "html_url": run["url"],
                    "pull_requests": [{"number": row["pr_number"]}],
                    "jobs": {
                        "available": True,
                        "total_count": job_data["count"],
                        "jobs": jobs,
                        "complete": True,
                    },
                }
                result = classify_workflow_evidence(
                    row["pr_number"],
                    row["manifest"]["required_workflow_id"],
                    {
                        "head_sha": row["live_pr"]["head_sha"],
                        "base_sha": row["live_pr"]["base_sha"],
                        "base_ref": row["live_pr"]["base_ref"],
                    },
                    [evidence],
                    {},
                )
                self.assertEqual(result["status"], row["classification"])
                self.assertNotEqual(result["status"], "executed_success")
                if run["conclusion"] == "success":
                    self.assertIsNone(result["reported_base_sha"])
                    self.assertIn("base", result["detail"].lower())

    def test_seven_stale_main_rows_have_live_ancestry_and_exact_event_evidence(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        reconciliation = json.loads(STALE_MAIN_RECONCILIATION.read_text(encoding="utf-8"))
        expected = {2, 3, 4, 6, 7, 23, 25}
        manifest_prs = {pr["number"]: pr for pr in manifest["pull_requests"]}
        rows = {row["pr_number"]: row for row in reconciliation["rows"]}

        self.assertEqual(set(rows), expected)
        self.assertEqual(reconciliation["current_main"]["sha"],
                         "3d8455edb1d26b462881c8a79096e5832fcf4457")
        self.assertEqual(reconciliation["policy"]["phase1_gate"], "FAIL_INCOMPLETE")
        self.assertEqual(reconciliation["policy"]["independent_approvals"], 0)
        for number, row in rows.items():
            pinned = manifest_prs[number]
            with self.subTest(pr=number):
                self.assertEqual(row["manifest"]["head_sha"], pinned["head"]["sha"])
                self.assertEqual(row["manifest"]["base_sha"], pinned["base"]["sha"])
                self.assertEqual(row["manifest"]["base_ref"], pinned["base"]["ref"])
                self.assertEqual(row["workflow"]["id"],
                                 manifest["required_workflow_ids"][str(number)][0])
                self.assertRegex(row["workflow"]["blob_sha"], r"^[0-9a-f]{40}$")
                self.assertEqual(row["main_compare"]["head_sha"],
                                 reconciliation["current_main"]["sha"])
                self.assertEqual(
                    classify_main_base_ancestry({
                        "expected_base_sha": row["manifest"]["base_sha"],
                        "observed_base_sha": row["live_pr"]["base_sha"],
                        "current_main_sha": reconciliation["current_main"]["sha"],
                        "compare": row["main_compare"],
                    })[0],
                    "stale_ancestor",
                )
                self.assertEqual(row["classification"],
                                 "stale_ancestor_and_changed_head" if number == 2
                                 else "stale_ancestor")
                self.assertEqual(
                    missing_required_workflow_events(
                        row["workflow"]["required_automatic_events"], row["runs"]
                    ),
                    [],
                )
                for run in row["runs"]:
                    self.assertGreater(run["attempt"], 0)
                    self.assertEqual(run["id"], int(run["url"].rsplit("/", 1)[1]))
                    self.assertEqual(run["conclusion"], "success")
                    self.assertEqual(len(run["jobs"]), 1)
                    self.assertEqual(run["jobs"][0]["conclusion"], "success")
                    self.assertIn(run["event"], row["workflow"]["configured_events"])
                    self.assertGreater(run["jobs"][0]["steps_completed"], 0)
                    self.assertTrue(run["jobs"][0]["url"].endswith(
                        "/job/%d" % run["jobs"][0]["id"]
                    ))
                    if number != 2 or run["event"] == "pull_request":
                        self.assertEqual(run["head_sha"], row["manifest"]["head_sha"])

        self.assertNotEqual(rows[2]["manifest"]["head_sha"], rows[2]["live_pr"]["head_sha"])
        self.assertEqual(rows[25]["workflow"]["required_automatic_events"], ["push"])
        self.assertNotIn("pull_request", rows[25]["workflow"]["configured_events"])
        self.assertEqual(
            reconciliation["api_limitations"][0],
            "Actions run metadata did not return run-time PR base SHA; successful PR runs do not establish exact base provenance.",
        )

    def test_main_ancestry_evidence_fails_closed_when_missing_or_mismatched(self):
        fixture = json.loads(STALE_MAIN_RECONCILIATION.read_text(encoding="utf-8"))
        row = fixture["rows"][1]
        observation = {
            "expected_base_sha": row["manifest"]["base_sha"],
            "observed_base_sha": row["live_pr"]["base_sha"],
            "current_main_sha": fixture["current_main"]["sha"],
            "compare": row["main_compare"],
        }
        self.assertEqual(classify_main_base_ancestry(observation)[0], "stale_ancestor")

        mutations = (
            ("compare", None, "unverified_ancestry"),
            ("expected_base_sha", "f" * 40, "changed_base"),
        )
        for field, value, expected_status in mutations:
            altered = copy.deepcopy(observation)
            altered[field] = value
            self.assertEqual(classify_main_base_ancestry(altered)[0], expected_status)

        altered = copy.deepcopy(observation)
        altered["compare"]["head_sha"] = "e" * 40
        self.assertEqual(classify_main_base_ancestry(altered)[0], "unverified_ancestry")
        altered = copy.deepcopy(observation)
        altered["compare"]["merge_base_sha"] = "not-a-sha"
        self.assertEqual(classify_main_base_ancestry(altered)[0], "unverified_ancestry")
        altered = copy.deepcopy(observation)
        altered["compare"]["behind_by"] = 1
        self.assertEqual(
            classify_main_base_ancestry(altered)[0], "diverged_or_inconsistent"
        )

    def test_nine_dependency_observations_remain_source_linked_and_blocked(self):
        fixture = json.loads(DEPENDENCY_RECONCILIATION.read_text(encoding="utf-8"))
        manifest_bytes = MANIFEST.read_bytes()
        manifest = json.loads(manifest_bytes)
        actual_hashes = {
            path: hashlib.sha256((MANIFEST.parents[2] / path).read_bytes()).hexdigest()
            for path in fixture["source_hashes"]
        }
        report = dependency_readiness_report(fixture, manifest, actual_hashes)
        rows = {row["pr_number"]: row for row in report["rows"]}

        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["row_count"], 9)
        self.assertEqual(report["blocked_count"], 9)
        self.assertEqual(set(rows), {8, 11, 12, 14, 15, 16, 17, 18, 21})
        self.assertEqual(report["phase1_gate"], "FAIL_INCOMPLETE")
        self.assertEqual(report["independent_approvals"], 0)
        self.assertEqual(report["first_concrete_blocker"]["pr_number"], 8)
        self.assertEqual(report["dependency_advance"]["ahead_by"], 32)
        self.assertEqual(len(report["safe_integration_order"]), 3)
        self.assertEqual(report["source_findings"], [])
        self.assertIn("dependency_history_diverged",
                      [item["code"] for item in rows[8]["findings"]])
        self.assertIn("stale_workflow_head",
                      [item["code"] for item in rows[8]["findings"]])
        for number in {11, 12, 14, 15, 16, 17, 18, 21}:
            codes = {item["code"] for item in rows[number]["findings"]}
            self.assertIn("stale_dependency_base", codes)
            self.assertIn("dependency_history_diverged", codes)
            self.assertIn("unverified_workflow_base", codes)
        self.assertIn("changed_child_head",
                      [item["code"] for item in rows[11]["findings"]])

    def test_dependency_observation_rejects_mutated_or_missing_evidence(self):
        fixture = json.loads(DEPENDENCY_RECONCILIATION.read_text(encoding="utf-8"))
        baseline = fixture["rows"][3]
        result = classify_stacked_dependency_observation(baseline)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("stale_dependency_base",
                      [item["code"] for item in result["findings"]])

        mutations = (
            ("missing dependency", lambda row: row.update(dependency=None),
             "missing_dependency"),
            ("wrong child SHA", lambda row: row["compare"].update(right_sha="f" * 40),
             "unverified_ancestry"),
            ("missing ancestry", lambda row: row.update(compare=None),
             "unverified_ancestry"),
            ("mismatched compare URL", lambda row: row["compare"].update(
                url="https://github.com/xbaconator9000x/XGBA-ROM-Expansion/compare/" + "f" * 40 + "..." + "e" * 40),
             "unverified_ancestry"),
            ("unconfigured required event", lambda row: row["workflow"].update(
                configured_events=["workflow_dispatch"]),
             "unconfigured_required_event"),
            ("missing required event", lambda row: row["workflow"].update(
                runs=[run for run in row["workflow"]["runs"] if run["event"] != "push"]),
             "missing_event"),
            ("wrong-head green run", lambda row: next(
                run for run in row["workflow"]["runs"] if run["event"] == "push"
            ).update(head_sha="f" * 40), "stale_workflow_head"),
            ("unverified green PR base", lambda row: next(
                run for run in row["workflow"]["runs"] if run["event"] == "pull_request"
            ).update(base_sha=row["live_pr"]["base_sha"]), "unverified_workflow_base"),
            ("invented run ID", lambda row: next(
                run for run in row["workflow"]["runs"] if run["event"] == "push"
            ).update(id=999999), "invalid_workflow_run_identity"),
            ("missing executed steps", lambda row: next(
                run for run in row["workflow"]["runs"] for job in run["jobs"]
            )["jobs"][0].update(successful_steps=0), "incomplete_job_evidence"),
        )
        for name, mutate, code in mutations:
            altered = copy.deepcopy(baseline)
            with self.subTest(mutation=name):
                mutate(altered)
                result = classify_stacked_dependency_observation(altered)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertIn(code, [item["code"] for item in result["findings"]])

    def test_dependency_report_fails_on_stale_source_hash_and_missing_row(self):
        fixture = json.loads(DEPENDENCY_RECONCILIATION.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        actual_hashes = {
            path: hashlib.sha256((MANIFEST.parents[2] / path).read_bytes()).hexdigest()
            for path in fixture["source_hashes"]
        }

        stale_hashes = dict(actual_hashes)
        stale_hashes["development/copilot-integration/manifest.json"] = "0" * 64
        report = dependency_readiness_report(fixture, manifest, stale_hashes)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("source_hash_mismatch",
                      [item["code"] for item in report["source_findings"]])

        missing_row = copy.deepcopy(fixture)
        missing_row["rows"].pop()
        report = dependency_readiness_report(missing_row, manifest, actual_hashes)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("dependency_row_set_mismatch",
                      [item["code"] for item in report["source_findings"]])

        altered_policy = copy.deepcopy(fixture)
        altered_policy["policy"]["source_pins_changed"] = True
        report = dependency_readiness_report(altered_policy, manifest, actual_hashes)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("policy_mismatch",
                      [item["code"] for item in report["source_findings"]])

    def test_dependency_observation_cli_is_offline_and_fails_closed(self):
        output = io.StringIO()
        with redirect_stdout(output):
            status = main([
                "--dependency-observations",
                str(DEPENDENCY_RECONCILIATION),
            ])
        self.assertEqual(status, 1)
        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["row_count"], 9)
        self.assertEqual(report["blocked_count"], 9)

    def test_snapshot_with_missing_main_ancestry_fails_closed(self):
        manifest = copy.deepcopy(self.manifest)
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["main_base_ancestry"] = {
            "77": {
                "expected_base_sha": "b" * 40,
                "observed_base_sha": "b" * 40,
                "current_main_sha": "b" * 40,
                "compare": None,
            }
        }
        self.assertTrue(
            any("PR #77 main-base ancestry status=unverified_ancestry" in issue
                for issue in validate(manifest, snapshot))
        )

    def test_required_workflow_event_absence_is_distinct_from_unconfigured_event(self):
        runs = [{"event": "pull_request"}]
        self.assertEqual(missing_required_workflow_events(["pull_request"], runs), [])
        self.assertEqual(
            missing_required_workflow_events(["push", "pull_request"], runs), ["push"]
        )
        self.assertEqual(missing_required_workflow_events(["push"], []), ["push"])

        snapshot = copy.deepcopy(self.snapshot)
        snapshot["required_workflow_events"] = {
            "77": {"42": ["push", "pull_request"]}
        }
        issues = validate(self.manifest, snapshot)
        self.assertTrue(
            any("PR #77 workflow #42 missing required event evidence: push" in issue
                for issue in issues)
        )

        snapshot["required_workflow_events"]["77"]["42"] = ["pull_request"]
        self.assertEqual(validate(self.manifest, snapshot), [])

    def test_triage_remains_serializable_for_malformed_manifest(self):
        report = blocker_triage_report(
            None,
            {},
            ["manifest must be a JSON object"],
        )
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["blockers"][0]["category"], "other_readiness_blocker")
        self.assertIsNone(report["blockers"][0]["pr_number"])

    def test_cross_category_closure_index_deduplicates_and_preserves_all_blockers(self):
        index = json.loads(CLOSURE_INDEX.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        triage = json.loads(BLOCKER_TRIAGE.read_text(encoding="utf-8"))
        package_paths = set(index["source_hashes"]) - {
            "development/copilot-integration/manifest.json",
            "development/copilot-integration/blocker-triage-20261104.json",
        }
        documents = {
            path: json.loads((MANIFEST.parents[2] / path).read_text(encoding="utf-8"))
            for path in package_paths
        }
        hashes = {
            path: hashlib.sha256((MANIFEST.parents[2] / path).read_bytes()).hexdigest()
            for path in index["source_hashes"]
        }
        report = closure_index_report(index, manifest, triage, documents, hashes)

        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["blocker_count"], 44)
        self.assertEqual(report["unique_blocker_ids"], 44)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["category_counts"], {
            "stale_dependency_base": 9,
            "stale_main_base": 7,
            "stale_workflow_evidence": 9,
            "unverified_workflow_id": 19,
        })
        self.assertEqual(report["phase1_gate"], "FAIL_INCOMPLETE")
        self.assertEqual(report["independent_approvals"], 0)
        pr37 = next(
            row for row in index["fresh_workflow_observations"]
            if row["pr_number"] == 37
        )
        self.assertEqual(
            pr37["conclusion"], "action_required"
        )
        self.assertEqual(pr37["base_provenance"], "unavailable_actions_api")
        self.assertIsNone(pr37["reported_base_sha"])
        self.assertEqual(pr37["job_count"], 0)
        self.assertNotEqual(pr37["conclusion"], "success")

    def test_cross_category_index_rejects_duplicate_and_missing_blocker_ids(self):
        index = json.loads(CLOSURE_INDEX.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        triage = json.loads(BLOCKER_TRIAGE.read_text(encoding="utf-8"))
        package_paths = set(index["source_hashes"]) - {
            "development/copilot-integration/manifest.json",
            "development/copilot-integration/blocker-triage-20261104.json",
        }
        documents = {
            path: json.loads((MANIFEST.parents[2] / path).read_text(encoding="utf-8"))
            for path in package_paths
        }
        hashes = {
            path: hashlib.sha256((MANIFEST.parents[2] / path).read_bytes()).hexdigest()
            for path in index["source_hashes"]
        }
        for mutation in ("duplicate", "missing"):
            altered = copy.deepcopy(index)
            if mutation == "duplicate":
                altered["rows"].append(copy.deepcopy(altered["rows"][0]))
                expected = "duplicate blocker IDs"
            else:
                altered["rows"].pop()
                expected = "blocker ID set does not exactly match"
            report = closure_index_report(altered, manifest, triage, documents, hashes)
            self.assertTrue(any(expected in finding for finding in report["findings"]))

    def test_cross_category_index_rejects_changed_sources_head_and_fake_gate(self):
        index = json.loads(CLOSURE_INDEX.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        triage = json.loads(BLOCKER_TRIAGE.read_text(encoding="utf-8"))
        package_paths = set(index["source_hashes"]) - {
            "development/copilot-integration/manifest.json",
            "development/copilot-integration/blocker-triage-20261104.json",
        }
        documents = {
            path: json.loads((MANIFEST.parents[2] / path).read_text(encoding="utf-8"))
            for path in package_paths
        }
        hashes = {
            path: hashlib.sha256((MANIFEST.parents[2] / path).read_bytes()).hexdigest()
            for path in index["source_hashes"]
        }
        mutations = (
            ("source hash", lambda value: value["source_hashes"].update({
                "development/copilot-integration/manifest.json": "0" * 64
            }), "source evidence hash mismatch"),
            ("wrong current head", lambda value: next(
                row for row in value["current_pr_observations"] if row[0] == 37
            ).__setitem__(1, "f" * 40),
             "not an exact-head zero-job gate"),
            ("fabricated success", lambda value: value["fresh_workflow_observations"][-1].update(
                conclusion="success"
            ), "not an exact-head zero-job gate"),
            ("nonzero jobs", lambda value: value["fresh_workflow_observations"][-1].update(
                job_count=1
            ), "not an exact-head zero-job gate"),
            ("wrong attempt", lambda value: value["fresh_workflow_observations"][-1].update(
                attempt=2
            ), "not an exact-head zero-job gate"),
            ("wrong base", lambda value: value["fresh_workflow_observations"][-1].update(
                pr_metadata_base_sha="f" * 40
            ), "not an exact-head zero-job gate"),
            ("fabricated run-time base", lambda value: value["fresh_workflow_observations"][-1].update(
                reported_base_sha="de2a775184d69411016ff683a8075af72ef4a58d"
            ), "misstates unavailable run-time base provenance"),
        )
        for name, mutate, expected in mutations:
            altered = copy.deepcopy(index)
            with self.subTest(mutation=name):
                mutate(altered)
                report = closure_index_report(altered, manifest, triage, documents, hashes)
                self.assertTrue(any(expected in finding for finding in report["findings"]))

        altered_documents = copy.deepcopy(documents)
        workflow_id_path = (
            "tests/fixtures/copilot-integration-readiness/"
            "workflow_id_reconciliation_20261104.json"
        )
        altered_documents[workflow_id_path]["rows"] = [
            row for row in altered_documents[workflow_id_path]["rows"]
            if row["pr"] != 3
        ]
        report = closure_index_report(index, manifest, triage, altered_documents, hashes)
        self.assertTrue(any(
            "B004 evidence package record is absent" in finding
            for finding in report["findings"]
        ))

    def test_closure_index_cli_is_offline_and_stays_blocked(self):
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["--closure-index", str(CLOSURE_INDEX)])
        self.assertEqual(status, 1)
        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["blocker_count"], 44)
        self.assertEqual(report["findings"], [])

    def _package_linkage_inputs(self):
        index = json.loads(CLOSURE_INDEX.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        triage = json.loads(BLOCKER_TRIAGE.read_text(encoding="utf-8"))
        package_paths = set(index["source_hashes"]) - {
            "development/copilot-integration/manifest.json",
            "development/copilot-integration/blocker-triage-20261104.json",
        }
        documents = {
            path: json.loads((MANIFEST.parents[2] / path).read_text(encoding="utf-8"))
            for path in package_paths
        }
        hashes = {
            path: hashlib.sha256((MANIFEST.parents[2] / path).read_bytes()).hexdigest()
            for path in index["source_hashes"]
        }
        fixture = json.loads(PACKAGE_LINKAGE.read_text(encoding="utf-8"))
        return fixture, index, manifest, triage, documents, hashes

    def test_package_linkage_reports_nine_identity_checked_blockers(self):
        fixture, index, manifest, triage, documents, hashes = self._package_linkage_inputs()
        report = closure_package_linkage_report(
            fixture, index, manifest, triage, documents, hashes
        )
        self.assertEqual(report["evidence_validation"], "VALID")
        self.assertEqual(report["row_count"], 9)
        self.assertEqual(report["selected_blocked_count"], 9)
        self.assertEqual(report["selected_resolved_count"], 0)
        self.assertEqual(
            [row["blocker_id"] for row in report["rows"]],
            ["B%03d" % number for number in range(12, 21)],
        )
        self.assertTrue(all(row["status"] == "BLOCKED" for row in report["rows"]))

    def test_package_linkage_rejects_tampered_identity_and_status(self):
        mutations = (
            ("package head", lambda docs: docs[
                "development/copilot-integration/dependency-base-reconciliation-20261105.json"
            ]["rows"][0]["manifest"].update(head_sha="f" * 40)),
            ("package base", lambda docs: docs[
                "development/copilot-integration/dependency-base-reconciliation-20261105.json"
            ]["rows"][0]["manifest"].update(base_sha="f" * 40)),
            ("package base ref", lambda docs: docs[
                "development/copilot-integration/dependency-base-reconciliation-20261105.json"
            ]["rows"][0]["manifest"].update(base_ref="invented")),
            ("package blocker", lambda docs: docs[
                "development/copilot-integration/dependency-base-reconciliation-20261105.json"
            ]["rows"][0].update(blocker_id="B044")),
            ("package PR", lambda docs: docs[
                "development/copilot-integration/dependency-base-reconciliation-20261105.json"
            ]["rows"][0].update(pr_number=999)),
            ("package workflow", lambda docs: docs[
                "tests/fixtures/copilot-integration-readiness/workflow_id_reconciliation_20261104.json"
            ]["rows"][next(
                index for index, row in enumerate(docs[
                    "tests/fixtures/copilot-integration-readiness/workflow_id_reconciliation_20261104.json"
                ]["rows"]) if row["pr"] == 10
            )].update(workflow_id=999999)),
            ("missing package workflow", lambda docs: docs[
                "tests/fixtures/copilot-integration-readiness/workflow_id_reconciliation_20261104.json"
            ]["rows"][next(
                index for index, row in enumerate(docs[
                    "tests/fixtures/copilot-integration-readiness/workflow_id_reconciliation_20261104.json"
                ]["rows"]) if row["pr"] == 10
            )].pop("workflow_id")),
        )
        for name, mutate in mutations:
            fixture, index, manifest, triage, documents, hashes = self._package_linkage_inputs()
            with self.subTest(mutation=name):
                mutate(documents)
                report = closure_package_linkage_report(
                    fixture, index, manifest, triage, documents, hashes
                )
                self.assertEqual(report["evidence_validation"], "BLOCKED")
                self.assertTrue(report["findings"])

    def test_package_linkage_rejects_duplicate_missing_hash_and_resolution(self):
        fixture, index, manifest, triage, documents, hashes = self._package_linkage_inputs()
        mutations = (
            ("duplicate", lambda value: value["rows"].append(copy.deepcopy(value["rows"][0]))),
            ("missing", lambda value: value["rows"].pop()),
            ("fabricated source hash", lambda value: value["source_hashes"].update({
                "development/copilot-integration/manifest.json": "0" * 64
            })),
            ("fabricated resolution", lambda value: value["rows"][0].update(
                after_status="RESOLVED"
            )),
        )
        for name, mutate in mutations:
            altered = copy.deepcopy(fixture)
            with self.subTest(mutation=name):
                mutate(altered)
                report = closure_package_linkage_report(
                    altered, index, manifest, triage, documents, hashes
                )
                self.assertEqual(report["evidence_validation"], "BLOCKED")
                self.assertTrue(report["findings"])

    def test_package_linkage_cli_is_offline_and_stays_blocked(self):
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["--package-linkage", str(PACKAGE_LINKAGE)])
        self.assertEqual(status, 1)
        report = json.loads(output.getvalue())
        self.assertEqual(report["evidence_validation"], "VALID")
        self.assertEqual(report["phase1_gate"], "FAIL_INCOMPLETE")
        self.assertEqual(report["selected_blocked_count"], 9)

    def _action_closure_inputs(self):
        fixture = json.loads(ACTION_CLOSURE.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        triage = json.loads(BLOCKER_TRIAGE.read_text(encoding="utf-8"))
        receipt_path = (
            "tests/fixtures/copilot-integration-readiness/"
            "workflow_id_reconciliation_20261104.json"
        )
        receipts = json.loads((MANIFEST.parents[2] / receipt_path).read_text(encoding="utf-8"))
        paths = (
            "development/copilot-integration/manifest.json",
            "development/copilot-integration/blocker-triage-20261104.json",
            "development/copilot-integration/closure-index-20261105.json",
            receipt_path,
        )
        hashes = {
            path: hashlib.sha256((MANIFEST.parents[2] / path).read_bytes()).hexdigest()
            for path in paths
        }
        return fixture, manifest, triage, receipts, hashes

    def test_action_closure_reclassifies_only_verified_ids_and_keeps_both_blocked(self):
        fixture, manifest, triage, receipts, hashes = self._action_closure_inputs()
        report = blocker_action_closure_report(
            fixture, manifest, triage, receipts, hashes
        )
        self.assertEqual(report["status"], "UNVERIFIED")
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["selected_blocker_count"], 2)
        self.assertEqual(report["selected_resolved_count"], 0)
        self.assertEqual(report["selected_blocked_count"], 2)
        self.assertEqual(report["phase1_gate"], "FAIL_INCOMPLETE")
        self.assertEqual(report["independent_approvals"], 0)
        self.assertEqual([row["blocker_id"] for row in report["rows"]], ["B043", "B044"])
        self.assertTrue(all(
            row["before_fingerprint_sha256"]
            and row["current_evidence_fingerprint_sha256"]
            and row["after_fingerprint_sha256"]
            for row in report["rows"]
        ))
        self.assertEqual(report["validation_gate"]["repair_validation"], "UNVERIFIED")
        self.assertFalse(report["validation_gate"]["push_event_configured"])

    def test_action_closure_rejects_stale_or_unauthorized_success_provenance(self):
        fixture, manifest, triage, receipts, hashes = self._action_closure_inputs()
        mutations = (
            ("missing ID", lambda value: value["rows"].pop(),
             "scope must contain exactly B043 and B044"),
            ("duplicate ID", lambda value: value["rows"].append(copy.deepcopy(value["rows"][0])),
             "scope must contain exactly B043 and B044"),
            ("wrong current head", lambda value: value["rows"][0]["current_run"].update(
                head_sha="f" * 40
            ), "not an exact-head action_required zero-job observation"),
            ("stale run attempt", lambda value: value["rows"][0]["current_run"].update(
                attempt=0
            ), "not an exact-head action_required zero-job observation"),
            ("missing required event", lambda value: value["rows"][1]["current_run"].update(
                event="push"
            ), "not an exact-head action_required zero-job observation"),
            ("invented run identity", lambda value: value["rows"][1]["current_run"].update(
                run_id=123
            ), "not an exact-head action_required zero-job observation"),
            ("nonzero jobs", lambda value: value["rows"][0]["current_run"].update(
                job_count=1, job_ids=[999]
            ), "not an exact-head action_required zero-job observation"),
            ("fabricated run base", lambda value: value["rows"][0]["current_run"].update(
                reported_run_base_sha="de2a775184d69411016ff683a8075af72ef4a58d"
            ), "not an exact-head action_required zero-job observation"),
            ("unauthorized pass", lambda value: value["rows"][0]["after"].update(
                status="READY", resolved=True
            ), "after-disposition clears or misstates"),
            ("fake exact-head PR CI", lambda value: value["validation_gate"].update(
                pr_conclusion="success", pr_job_count=1
            ), "validation gate is missing, stale, or falsely green"),
            ("fake push coverage", lambda value: value["validation_gate"].update(
                push_event_configured=True, push_event_coverage="passed"
            ), "validation gate is missing, stale, or falsely green"),
            ("changed source hash", lambda value: value["source_hashes"].update({
                "development/copilot-integration/manifest.json": "0" * 64
            }), "source hash mismatch"),
        )
        for name, mutate, expected in mutations:
            altered = copy.deepcopy(fixture)
            with self.subTest(mutation=name):
                mutate(altered)
                report = blocker_action_closure_report(
                    altered, manifest, triage, receipts, hashes
                )
                self.assertEqual(report["status"], "BLOCKED")
                self.assertTrue(any(expected in finding for finding in report["findings"]))

    def test_action_closure_cli_stays_unverified_until_pr_and_push_ci_execute(self):
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["--action-closure", str(ACTION_CLOSURE)])
        self.assertEqual(status, 1)
        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "UNVERIFIED")
        self.assertEqual(report["selected_blocked_count"], 2)
        self.assertEqual(report["validation_gate"]["pr_conclusion"], "action_required")
        self.assertEqual(report["validation_gate"]["pr_job_count"], 0)

    def _workflow_id_correction_inputs(self):
        fixture = json.loads(WORKFLOW_ID_CORRECTION.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        triage = json.loads(BLOCKER_TRIAGE.read_text(encoding="utf-8"))
        receipt_path = (
            "tests/fixtures/copilot-integration-readiness/"
            "workflow_id_reconciliation_20261104.json"
        )
        receipts = json.loads((MANIFEST.parents[2] / receipt_path).read_text(encoding="utf-8"))
        paths = (
            "development/copilot-integration/manifest.json",
            "development/copilot-integration/blocker-triage-20261104.json",
            "development/copilot-integration/closure-index-20261105.json",
            receipt_path,
        )
        hashes = {
            path: hashlib.sha256((MANIFEST.parents[2] / path).read_bytes()).hexdigest()
            for path in paths
        }
        return fixture, manifest, triage, receipts, hashes

    def test_selected_workflow_id_corrections_verify_provenance_but_stay_blocked(self):
        fixture, manifest, triage, receipts, hashes = self._workflow_id_correction_inputs()
        report = workflow_id_correction_report(
            fixture, manifest, triage, receipts, hashes
        )
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["evidence_validation"], "VALID")
        self.assertEqual(report["findings"], [])
        self.assertEqual(
            [row["blocker_id"] for row in report["rows"]],
            ["B004", "B006", "B007", "B009", "B011"],
        )
        self.assertEqual(report["workflow_id_dimension_corrected_count"], 5)
        self.assertEqual(report["selected_resolved_count"], 0)
        self.assertEqual(report["selected_blocked_count"], 5)
        self.assertEqual(report["phase1_gate"], "FAIL_INCOMPLETE")
        self.assertEqual(report["independent_approvals"], 0)
        self.assertTrue(all(
            row["before_fingerprint_sha256"]
            and row["current_evidence_fingerprint_sha256"]
            and row["after_fingerprint_sha256"]
            and row["status"] == "BLOCKED"
            and row["after"]["run_time_base_provenance"] == "unavailable"
            and row["after"]["resolved"] is False
            for row in report["rows"]
        ))

    def test_workflow_id_correction_rejects_malformed_or_fabricated_evidence(self):
        fixture, manifest, triage, receipts, hashes = self._workflow_id_correction_inputs()
        mutations = (
            ("missing row", lambda value: value["rows"].pop(),
             "scope must contain B004/B006/B007/B009/B011"),
            ("duplicate row", lambda value: value["rows"].append(copy.deepcopy(value["rows"][0])),
             "scope must contain B004/B006/B007/B009/B011"),
            ("missing before disposition", lambda value: value["rows"][0].pop("before"),
             "before-disposition differs from immutable blocker identity"),
            ("invented workflow ID", lambda value: value["rows"][0]["workflow"].update(id=999),
             "not corroborated by manifest and pinned receipt"),
            ("wrong event", lambda value: value["rows"][0]["run"].update(event="push"),
             "not the recorded successful exact-head pull_request attempt"),
            ("wrong head", lambda value: value["rows"][0]["run"].update(tested_sha="f" * 40),
             "not the recorded successful exact-head pull_request attempt"),
            ("invented run ID", lambda value: value["rows"][0]["run"].update(id=999),
             "not the recorded successful exact-head pull_request attempt"),
            ("wrong PR association", lambda value: value["rows"][0]["run"].update(
                pull_request_number=4
            ), "not the recorded successful exact-head pull_request attempt"),
            ("wrong attempt", lambda value: value["rows"][0]["run"].update(attempt=2),
             "not the recorded successful exact-head pull_request attempt"),
            ("wrong current base", lambda value: value["rows"][0]["current_pr"].update(
                base_sha="b" * 40
            ), "current PR metadata differs from manifest or pinned receipt"),
            ("zero jobs", lambda value: value["rows"][0]["job"].update(id=None),
             "job/step coverage is absent"),
            ("incomplete steps", lambda value: value["rows"][0]["job"].update(
                successful_step_count=0
            ), "job/step coverage is absent"),
            ("fabricated run-time base", lambda value: value["rows"][0]["run"].update(
                reported_base_sha="b" * 40
            ), "not the recorded successful exact-head pull_request attempt"),
            ("false resolution", lambda value: value["rows"][0]["after"].update(
                status="READY", resolved=True
            ), "after-disposition clears or misstates"),
            ("changed source hash", lambda value: value["source_hashes"].update({
                "development/copilot-integration/manifest.json": "0" * 64
            }), "source hash mismatch"),
        )
        for name, mutate, expected in mutations:
            altered = copy.deepcopy(fixture)
            with self.subTest(mutation=name):
                mutate(altered)
                report = workflow_id_correction_report(
                    altered, manifest, triage, receipts, hashes
                )
                self.assertEqual(report["status"], "BLOCKED")
                self.assertTrue(any(expected in finding for finding in report["findings"]))

    def test_workflow_id_correction_cli_reports_valid_evidence_as_blocked(self):
        output = io.StringIO()
        with redirect_stdout(output):
            status = main([
                "--workflow-id-correction",
                str(WORKFLOW_ID_CORRECTION),
            ])
        self.assertEqual(status, 1)
        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["evidence_validation"], "VALID")
        self.assertEqual(report["selected_blocked_count"], 5)


if __name__ == "__main__":
    unittest.main()
