import copy
import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import phase1_copilot_receipts_v4_adapter as adapter


class FixtureAPI:
    def __init__(self):
        self.runs = []
        self.jobs = {}

    def paginate(self, url, *, result_key=None):
        parsed = urlparse(url)
        if parsed.path.endswith("/actions/runs"):
            return self.runs
        raise AssertionError(f"Unexpected paginated request: {url}")

    def __call__(self, url):
        parsed = urlparse(url)
        parts = parsed.path.split("/")
        if "jobs" in parts:
            run_id = int(parts[parts.index("runs") + 1])
            jobs = self.jobs[run_id]
            return {"total_count": len(jobs), "jobs": copy.deepcopy(jobs)}
        raise AssertionError(f"Unexpected API request: {url}")


class FakeVerifier:
    class GitHubAPICache:
        def __init__(self, getter):
            self.getter = getter

        def __call__(self, url):
            return self.getter(url)


def fixture_run(event, run_id, *, head=adapter.PR8_HEAD, conclusion="success",
                status="completed", path=None, name=None):
    run = {
        "id": run_id,
        "run_attempt": 1,
        "event": event,
        "head_sha": head,
        "path": path or (adapter.PR_WORKFLOW if event == "pull_request" else adapter.CENSUS_WORKFLOW),
        "status": status,
        "conclusion": conclusion,
        "created_at": "2026-10-31T19:00:00Z",
        "run_started_at": "2026-10-31T19:00:10Z",
        "pull_requests": [],
    }
    if event == "pull_request":
        run.update({
            "name": name or adapter.PR_WORKFLOW_NAME,
            "pull_requests": [{"number": adapter.PR_NUMBER, "head": {"sha": head}}],
            "referenced_workflows": [{
                "path": f"{adapter.OWNER_REPOSITORY}/{adapter.CENSUS_WORKFLOW}@refs/pull/8/merge",
            }],
        })
    return run


def fixture_job(job_id, *, status="completed", conclusion="success", started=True):
    return {
        "id": job_id,
        "status": status,
        "conclusion": conclusion,
        "steps": [{
            "status": "completed",
            "conclusion": "success",
            "started_at": "2026-10-31T19:01:00Z" if started else None,
            "completed_at": "2026-10-31T19:02:00Z" if started else None,
        }],
    }


class CopilotReceiptV4AdapterTests(unittest.TestCase):
    def valid_api(self):
        api = FixtureAPI()
        pr_run = fixture_run("pull_request", 11)
        push_run = fixture_run("push", 12)
        api.runs = [pr_run, push_run]
        api.jobs = {11: [fixture_job(101)], 12: [fixture_job(102)]}
        return api

    def test_receipt_digest_excludes_attestation(self):
        receipt = {"schema": adapter.RECEIPT_SCHEMA, "review": {"decision": "fixture"}}
        digest = adapter.receipt_digest(receipt)
        with_attestation = {**receipt, "attestation": {"receipt_sha256": digest}}
        self.assertEqual(adapter.receipt_digest(with_attestation), digest)
        with_attestation["review"]["decision"] = "tampered"
        self.assertNotEqual(adapter.receipt_digest(with_attestation), digest)

    def test_verified_copilot_identity_requires_all_immutable_fields(self):
        user = {
            "login": "Copilot",
            "id": adapter.BOT_ID,
            "node_id": adapter.BOT_NODE_ID,
            "type": "Bot",
        }
        self.assertTrue(adapter._bot_identity(user))
        for field, value in (
            ("login", "copilot"),
            ("login", "copilot-swe-agent"),
            ("id", adapter.BOT_ID + 1),
            ("node_id", "spoofed"),
            ("type", "User"),
        ):
            spoof = {**user, field: value}
            with self.subTest(field=field, value=value):
                self.assertFalse(adapter._bot_identity(spoof))

    def test_public_api_client_uses_anonymous_read_only_getter_without_user_probe(self):
        requests = []

        def getter(url, *, token):
            requests.append((url, token))
            return {"public": True}

        verifier = FakeVerifier()
        verifier.github_get_json = getter
        api = adapter.github_api_client(verifier)
        url = f"{adapter.API_ROOT}/issues/8/comments?per_page=100&page=1"
        self.assertEqual(api(url), {"public": True})
        self.assertEqual(requests, [(url, None)])

    def test_public_api_client_fails_closed_on_anonymous_api_error(self):
        def getter(url, *, token):
            self.assertIsNone(token)
            raise ValueError("GitHub API returned HTTP 403")

        verifier = FakeVerifier()
        verifier.github_get_json = getter
        api = adapter.github_api_client(verifier)
        with self.assertRaisesRegex(ValueError, "HTTP 403"):
            api(f"{adapter.API_ROOT}/actions/runs?head_sha={adapter.PR8_HEAD}")

    def test_expected_comment_rejects_spoofed_identity_and_tampered_marker(self):
        key, expected = next(iter(adapter.EXPECTED_RECEIPTS.items()))
        markers = (
            "receipt-digest:" + expected["receipt_sha256"],
            "receipt-commit:" + expected["receipt_commit"],
            "evidence-commit:" + expected["evidence_commit"],
            "decision:APPROVED",
        )

        class MarkerVerifier:
            RECEIPT_MARKER = "receipt-digest:"
            INTRO_COMMIT_MARKER = "receipt-commit:"
            EVIDENCE_COMMIT_MARKER = "evidence-commit:"
            DECISION_MARKER = "decision:APPROVED"

            @staticmethod
            def _attestation_section_is_valid(body, required):
                return isinstance(body, str) and all(marker in body for marker in required)

        class CommentAPI:
            def __init__(self, comment):
                self.comment = comment

            def paginate(self, _url):
                return [self.comment]

        comment = {
            "id": expected["comment_id"],
            "user": {
                "login": "Copilot",
                "id": adapter.BOT_ID,
                "node_id": adapter.BOT_NODE_ID,
                "type": "Bot",
            },
            "issue_url": f"{adapter.API_ROOT}/issues/8",
            "html_url": f"https://github.com/{adapter.OWNER_REPOSITORY}/pull/8"
            f"#issuecomment-{expected['comment_id']}",
            "body": "\n".join(markers),
            "created_at": "2026-10-31T20:00:00Z",
        }
        receipt = {"source": {"repository": key[0], "path": key[1]}}
        for field, value in (
            ("user", {"login": "Copilot", "id": adapter.BOT_ID + 1,
                      "node_id": adapter.BOT_NODE_ID, "type": "Bot"}),
            ("body", comment["body"].replace(expected["receipt_sha256"], "0" * 64)),
        ):
            tampered = {**comment, field: value}
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "identity/markers did not match"):
                    adapter.verify_expected_comment(
                        receipt, MarkerVerifier(), CommentAPI(tampered), Path("/unused")
                    )

    def test_v4_register_rejects_unknown_duplicate_and_wrong_schema(self):
        for records in (
            [],
            [{"schema": "xgba.phase1.copilot_review_receipt.v1"}],
            [{"schema": adapter.RECEIPT_SCHEMA, "source": {"repository": "owner/repo", "path": "x"}}] * 3,
        ):
            with self.subTest(records=records):
                with self.assertRaises(ValueError):
                    adapter.validate_receipt_inventory(records)

    def test_exact_head_pull_and_push_runs_with_executed_jobs_pass(self):
        self.assertEqual(
            adapter.validate_exact_ci(self.valid_api()),
            {"pull_request": 1, "push": 1},
        )

    def test_action_required_exact_head_run_fails_closed(self):
        api = self.valid_api()
        api.runs[0]["status"] = "action_required"
        with self.assertRaisesRegex(ValueError, "not successful"):
            adapter.validate_exact_ci(api)

    def test_missing_exact_head_push_run_fails_closed(self):
        api = self.valid_api()
        api.runs = api.runs[:1]
        with self.assertRaisesRegex(ValueError, "push Actions run is missing"):
            adapter.validate_exact_ci(api)

    def test_stale_or_wrong_head_run_fails_closed(self):
        api = self.valid_api()
        api.runs[0]["head_sha"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "pull_request Actions run is missing"):
            adapter.validate_exact_ci(api)

    def test_pull_run_must_belong_to_pr8_exact_head(self):
        api = self.valid_api()
        api.runs[0]["pull_requests"][0]["number"] = 9
        with self.assertRaisesRegex(ValueError, "pull_request Actions run is missing"):
            adapter.validate_exact_ci(api)

    def test_pull_run_must_reference_the_census_workflow(self):
        api = self.valid_api()
        api.runs[0]["referenced_workflows"] = []
        with self.assertRaisesRegex(ValueError, "does not reference"):
            adapter.validate_exact_ci(api)

    def test_zero_job_run_fails_closed(self):
        api = self.valid_api()
        api.jobs[12] = []
        with self.assertRaisesRegex(ValueError, "zero or incomplete jobs"):
            adapter.validate_exact_ci(api)

    def test_failed_or_nonexecuted_job_fails_closed(self):
        api = self.valid_api()
        api.jobs[11] = [fixture_job(101, conclusion="failure")]
        with self.assertRaisesRegex(ValueError, "failed or non-executed"):
            adapter.validate_exact_ci(api)
        api = self.valid_api()
        api.jobs[12] = [fixture_job(102, started=False)]
        with self.assertRaisesRegex(ValueError, "failed or non-executed"):
            adapter.validate_exact_ci(api)

    def test_latest_exact_head_run_is_used_not_an_older_success(self):
        api = self.valid_api()
        newer = fixture_run("push", 13, conclusion="action_required", status="completed")
        newer["created_at"] = "2026-10-31T20:00:00Z"
        api.runs.append(newer)
        api.jobs[13] = [fixture_job(103)]
        with self.assertRaisesRegex(ValueError, "push Actions run is not successful"):
            adapter.validate_exact_ci(api)

    def test_exact_head_run_must_postdate_final_receipt_commit(self):
        with self.assertRaisesRegex(ValueError, "predates the final receipt commit"):
            adapter.validate_exact_ci(
                self.valid_api(), not_before="2026-10-31T20:00:00Z"
            )


if __name__ == "__main__":
    unittest.main()
