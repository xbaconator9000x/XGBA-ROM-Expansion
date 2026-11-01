import copy
import hashlib
import sys
from tempfile import TemporaryDirectory
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import phase1_copilot_receipts_v4_adapter as v4
import phase1_copilot_receipts_v5_adapter as v5
import phase1_copilot_receipts_v6_adapter as adapter


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
        "path": v4.PR_WORKFLOW if event == "pull_request" else v4.CENSUS_WORKFLOW,
        "status": status,
        "conclusion": conclusion,
        "created_at": "2026-11-02T12:00:00Z",
        "run_started_at": "2026-11-02T12:01:00Z",
        "pull_requests": [],
    }
    if event == "pull_request":
        run.update({
            "name": v4.PR_WORKFLOW_NAME,
            "pull_requests": [{"number": 8, "head": {"sha": head}}],
            "referenced_workflows": [{
                "path": f"{v4.OWNER_REPOSITORY}/{v4.CENSUS_WORKFLOW}@refs/pull/8/merge",
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
            "started_at": "2026-11-02T12:02:00Z" if executed else None,
            "completed_at": "2026-11-02T12:03:00Z" if executed else None,
        }],
    }


def fixture_receipts():
    original = adapter.EXPECTED_RECEIPTS
    records = []
    expected = {}
    for index, key in enumerate(adapter.EXPECTED_ORDER):
        source_sha = f"{index + 1:064x}"
        entry = {
            "schema": "xgba.phase1.copilot_semantic_review_receipt.v4",
            "source": {
                "repository": key[0],
                "path": key[1],
                "revision": "fd9dc5c2cbf234365068855851107e762fc6211b",
                "git_blob_sha1": f"{index + 1:040x}",
                "source_sha256": source_sha,
            },
            "machine_dossier_sha256": f"{index + 5:064x}",
            "target": {
                "repository": v4.OWNER_REPOSITORY,
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
                    "source_sha256": source_sha,
                    "source_lines": 2,
                    "reviewed_line_ranges": [[1, 2]],
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
                    "source": {"status": "VERIFIED", "source_sha256": source_sha},
                    "synthetic": {"status": "NOT_CLAIMED"},
                    "compiled_native": {"status": "NOT_CLAIMED"},
                    "runtime_gameplay": {"status": "NOT_CLAIMED"},
                    "save_restart": {"status": "NOT_APPLICABLE"},
                    "physical_flash": {"status": "NOT_APPLICABLE"},
                },
            },
        }
        digest = v4.receipt_digest(entry)
        entry["attestation"] = {"mode": "conversation_comment", "receipt_sha256": digest}
        expected[key] = {
            "blob": entry["source"]["git_blob_sha1"],
            "source_sha256": source_sha,
            "dossier_sha256": entry["machine_dossier_sha256"],
            "receipt_sha256": digest,
            "evidence_commit": entry["target"]["evidence_commit"],
            "receipt_commit": original[key]["receipt_commit"],
        }
        records.append(entry)
    adapter.EXPECTED_RECEIPTS = expected
    return original, records


class V6AdapterTests(unittest.TestCase):
    def setUp(self):
        self.original_expected, self.receipts = fixture_receipts()

    def tearDown(self):
        adapter.EXPECTED_RECEIPTS = self.original_expected

    def test_exact_seven_ordered_synthetic_register_passes(self):
        self.assertTrue(adapter.validate_receipt_inventory(self.receipts))
        self.assertEqual(adapter.PR8_HEAD, "487da72f27dfc4e634cecc11b4dbdd596ec05e00")

    def test_v5_receipts_and_historical_register_prefix_are_preserved(self):
        self.assertEqual(adapter.EXPECTED_ORDER[:4], v5.EXPECTED_ORDER)
        for key in v5.EXPECTED_ORDER:
            self.assertEqual(self.original_expected[key], v5.EXPECTED_RECEIPTS[key])
        self.assertEqual(adapter.REGISTER_BLOB, "0c5b50003b89d346d04c86e52774c4e01e9d321b")
        self.assertEqual(adapter.EVIDENCE_COMMIT, "e2cae6f1c073be4ee04691a57915adf740868279")

    def test_reordered_duplicate_missing_and_extra_receipts_fail(self):
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

    def test_source_dossier_evidence_and_canonical_digest_tampering_fail(self):
        for path, value in (
            (("source", "git_blob_sha1"), "0" * 40),
            (("source", "source_sha256"), "0" * 64),
            (("machine_dossier_sha256",), "0" * 64),
            (("target", "evidence_commit"), "0" * 40),
            (("review", "semantic_rationale"), "tampered"),
        ):
            records = copy.deepcopy(self.receipts)
            target = records[4]
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(ValueError):
                adapter.validate_receipt_inventory(records)

    def test_whole_file_dependency_license_objection_and_claim_gates_fail_closed(self):
        mutations = (
            (("whole_file_coverage", "reviewed_line_ranges"), [[2, 2]], "coverage"),
            (("dependency_closure", "status"), "INCOMPLETE", "Dependency closure"),
            (("licensing", "rationale"), "Distribution status unavailable.", "Licensing"),
            (("objections", 0, "status"), "OPEN", "objection"),
            (("evidence_distinctions", "compiled_native", "status"), "VERIFIED", "compiled_native"),
            (("evidence_distinctions", "runtime_gameplay", "status"), "VERIFIED", "runtime_gameplay"),
        )
        for path, value, message in mutations:
            receipt = copy.deepcopy(self.receipts[4])
            target = receipt["review"]
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, message):
                adapter.validate_semantic_scope(receipt)

    def test_stale_worktree_head_fails_before_reading_any_files(self):
        old_git = v4._git
        v4._git = lambda *_args: "0" * 40
        try:
            with self.assertRaisesRegex(ValueError, "exact pinned head"):
                adapter.verify_pinned_worktree("/unused")
        finally:
            v4._git = old_git

    def test_substantive_evidence_authorship_rejects_copilot_and_accepts_distinct_owner(self):
        class CommitAPI:
            def __init__(self, author):
                self.author = author
                self.filename = None

            def __call__(self, url):
                if "/commits?path=" in url:
                    self.filename = parse_qs(urlparse(url).query)["path"][0]
                    return [{"sha": "a" * 40}]
                if url.endswith("/commits/" + "a" * 40):
                    return {
                        "sha": "a" * 40,
                        "files": [{"filename": self.filename}],
                        "author": self.author,
                        "committer": {"login": "xbaconator9000x", "id": 343442676},
                    }
                raise AssertionError(url)

        receipt = copy.deepcopy(self.receipts[4])
        receipt["target"]["evidence_commit"] = adapter.EVIDENCE_COMMIT
        receipt["review"]["authorship"] = {
            "dossier": {"path": "dossier.json", "sha256": "1" * 64},
            "substantive_evidence": [{"path": "evidence.md", "sha256": "2" * 64}],
        }
        files = {"dossier.json": b"dossier", "evidence.md": b"evidence"}
        receipt["review"]["authorship"]["dossier"]["sha256"] = hashlib.sha256(files["dossier.json"]).hexdigest()
        receipt["review"]["authorship"]["substantive_evidence"][0]["sha256"] = hashlib.sha256(files["evidence.md"]).hexdigest()
        old_git = v4._git
        old_check_output = adapter.subprocess.check_output
        with TemporaryDirectory() as root:
            for name, content in files.items():
                (Path(root) / name).write_bytes(content)

            def fake_git(_root, *args):
                if args[:2] == ("merge-base", "--is-ancestor"):
                    return ""
                raise AssertionError(args)

            def fake_check_output(args, **kwargs):
                if args[0:3] == ["git", "-C", str(Path(root).resolve())] and args[3] == "show":
                    return files[args[-1].split(":", 1)[1]]
                return old_check_output(args, **kwargs)

            v4._git = fake_git
            adapter.subprocess.check_output = fake_check_output
            try:
                owner = {"login": "xbaconator9000x", "id": 343442676}
                adapter.verify_non_copilot_evidence_authorship(receipt, CommitAPI(owner), root)
                for bot in (
                    {"login": "Copilot", "id": 198982749, "node_id": "BOT_kgDOC9w8XQ"},
                    {"login": "copilot-swe-agent[bot]", "id": 198982749},
                ):
                    with self.subTest(bot=bot), self.assertRaisesRegex(ValueError, "Copilot cannot review"):
                        adapter.verify_non_copilot_evidence_authorship(receipt, CommitAPI(bot), root)
            finally:
                v4._git = old_git
                adapter.subprocess.check_output = old_check_output

    def test_exact_head_pr_and_push_runs_need_executed_jobs_and_steps(self):
        api = FixtureAPI()
        api.runs = [fixture_run("pull_request", 11), fixture_run("push", 12)]
        api.jobs = {11: [fixture_job(101)], 12: [fixture_job(102)]}
        self.assertEqual(
            v5.validate_exact_ci(api, expected_head=adapter.PR8_HEAD, not_before="2026-11-02T11:00:00Z"),
            {"pull_request": 1, "push": 1},
        )
        api.runs[1]["status"] = "action_required"
        api.runs[1]["conclusion"] = "action_required"
        with self.assertRaisesRegex(ValueError, "push Actions run is not successful"):
            v5.validate_exact_ci(api, expected_head=adapter.PR8_HEAD)
        api.runs = [fixture_run("pull_request", 11)]
        with self.assertRaisesRegex(ValueError, "push Actions run is missing"):
            v5.validate_exact_ci(api, expected_head=adapter.PR8_HEAD)
        api.runs = [fixture_run("pull_request", 11), fixture_run("push", 12)]
        api.jobs = {11: [], 12: [fixture_job(102)]}
        with self.assertRaisesRegex(ValueError, "zero or incomplete"):
            v5.validate_exact_ci(api, expected_head=adapter.PR8_HEAD)
        api.jobs = {11: [fixture_job(101, executed=False)], 12: [fixture_job(102)]}
        with self.assertRaisesRegex(ValueError, "failed, skipped, or non-executed"):
            v5.validate_exact_ci(api, expected_head=adapter.PR8_HEAD)

    def test_authenticated_unquoted_attestation_is_unique_and_post_introduction(self):
        receipt = self.receipts[4]
        key = (receipt["source"]["repository"], receipt["source"]["path"])
        expected = adapter.EXPECTED_RECEIPTS[key]
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

        def comment(user=None, body=None, comment_id=900):
            return {
                "id": comment_id,
                "user": user or {
                    "login": "Copilot",
                    "id": v4.BOT_ID,
                    "node_id": v4.BOT_NODE_ID,
                    "type": "Bot",
                },
                "issue_url": f"{v4.API_ROOT}/issues/8",
                "html_url": f"https://github.com/{v4.OWNER_REPOSITORY}/pull/8#issuecomment-{comment_id}",
                "body": body if body is not None else "\n".join(markers),
                "created_at": "2026-11-02T13:00:00Z",
            }

        old_git = v4._git
        v4._git = lambda *_args: "2026-11-02T12:00:00+00:00"
        try:
            good = comment()
            self.assertIs(
                adapter.verify_expected_comment(receipt, FakeVerifier, CommentAPI([good]), "/unused"),
                good,
            )
            bad_cases = [
                [comment(user={"login": "xbaconator9000x", "id": 343442676, "type": "User"})],
                [comment(user={"login": "Copilot", "id": 0, "node_id": v4.BOT_NODE_ID, "type": "Bot"})],
                [comment(body="> " + "\n> ".join(markers))],
                [good, copy.deepcopy(good)],
                [],
            ]
            for comments in bad_cases:
                with self.subTest(comments=comments), self.assertRaises(ValueError):
                    adapter.verify_expected_comment(receipt, FakeVerifier, CommentAPI(comments), "/unused")
            stale = comment()
            stale["created_at"] = "2026-11-02T11:59:59Z"
            with self.assertRaisesRegex(ValueError, "predates"):
                adapter.verify_expected_comment(receipt, FakeVerifier, CommentAPI([stale]), "/unused")
        finally:
            v4._git = old_git


if __name__ == "__main__":
    unittest.main()
