"""Offline tests: bounded, non-approving autonomous product dispatcher."""
import copy
import unittest
from unittest.mock import patch

from tools import xgba_autonomous_product as a
from tools.phase1_agent_task_pilot import PilotError


def pr(sha="a" * 40):
    return {"number": 40, "state": "open", "draft": True,
            "head": {"ref": a.HEAD, "sha": sha, "repo": {"full_name": a.REPO}},
            "base": {"ref": a.BASE, "repo": {"full_name": a.REPO}}}


class FakeAPI:
    def __init__(self):
        self.sha = "a" * 40
        self.active = []
        self.task_state = "queued"
        self.task_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        self.posts = []
        self.ci = "success"
        self.changed = list(a.PACKAGES[0]["files"])

    def get(self, path):
        if path.endswith("/pulls/40"):
            return pr(self.sha)
        if path.startswith(a.AGENT_PATH + "?"):
            return {"tasks": copy.deepcopy(self.active)}
        if path.startswith(a.AGENT_PATH + "/"):
            return {"id": self.task_id, "state": self.task_state}
        if "/compare/" in path:
            return {"status": "ahead", "files": [{"filename": f} for f in self.changed]}
        if "/actions/runs?" in path:
            return {"total_count": 1, "workflow_runs": [
                {"name": a.WORKFLOW_NAME, "head_sha": self.sha,
                 "event": "pull_request", "status": "completed" if self.ci else "in_progress",
                 "conclusion": self.ci},
            ]}
        if "/contents/" in path:
            return {"type": "file", "size": 4096}
        raise AssertionError(path)

    def post(self, path, payload):
        self.posts.append((path, copy.deepcopy(payload)))
        if path != a.AGENT_PATH:
            raise AssertionError(path)
        return {"id": self.task_id, "state": "queued"}


class FakeLedger:
    def __init__(self, api):
        self.value = a.new_state()
        self.writes = []
        self.api = api

    def ensure(self):
        pass

    def load(self):
        return copy.deepcopy(self.value), "sha"

    def save(self, state, old):
        a.verify_state(state)
        self.value = copy.deepcopy(state)
        self.writes.append(copy.deepcopy(state))
        return "sha"


class TestAutoProduct(unittest.TestCase):
    def test_dry_run_catalog(self):
        a.verify_state(a.new_state())
        self.assertEqual(len(a.PACKAGES), 3)
        files = [f for p in a.PACKAGES for f in p["files"]]
        self.assertEqual(len(files), len(set(files)))
        self.assertFalse(any("matrix" in f for f in files))

    def test_existing_pr_validated(self):
        api = FakeAPI()
        self.assertEqual(a.pr_head(api), api.sha)
        for kind in ("draft", "state", "number"):
            data = pr()
            data[kind] = False if kind == "draft" else "closed" if kind == "state" else 41
            api.get = lambda path, data=data: data
            with self.assertRaises(PilotError):
                a.pr_head(api)

    def test_source_prompt_cannot_claim_approval(self):
        msg = a.prompt_for(a.PACKAGES[0], "a" * 40)
        self.assertIn("ALREADY", msg)
        self.assertIn("No main merge", msg)
        self.assertIn("required", msg.lower())
        self.assertIn("independent approval", msg)

    def test_state_rejects_claimed_approval_and_invalid_cursor(self):
        state = a.new_state()
        state["independent_semantic_approvals"] = 1
        with self.assertRaises(PilotError):
            a.verify_state(state)
        state = a.new_state()
        state["next"] = 99
        with self.assertRaises(PilotError):
            a.verify_state(state)

    def test_state_rejects_forged_quota_and_delivery_history(self):
        original = a.new_state()
        for invalid in (-1, True, a.MAX_PER_UTC_DAY + 1, "1"):
            state = copy.deepcopy(original)
            state["daily_dispatches"] = {"2026-11-10": invalid}
            with self.subTest(count=invalid), self.assertRaises(PilotError):
                a.verify_state(state)
        state = copy.deepcopy(original)
        state["daily_dispatches"] = {"tomorrow": 1}
        with self.assertRaises(PilotError):
            a.verify_state(state)
        state = copy.deepcopy(original)
        state["next"] = 1
        with self.assertRaises(PilotError):
            a.verify_state(state)
        state["history"].append({"package": a.PACKAGES[0]["id"],
                                 "status": "DELIVERED_AWAITING_INDEPENDENT_REVIEW",
                                 "review_approved": True, "head": "a" * 40,
                                 "task_id": "12345678"})
        with self.assertRaises(PilotError):
            a.verify_state(state)
        state["history"][0]["review_approved"] = False
        a.verify_state(state)

    def test_state_rejects_foreign_package(self):
        s = a.new_state()
        s["current"] = {"id": "DIFFERENT", "status": "DISPATCHED"}
        with self.assertRaises(PilotError):
            a.verify_state(s)

    def test_missing_delivery_code_is_not_accepted(self):
        api = FakeAPI()
        api.changed = [a.PACKAGES[0]["files"][0]]
        ok, why = a.has_required_changes(api, "a" * 40, "b" * 40, a.PACKAGES[0])
        self.assertFalse(ok)
        self.assertIn("missing", why)

    def test_scope_violation_is_blocked(self):
        api = FakeAPI()
        api.changed.append(".github/workflows/phase1-copilot-chain.yml")
        ok, why = a.has_required_changes(api, "a" * 40, "b" * 40, a.PACKAGES[0])
        self.assertFalse(ok)
        self.assertIn("Unexpected", why)

    def test_product_ci_requires_exact_head(self):
        api = FakeAPI()
        self.assertEqual(a.ci_gate(api, api.sha)[0], "PASS")
        api.ci = None
        self.assertEqual(a.ci_gate(api, api.sha)[0], "WAIT")
        api.ci = "failure"
        self.assertEqual(a.ci_gate(api, api.sha)[0], "BLOCKED")

    def test_active_other_task_means_no_new_task(self):
        api, store = FakeAPI(), FakeLedger(None)
        api.active = [{"id": "unrelated", "state": "in_progress"}]
        with patch.object(a, "Ledger", return_value=store), patch.object(a, "live_tasks", return_value=api.active), patch.dict(
            "os.environ", {"GITHUB_REPOSITORY": a.REPO, "XGBA_AUTONOMY_ENABLED": "1"}
        ):
            a.run(api)
        self.assertFalse(api.posts)
        self.assertEqual(store.value["current"], None)

    def test_single_dispatch_with_reservation_and_hard_daily_limit(self):
        api, store = FakeAPI(), FakeLedger(None)
        with patch.object(a, "Ledger", return_value=store), patch.object(a, "live_tasks", return_value=[]), patch.dict(
            "os.environ", {"GITHUB_REPOSITORY": a.REPO, "XGBA_AUTONOMY_ENABLED": "1"}
        ):
            a.run(api)
            self.assertEqual(len(api.posts), 1)
            self.assertEqual(store.writes[0]["current"]["status"], "RESERVED")
            self.assertEqual(store.writes[-1]["current"]["status"], "DISPATCHED")
            self.assertFalse(api.posts[0][1]["create_pull_request"])
            a.run(api)
            self.assertEqual(len(api.posts), 1)
            self.assertEqual(store.value["independent_semantic_approvals"], 0)

    def test_completed_task_does_not_claim_approval_and_advances(self):
        api, store = FakeAPI(), FakeLedger(None)
        # Simulate completed R1 with exact expected code and green CI.
        store.value["current"] = {
            "id": a.PACKAGES[0]["id"], "status": "DISPATCHED",
            "task_id": api.task_id, "baseline": "a" * 40,
        }
        api.sha = "b" * 40
        api.task_state = "completed"
        with patch.object(a, "Ledger", return_value=store), patch.object(a, "live_tasks", return_value=[]), patch.dict(
            "os.environ", {"GITHUB_REPOSITORY": a.REPO, "XGBA_AUTONOMY_ENABLED": "1"}
        ):
            a.run(api)
        self.assertEqual(store.value["history"][0]["status"], "DELIVERED_AWAITING_INDEPENDENT_REVIEW")
        self.assertFalse(store.value["history"][0]["review_approved"])
        self.assertEqual(store.value["next"], 1)
        self.assertEqual(len(api.posts), 1)
        self.assertEqual(store.value["current"]["id"], a.PACKAGES[1]["id"])

    def test_missing_ci_eventually_blocks_not_forever_waiting(self):
        api, store = FakeAPI(), FakeLedger(None)
        store.value["current"] = {
            "id": a.PACKAGES[0]["id"], "status": "DISPATCHED",
            "task_id": api.task_id, "baseline": "a" * 40,
        }
        api.sha = "b" * 40
        api.task_state = "completed"
        api.ci = None
        with patch.object(a, "Ledger", return_value=store), patch.object(a, "live_tasks", return_value=[]), patch.dict(
            "os.environ", {"GITHUB_REPOSITORY": a.REPO, "XGBA_AUTONOMY_ENABLED": "1"}
        ):
            for index in range(6):
                a.run(api)
                self.assertEqual(store.value["current"]["status"],
                                 "WAIT_CI" if index < 5 else "BLOCKED")
        self.assertEqual(api.posts, [])
        self.assertEqual(store.value["next"], 0)
        self.assertIn("six scheduled checks", store.value["current"]["reason"])

    def test_completed_without_commit_blocks(self):
        api, store = FakeAPI(), FakeLedger(None)
        store.value["current"] = {
            "id": a.PACKAGES[0]["id"], "status": "DISPATCHED",
            "task_id": api.task_id, "baseline": api.sha,
        }
        api.task_state = "completed"
        with patch.object(a, "Ledger", return_value=store), patch.object(a, "live_tasks", return_value=[]), patch.dict(
            "os.environ", {"GITHUB_REPOSITORY": a.REPO, "XGBA_AUTONOMY_ENABLED": "1"}
        ):
            a.run(api)
        self.assertEqual(store.value["current"]["status"], "BLOCKED")
        self.assertEqual(api.posts, [])


if __name__ == "__main__":
    unittest.main()
