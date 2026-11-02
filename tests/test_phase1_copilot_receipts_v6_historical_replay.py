import copy
import contextlib
import io
import hashlib
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch
from pathlib import Path
import unittest
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import phase1_copilot_receipts_v4_adapter as v4
import phase1_copilot_receipts_v6_adapter as v6
import phase1_copilot_receipts_v6_historical_replay as replay


NOT_BEFORE = "2026-11-02T01:40:00Z"


def fixture_run(run_id, **changes):
    if run_id == replay.HISTORICAL_PR2_RUN_ID:
        run = {
            "id": run_id,
            "run_attempt": replay.HISTORICAL_PR2_RUN_ATTEMPT,
            "workflow_id": replay.HISTORICAL_PR2_WORKFLOW_ID,
            "path": replay.HISTORICAL_PR2_WORKFLOW_PATH,
            "name": replay.HISTORICAL_PR2_WORKFLOW_NAME,
            "event": "push",
            "head_branch": replay.HISTORICAL_BRANCH,
            "head_sha": replay.HISTORICAL_PR2_HEAD,
            "status": "completed",
            "conclusion": "success",
            "run_started_at": "2026-11-02T03:44:46Z",
        }
    elif run_id == replay.HISTORICAL_PR8_PR_RUN_ID:
        run = {
            "id": run_id,
            "run_attempt": replay.HISTORICAL_PR8_RUN_ATTEMPT,
            "workflow_id": replay.HISTORICAL_PR8_PR_WORKFLOW_ID,
            "path": replay.HISTORICAL_PR8_PR_WORKFLOW_PATH,
            "name": replay.HISTORICAL_PR8_PR_WORKFLOW_NAME,
            "event": "pull_request",
            "head_branch": replay.HISTORICAL_PR8_HEAD_BRANCH,
            "head_sha": v6.PR8_HEAD,
            "status": "completed",
            "conclusion": "success",
            "run_started_at": "2026-11-02T01:47:07Z",
            "pull_requests": [{"number": 8, "head": {"sha": v6.PR8_HEAD}}],
            "referenced_workflows": [{
                "path": f"{v4.OWNER_REPOSITORY}/.github/workflows/phase1-census.yml@refs/pull/8/merge",
            }],
        }
    else:
        run = {
            "id": run_id,
            "run_attempt": replay.HISTORICAL_PR8_RUN_ATTEMPT,
            "workflow_id": replay.HISTORICAL_PR8_PUSH_WORKFLOW_ID,
            "path": replay.HISTORICAL_PR8_PUSH_WORKFLOW_PATH,
            "name": replay.HISTORICAL_PR8_PUSH_WORKFLOW_NAME,
            "event": "push",
            "head_branch": replay.HISTORICAL_PR8_HEAD_BRANCH,
            "head_sha": v6.PR8_HEAD,
            "status": "completed",
            "conclusion": "success",
            "run_started_at": "2026-11-02T01:46:52Z",
        }
    run.update(changes)
    return run


def fixture_job(run_id, attempt, head, name, job_id, *, conclusion="success", executed=True):
    return {
        "id": job_id,
        "run_id": run_id,
        "run_attempt": attempt,
        "head_sha": head,
        "name": name,
        "status": "completed",
        "conclusion": conclusion,
        "steps": [{
            "name": "Set up job",
            "status": "completed" if executed else "queued",
            "conclusion": "success" if executed else None,
            "started_at": "2026-11-02T01:47:08Z" if executed else None,
            "completed_at": "2026-11-02T01:47:09Z" if executed else None,
        }],
    }


def fixture_jobs(run_id):
    if run_id == replay.HISTORICAL_PR2_RUN_ID:
        jobs = []
        for name, job_id in replay.HISTORICAL_PR2_JOB_IDS.items():
            job = fixture_job(
                run_id,
                replay.HISTORICAL_PR2_RUN_ATTEMPT,
                replay.HISTORICAL_PR2_HEAD,
                name,
                job_id,
            )
            if name == "v6-live-pinned-source-and-github-evidence":
                job["steps"].append({
                    "name": replay.HISTORICAL_V6_STEP,
                    "status": "completed",
                    "conclusion": "success",
                    "started_at": "2026-11-02T03:44:55Z",
                    "completed_at": "2026-11-02T03:45:11Z",
                })
            jobs.append(job)
        return jobs
    if run_id == replay.HISTORICAL_PR8_PR_RUN_ID:
        return [
            fixture_job(
                run_id,
                replay.HISTORICAL_PR8_RUN_ATTEMPT,
                v6.PR8_HEAD,
                "census / census" if index == 0 else f"source-check-{index}",
                125051016935 + index,
            )
            for index in range(replay.HISTORICAL_PR8_PR_JOB_COUNT)
        ]
    return [fixture_job(
        run_id,
        replay.HISTORICAL_PR8_RUN_ATTEMPT,
        v6.PR8_HEAD,
        "census",
        125050952201,
    )]


class FixtureAPI:
    def __init__(self, *, run_overrides=None, job_overrides=None, totals=None):
        run_ids = (
            replay.HISTORICAL_PR2_RUN_ID,
            replay.HISTORICAL_PR8_PR_RUN_ID,
            replay.HISTORICAL_PR8_PUSH_RUN_ID,
        )
        self.runs = {run_id: fixture_run(run_id) for run_id in run_ids}
        self.runs.update(run_overrides or {})
        self.jobs = {run_id: fixture_jobs(run_id) for run_id in run_ids}
        self.jobs.update(job_overrides or {})
        self.totals = totals or {}

    def __call__(self, url):
        path = urlparse(url).path
        for run_id, run in self.runs.items():
            if path.endswith(f"/actions/runs/{run_id}"):
                return copy.deepcopy(run)
        for run_id, jobs in self.jobs.items():
            if f"/actions/runs/{run_id}/attempts/" in path and path.endswith("/jobs"):
                return {
                    "total_count": self.totals.get(run_id, len(jobs)),
                    "jobs": copy.deepcopy(jobs),
                }
        raise AssertionError(f"Unexpected API request: {url}")

    def paginate(self, url, *, result_key=None):
        path = urlparse(url).path
        for run_id, jobs in self.jobs.items():
            if f"/actions/runs/{run_id}/attempts/" in path and path.endswith("/jobs"):
                return copy.deepcopy(jobs)
        raise AssertionError(f"Unexpected paginated URL: {url}")


class OriginalSourceReplayTests(unittest.TestCase):
    def test_original_source_bytes_and_identity(self):
        with TemporaryDirectory() as td:
            root = Path(td) / "mgba"
            rel = "include/mgba/internal/arm/isa-thumb.h"
            target = root / rel
            target.parent.mkdir(parents=True)
            data = b"immutable historical source fixture"
            target.write_bytes(data)
            source = {
                "repository": "mgba-emu/mgba",
                "path": rel,
                "git_blob_sha1": "a" * 40,
                "source_sha256": hashlib.sha256(data).hexdigest(),
            }
            def git_ok(_root, *args):
                return replay.PINNED_MGBA_REVISION if args == ("rev-parse", "HEAD") else "a" * 40
            with patch.object(replay, "_git", side_effect=git_ok):
                self.assertTrue(replay.verify_original_pinned_source(td, source))
                target.write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "SHA-256"):
                    replay.verify_original_pinned_source(td, source)
                target.write_bytes(data)
            with patch.object(replay, "_git", return_value="0" * 40):
                with self.assertRaisesRegex(ValueError, "unpinned"):
                    replay.verify_original_pinned_source(td, source)
            def bad_blob(_root, *args):
                return replay.PINNED_MGBA_REVISION if args == ("rev-parse", "HEAD") else "0" * 40
            with patch.object(replay, "_git", side_effect=bad_blob):
                with self.assertRaisesRegex(ValueError, "Git blob"):
                    replay.verify_original_pinned_source(td, source)
            source["path"] = "../escape"
            with patch.object(replay, "_git", side_effect=git_ok):
                with self.assertRaisesRegex(ValueError, "unsafe"):
                    replay.verify_original_pinned_source(td, source)


class V6HistoricalReplayTests(unittest.TestCase):
    def test_exact_pinned_historical_runs_and_executed_jobs_pass(self):
        result = replay.validate_historical_actions(FixtureAPI(), not_before=NOT_BEFORE)
        self.assertEqual(result, {
            "pr2_run_id": replay.HISTORICAL_PR2_RUN_ID,
            "pr2_run_attempt": 3,
            "pr2_jobs": 7,
            "pr8_pr_run_id": replay.HISTORICAL_PR8_PR_RUN_ID,
            "pr8_pr_jobs": 41,
            "pr8_push_run_id": replay.HISTORICAL_PR8_PUSH_RUN_ID,
            "pr8_push_jobs": 1,
            "receipts": 7,
        })

    def test_wrong_or_stale_historical_runs_fail_closed(self):
        cases = (
            (replay.HISTORICAL_PR2_RUN_ID, {"run_attempt": 2}),
            (replay.HISTORICAL_PR2_RUN_ID, {"head_sha": "0" * 40}),
            (replay.HISTORICAL_PR2_RUN_ID, {"conclusion": "failure"}),
            (replay.HISTORICAL_PR8_PR_RUN_ID, {"event": "push"}),
            (replay.HISTORICAL_PR8_PR_RUN_ID, {"status": "action_required", "conclusion": "action_required"}),
            (replay.HISTORICAL_PR8_PR_RUN_ID, {"head_sha": "0" * 40}),
            (replay.HISTORICAL_PR8_PUSH_RUN_ID, {"workflow_id": 1}),
        )
        for run_id, changes in cases:
            with self.subTest(run_id=run_id, changes=changes), self.assertRaises(ValueError):
                replay.validate_historical_actions(
                    FixtureAPI(run_overrides={run_id: fixture_run(run_id, **changes)}),
                    not_before=NOT_BEFORE,
                )
        with self.assertRaisesRegex(ValueError, "predates"):
            replay.validate_historical_actions(
                FixtureAPI(run_overrides={
                    replay.HISTORICAL_PR8_PUSH_RUN_ID: fixture_run(
                        replay.HISTORICAL_PR8_PUSH_RUN_ID,
                        run_started_at="2026-11-02T01:39:59Z",
                    )
                }),
                not_before=NOT_BEFORE,
            )

    def test_missing_duplicate_failed_or_nonexecuted_jobs_fail_closed(self):
        base = FixtureAPI()
        cases = (
            (replay.HISTORICAL_PR2_RUN_ID, base.jobs[replay.HISTORICAL_PR2_RUN_ID][:-1], None),
            (
                replay.HISTORICAL_PR2_RUN_ID,
                base.jobs[replay.HISTORICAL_PR2_RUN_ID] + [base.jobs[replay.HISTORICAL_PR2_RUN_ID][0]],
                None,
            ),
            (
                replay.HISTORICAL_PR8_PR_RUN_ID,
                base.jobs[replay.HISTORICAL_PR8_PR_RUN_ID][:-1],
                None,
            ),
            (
                replay.HISTORICAL_PR8_PUSH_RUN_ID,
                [fixture_job(
                    replay.HISTORICAL_PR8_PUSH_RUN_ID,
                    replay.HISTORICAL_PR8_RUN_ATTEMPT,
                    v6.PR8_HEAD,
                    "unexpected",
                    125050952201,
                )],
                None,
            ),
            (
                replay.HISTORICAL_PR8_PR_RUN_ID,
                [fixture_job(
                    replay.HISTORICAL_PR8_PR_RUN_ID,
                    replay.HISTORICAL_PR8_RUN_ATTEMPT,
                    v6.PR8_HEAD,
                    "census / census",
                    125051016935,
                    conclusion="failure",
                )] + base.jobs[replay.HISTORICAL_PR8_PR_RUN_ID][1:],
                None,
            ),
            (
                replay.HISTORICAL_PR8_PUSH_RUN_ID,
                [fixture_job(
                    replay.HISTORICAL_PR8_PUSH_RUN_ID,
                    replay.HISTORICAL_PR8_RUN_ATTEMPT,
                    v6.PR8_HEAD,
                    "census",
                    125050952201,
                    executed=False,
                )],
                None,
            ),
        )
        for run_id, jobs, total in cases:
            with self.subTest(run_id=run_id, jobs=len(jobs)), self.assertRaises(ValueError):
                replay.validate_historical_actions(
                    FixtureAPI(
                        job_overrides={run_id: jobs},
                        totals={} if total is None else {run_id: total},
                    ),
                    not_before=NOT_BEFORE,
                )

        with self.assertRaisesRegex(ValueError, "inventory is incomplete"):
            replay.validate_historical_actions(
                FixtureAPI(totals={replay.HISTORICAL_PR8_PR_RUN_ID: 40}),
                not_before=NOT_BEFORE,
            )

    def test_historical_pr8_pr_requires_bound_head_and_census_workflow(self):
        api = FixtureAPI()
        run = api.runs[replay.HISTORICAL_PR8_PR_RUN_ID]
        # GitHub mutates the nested PR head metadata on historical runs.
        # The immutable run.head_sha must still be pinned to the old receipt.
        run["pull_requests"][0]["head"]["sha"] = "b455f218537f7aad7876f51ced2542486835c3bf"
        self.assertEqual(
            replay.validate_historical_actions(api, not_before=NOT_BEFORE)["receipts"], 7
        )
        run["pull_requests"][0]["head"]["ref"] = "wrong-branch"
        with self.assertRaisesRegex(ValueError, "exact receipt head"):
            replay.validate_historical_actions(api, not_before=NOT_BEFORE)

        api = FixtureAPI()
        api.runs[replay.HISTORICAL_PR8_PR_RUN_ID]["referenced_workflows"] = []
        with self.assertRaisesRegex(ValueError, "census workflow"):
            replay.validate_historical_actions(api, not_before=NOT_BEFORE)

        api = FixtureAPI()
        api.jobs[replay.HISTORICAL_PR2_RUN_ID][0]["head_sha"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "job identity"):
            replay.validate_historical_actions(api, not_before=NOT_BEFORE)

    def test_historical_replay_is_distinct_from_current_validation_and_approval(self):
        old_ancestry = replay.verify_historical_pr2_ancestry
        old_worktree = v6.verify_pinned_worktree
        old_loader = v4._load_pinned_validator
        old_receipts = replay.verify_historical_receipt_bytes
        old_git = replay._git
        try:
            replay.verify_historical_pr2_ancestry = lambda _root: Path("/historical-pr2")
            v6.verify_pinned_worktree = lambda _root: Path("/historical-pr8")
            v4._load_pinned_validator = lambda _root: (None, object())
            replay.verify_historical_receipt_bytes = lambda *_args: 7
            replay._git = lambda *_args: "2026-11-02T01:30:00+00:00"
            result = replay.run_historical_replay(
                "/historical-pr8",
                "/pinned-upstreams",
                "/current-pr2",
                api=FixtureAPI(),
            )
        finally:
            replay.verify_historical_pr2_ancestry = old_ancestry
            v6.verify_pinned_worktree = old_worktree
            v4._load_pinned_validator = old_loader
            replay.verify_historical_receipt_bytes = old_receipts
            replay._git = old_git
        self.assertEqual(result["status"], "HISTORICAL_V6_REPLAY_VERIFIED")
        self.assertEqual(result["pr8_head"], v6.PR8_HEAD)
        self.assertEqual(result["receipt_count"], 7)
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

    def test_historical_ancestry_requires_exact_old_blobs(self):
        old_git = replay._git
        current_head = "a" * 40
        expected = {
            ("rev-parse", "HEAD"): current_head,
            (
                "rev-parse",
                f"{replay.HISTORICAL_PR2_HEAD}:tools/phase1_copilot_receipts_v6_adapter.py",
            ): replay.HISTORICAL_PR2_ADAPTER_BLOB,
            (
                "rev-parse",
                f"{replay.HISTORICAL_PR2_HEAD}:{replay.HISTORICAL_PR2_WORKFLOW_PATH}",
            ): replay.HISTORICAL_PR2_WORKFLOW_BLOB,
        }

        def fake_git(_root, *args):
            if args[:2] == ("merge-base", "--is-ancestor"):
                self.assertEqual(args[2:], (replay.HISTORICAL_PR2_HEAD, current_head))
                return ""
            return expected[args]

        replay._git = fake_git
        try:
            self.assertEqual(
                replay.verify_historical_pr2_ancestry("/current-pr2"),
                Path("/current-pr2").resolve(),
            )
            expected[(
                "rev-parse",
                f"{replay.HISTORICAL_PR2_HEAD}:tools/phase1_copilot_receipts_v6_adapter.py",
            )] = "0" * 40
            with self.assertRaisesRegex(ValueError, "validation blob mismatch"):
                replay.verify_historical_pr2_ancestry("/current-pr2")
        finally:
            replay._git = old_git


if __name__ == "__main__":
    unittest.main()
