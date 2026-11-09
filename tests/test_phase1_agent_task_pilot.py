#!/usr/bin/env python3
"""Offline, no-secret, no-billable-task regression tests for the XGBA pilot."""
import base64
import copy
import json
import unittest

from tools import phase1_agent_task_pilot as p


def sample_pr(sha="a" * 40):
    return {
        "number": p.PR_NUMBER, "state": "open", "draft": True,
        "head": {"ref": p.HEAD_REF, "sha": sha, "repo": {"full_name": p.REPO}},
        "base": {"ref": p.BASE_REF, "repo": {"full_name": p.REPO}},
    }


class FakeClient:
    def __init__(self):
        self.pr = sample_pr()
        self.active = []
        self.task_details = {}
        self.post_calls = []
        self.get_calls = []
        self.post_failure = False

    def get(self, path):
        self.get_calls.append(path)
        if path == p.REPO_PATH + "/pulls/27":
            return copy.deepcopy(self.pr)
        if path.startswith(p.AGENT_PATH + "?"):
            return {"tasks": copy.deepcopy(self.active)}
        if path.startswith(p.AGENT_PATH + "/"):
            return copy.deepcopy(self.task_details[path.rsplit("/", 1)[-1]])
        raise AssertionError("unexpected GET: " + path)

    def post(self, path, data):
        self.post_calls.append((path, copy.deepcopy(data)))
        if self.post_failure:
            raise p.PilotError("Simulated uncertain API failure")
        return {"id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "state": "queued"}


class FakeStore:
    def __init__(self):
        self.value = None
        self.history = []
        self.branch_created = False

    def ensure_branch(self):
        self.branch_created = True

    def load(self):
        return copy.deepcopy(self.value), "sha" if self.value else None

    def save(self, data, old_sha):
        self.value = copy.deepcopy(data)
        self.history.append(copy.deepcopy(data["ticket"]["status"]))
        return "sha"


class PilotTests(unittest.TestCase):
    def test_task_payload_reuses_existing_branch_not_new_pr(self):
        payload = p.task_payload("d" * 40)
        self.assertEqual(payload["head_ref"], p.HEAD_REF)
        self.assertEqual(payload["base_ref"], p.BASE_REF)
        self.assertIs(payload["create_pull_request"], False)
        self.assertIn(p.TASK_MARKER, payload["prompt"])
        self.assertIn("d" * 40, payload["prompt"])
        self.assertIn("independent", payload["prompt"])

    def test_rejects_bad_head(self):
        with self.assertRaises(p.PilotError):
            p.task_payload("not-a-commit")

    def test_exact_pr_identity_enforced(self):
        self.assertEqual(p.validate_pr(sample_pr()), "a" * 40)
        for field, value in [
            ("draft", False), ("state", "closed"), ("number", 28)
        ]:
            case = sample_pr()
            case[field] = value
            with self.subTest(field=field), self.assertRaises(p.PilotError):
                p.validate_pr(case)
        case = sample_pr()
        case["head"]["ref"] = "main"
        with self.assertRaises(p.PilotError):
            p.validate_pr(case)

    def test_pr_repo_mismatch_denied(self):
        case = sample_pr()
        case["head"]["repo"]["full_name"] = "other/repository"
        with self.assertRaises(p.PilotError):
            p.validate_pr(case)

    def test_preflight_read_only(self):
        api = FakeClient()
        sha, active = p.preflight(api)
        self.assertEqual(sha, "a" * 40)
        self.assertEqual(active, [])
        self.assertEqual(api.post_calls, [])
        self.assertEqual(len(api.get_calls), 2)

    def test_active_task_blocks_entire_pilot(self):
        api, store = FakeClient(), FakeStore()
        api.active = [{"state": "in_progress", "id": "another-task"}]
        with self.assertRaisesRegex(p.PilotError, "active agent"):
            p.dispatch(api, store, "I_AUTHORIZE_ONE_AGENT_TASK", "ZERO_OVERAGES_CONFIRMED")
        self.assertEqual(api.post_calls, [])
        self.assertFalse(store.branch_created)

    def test_unknown_task_listing_blocks(self):
        api = FakeClient()
        api.active = [{"id": "task-without-state"}]
        with self.assertRaises(p.PilotError):
            p.preflight(api)

    def test_page_limit_blocks(self):
        api = FakeClient()
        api.active = [{"state": "queued", "id": str(i)} for i in range(100)]
        with self.assertRaisesRegex(p.PilotError, "pagination"):
            p.preflight(api)

    def test_no_confirmation_no_state_write(self):
        api, store = FakeClient(), FakeStore()
        for task, billing in [
            ("", ""), ("I_AUTHORIZE_ONE_AGENT_TASK", ""),
            ("", "ZERO_OVERAGES_CONFIRMED")
        ]:
            with self.subTest(task=task, billing=billing), self.assertRaises(p.PilotError):
                p.dispatch(api, store, task, billing)
        self.assertEqual(store.history, [])
        self.assertEqual(api.post_calls, [])

    def test_one_dispatch_reserves_before_post(self):
        api, store = FakeClient(), FakeStore()
        result = p.dispatch(api, store, "I_AUTHORIZE_ONE_AGENT_TASK", "ZERO_OVERAGES_CONFIRMED")
        self.assertEqual(store.history, ["RESERVED", "DISPATCHED"])
        self.assertEqual(result["ticket"]["status"], "DISPATCHED")
        self.assertEqual(len(api.post_calls), 1)
        self.assertEqual(api.post_calls[0][0], p.AGENT_PATH)
        self.assertEqual(result["independent_semantic_approvals"], 0)
        with self.assertRaisesRegex(p.PilotError, "already reserved"):
            p.dispatch(api, store, "I_AUTHORIZE_ONE_AGENT_TASK", "ZERO_OVERAGES_CONFIRMED")
        self.assertEqual(len(api.post_calls), 1)

    def test_post_error_retains_reservation_no_automatic_retry(self):
        api, store = FakeClient(), FakeStore()
        api.post_failure = True
        with self.assertRaises(p.PilotError):
            p.dispatch(api, store, "I_AUTHORIZE_ONE_AGENT_TASK", "ZERO_OVERAGES_CONFIRMED")
        self.assertEqual(store.history, ["RESERVED"])
        self.assertEqual(store.value["ticket"]["status"], "RESERVED")
        self.assertEqual(len(api.post_calls), 1)
        with self.assertRaisesRegex(p.PilotError, "already reserved"):
            p.dispatch(api, store, "I_AUTHORIZE_ONE_AGENT_TASK", "ZERO_OVERAGES_CONFIRMED")
        self.assertEqual(len(api.post_calls), 1)

    def test_pr_head_change_after_reservation_blocks(self):
        api, store = FakeClient(), FakeStore()
        original_get = api.get
        reads = [0]
        def get(path):
            if path == p.REPO_PATH + "/pulls/27":
                reads[0] += 1
                if reads[0] == 2:
                    changed = sample_pr("f" * 40)
                    return changed
            return original_get(path)
        api.get = get
        with self.assertRaisesRegex(p.PilotError, "changed"):
            p.dispatch(api, store, "I_AUTHORIZE_ONE_AGENT_TASK", "ZERO_OVERAGES_CONFIRMED")
        self.assertEqual(store.history, ["RESERVED"])
        self.assertEqual(api.post_calls, [])

    def test_completed_is_not_semantic_approval(self):
        api, store = FakeClient(), FakeStore()
        p.dispatch(api, store, "I_AUTHORIZE_ONE_AGENT_TASK", "ZERO_OVERAGES_CONFIRMED")
        task_id = store.value["ticket"]["task_id"]
        api.task_details[task_id] = {"id": task_id, "state": "completed"}
        report = p.inspect(api, store)
        self.assertEqual(report["status"], "AWAITING_REVIEW")
        self.assertEqual(report["independent_semantic_approvals"], 0)
        self.assertEqual(store.history[-1], "AWAITING_REVIEW")
        self.assertEqual(len(api.post_calls), 1)

    def test_failed_task_is_blocked_not_retried(self):
        api, store = FakeClient(), FakeStore()
        p.dispatch(api, store, "I_AUTHORIZE_ONE_AGENT_TASK", "ZERO_OVERAGES_CONFIRMED")
        task_id = store.value["ticket"]["task_id"]
        api.task_details[task_id] = {"id": task_id, "state": "failed"}
        self.assertEqual(p.inspect(api, store)["status"], "BLOCKED")
        self.assertEqual(len(api.post_calls), 1)

    def test_reserved_requires_manual_reconciliation(self):
        api, store = FakeClient(), FakeStore()
        api.post_failure = True
        with self.assertRaises(p.PilotError):
            p.dispatch(api, store, "I_AUTHORIZE_ONE_AGENT_TASK", "ZERO_OVERAGES_CONFIRMED")
        report = p.inspect(api, store)
        self.assertEqual(report["status"], "NEEDS_MANUAL_RECONCILIATION")

    def test_ledger_validation_fails_closed(self):
        cases = [
            {"schema": 42, "marker": p.TASK_MARKER, "ticket": {}},
            {"schema": 1, "marker": "bad", "ticket": {}},
            {"schema": 1, "marker": p.TASK_MARKER,
             "ticket": {"package_id": p.TASK_MARKER, "status": "APPROVED"}},
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(p.PilotError):
                p.validate_ledger(case)



class FakeStateAPI:
    """Exercise the actual GitHub contents CAS request shape without the network."""

    def __init__(self):
        self.branch = False
        self.contents = None
        self.sha = "first-blob"

    def get(self, path):
        if "/git/ref/heads/" in path:
            if not self.branch:
                raise p.ApiError(404, path)
            return {"object": {"sha": "branch-sha"}}
        if path.endswith("/git/ref/heads/main"):
            return {"object": {"sha": "main-sha"}}
        if "/contents/" in path:
            if self.contents is None:
                raise p.ApiError(404, path)
            return {"sha": self.sha, "content": self.contents}
        raise AssertionError(path)

    def post(self, path, payload):
        assert path.endswith("/git/refs")
        assert payload["ref"] == "refs/heads/" + p.STATE_BRANCH
        self.branch = True
        return {"ref": payload["ref"]}

    def put(self, path, payload):
        assert path.endswith("/contents/" + p.STATE_PATH)
        assert payload["branch"] == p.STATE_BRANCH
        if self.contents is None:
            if "sha" in payload:
                raise p.ApiError(409, path)
        elif payload.get("sha") != self.sha:
            raise p.ApiError(409, path)
        self.contents = payload["content"]
        self.sha = "next-blob"
        return {"content": {"sha": self.sha}}


class StateStoreTests(unittest.TestCase):
    def test_real_encoded_contents_and_cas(self):
        api = FakeStateAPI()
        store = p.StateStore(api)
        store.ensure_branch()
        self.assertTrue(api.branch)
        self.assertEqual(store.load(), (None, None))
        state = {
            "schema": 1, "marker": p.TASK_MARKER, "independent_semantic_approvals": 0,
            "ticket": {"package_id": p.TASK_MARKER, "status": "RESERVED",
                       "baseline_head_sha": "a" * 40, "task_id": None},
        }
        sha = store.save(state, None)
        self.assertEqual(sha, "next-blob")
        self.assertEqual(json.loads(base64.b64decode(api.contents)), state)
        loaded, current = store.load()
        self.assertEqual((loaded, current), (state, sha))
        with self.assertRaises(p.ApiError):
            store.save(state, "stale-blob")

    def test_ledger_cannot_claim_independent_approvals(self):
        state = {
            "schema": 1, "marker": p.TASK_MARKER, "independent_semantic_approvals": 1,
            "ticket": {"package_id": p.TASK_MARKER, "status": "AWAITING_REVIEW"},
        }
        with self.assertRaisesRegex(p.PilotError, "semantic approval"):
            p.validate_ledger(state)

if __name__ == "__main__":
    unittest.main()
