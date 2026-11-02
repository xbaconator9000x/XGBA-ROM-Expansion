import copy
import contextlib
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import phase1_copilot_receipts_v5_adapter as v5
import phase1_copilot_receipts_v5_historical_replay as replay


def fixture_run(**changes):
    run = {
        "id": replay.HISTORICAL_RUN_ID,
        "run_attempt": replay.HISTORICAL_RUN_ATTEMPT,
        "workflow_id": replay.HISTORICAL_WORKFLOW_ID,
        "path": replay.HISTORICAL_WORKFLOW_PATH,
        "name": replay.HISTORICAL_WORKFLOW_NAME,
        "event": "push",
        "head_branch": replay.HISTORICAL_BRANCH,
        "head_sha": replay.HISTORICAL_PR2_HEAD,
        "status": "completed",
        "conclusion": "success",
        "run_started_at": "2026-11-01T18:38:55Z",
    }
    run.update(changes)
    return run


def fixture_job(name, job_id, *, conclusion="success", executed=True):
    steps = [{
        "name": "Set up job",
        "status": "completed" if executed else "queued",
        "conclusion": "success" if executed else None,
        "started_at": "2026-11-01T18:38:55Z" if executed else None,
        "completed_at": "2026-11-01T18:38:56Z" if executed else None,
    }]
    if name == "v5-live-pinned-source-and-github-evidence":
        steps.append({
            "name": replay.HISTORICAL_V5_STEP,
            "status": "completed" if executed else "queued",
            "conclusion": "success" if executed else None,
            "started_at": "2026-11-01T18:39:02Z" if executed else None,
            "completed_at": "2026-11-01T18:39:15Z" if executed else None,
        })
    return {
        "name": name,
        "id": job_id,
        "status": "completed",
        "conclusion": conclusion,
        "steps": steps,
    }


def fixture_jobs():
    return [
        fixture_job(name, job_id)
        for name, job_id in replay.HISTORICAL_JOB_IDS.items()
    ]


class FixtureAPI:
    def __init__(self, run=None, jobs=None, total_count=None):
        self.run = run or fixture_run()
        self.jobs = jobs or fixture_jobs()
        self.total_count = len(self.jobs) if total_count is None else total_count

    def __call__(self, url):
        if url.endswith(f"/actions/runs/{replay.HISTORICAL_RUN_ID}"):
            return copy.deepcopy(self.run)
        if "/attempts/1/jobs?" in url:
            return {
                "total_count": self.total_count,
                "jobs": copy.deepcopy(self.jobs),
            }
        raise AssertionError(f"Unexpected API request: {url}")

    def paginate(self, _url, *, result_key=None):
        return copy.deepcopy(self.jobs)


class V5HistoricalReplayTests(unittest.TestCase):
    def test_exact_pinned_historical_run_and_all_jobs_pass(self):
        result = replay.validate_historical_actions(
            FixtureAPI(), not_before="2026-11-01T08:43:23Z"
        )
        self.assertEqual(result, {
            "run_id": 41337689699,
            "run_attempt": 1,
            "jobs": 4,
            "receipts": 4,
        })
        self.assertEqual(v5.PR8_HEAD, "3ee4b1117f2976b6ea41098f5456634da18a50f8")

    def test_wrong_or_stale_run_identity_and_status_fail_closed(self):
        for changes in (
            {"id": replay.HISTORICAL_RUN_ID + 1},
            {"run_attempt": 2},
            {"workflow_id": replay.HISTORICAL_WORKFLOW_ID + 1},
            {"path": "other.yml"},
            {"event": "pull_request"},
            {"head_branch": "other-branch"},
            {"head_sha": "0" * 40},
            {"status": "in_progress"},
            {"conclusion": "failure"},
        ):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "historical v5 Actions run"):
                replay.validate_historical_actions(
                    FixtureAPI(run=fixture_run(**changes)),
                    not_before="2026-11-01T08:43:23Z",
                )

    def test_historical_run_must_follow_pinned_receipt_head(self):
        run = fixture_run(run_started_at="2026-11-01T08:43:23Z")
        with self.assertRaisesRegex(ValueError, "predates the pinned PR8 receipt head"):
            replay.validate_historical_actions(
                FixtureAPI(run=run), not_before="2026-11-01T08:43:23Z"
            )

    def test_wrong_missing_duplicate_or_incomplete_job_inventory_fails_closed(self):
        cases = [
            (fixture_jobs()[:-1], 3),
            (fixture_jobs() + [fixture_jobs()[0]], 5),
            ([fixture_job("unexpected", 1)], 1),
            ([fixture_job("v5-live-pinned-source-and-github-evidence", 1)], 1),
        ]
        for jobs, count in cases:
            with self.subTest(jobs=jobs), self.assertRaises(ValueError):
                replay.validate_historical_actions(
                    FixtureAPI(jobs=jobs, total_count=count),
                    not_before="2026-11-01T08:43:23Z",
                )
        with self.assertRaisesRegex(ValueError, "inventory is incomplete"):
            replay.validate_historical_actions(
                FixtureAPI(total_count=3), not_before="2026-11-01T08:43:23Z"
            )

    def test_failed_or_nonexecuted_jobs_and_missing_cli_step_fail(self):
        jobs = fixture_jobs()
        jobs[0]["conclusion"] = "failure"
        with self.assertRaisesRegex(ValueError, "identity or result"):
            replay.validate_historical_actions(
                FixtureAPI(jobs=jobs), not_before="2026-11-01T08:43:23Z"
            )

        jobs = fixture_jobs()
        jobs[0]["steps"][0]["status"] = "queued"
        jobs[0]["steps"][0]["conclusion"] = None
        jobs[0]["steps"][0]["started_at"] = None
        jobs[0]["steps"][0]["completed_at"] = None
        with self.assertRaisesRegex(ValueError, "failed or non-executed"):
            replay.validate_historical_actions(
                FixtureAPI(jobs=jobs), not_before="2026-11-01T08:43:23Z"
            )

        jobs = fixture_jobs()
        jobs[0]["steps"].append(copy.deepcopy(jobs[0]["steps"][0]))
        jobs[0]["steps"][1]["name"] = "not the v5 validator"
        with self.assertRaisesRegex(ValueError, "unique exact validator step"):
            replay.validate_historical_actions(
                FixtureAPI(jobs=jobs), not_before="2026-11-01T08:43:23Z"
            )

    def test_historical_result_is_distinct_from_current_validation_and_approvals(self):
        old_ancestry = replay.verify_historical_pr2_ancestry
        old_receipts = replay.verify_historical_receipt_bytes
        old_loader = replay.v4._load_pinned_validator
        old_git = replay.v4._git
        try:
            replay.verify_historical_pr2_ancestry = lambda _root: Path("/historical-pr2")
            replay.verify_historical_receipt_bytes = lambda *_args: 4
            replay.v4._load_pinned_validator = lambda _root: (None, object())
            replay.v4._git = lambda *_args: "2026-11-01T08:43:23+00:00"
            result = replay.run_historical_replay(
                "/historical-pr8", "/pinned-upstreams", "/current-pr2", api=FixtureAPI()
            )
        finally:
            replay.verify_historical_pr2_ancestry = old_ancestry
            replay.verify_historical_receipt_bytes = old_receipts
            replay.v4._load_pinned_validator = old_loader
            replay.v4._git = old_git
        self.assertEqual(result["status"], "HISTORICAL_V5_REPLAY_VERIFIED")
        self.assertEqual(result["pr8_head"], v5.PR8_HEAD)
        self.assertIn("historical only", result["scope"])
        self.assertNotEqual(result["status"], "COPILOT_RECEIPT_VALIDATED")

    def test_historical_mode_must_be_explicit(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as exc:
                replay.main([
                    "--pr8-root", "/historical-pr8",
                    "--source-root", "/pinned-upstreams",
                    "--pr2-root", "/current-pr2",
                ])
        self.assertEqual(exc.exception.code, 2)

    def test_historical_ancestry_requires_old_commit_and_immutable_blobs(self):
        old_git = replay.v4._git
        current_head = "a" * 40
        expected = {
            ("rev-parse", "HEAD"): current_head,
            (
                "rev-parse",
                f"{replay.HISTORICAL_PR2_HEAD}:tools/phase1_copilot_receipts_v5_adapter.py",
            ): replay.HISTORICAL_PR2_ADAPTER_BLOB,
            (
                "rev-parse",
                f"{replay.HISTORICAL_PR2_HEAD}:{replay.HISTORICAL_WORKFLOW_PATH}",
            ): replay.HISTORICAL_PR2_WORKFLOW_BLOB,
        }

        def fake_git(_root, *args):
            if args[:2] == ("merge-base", "--is-ancestor"):
                self.assertEqual(args[2:], (replay.HISTORICAL_PR2_HEAD, current_head))
                return ""
            return expected[args]

        replay.v4._git = fake_git
        try:
            self.assertEqual(
                replay.verify_historical_pr2_ancestry("/current-pr2"),
                Path("/current-pr2").resolve(),
            )
            expected[(
                "rev-parse",
                f"{replay.HISTORICAL_PR2_HEAD}:tools/phase1_copilot_receipts_v5_adapter.py",
            )] = "0" * 40
            with self.assertRaisesRegex(ValueError, "Historical PR2 validation blob mismatch"):
                replay.verify_historical_pr2_ancestry("/current-pr2")
        finally:
            replay.v4._git = old_git


if __name__ == "__main__":
    unittest.main()
