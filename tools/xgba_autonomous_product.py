#!/usr/bin/env python3
"""Bounded autonomous XGBA PRODUCT deliveries, not blanket semantic approvals.

Uses the already live-tested Copilot Pro Agent Tasks API and an isolated CAS ledger.
One active task max, no automatic merges, no legacy 14,834-file audit queue.
"""
from __future__ import annotations
import argparse
import base64
from datetime import datetime, timezone
import json
import os
import re
import sys
import urllib.parse

from tools.phase1_agent_task_pilot import (
    GitHub, ApiError, PilotError, AGENT_PATH, REPO, REPO_PATH,
    canonical, live_tasks,
)

PR = 40
HEAD = "phase1/xgba-optin-resource-prototype-20261110"
BASE = "main"
STATE_BRANCH = "xgba-autonomous-product-state"
STATE_PATH = ".xgba-autonomy/ledger.json"
WORKFLOW_NAME = "XGBA opt-in resource prototype CI"
MAX_PER_UTC_DAY = 3
ACTIVE = {"queued", "in_progress", "waiting_for_user", "idle"}
FAILED = {"failed", "cancelled", "timed_out"}
NO_APPROVALS = 0

PACKAGES = (
    {
        "id": "R1_STREAMING_SIDECAR",
        "files": ("tools/xgba_resource_sidecar.py", "tests/test_xgba_resource_sidecar.py"),
        "goal": (
            "Implement a small, versioned, opt-in host-side resource manifest and "
            "streaming reader for >32 MiB assets (sparse 96 MiB test fixture). "
            "Support stable resource IDs, bounded 64-bit offsets/length, source "
            "identity and per-resource SHA-256. Reject malformed metadata, duplicate "
            "IDs, truncated content, path escape, overflow, out-of-bounds and "
            "hash mismatches. Load bounded chunks only, never all 96 MiB. "
            "Deliver actual code and positive/negative unit tests."
        ),
    },
    {
        "id": "R2_DETERMINISTIC_PACKER",
        "files": ("tools/xgba_resource_pack.py", "tests/test_xgba_resource_pack.py"),
        "goal": (
            "Using existing R1 sidecar parser, implement deterministic resource-pack "
            "creation with stable IDs, canonical sorted manifest, binary payload "
            "integrity, streaming I/O, rollback on write failure, and atomic publication. "
            "Negative tests for duplicate IDs, corruption and non-atomic failure. "
            "Avoid rewriting the R1 code unless a strictly necessary tiny fix with tests."
        ),
    },
    {
        "id": "R3_OPTIN_HOST_BRIDGE",
        "files": ("tools/xgba_resource_bridge.py", "tests/test_xgba_resource_bridge.py"),
        "goal": (
            "Implement a small opt-in host staging proof using R1/R2 APIs. "
            "Keep original 32 MiB ROM pointer and native cartridge mapping unchanged. "
            "Stage only bounded named resources into explicit host buffers. "
            "Test repeated open/close and replacement, wrong ROM identity, savestate "
            "identity drift and failure rollback. Tests must assert the native Matrix, "
            "EEPROM/e-Reader and original Flash routes are NOT intercepted. "
            "Do not edit mGBA, FireRed or Porymap upstream sources; this is a prototype."
        ),
    },
)


def now():
    return datetime.now(timezone.utc)


def new_state():
    return {"schema": 1, "repository": REPO, "target_pr": PR,
            "next": 0, "current": None, "history": [],
            "daily_dispatches": {}, "independent_semantic_approvals": 0}


def verify_state(state):
    if not isinstance(state, dict) or state.get("schema") != 1:
        raise PilotError("Unrecognised autonomous state; refusing dispatch")
    if (state.get("repository"), state.get("target_pr"),
        state.get("independent_semantic_approvals")) != (REPO, PR, 0):
        raise PilotError("State identity or semantic-approval assertion altered")
    idx = state.get("next")
    if type(idx) is not int or not 0 <= idx <= len(PACKAGES):
        raise PilotError("Invalid workpack cursor")
    history = state.get("history")
    counts = state.get("daily_dispatches")
    if not isinstance(history, list) or not isinstance(counts, dict):
        raise PilotError("Invalid history or quota ledger")
    if len(history) != idx:
        raise PilotError("History length does not match package cursor")
    for i, entry in enumerate(history):
        if (not isinstance(entry, dict) or
            entry.get("package") != PACKAGES[i]["id"] or
            entry.get("status") != "DELIVERED_AWAITING_INDEPENDENT_REVIEW" or
            entry.get("review_approved") is not False or
            not isinstance(entry.get("task_id"), str) or
            not re.fullmatch(r"[A-Za-z0-9-]{8,128}", entry["task_id"]) or
            not isinstance(entry.get("head"), str) or
            not re.fullmatch(r"[0-9a-f]{40}", entry["head"])):
            raise PilotError("Unverified or out-of-order delivery history")
    for day, count in counts.items():
        if (not isinstance(day, str) or
            not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) or
            type(count) is not int or
            count < 0 or count > MAX_PER_UTC_DAY):
            raise PilotError("Invalid historical daily dispatch count")
    current = state.get("current")
    if current is not None:
        if idx >= len(PACKAGES) or not isinstance(current, dict):
            raise PilotError("Cannot have active workpack after queue is exhausted")
        if current.get("id") != PACKAGES[idx]["id"]:
            raise PilotError("Unknown active workpack")
        if current.get("status") not in {"RESERVED", "DISPATCHED", "WAIT_CI", "BLOCKED"}:
            raise PilotError("Invalid current status")
        checks = current.get("ci_wait_checks", 0)
        if type(checks) is not int or checks < 0 or checks > 6:
            raise PilotError("Invalid CI wait count")


def pr_head(api):
    pr = api.get(REPO_PATH + "/pulls/" + str(PR))
    h, b = pr.get("head") or {}, pr.get("base") or {}
    if (pr.get("number") != PR or pr.get("state") != "open" or
        pr.get("draft") is not True or h.get("ref") != HEAD or
        b.get("ref") != BASE or
        (h.get("repo") or {}).get("full_name") != REPO or
        (b.get("repo") or {}).get("full_name") != REPO):
        raise PilotError("Product PR #40 identity/status changed; refusing work")
    sha = h.get("sha", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise PilotError("No exact product PR HEAD")
    return sha


class Ledger:
    def __init__(self, api):
        self.api = api

    def ensure(self):
        path = REPO_PATH + "/git/ref/heads/" + urllib.parse.quote(STATE_BRANCH, safe="")
        try:
            self.api.get(path)
            return
        except ApiError as e:
            if e.code != 404:
                raise
        head = self.api.get(REPO_PATH + "/git/ref/heads/main")["object"]["sha"]
        try:
            self.api.post(REPO_PATH + "/git/refs", {"ref": "refs/heads/" + STATE_BRANCH, "sha": head})
        except ApiError as e:
            if e.code != 422:
                raise
            self.api.get(path)

    def load(self):
        try:
            reply = self.api.get(REPO_PATH + "/contents/" + STATE_PATH + "?ref=" + STATE_BRANCH)
        except ApiError as e:
            if e.code == 404:
                return new_state(), None
            raise
        try:
            state = json.loads(base64.b64decode(reply["content"]).decode("utf-8"))
            blob = reply["sha"]
        except (KeyError, ValueError, TypeError, UnicodeDecodeError) as e:
            raise PilotError("Invalid ledger bytes; fail closed") from e
        verify_state(state)
        return state, blob

    def save(self, state, sha):
        verify_state(state)
        payload = {"branch": STATE_BRANCH, "message": "XGBA bounded autonomous product ledger (no approvals)",
                   "content": base64.b64encode(canonical(state)).decode("ascii")}
        if sha:
            payload["sha"] = sha
        reply = self.api.put(REPO_PATH + "/contents/" + STATE_PATH, payload)
        new_sha = (reply.get("content") or {}).get("sha")
        if not new_sha:
            raise PilotError("Ledger write outcome uncertain; do not retry")
        return new_sha


def prompt_for(pkg, head):
    return (
        "XGBA_AUTONOMOUS_PRODUCT " + pkg["id"] + " BASELINE " + head + "\n"
        "Execute one substantial implementation package on EXISTING draft PR #40 "
        "(head_ref=" + HEAD + ", base_ref=main). Do NOT create a branch or PR. "
        "Check HEAD and the latest discussions before editing. "
        "Read docs/XGBA_RESOURCE_PROTOTYPE_REUSE_20261110.md and existing "
        "tests/mgba_bank_boundary.c. Standard GBA memory layout and Matrix "
        "64 MiB bank-switching have ALREADY been documented and tested in XGBA: "
        "do NOT recreate, re-review or recount those tests. "
        "Package: " + pkg["goal"] + "\n"
        "REQUIRED OUTPUT FILES: " + ", ".join(pkg["files"]) + ". "
        "Run python3 -m unittest discover -s tests -p 'test_xgba_resource_*.py' -v. "
        "Commit meaningful working source and negative controls, not plans alone. "
        "Strictly limit changed paths to the required output files and, only if "
        "necessary, docs/XGBA_RESOURCE_PROTOTYPE_REUSE_20261110.md. "
        "No main merge, no source pin/gate changes, no independent approval claims, "
        "no Phase 1 done claims, no new repository, no vendor code copied without "
        "licence compliance. If blocked, report a precise BLOCKED outcome."
    )


def has_required_changes(api, baseline, head, pkg):
    cmp = api.get(REPO_PATH + "/compare/" + baseline + "..." + head)
    if cmp.get("status") != "ahead" or not isinstance(cmp.get("files"), list):
        return False, "No forward changed-file diff"
    changed = {f.get("filename") for f in cmp["files"]}
    allowed = set(pkg["files"]) | {"docs/XGBA_RESOURCE_PROTOTYPE_REUSE_20261110.md"}
    if changed - allowed:
        return False, "Unexpected paths in code delta: " + ", ".join(sorted(changed - allowed)[:5])
    if not set(pkg["files"]).issubset(changed):
        return False, "Required source and test changes missing"
    for path in pkg["files"]:
        try:
            f = api.get(REPO_PATH + "/contents/" + path + "?ref=" + head)
            if f.get("type") != "file" or f.get("size", 0) < 250:
                return False, "Expected substantive code/test file absent: " + path
        except ApiError:
            return False, "Expected source/test absent: " + path
    return True, "Source and test code changes confirmed"


def ci_gate(api, head):
    runs = api.get(REPO_PATH + "/actions/runs?head_sha=" + head + "&per_page=100")
    if not isinstance(runs.get("workflow_runs"), list) or runs.get("total_count", 0) > 100:
        return "WAIT", "CI run list unavailable/incomplete"
    exact = [x for x in runs["workflow_runs"]
             if x.get("name") == WORKFLOW_NAME and
             x.get("head_sha") == head and x.get("event") in ("push", "pull_request")]
    if any(x.get("conclusion") in ("failure", "timed_out", "cancelled") for x in exact):
        return "BLOCKED", "Required prototype CI failed/cancelled"
    if not exact or any(x.get("status") != "completed" for x in exact):
        return "WAIT", "Waiting for exact-head prototype CI"
    if not any(x.get("conclusion") == "success" for x in exact):
        return "WAIT", "No successful exact-head prototype CI"
    return "PASS", "Exact-head product CI successful; not independent signoff"


def report(status, **kwargs):
    print(json.dumps({"result": status, "independent_semantic_approvals": 0, **kwargs}, sort_keys=True))


def run(api):
    if os.environ.get("GITHUB_REPOSITORY") != REPO or os.environ.get("XGBA_AUTONOMY_ENABLED") != "1":
        raise PilotError("Autonomous mode must be deliberately enabled for XGBA only")
    head = pr_head(api)
    active = live_tasks(api)
    ledger = Ledger(api)
    ledger.ensure()
    state, blob = ledger.load()
    current = state["current"]

    if current:
        if current["status"] in ("RESERVED", "BLOCKED"):
            report("NEEDS_MANUAL_RECONCILIATION", package=current["id"], status=current["status"])
            return
        tid = current["task_id"]
        detail = api.get(AGENT_PATH + "/" + urllib.parse.quote(tid, safe=""))
        if detail.get("id") != tid:
            raise PilotError("Task identity mismatched")
        status = detail.get("state")
        if status in ACTIVE:
            report("AGENT_ACTIVE", package=current["id"], state=status, task_id=tid)
            return
        if status in FAILED:
            current["status"] = "BLOCKED"
            current["reason"] = "Copilot task ended: " + status
            ledger.save(state, blob)
            report("BLOCKED", package=current["id"], reason=current["reason"])
            return
        if status != "completed":
            raise PilotError("Unknown agent task state; fail closed")
        pkg = PACKAGES[state["next"]]
        if head == current["baseline"]:
            current["status"] = "BLOCKED"
            current["reason"] = "Task finished with no new PR commit"
            ledger.save(state, blob)
            report("BLOCKED", package=current["id"], reason=current["reason"])
            return
        changes_ok, description = has_required_changes(api, current["baseline"], head, pkg)
        if not changes_ok:
            current["status"] = "BLOCKED"
            current["reason"] = description
            ledger.save(state, blob)
            report("BLOCKED", package=current["id"], reason=description)
            return
        ci, reason = ci_gate(api, head)
        if ci == "WAIT":
            current["ci_wait_checks"] = current.get("ci_wait_checks", 0) + 1
            if current["ci_wait_checks"] >= 6:
                current["status"] = "BLOCKED"
                current["reason"] = "Exact-head CI remained unverified after six scheduled checks: " + reason
                ledger.save(state, blob)
                report("BLOCKED", package=current["id"], reason=current["reason"])
                return
            current["status"] = "WAIT_CI"
            ledger.save(state, blob)
            report("WAIT_CI", package=current["id"], checks=current["ci_wait_checks"], reason=reason)
            return
        if ci == "BLOCKED":
            current["status"] = "BLOCKED"
            current["reason"] = reason
            ledger.save(state, blob)
            report("BLOCKED", package=current["id"], reason=reason)
            return
        state["history"].append({"package": current["id"], "task_id": tid,
                                 "head": head, "status": "DELIVERED_AWAITING_INDEPENDENT_REVIEW",
                                 "review_approved": False})
        state["next"] += 1
        state["current"] = None
        blob = ledger.save(state, blob)
        report("DELIVERY_RECORDED", package=pkg["id"], exact_head=head,
               note="Only code and CI; not independent semantic approval")

    if state["next"] == len(PACKAGES):
        report("QUEUE_DONE_AWAITING_REVIEW", delivered=len(state["history"]))
        return
    # Re-list active agents immediately before paid POST to avoid overlapping
    # external/manual tasks; requires zero outstanding tasks in whole repository.
    if active or live_tasks(api):
        report("WAIT_OTHER_AGENT", active_task_count=len(active))
        return
    day = now().date().isoformat()
    if state["daily_dispatches"].get(day, 0) >= MAX_PER_UTC_DAY:
        report("DAILY_CAP_REACHED", daily_cap=MAX_PER_UTC_DAY)
        return
    pkg = PACKAGES[state["next"]]
    checked = pr_head(api)
    if checked != head:
        raise PilotError("PR changed during dispatcher; not posting")
    state["current"] = {"id": pkg["id"], "status": "RESERVED", "baseline": head,
                        "task_id": None, "created_at": now().isoformat()}
    blob = ledger.save(state, blob)  # Reservation BEFORE billable POST.
    if pr_head(api) != head or live_tasks(api):
        report("RESERVED_RECONCILE", reason="PR/queue changed after reservation")
        return
    # Exactly one paid-capable POST. Any unknown outcome preserves RESERVED.
    response = api.post(AGENT_PATH, {
        "prompt": prompt_for(pkg, head), "head_ref": HEAD,
        "base_ref": BASE, "create_pull_request": False,
    })
    task_id = response.get("id")
    if not isinstance(task_id, str) or not re.fullmatch("[a-zA-Z0-9-]{8,128}", task_id):
        raise PilotError("Ambiguous task API result; reservation retained")
    state["current"]["status"] = "DISPATCHED"
    state["current"]["task_id"] = task_id
    state["daily_dispatches"][day] = state["daily_dispatches"].get(day, 0) + 1
    ledger.save(state, blob)
    report("DISPATCHED", package=pkg["id"], task_id=task_id,
           daily_count=state["daily_dispatches"][day])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("dry-run", "run"), default="dry-run")
    args = parser.parse_args()
    if args.mode == "dry-run":
        for pkg in PACKAGES:
            assert len(pkg["files"]) == 2
            assert pkg["files"][0].startswith("tools/xgba_resource_")
            assert pkg["files"][1].startswith("tests/test_xgba_resource_")
            assert pkg["id"] in prompt_for(pkg, "0" * 40)
        verify_state(new_state())
        report("OFFLINE_CHECK_PASSED", total_packages=len(PACKAGES))
        return
    api = GitHub(os.environ.get("XGBA_COPILOT_AGENT_PAT", ""))
    run(api)


if __name__ == "__main__":
    try:
        main()
    except (PilotError, KeyError, ValueError, TypeError) as e:
        print("BLOCKED:", str(e), file=sys.stderr)
        sys.exit(2)
