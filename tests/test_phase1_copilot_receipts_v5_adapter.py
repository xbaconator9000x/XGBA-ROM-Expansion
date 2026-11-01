import copy
import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import phase1_copilot_receipts_v5_adapter as adapter


class FixtureAPI:
    def __init__(self):
        self.runs = []
        self.jobs = {}

    def paginate(self, url, *, result_key=None):
        if urlparse(url).path.endswith("/actions/runs"):
            return self.runs
        return []

    def __call__(self, url):
        parts = urlparse(url).path.split("/")
        if "jobs" in parts:
            run_id = int(parts[parts.index("runs") + 1])
            jobs = copy.deepcopy(self.jobs[run_id])
            return {"total_count": len(jobs), "jobs": jobs}
        raise AssertionError(f"Unexpected API request: {url}")


def fixture_run(event, run_id, *, conclusion="success", status="completed", head=adapter.PR8_HEAD):
    run = {
        "id": run_id,
        "run_attempt": 1,
        "event": event,
        "head_sha": head,
        "path": adapter.v4.PR_WORKFLOW if event == "pull_request" else adapter.v4.CENSUS_WORKFLOW,
        "status": status,
        "conclusion": conclusion,
        "created_at": "2026-11-01T12:00:00Z",
        "run_started_at": "2026-11-01T12:01:00Z",
        "pull_requests": [],
    }
    if event == "pull_request":
        run.update({
            "name": adapter.v4.PR_WORKFLOW_NAME,
            "pull_requests": [{"number": 8, "head": {"sha": head}}],
            "referenced_workflows": [{
                "path": f"{adapter.v4.OWNER_REPOSITORY}/{adapter.v4.CENSUS_WORKFLOW}@refs/pull/8/merge",
            }],
        })
    return run


def fixture_job(job_id, *, conclusion="success", executed=True):
    return {
        "id": job_id,
        "status": "completed",
        "conclusion": conclusion,
        "steps": [{
            "status": "completed" if executed else "queued",
            "conclusion": "success" if executed else None,
            "started_at": "2026-11-01T12:02:00Z" if executed else None,
            "completed_at": "2026-11-01T12:03:00Z" if executed else None,
        }],
    }


def fixture_receipts():
    original = adapter.EXPECTED_RECEIPTS
    records = []
    expected = {}
    for index, key in enumerate(adapter.EXPECTED_ORDER):
        entry = {
            "schema": "xgba.phase1.copilot_semantic_review_receipt.v4",
            "source": {
                "repository": key[0],
                "path": key[1],
                "revision": "fd9dc5c2cbf234365068855851107e762fc6211b",
                "git_blob_sha1": f"{index + 1:040x}",
                "source_sha256": f"{index + 1:064x}",
            },
            "machine_dossier_sha256": f"{index + 5:064x}",
            "target": {
                "repository": adapter.v4.OWNER_REPOSITORY,
                "pull_number": 8,
                "receipt_path": adapter.RECEIPT_PATH,
                "evidence_commit": f"{index + 9:040x}",
            },
            "review": {
                "decision": "APPROVED",
                "reviewer_classification": (
                    "COPILOT_REVIEWED/PASSED (user-authorized source review; not human or external approval)"
                ),
                "whole_file_coverage": {
                    "scope": "WHOLE_FILE",
                    "source_sha256": f"{index + 1:064x}",
                    "source_lines": 1,
                    "reviewed_line_ranges": [[1, 1]],
                },
                "dependency_closure": {
                    "status": "COMPLETE",
                    "dependencies": [{"repository": "synthetic/source"}],
                    "rationale": "Synthetic fixture has an explicit, bounded dependency statement.",
                },
                "licensing": {
                    "status": "CLEARED",
                    "evidence": [{"fixture": True}],
                    "rationale": "Clearance is source-file scoped only; combined distribution is NOT CLEARED.",
                },
                "objections": [{
                    "status": "RESOLVED",
                    "resolution": "Synthetic fixture records an explicit scoped resolution.",
                }],
                "evidence_distinctions": {
                    "source": {"status": "VERIFIED", "source_sha256": f"{index + 1:064x}"},
                    "synthetic": {"status": "NOT_CLAIMED"},
                    "compiled_native": {"status": "NOT_CLAIMED"},
                    "runtime_gameplay": {"status": "NOT_CLAIMED"},
                    "save_restart": {"status": "NOT_APPLICABLE"},
                    "physical_flash": {"status": "NOT_APPLICABLE"},
                },
            },
        }
        digest = adapter.v4.receipt_digest(entry)
        entry["attestation"] = {"mode": "conversation_comment", "receipt_sha256": digest}
        expected[key] = {
            "blob": entry["source"]["git_blob_sha1"],
            "source_sha256": entry["source"]["source_sha256"],
            "dossier_sha256": entry["machine_dossier_sha256"],
            "receipt_sha256": digest,
            "evidence_commit": entry["target"]["evidence_commit"],
            "receipt_commit": adapter.EXPECTED_RECEIPTS[key]["receipt_commit"],
        }
        records.append(entry)
    adapter.EXPECTED_RECEIPTS = expected
    return original, records


class V5AdapterTests(unittest.TestCase):
    def setUp(self):
        self.original_expected, self.receipts = fixture_receipts()

    def tearDown(self):
        adapter.EXPECTED_RECEIPTS = self.original_expected

    def test_exact_ordered_synthetic_register_passes_without_minting_a_review(self):
        self.assertTrue(adapter.validate_receipt_inventory(self.receipts))
        self.assertEqual(adapter.PR8_HEAD, "3ee4b1117f2976b6ea41098f5456634da18a50f8")

    def test_reordered_unknown_duplicate_and_missing_records_fail_closed(self):
        variants = [
            list(reversed(self.receipts)),
            self.receipts[:-1] + [copy.deepcopy(self.receipts[0])],
            self.receipts[:-1],
            self.receipts + [copy.deepcopy(self.receipts[-1])],
        ]
        for records in variants:
            with self.subTest(count=len(records)):
                with self.assertRaises(ValueError):
                    adapter.validate_receipt_inventory(records)

    def test_tampered_source_dossier_target_and_body_digest_fail_closed(self):
        for path, value in (
            (("source", "source_sha256"), "0" * 64),
            (("machine_dossier_sha256",), "0" * 64),
            (("target", "evidence_commit"), "0" * 40),
            (("review", "semantic_rationale"), "tampered"),
        ):
            records = copy.deepcopy(self.receipts)
            target = records[3]
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    adapter.validate_receipt_inventory(records)

    def test_missing_original_file_and_wrong_worktree_head_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "exact pinned head"):
            adapter.verify_pinned_worktree(Path(__file__).resolve().parents[1])
        from tempfile import TemporaryDirectory

        old_git = adapter.v4._git
        adapter.v4._git = lambda _root, *args: (
            adapter.PR8_HEAD if args == ("rev-parse", "HEAD") else adapter.EXPECTED_BLOBS[args[1].split(":", 1)[1]]
        )
        try:
            with TemporaryDirectory() as root:
                with self.assertRaisesRegex(ValueError, "missing or unsafe"):
                    adapter.verify_pinned_worktree(root)
        finally:
            adapter.v4._git = old_git

    def test_incomplete_whole_file_ranges_fail_closed(self):
        receipt = copy.deepcopy(self.receipts[3])
        receipt["review"]["whole_file_coverage"]["reviewed_line_ranges"] = [[2, 2]]
        with self.assertRaisesRegex(ValueError, "coverage"):
            adapter.validate_semantic_scope(receipt)

    def test_unresolved_objection_and_unsupported_runtime_claim_fail_closed(self):
        receipt = copy.deepcopy(self.receipts[3])
        receipt["review"]["objections"][0]["status"] = "OPEN"
        with self.assertRaisesRegex(ValueError, "objection"):
            adapter.validate_semantic_scope(receipt)
        receipt = copy.deepcopy(self.receipts[3])
        receipt["review"]["evidence_distinctions"]["runtime_gameplay"]["status"] = "VERIFIED"
        with self.assertRaisesRegex(ValueError, "runtime_gameplay"):
            adapter.validate_semantic_scope(receipt)

    def test_incomplete_dependency_or_unassessed_licensing_fails_closed(self):
        receipt = copy.deepcopy(self.receipts[3])
        receipt["review"]["dependency_closure"]["status"] = "INCOMPLETE"
        with self.assertRaisesRegex(ValueError, "Dependency closure"):
            adapter.validate_semantic_scope(receipt)
        receipt = copy.deepcopy(self.receipts[3])
        receipt["review"]["licensing"]["rationale"] = "Distribution status unavailable."
        with self.assertRaisesRegex(ValueError, "Licensing"):
            adapter.validate_semantic_scope(receipt)

    def test_exact_head_pr_and_push_runs_with_all_executed_steps_pass(self):
        api = FixtureAPI()
        api.runs = [fixture_run("pull_request", 11), fixture_run("push", 12)]
        api.jobs = {11: [fixture_job(101)], 12: [fixture_job(102)]}
        self.assertEqual(
            adapter.validate_exact_ci(api, not_before="2026-11-01T11:00:00Z"),
            {"pull_request": 1, "push": 1},
        )

    def test_action_required_missing_stale_zero_job_and_failed_step_runs_fail(self):
        api = FixtureAPI()
        api.runs = [
            fixture_run("pull_request", 11),
            fixture_run("push", 12, status="action_required"),
        ]
        api.jobs = {11: [fixture_job(101)], 12: [fixture_job(102)]}
        with self.assertRaisesRegex(ValueError, "push Actions run is not successful"):
            adapter.validate_exact_ci(api)
        api.runs = [fixture_run("pull_request", 11)]
        with self.assertRaisesRegex(ValueError, "push Actions run is missing"):
            adapter.validate_exact_ci(api)
        api.runs = [fixture_run("pull_request", 11, head="0" * 40), fixture_run("push", 12)]
        with self.assertRaisesRegex(ValueError, "pull_request Actions run is missing"):
            adapter.validate_exact_ci(api)
        api.runs = [fixture_run("pull_request", 11), fixture_run("push", 12)]
        api.jobs = {11: [], 12: [fixture_job(102)]}
        with self.assertRaisesRegex(ValueError, "zero or incomplete"):
            adapter.validate_exact_ci(api)
        api.jobs = {11: [fixture_job(101, executed=False)], 12: [fixture_job(102)]}
        with self.assertRaisesRegex(ValueError, "failed, skipped, or non-executed"):
            adapter.validate_exact_ci(api)

    def test_newer_failed_run_and_pre_receipt_run_fail_closed(self):
        api = FixtureAPI()
        older_push = fixture_run("push", 12)
        newer_push = fixture_run("push", 13, status="action_required", conclusion="action_required")
        newer_push["created_at"] = "2026-11-01T13:00:00Z"
        api.runs = [fixture_run("pull_request", 11), older_push, newer_push]
        api.jobs = {11: [fixture_job(101)], 12: [fixture_job(102)], 13: [fixture_job(103)]}
        with self.assertRaisesRegex(ValueError, "not successful"):
            adapter.validate_exact_ci(api)
        api.runs = [fixture_run("pull_request", 11), fixture_run("push", 12)]
        api.runs[0]["run_started_at"] = "2026-10-31T23:59:59Z"
        with self.assertRaisesRegex(ValueError, "predates the final receipt"):
            adapter.validate_exact_ci(api, not_before="2026-11-01T00:00:00Z")

    def test_bot_spoof_duplicate_and_missing_fourth_attestation_fail(self):
        receipt = self.receipts[3]
        expected = adapter.EXPECTED_RECEIPTS[(receipt["source"]["repository"], receipt["source"]["path"])]
        markers = (
            "receipt:" + expected["receipt_sha256"],
            "intro:" + expected["receipt_commit"],
            "evidence:" + expected["evidence_commit"],
            "decision:approved",
        )

        class FakeVerifier:
            RECEIPT_MARKER = "receipt:"
            INTRO_COMMIT_MARKER = "intro:"
            EVIDENCE_COMMIT_MARKER = "evidence:"
            DECISION_MARKER = "decision:approved"

            @staticmethod
            def _attestation_section_is_valid(body, required):
                active = [
                    line for line in body.splitlines()
                    if not line.lstrip().startswith(">") and not line.startswith("```")
                ]
                return all(marker in active for marker in required)

        class CommentAPI:
            def __init__(self, comments):
                self.comments = comments

            def paginate(self, _url):
                return self.comments

        def comment(user=None, body=None, id=900):
            return {
                "id": id,
                "user": user or {
                    "login": "Copilot",
                    "id": adapter.v4.BOT_ID,
                    "node_id": adapter.v4.BOT_NODE_ID,
                    "type": "Bot",
                },
                "issue_url": f"{adapter.v4.API_ROOT}/issues/8",
                "html_url": f"https://github.com/{adapter.v4.OWNER_REPOSITORY}/pull/8#issuecomment-{id}",
                "body": body if body is not None else "\n".join(markers),
                "created_at": "2026-11-02T00:00:00Z",
            }

        old_git = adapter.v4._git
        adapter.v4._git = lambda *_args: "2026-11-01T00:00:00+00:00"
        try:
            good = comment()
            self.assertIs(
                adapter.verify_expected_comment(receipt, FakeVerifier, CommentAPI([good]), Path("/unused")),
                good,
            )
            cases = [
                [comment(user={"login": "Copilot", "id": 0, "node_id": adapter.v4.BOT_NODE_ID, "type": "Bot"})],
                [comment(body="\n".join(markers).replace(expected["receipt_sha256"], "0" * 64))],
                [comment(body="> " + "\n> ".join(markers))],
                [good, copy.deepcopy(good)],
                [],
            ]
            for comments in cases:
                with self.subTest(comments=comments):
                    with self.assertRaises(ValueError):
                        adapter.verify_expected_comment(
                            receipt, FakeVerifier, CommentAPI(comments), Path("/unused")
                        )
            stale = comment()
            stale["created_at"] = "2026-10-31T00:00:00Z"
            with self.assertRaisesRegex(ValueError, "predates"):
                adapter.verify_expected_comment(
                    receipt, FakeVerifier, CommentAPI([stale]), Path("/unused")
                )
        finally:
            adapter.v4._git = old_git

    def test_boolean_actions_metadata_is_rejected(self):
        api = FixtureAPI()
        api.runs = [fixture_run("pull_request", 11), fixture_run("push", 12)]
        api.runs[0]["id"] = True
        api.jobs = {11: [fixture_job(101)], 12: [fixture_job(102)]}
        with self.assertRaisesRegex(ValueError, "invalid ID or attempt"):
            adapter.validate_exact_ci(api)


if __name__ == "__main__":
    unittest.main()
