import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import phase1_arm_receipt_status as status
import phase1_copilot_receipts as receipt_validator


class API:
    repository = "xbaconator9000x/XGBA-ROM-Expansion"

    def __init__(self, runs, jobs, pull_head="a" * 40):
        self.runs = runs
        self.jobs = jobs
        self.pull_head = pull_head

    def paginate(self, url, *, result_key=None):
        if "/actions/runs?" in url:
            return self.runs
        if url.endswith("/jobs"):
            run_id = int(url.split("/runs/")[1].split("/")[0])
            return self.jobs.get(run_id, [])
        raise AssertionError("Unexpected pagination URL: " + url)

    def __call__(self, url):
        if url.endswith("/pulls/8"):
            return {"head": {"sha": self.pull_head}}
        raise AssertionError("Unexpected API URL: " + url)


def run(run_id, *, name, path, event, sha="a" * 40, conclusion="success",
        job_name="census"):
    steps = [
        {"number": 1, "name": "Verify pinned mGBA ARM decode/emit review evidence",
         "status": "completed", "conclusion": "success"},
        {"number": 2, "name": "Evaluate Phase 1 semantic gate (incomplete is expected until signed review)",
         "status": "completed", "conclusion": "success"},
    ]
    result = {
        "id": run_id, "head_sha": sha, "name": name, "path": path, "event": event,
        "status": "completed", "conclusion": conclusion, "run_attempt": 1,
        "referenced_workflows": [{
            "path": "xbaconator9000x/XGBA-ROM-Expansion/"
                    ".github/workflows/phase1-census.yml@sha"
        }],
        "pull_requests": [8] if event == "pull_request" else [],
    }
    return result, {"id": 1000 + run_id, "name": job_name,
                    "conclusion": conclusion, "steps": steps}


def valid_api():
    pr, pr_job = run(
        1, name=status.PR_WORKFLOW_NAME, path=".github/workflows/phase1-pr-checks.yml",
        event="pull_request", job_name="census / census",
    )
    push, push_job = run(
        2, name="Phase 1 pinned source census and review dossiers",
        path=status.CENSUS_WORKFLOW_PATH, event="push",
    )
    return API([pr, push], {1: [pr_job], 2: [push_job]})


class ArmReceiptStatusTests(unittest.TestCase):
    def test_exact_head_pull_and_push_runs_require_successful_census_jobs_and_steps(self):
        result = status.verify_exact_head_ci(
            valid_api(), "a" * 40, "xbaconator9000x/XGBA-ROM-Expansion", 8
        )
        self.assertTrue(result["verified"])
        self.assertEqual(result["runs"]["pull_request"]["job_id"], 1001)
        self.assertEqual(result["runs"]["push_census"]["job_id"], 1002)
        self.assertEqual(len(result["runs"]["push_census"]["steps"]), 2)

    def test_stale_head_is_rejected(self):
        api = valid_api()
        api.runs[1]["head_sha"] = "b" * 40
        result = status.verify_exact_head_ci(
            api, "a" * 40, "xbaconator9000x/XGBA-ROM-Expansion", 8
        )
        self.assertFalse(result["verified"])
        self.assertTrue(any("push_census" in item for item in result["blockers"]))

    def test_wrong_event_is_rejected(self):
        api = valid_api()
        api.runs[1]["event"] = "workflow_dispatch"
        result = status.verify_exact_head_ci(
            api, "a" * 40, "xbaconator9000x/XGBA-ROM-Expansion", 8
        )
        self.assertFalse(result["verified"])

    def test_failed_run_is_rejected(self):
        api = valid_api()
        api.runs[1]["conclusion"] = "failure"
        api.jobs[2][0]["conclusion"] = "failure"
        result = status.verify_exact_head_ci(
            api, "a" * 40, "xbaconator9000x/XGBA-ROM-Expansion", 8
        )
        self.assertFalse(result["verified"])

    def test_missing_census_job_is_rejected(self):
        api = valid_api()
        api.jobs[2][0]["name"] = "other"
        result = status.verify_exact_head_ci(
            api, "a" * 40, "xbaconator9000x/XGBA-ROM-Expansion", 8
        )
        self.assertFalse(result["verified"])

    def test_missing_required_step_is_rejected(self):
        api = valid_api()
        api.jobs[1][0]["steps"] = api.jobs[1][0]["steps"][:1]
        result = status.verify_exact_head_ci(
            api, "a" * 40, "xbaconator9000x/XGBA-ROM-Expansion", 8
        )
        self.assertFalse(result["verified"])

    def test_pr_workflow_must_reference_the_census(self):
        api = valid_api()
        api.runs[0]["referenced_workflows"] = []
        result = status.verify_exact_head_ci(
            api, "a" * 40, "xbaconator9000x/XGBA-ROM-Expansion", 8
        )
        self.assertFalse(result["verified"])

    def test_pull_request_head_must_match_expected_head(self):
        api = valid_api()
        api.pull_head = "b" * 40
        result = status.verify_exact_head_ci(
            api, "a" * 40, "xbaconator9000x/XGBA-ROM-Expansion", 8
        )
        self.assertFalse(result["verified"])

    def test_target_receipt_map_is_immutable_and_has_three_distinct_sources(self):
        self.assertEqual(len(status.TARGETS), 3)
        self.assertEqual(len({item["path"] for item in status.TARGETS.values()}), 3)
        for digest, expected in status.TARGETS.items():
            self.assertEqual(len(digest), 64)
            self.assertEqual(len(expected["blob"]), 40)
            self.assertEqual(len(expected["source_sha256"]), 64)
            self.assertEqual(len(expected["dossier_sha256"]), 64)

    def test_legacy_approved_is_never_mapped_to_gate_contribution(self):
        review = {"decision": "APPROVED"}
        blockers = status._nonapproving_policy_blockers(review)
        self.assertTrue(any("gate-affecting" in item for item in blockers))
        decision = status._nonapproving_status(review)
        self.assertEqual(decision["status"], "NEEDS_EVIDENCE")
        self.assertEqual(decision["gate_contribution"], 0)
        self.assertFalse(decision["external_human_approval"])
        self.assertEqual(status.TARGETS[
            "68d40e2e26b63751fd5ebe5b2c6d8088d1ee4435174946782d87c24dc2eb7361"
        ]["path"], "include/mgba/internal/arm/decoder-inlines.h")
        self.assertTrue(status.OUTSTANDING_CLOSURE_OBJECTIONS)

    def test_non_source_verified_evidence_claims_are_blocked(self):
        review = {
            "decision": "COPILOT_REVIEWED",
            "evidence_distinctions": {
                "compiled_native": {"status": "VERIFIED"},
                "runtime_gameplay": {"status": "NOT_RUN"},
            },
        }
        self.assertIn(
            "Unsupported non-source VERIFIED claim: compiled_native",
            status._nonapproving_policy_blockers(review),
        )

    def test_armv4t_oracle_claim_requires_independent_evidence(self):
        review = {
            "decision": "COPILOT_REVIEWED",
            "armv4t_oracle": {"status": "VERIFIED"},
        }
        self.assertIn(
            "Unsupported ARMv4T oracle verification claim",
            status._nonapproving_policy_blockers(review),
        )

    def test_standalone_attribution_marker_requires_exactly_one_unquoted_block(self):
        markers = (
            receipt_validator.RECEIPT_MARKER + "1" * 64,
            receipt_validator.INTRO_COMMIT_MARKER + "2" * 40,
            receipt_validator.EVIDENCE_COMMIT_MARKER + "3" * 40,
            receipt_validator.DECISION_MARKER,
        )
        block = "\n".join((
            receipt_validator.ATTESTATION_BEGIN, *markers,
            receipt_validator.ATTESTATION_END,
        ))
        self.assertTrue(receipt_validator._attestation_section_is_valid(block, markers))
        self.assertFalse(receipt_validator._attestation_section_is_valid(block + "\n" + block, markers))
        self.assertFalse(receipt_validator._attestation_section_is_valid(
            "\n".join("> " + line for line in block.splitlines()), markers
        ))

    def test_missing_standalone_attribution_is_not_synthesized(self):
        markers = (
            receipt_validator.RECEIPT_MARKER + "1" * 64,
            receipt_validator.INTRO_COMMIT_MARKER + "2" * 40,
            receipt_validator.EVIDENCE_COMMIT_MARKER + "3" * 40,
            receipt_validator.DECISION_MARKER,
        )
        self.assertFalse(receipt_validator._attestation_section_is_valid("", markers))
        self.assertFalse(receipt_validator._attestation_section_is_valid(
            "\n".join((
                receipt_validator.ATTESTATION_BEGIN,
                markers[0],
                markers[1],
                markers[3],
                receipt_validator.ATTESTATION_END,
            )), markers,
        ))

    def test_status_checker_requires_conversation_comment_attribution(self):
        with self.assertRaisesRegex(ValueError, "conversation-comment attribution"):
            status._validate_standalone_attribution(
                {"attestation": {"mode": "github_review"}},
                "1" * 64,
                ".",
                valid_api(),
            )

    def test_source_identity_mutation_is_rejected(self):
        digest = "68d40e2e26b63751fd5ebe5b2c6d8088d1ee4435174946782d87c24dc2eb7361"
        expected = status.TARGETS[digest]
        receipt = {
            "source": {
                "repository": "mgba-emu/mgba",
                "path": expected["path"],
                "git_blob_sha1": "0" * 40,
                "source_sha256": expected["source_sha256"],
            },
            "target": {
                "receipt_path": status.RECEIPT_PATH,
                "evidence_commit": "e2cae6f1c073be4ee04691a57915adf740868279",
            },
            "machine_dossier_sha256": expected["dossier_sha256"],
            "attestation": {},
        }
        row = {"blob_sha": expected["blob"]}
        dossier = {"provenance": {"source_content_sha256": expected["source_sha256"]}}
        problems = status._receipt_identity_problems(
            receipt, receipt_validator.receipt_digest(receipt), expected, row, dossier
        )
        self.assertIn("Receipt identity or immutable lifecycle binding mismatch", problems)

    def test_dossier_row_mutation_is_rejected(self):
        digest = "a9a92f196fb14985d9d7dbe36e647ed5bc17ab67c74c9426c0b7c2f92dfe3bf8"
        expected = status.TARGETS[digest]
        receipt = {
            "source": {
                "repository": "mgba-emu/mgba",
                "path": expected["path"],
                "git_blob_sha1": expected["blob"],
                "source_sha256": expected["source_sha256"],
            },
            "target": {
                "receipt_path": status.RECEIPT_PATH,
                "evidence_commit": "e2cae6f1c073be4ee04691a57915adf740868279",
            },
            "machine_dossier_sha256": expected["dossier_sha256"],
            "attestation": {},
        }
        row = {"blob_sha": expected["blob"]}
        dossier = {"provenance": {"source_content_sha256": expected["source_sha256"]}}
        problems = status._receipt_identity_problems(
            receipt, receipt_validator.receipt_digest(receipt), expected, row, dossier
        )
        self.assertIn("Original dossier row SHA-256 mismatch", problems)

    def test_status_policy_is_always_non_approving(self):
        report_schema = status.SCHEMA
        self.assertEqual(report_schema, "xgba.phase1.arm_receipt_status.v1")
        self.assertEqual(status.RECEIPT_PATH,
                         "docs/phase1-review-readiness/copilot-semantic-review-receipts.jsonl")
        self.assertEqual(status.VALIDATOR_RUN_BLOCKER,
                         "Exact-head validation run is missing or unsuccessful")


if __name__ == "__main__":
    unittest.main()
