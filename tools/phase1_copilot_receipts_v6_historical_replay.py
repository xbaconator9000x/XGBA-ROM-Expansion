#!/usr/bin/env python3
"""Replay immutable evidence for the original seven-receipt v6 validation only."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

import phase1_copilot_receipts_v4_adapter as v4
import phase1_copilot_receipts_v6_adapter as v6

HISTORICAL_PR2_HEAD = "efcd6f2fcd6342c583dd67d38c3fde73e5fb582b"
HISTORICAL_PR2_ADAPTER_BLOB = "2209fb7c5ec776c107eb47870aeb29b0fffc1636"
HISTORICAL_PR2_WORKFLOW_BLOB = "2439bf050e77953044455498ea7064d095c90092"
HISTORICAL_PR2_RUN_ID = 41379058968
HISTORICAL_PR2_RUN_ATTEMPT = 3
HISTORICAL_PR2_WORKFLOW_ID = 402985021
HISTORICAL_PR2_WORKFLOW_PATH = ".github/workflows/phase1-copilot-receipts-v1.yml"
HISTORICAL_PR2_WORKFLOW_NAME = "Phase 1 standalone Copilot receipt verifier v1"
HISTORICAL_BRANCH = "phase1/verified-review-attestation-gate-20261026"
HISTORICAL_PR2_JOB_IDS = {
    "v6-live-pinned-source-and-github-evidence": 125082967874,
    "v4-adapter-fail-closed-controls": 125082969283,
    "synthetic-verifier-controls": 125082969400,
    "v6-adapter-fail-closed-controls": 125082969717,
    "v5-adapter-fail-closed-controls": 125082969953,
    "v5-historical-replay-fail-closed-controls": 125082997491,
    "v5-historical-replay-pinned-evidence": 125083002892,
}
HISTORICAL_V6_STEP = "Execute real seven-receipt v6 validator (fail closed)"

HISTORICAL_PR8_PR_RUN_ID = 41374267141
HISTORICAL_PR8_PUSH_RUN_ID = 41374245209
HISTORICAL_PR8_RUN_ATTEMPT = 1
HISTORICAL_PR8_PR_WORKFLOW_ID = 401954643
HISTORICAL_PR8_PR_WORKFLOW_PATH = ".github/workflows/phase1-pr-checks.yml"
HISTORICAL_PR8_PR_WORKFLOW_NAME = "Phase 1 consolidated PR checks"
HISTORICAL_PR8_PUSH_WORKFLOW_ID = 395613872
HISTORICAL_PR8_PUSH_WORKFLOW_PATH = ".github/workflows/phase1-census.yml"
HISTORICAL_PR8_PUSH_WORKFLOW_NAME = "Phase 1 pinned source census and review dossiers"
HISTORICAL_PR8_HEAD_BRANCH = "phase1/review-readiness-handoff-20261027"
HISTORICAL_PR8_PR_JOB_COUNT = 41
HISTORICAL_PR8_PUSH_JOB_COUNT = 1


def _git(root, *args):
    return v4._git(root, *args)


def verify_historical_pr2_ancestry(pr2_root):
    root = Path(pr2_root).resolve()
    head = _git(root, "rev-parse", "HEAD")
    _git(root, "merge-base", "--is-ancestor", HISTORICAL_PR2_HEAD, head)
    expected_blobs = {
        "tools/phase1_copilot_receipts_v6_adapter.py": HISTORICAL_PR2_ADAPTER_BLOB,
        HISTORICAL_PR2_WORKFLOW_PATH: HISTORICAL_PR2_WORKFLOW_BLOB,
    }
    for path, expected in expected_blobs.items():
        if _git(root, "rev-parse", f"{HISTORICAL_PR2_HEAD}:{path}") != expected:
            raise ValueError(f"Historical PR2 validation blob mismatch: {path}")
    return root


def _check_timestamp(run, not_before, label):
    try:
        started = datetime.fromisoformat(run["run_started_at"].replace("Z", "+00:00"))
        cutoff = datetime.fromisoformat(not_before.replace("Z", "+00:00"))
    except (KeyError, AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"{label} Actions timestamp is invalid") from exc
    if (
        started.tzinfo is None
        or cutoff.tzinfo is None
        or started.astimezone(timezone.utc) <= cutoff.astimezone(timezone.utc)
    ):
        raise ValueError(f"{label} Actions run predates the pinned PR8 receipt head")


def _get_executed_jobs(api, run_id, attempt, expected_count, expected_head, *, label):
    jobs_url = (
        f"{v4.API_ROOT}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100"
    )
    first_page = api(jobs_url + "&page=1")
    if (
        not isinstance(first_page, dict)
        or type(first_page.get("total_count")) is not int
        or first_page["total_count"] != expected_count
        or not isinstance(first_page.get("jobs"), list)
    ):
        raise ValueError(f"{label} Actions job inventory is incomplete")
    jobs = api.paginate(jobs_url, result_key="jobs")
    if not isinstance(jobs, list) or len(jobs) != expected_count:
        raise ValueError(f"{label} Actions job pagination is incomplete")

    seen = set()
    for job in jobs:
        if not isinstance(job, dict):
            raise ValueError(f"{label} Actions job is malformed")
        job_id = job.get("id")
        if (
            type(job_id) is not int
            or job_id < 1
            or job_id in seen
            or job.get("run_id") != run_id
            or job.get("run_attempt") != attempt
            or job.get("head_sha") != expected_head
            or not isinstance(job.get("name"), str)
            or not job["name"]
            or job.get("status") != "completed"
            or job.get("conclusion") != "success"
        ):
            raise ValueError(f"{label} Actions job identity or result is invalid")
        seen.add(job_id)
        steps = job.get("steps")
        if (
            not isinstance(steps, list)
            or not steps
            or any(
                not isinstance(step, dict)
                or step.get("status") != "completed"
                or step.get("conclusion") != "success"
                or not step.get("started_at")
                or not step.get("completed_at")
                for step in steps
            )
        ):
            raise ValueError(f"{label} Actions job has failed or non-executed steps")
    return jobs


def validate_historical_pr2_actions(api, *, not_before):
    run = api(f"{v4.API_ROOT}/actions/runs/{HISTORICAL_PR2_RUN_ID}")
    if (
        not isinstance(run, dict)
        or type(run.get("id")) is not int
        or run["id"] != HISTORICAL_PR2_RUN_ID
        or type(run.get("run_attempt")) is not int
        or run["run_attempt"] != HISTORICAL_PR2_RUN_ATTEMPT
        or type(run.get("workflow_id")) is not int
        or run["workflow_id"] != HISTORICAL_PR2_WORKFLOW_ID
        or run.get("path") != HISTORICAL_PR2_WORKFLOW_PATH
        or run.get("name") != HISTORICAL_PR2_WORKFLOW_NAME
        or run.get("event") != "push"
        or run.get("head_branch") != HISTORICAL_BRANCH
        or run.get("head_sha") != HISTORICAL_PR2_HEAD
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
    ):
        raise ValueError("Pinned historical v6 PR2 Actions run is missing or mismatched")
    _check_timestamp(run, not_before, "Historical v6 PR2")
    jobs = _get_executed_jobs(
        api,
        HISTORICAL_PR2_RUN_ID,
        HISTORICAL_PR2_RUN_ATTEMPT,
        len(HISTORICAL_PR2_JOB_IDS),
        HISTORICAL_PR2_HEAD,
        label="Historical v6 PR2",
    )
    by_name = {}
    seen_ids = set()
    for job in jobs:
        name, job_id = job.get("name"), job.get("id")
        if (
            name not in HISTORICAL_PR2_JOB_IDS
            or job_id != HISTORICAL_PR2_JOB_IDS[name]
            or name in by_name
            or job_id in seen_ids
        ):
            raise ValueError("Historical v6 PR2 job set differs from its pinned inventory")
        by_name[name] = job
        seen_ids.add(job_id)
    if set(by_name) != set(HISTORICAL_PR2_JOB_IDS):
        raise ValueError("Historical v6 PR2 job inventory is incomplete")
    live_steps = by_name["v6-live-pinned-source-and-github-evidence"]["steps"]
    if sum(step.get("name") == HISTORICAL_V6_STEP for step in live_steps) != 1:
        raise ValueError("Historical v6 PR2 live job lacks its unique exact validator step")
    return len(jobs)


def _validate_pr8_run(api, run_id, *, event, workflow_id, workflow_path, workflow_name,
                      job_count, not_before):
    run = api(f"{v4.API_ROOT}/actions/runs/{run_id}")
    if (
        not isinstance(run, dict)
        or type(run.get("id")) is not int
        or run["id"] != run_id
        or type(run.get("run_attempt")) is not int
        or run["run_attempt"] != HISTORICAL_PR8_RUN_ATTEMPT
        or type(run.get("workflow_id")) is not int
        or run["workflow_id"] != workflow_id
        or run.get("path") != workflow_path
        or run.get("name") != workflow_name
        or run.get("event") != event
        or run.get("head_branch") != HISTORICAL_PR8_HEAD_BRANCH
        or run.get("head_sha") != v6.PR8_HEAD
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
    ):
        raise ValueError(f"Pinned historical PR8 {event} Actions run is missing or mismatched")
    _check_timestamp(run, not_before, f"Historical PR8 {event}")
    if event == "pull_request":
        pull_requests = run.get("pull_requests")
        if (
            not isinstance(pull_requests, list)
            or not any(
                isinstance(item, dict)
                and item.get("number") == v4.PR_NUMBER
                and isinstance(item.get("head"), dict)
                and item["head"].get("sha") == v6.PR8_HEAD
                for item in pull_requests
            )
        ):
            raise ValueError("Historical PR8 PR run does not identify the exact receipt head")
        referenced = run.get("referenced_workflows")
        if (
            not isinstance(referenced, list)
            or not any(
                isinstance(item, dict)
                and isinstance(item.get("path"), str)
                and item["path"].split("@", 1)[0].endswith(
                    f"{v4.OWNER_REPOSITORY}/.github/workflows/phase1-census.yml"
                )
                for item in referenced
            )
        ):
            raise ValueError("Historical PR8 PR run does not reference the pinned census workflow")

    jobs = _get_executed_jobs(
        api,
        run_id,
        HISTORICAL_PR8_RUN_ATTEMPT,
        job_count,
        v6.PR8_HEAD,
        label=f"Historical PR8 {event}",
    )
    if event == "pull_request" and not any(job.get("name") == "census / census" for job in jobs):
        raise ValueError("Historical PR8 PR run lacks its executed census job")
    if event == "push" and (
        len(jobs) != 1 or jobs[0].get("name") != "census"
    ):
        raise ValueError("Historical PR8 push run lacks its unique census job")
    return len(jobs)


def validate_historical_actions(api, *, not_before):
    pr2_jobs = validate_historical_pr2_actions(api, not_before=not_before)
    pr_jobs = _validate_pr8_run(
        api,
        HISTORICAL_PR8_PR_RUN_ID,
        event="pull_request",
        workflow_id=HISTORICAL_PR8_PR_WORKFLOW_ID,
        workflow_path=HISTORICAL_PR8_PR_WORKFLOW_PATH,
        workflow_name=HISTORICAL_PR8_PR_WORKFLOW_NAME,
        job_count=HISTORICAL_PR8_PR_JOB_COUNT,
        not_before=not_before,
    )
    push_jobs = _validate_pr8_run(
        api,
        HISTORICAL_PR8_PUSH_RUN_ID,
        event="push",
        workflow_id=HISTORICAL_PR8_PUSH_WORKFLOW_ID,
        workflow_path=HISTORICAL_PR8_PUSH_WORKFLOW_PATH,
        workflow_name=HISTORICAL_PR8_PUSH_WORKFLOW_NAME,
        job_count=HISTORICAL_PR8_PUSH_JOB_COUNT,
        not_before=not_before,
    )
    return {
        "pr2_run_id": HISTORICAL_PR2_RUN_ID,
        "pr2_run_attempt": HISTORICAL_PR2_RUN_ATTEMPT,
        "pr2_jobs": pr2_jobs,
        "pr8_pr_run_id": HISTORICAL_PR8_PR_RUN_ID,
        "pr8_pr_jobs": pr_jobs,
        "pr8_push_run_id": HISTORICAL_PR8_PUSH_RUN_ID,
        "pr8_push_jobs": push_jobs,
        "receipts": len(v6.EXPECTED_ORDER),
    }


def verify_historical_receipt_bytes(pr8_root, source_root, api):
    root = v6.verify_pinned_worktree(pr8_root)
    triage, verifier = v4._load_pinned_validator(root)
    snapshot_root = root / "semantic-snapshots/current"
    queue = triage.read_queue(snapshot_root)
    dossiers = triage.checked_dossiers(snapshot_root, queue)
    receipts, problems = verifier.load_receipts(root / v6.RECEIPT_PATH)
    if problems:
        raise ValueError("; ".join(problems))
    v6.validate_receipt_inventory(receipts)
    if len(queue) != 14834 or len(dossiers) != 14834:
        raise ValueError("Historical queue/dossier inventory is not exactly 14,834")

    source_root = Path(source_root).resolve()
    if not source_root.is_dir():
        raise ValueError("Pinned mGBA source checkout is unavailable")
    queue_by_key = {(record["repo"], record["path"]): record for record in queue}
    for receipt in receipts:
        source = receipt["source"]
        key = (source["repository"], source["path"])
        queue_record = queue_by_key.get(key)
        dossier = dossiers.get(key)
        if queue_record is None or dossier is None:
            raise ValueError("Historical receipt is absent from the pinned queue/dossier")
        original_dossier_sha = triage.digest(triage.canonical(dossier))
        if (
            source.get("revision") != triage.PINS.get(source["repository"])
            or source.get("git_blob_sha1") != queue_record.get("blob_sha")
            or source.get("source_sha256") != dossier.get("provenance", {}).get("source_content_sha256")
            or receipt.get("machine_dossier_sha256") != original_dossier_sha
            or queue_record.get("evidence_sha256") != original_dossier_sha
        ):
            raise ValueError("Historical receipt differs from its original pinned dossier identity")

        returned_key, validation_problems = verifier.validate_receipt(
            receipt,
            queue=queue_by_key,
            dossiers=dossiers,
            source_root=source_root,
            expected_head=v6.PR8_HEAD,
            repository_root=root,
            repository=v4.OWNER_REPOSITORY,
            github_api=api,
        )
        if returned_key != key or validation_problems:
            raise ValueError(
                "; ".join(validation_problems)
                or "Pinned validator returned a different historical receipt identity"
            )
        v6.verify_non_copilot_evidence_authorship(receipt, api, root)
        v6.verify_expected_comment(receipt, verifier, api, root)

        line = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        introduction, _ = verifier._find_receipt_introduction(
            root,
            v6.RECEIPT_PATH,
            line,
            receipt["target"]["evidence_commit"],
            v6.PR8_HEAD,
        )
        if introduction != v6.EXPECTED_RECEIPTS[key]["receipt_commit"]:
            raise ValueError("Historical receipt introduction differs from its immutable pin")
    return len(receipts)


def run_historical_replay(pr8_root, source_root, pr2_root, token=None, api=None):
    verify_historical_pr2_ancestry(pr2_root)
    root = v6.verify_pinned_worktree(pr8_root)
    _, verifier = v4._load_pinned_validator(root)
    token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    api = api or v4.github_api_client(verifier, token=token)
    count = verify_historical_receipt_bytes(root, source_root, api)
    receipt_head_time = _git(root, "show", "-s", "--format=%cI", v6.PR8_HEAD)
    evidence = validate_historical_actions(api, not_before=receipt_head_time)
    if evidence["receipts"] != count:
        raise ValueError("Historical Actions evidence does not cover the pinned receipt count")
    return {
        "status": "HISTORICAL_V6_REPLAY_VERIFIED",
        "scope": "historical only; not current PR8 validation or a new approval",
        "pr8_head": v6.PR8_HEAD,
        "receipt_count": count,
        **evidence,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-replay", action="store_true", required=True)
    parser.add_argument("--pr8-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--pr2-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run_historical_replay(args.pr8_root, args.source_root, args.pr2_root)
    except Exception as exc:
        print(json.dumps({"status": "BLOCKED", "blocker": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
