#!/usr/bin/env python3
"""Opt-in Copilot Pro Agent Tasks pilot for XGBA Phase 1.

One existing draft PR, one task maximum, durable fail-closed reservation.
Never confuses Copilot completion with independent semantic approval.
Requires a user PAT (not GITHUB_TOKEN); no scheduled or implicit dispatch.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = "xbaconator9000x/XGBA-ROM-Expansion"
PR_NUMBER = 27
HEAD_REF = "phase1/porymap-full-qt-project-roundtrip-20261028"
BASE_REF = "phase1/porymap-qt-writer-failure-boundary-20261027"
STATE_BRANCH = "phase1-agent-pilot-state"
STATE_PATH = ".phase1-agent-pilot/ledger.json"
ACTIVE_STATES = frozenset({"queued", "in_progress", "idle", "waiting_for_user"})
FINISHED_STATES = frozenset({"completed", "failed", "timed_out", "cancelled"})
AGENT_PATH = "/agents/repos/" + REPO + "/tasks"
REPO_PATH = "/repos/" + REPO
TASK_MARKER = "XGBA_PHASE1_PILOT_PORYMAP_001"
TASK_LIMIT = 1


class PilotError(RuntimeError):
    pass


class ApiError(PilotError):
    def __init__(self, code, path):
        self.code = code
        super().__init__(
            "GitHub HTTP %s at %s. Check PAT permissions, repository access, "
            "or API preview availability. Response suppressed." % (code, path.split("?")[0])
        )


def canonical(data):
    return (json.dumps(data, sort_keys=True, indent=2) + "\n").encode("utf-8")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class GitHub:
    def __init__(self, token):
        if not token:
            raise PilotError(
                "XGBA_COPILOT_AGENT_PAT is missing; use a user PAT with Agent tasks "
                "read/write and repository Contents read/write. Never use GITHUB_TOKEN."
            )
        self.token = token

    def call(self, method, path, payload=None):
        if not path.startswith(AGENT_PATH) and not path.startswith(REPO_PATH):
            raise PilotError("Unexpected API path")
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10" if path.startswith(AGENT_PATH) else "2022-11-28",
            "User-Agent": "XGBA-Phase1-Agent-Pilot",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            "https://api.github.com" + path, headers=headers, data=data, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                contents = response.read()
                return json.loads(contents) if contents else {}
        except urllib.error.HTTPError as error:
            error.read()  # Never print a potentially sensitive error body.
            raise ApiError(error.code, path) from None
        except (urllib.error.URLError, TimeoutError) as error:
            raise PilotError("GitHub API not reachable; no automatic retry: " + type(error).__name__) from None

    def get(self, path):
        return self.call("GET", path)

    def post(self, path, payload):
        return self.call("POST", path, payload)

    def put(self, path, payload):
        return self.call("PUT", path, payload)


def validate_pr(pr):
    if pr.get("number") != PR_NUMBER or pr.get("state") != "open" or pr.get("draft") is not True:
        raise PilotError("PR #27 must remain an open draft")
    head, base = pr.get("head") or {}, pr.get("base") or {}
    if (
        head.get("ref") != HEAD_REF
        or base.get("ref") != BASE_REF
        or (head.get("repo") or {}).get("full_name") != REPO
        or (base.get("repo") or {}).get("full_name") != REPO
    ):
        raise PilotError("PR #27 branch/repository identity has changed")
    sha = head.get("sha", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise PilotError("Missing exact PR head SHA")
    return sha


def live_tasks(client):
    # Filter server-side; do not mistake a page of completed tasks for a clear queue.
    query = "?per_page=100&state=queued%2Cin_progress%2Cidle%2Cwaiting_for_user"
    result = client.get(AGENT_PATH + query)
    tasks = result.get("tasks")
    if not isinstance(tasks, list) or len(tasks) >= 100:
        raise PilotError("Active-task list missing or pagination uncertain; fail closed")
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("state"), str):
            raise PilotError("Unexpected agent task API response")
    return [task for task in tasks if task["state"] in ACTIVE_STATES]


def preflight(client):
    pr = client.get(REPO_PATH + "/pulls/" + str(PR_NUMBER))
    sha = validate_pr(pr)
    active = live_tasks(client)
    return sha, active


def task_payload(sha):
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise PilotError("Cannot dispatch without exact head SHA")
    prompt = (
        TASK_MARKER + "\n"
        "PHASE 1 ONLY, on the EXISTING draft PR #27 branch (do not create another PR).\n"
        "Start by checking current HEAD against this pinned baseline: " + sha + ". "
        "If HEAD differs or another agent owns this scope, STOP and report BLOCKED.\n"
        "Review a NEW, dependency-connected Porymap source scope actually present in "
        "pinned upstream revision 26b919d7ff4b54152de010abd5bf344af2ebe116. "
        "Avoid previously reviewed scopes and all other active assignments. "
        "Produce original-source-identity evidence, meaningful positive and negative "
        "regressions, and a precise changed-path summary. Do NOT claim independent "
        "semantic approvals or a finished expansion runtime. Keep edits within the "
        "existing draft PR branch; do not merge, create a PR or branch, modify "
        "main, source pins, semantic approval gate, or unrelated repositories. "
        "If blocked, say BLOCKED with the reason; never invent a completion receipt."
    )
    return {
        "prompt": prompt,
        "base_ref": BASE_REF,
        "head_ref": HEAD_REF,
        "create_pull_request": False,
    }


def validate_ledger(data):
    if data is None:
        return
    if not isinstance(data, dict) or data.get("schema") != 1 or data.get("marker") != TASK_MARKER:
        raise PilotError("Unknown state ledger; manual reconciliation required")
    ticket = data.get("ticket")
    if not isinstance(ticket, dict) or ticket.get("status") not in {
        "RESERVED", "DISPATCHED", "AWAITING_REVIEW", "BLOCKED"
    }:
        raise PilotError("Invalid reservation state; fail closed")
    if ticket.get("package_id") != TASK_MARKER:
        raise PilotError("Unknown package identity")


class StateStore:
    """A compare-and-swap contents file on an isolated GitHub state branch."""

    def __init__(self, client):
        self.client = client

    def ensure_branch(self):
        ref_path = REPO_PATH + "/git/ref/heads/" + urllib.parse.quote(STATE_BRANCH, safe="")
        try:
            self.client.get(ref_path)
            return
        except ApiError as error:
            if error.code != 404:
                raise
        main = self.client.get(REPO_PATH + "/git/ref/heads/main")["object"]["sha"]
        try:
            self.client.post(
                REPO_PATH + "/git/refs",
                {"ref": "refs/heads/" + STATE_BRANCH, "sha": main},
            )
        except ApiError as error:
            if error.code != 422:
                raise
            self.client.get(ref_path)  # Branch created concurrently.

    def load(self):
        path = REPO_PATH + "/contents/" + STATE_PATH + "?ref=" + STATE_BRANCH
        try:
            response = self.client.get(path)
        except ApiError as error:
            if error.code == 404:
                return None, None
            raise
        try:
            data = json.loads(base64.b64decode(response["content"]).decode("utf-8"))
            sha = response["sha"]
        except (KeyError, ValueError, TypeError, UnicodeDecodeError) as error:
            raise PilotError("Cannot decode existing state; fail closed") from error
        validate_ledger(data)
        return data, sha

    def save(self, data, old_sha):
        validate_ledger(data)
        payload = {
            "branch": STATE_BRANCH,
            "message": "Record XGBA Copilot task pilot state (not a semantic approval)",
            "content": base64.b64encode(canonical(data)).decode("ascii"),
        }
        if old_sha:
            payload["sha"] = old_sha
        response = self.client.put(REPO_PATH + "/contents/" + STATE_PATH, payload)
        new_sha = (response.get("content") or {}).get("sha")
        if not new_sha:
            raise PilotError("GitHub did not confirm state contents SHA")
        return new_sha


def dispatch(client, store, confirm_task, confirm_billing):
    # Two independent deliberate controls: no scheduled/implicit paid work.
    if confirm_task != "I_AUTHORIZE_ONE_AGENT_TASK" or confirm_billing != "ZERO_OVERAGES_CONFIRMED":
        raise PilotError("Dispatch disabled: task and zero-overages confirmations both required")
    head, active = preflight(client)
    if active:
        raise PilotError("Existing active agent tasks: refusing duplicate or overlapping dispatch")
    store.ensure_branch()
    existing, old_sha = store.load()
    if existing is not None:
        raise PilotError("Pilot already reserved or dispatched; manual reconciliation required")
    state = {
        "schema": 1,
        "marker": TASK_MARKER,
        "independent_semantic_approvals": 0,
        "ticket": {
            "package_id": TASK_MARKER,
            "status": "RESERVED",
            "baseline_head_sha": head,
            "task_id": None,
            "observed_task_state": None,
            "reserved_at": utc_now(),
        },
    }
    old_sha = store.save(state, old_sha)  # Reserve BEFORE billable POST.
    fresh = client.get(REPO_PATH + "/pulls/" + str(PR_NUMBER))
    if validate_pr(fresh) != head or live_tasks(client):
        raise PilotError("PR head or queue changed after reservation; investigate before retry")
    # Exactly one POST. An ambiguous network failure keeps RESERVED; never retry blindly.
    result = client.post(AGENT_PATH, task_payload(head))
    task_id = result.get("id")
    if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9-]{8,128}", task_id):
        raise PilotError("Task POST outcome ambiguous; reservation retained for reconciliation")
    state["ticket"].update({
        "status": "DISPATCHED",
        "task_id": task_id,
        "observed_task_state": result.get("state"),
    })
    store.save(state, old_sha)
    return state


def inspect(client, store):
    # Read-only API check first; no new task can be launched from this mode.
    preflight(client)
    state, old_sha = store.load()
    if state is None:
        return {"status": "NOT_STARTED"}
    ticket = state["ticket"]
    if ticket["status"] == "RESERVED":
        return {"status": "NEEDS_MANUAL_RECONCILIATION", "marker": TASK_MARKER}
    if ticket["status"] in {"AWAITING_REVIEW", "BLOCKED"}:
        return {"status": ticket["status"], "task_id": ticket["task_id"]}
    task_id = ticket.get("task_id")
    if not isinstance(task_id, str):
        raise PilotError("Dispatched ticket missing task ID")
    detail = client.get(AGENT_PATH + "/" + urllib.parse.quote(task_id, safe=""))
    if detail.get("id") != task_id:
        raise PilotError("Agent task ID mismatch")
    observed = detail.get("state")
    if observed not in ACTIVE_STATES | FINISHED_STATES:
        raise PilotError("Unknown agent state; fail closed")
    ticket["observed_task_state"] = observed
    if observed == "completed":
        ticket["status"] = "AWAITING_REVIEW"
    elif observed in FINISHED_STATES:
        ticket["status"] = "BLOCKED"
    if ticket["status"] != "DISPATCHED":
        store.save(state, old_sha)
    return {"status": ticket["status"], "task_id": task_id, "observed_state": observed,
            "independent_semantic_approvals": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("dry-run", "preflight", "inspect", "dispatch"),
                        default="dry-run")
    args = parser.parse_args()
    if os.environ.get("GITHUB_REPOSITORY", REPO) != REPO:
        raise PilotError("Repository mismatch: pilot is XGBA-only")
    if args.mode == "dry-run":
        # No credentials or API requests: zero tasks created.
        print(json.dumps({"mode": args.mode, "repo": REPO, "pr": PR_NUMBER,
                          "payload": task_payload("0" * 40),
                          "billable_tasks_created": 0}, sort_keys=True))
        return
    client = GitHub(os.environ.get("XGBA_COPILOT_AGENT_PAT", ""))
    if args.mode == "preflight":
        sha, active = preflight(client)
        print(json.dumps({"mode": args.mode, "pr_head_sha": sha,
                          "active_task_count": len(active), "billable_tasks_created": 0,
                          "note": "Read access proven; write permission and billing cannot be proven without a POST."}))
    elif args.mode == "inspect":
        print(json.dumps(inspect(client, StateStore(client)), sort_keys=True))
    elif args.mode == "dispatch":
        state = dispatch(client, StateStore(client),
                         os.environ.get("XGBA_CONFIRM_TASK", ""),
                         os.environ.get("XGBA_CONFIRM_ZERO_OVERAGES", ""))
        print(json.dumps({"status": state["ticket"]["status"],
                          "task_id": state["ticket"]["task_id"],
                          "independent_semantic_approvals": 0}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except PilotError as exc:
        print("BLOCKED:", exc, file=sys.stderr)
        sys.exit(2)
