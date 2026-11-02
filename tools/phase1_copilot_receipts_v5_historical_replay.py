#!/usr/bin/env python3
"""Replay immutable evidence for the original four-receipt v5 validation only."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

import phase1_copilot_receipts_v4_adapter as v4
import phase1_copilot_receipts_v5_adapter as v5

HISTORICAL_PR2_HEAD = "2aec2ff18f40604cc72f8899d35f92d0364570cd"
HISTORICAL_PR2_ADAPTER_BLOB = "cb64da41dd7d28d305916b60ec5b8a93590bd92d"
HISTORICAL_PR2_WORKFLOW_BLOB = "60b422a086e6bb7f9c03a9d4e251cf66c9689573"
HISTORICAL_RUN_ID = 41337689699
HISTORICAL_RUN_ATTEMPT = 1
HISTORICAL_WORKFLOW_ID = 402985021
HISTORICAL_WORKFLOW_PATH = ".github/workflows/phase1-copilot-receipts-v1.yml"
HISTORICAL_WORKFLOW_NAME = "Phase 1 standalone Copilot receipt verifier v1"
HISTORICAL_BRANCH = "phase1/verified-review-attestation-gate-20261026"
HISTORICAL_JOB_IDS = {
    "v5-live-pinned-source-and-github-evidence": 124940882056,
    "v4-adapter-fail-closed-controls": 124940882242,
    "synthetic-verifier-controls": 124940882318,
    "v5-adapter-fail-closed-controls": 124940882421,
}
HISTORICAL_V5_STEP = "Execute real four-receipt v5 validator (fail closed)"


def _git(root, *args):
    return v4._git(root, *args)


def verify_historical_pr2_ancestry(pr2_root):
    root = Path(pr2_root).resolve()
    head = _git(root, "rev-parse", "HEAD")
    _git(root, "merge-base", "--is-ancestor", HISTORICAL_PR2_HEAD, head)
    expected_blobs = {
        "tools/phase1_copilot_receipts_v5_adapter.py": HISTORICAL_PR2_ADAPTER_BLOB,
        HISTORICAL_WORKFLOW_PATH: HISTORICAL_PR2_WORKFLOW_BLOB,
    }
    for path, expected in expected_blobs.items():
        if _git(root, "rev-parse", f"{HISTORICAL_PR2_HEAD}:{path}") != expected:
            raise ValueError(f"Historical PR2 validation blob mismatch: {path}")
    return root


def validate_historical_actions(api, *, not_before):
    run = api(f"{v4.API_ROOT}/actions/runs/{HISTORICAL_RUN_ID}")
    if (
        not isinstance(run, dict)
        or type(run.get("id")) is not int
        or run["id"] != HISTORICAL_RUN_ID
        or type(run.get("run_attempt")) is not int
        or run["run_attempt"] != HISTORICAL_RUN_ATTEMPT
        or type(run.get("workflow_id")) is not int
        or run["workflow_id"] != HISTORICAL_WORKFLOW_ID
        or run.get("path") != HISTORICAL_WORKFLOW_PATH
        or run.get("name") != HISTORICAL_WORKFLOW_NAME
        or run.get("event") != "push"
        or run.get("head_branch") != HISTORICAL_BRANCH
        or run.get("head_sha") != HISTORICAL_PR2_HEAD
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
    ):
        raise ValueError("Pinned historical v5 Actions run is missing or mismatched")
    try:
        started = datetime.fromisoformat(run["run_started_at"].replace("Z", "+00:00"))
        cutoff = datetime.fromisoformat(not_before.replace("Z", "+00:00"))
    except (KeyError, AttributeError, TypeError, ValueError) as exc:
        raise ValueError("Historical v5 Actions timestamp is invalid") from exc
    if (
        started.tzinfo is None
        or cutoff.tzinfo is None
        or started.astimezone(timezone.utc) <= cutoff.astimezone(timezone.utc)
    ):
        raise ValueError("Historical v5 Actions run predates the pinned PR8 receipt head")

    jobs_url = (
        f"{v4.API_ROOT}/actions/runs/{HISTORICAL_RUN_ID}/attempts/"
        f"{HISTORICAL_RUN_ATTEMPT}/jobs?per_page=100&page=1"
    )
    first_page = api(jobs_url)
    if (
        not isinstance(first_page, dict)
        or type(first_page.get("total_count")) is not int
        or first_page["total_count"] != len(HISTORICAL_JOB_IDS)
        or not isinstance(first_page.get("jobs"), list)
    ):
        raise ValueError("Historical v5 Actions job inventory is incomplete")
    jobs = api.paginate(
        f"{v4.API_ROOT}/actions/runs/{HISTORICAL_RUN_ID}/attempts/"
        f"{HISTORICAL_RUN_ATTEMPT}/jobs?per_page=100",
        result_key="jobs",
    )
    if len(jobs) != len(HISTORICAL_JOB_IDS):
        raise ValueError("Historical v5 Actions job pagination is incomplete")

    by_name = {}
    seen_ids = set()
    for job in jobs:
        if not isinstance(job, dict):
            raise ValueError("Historical v5 Actions job is malformed")
        name, job_id = job.get("name"), job.get("id")
        if (
            name not in HISTORICAL_JOB_IDS
            or type(job_id) is not int
            or job_id != HISTORICAL_JOB_IDS[name]
            or job_id in seen_ids
            or name in by_name
            or job.get("status") != "completed"
            or job.get("conclusion") != "success"
        ):
            raise ValueError("Historical v5 Actions job identity or result is invalid")
        seen_ids.add(job_id)
        by_name[name] = job
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
            raise ValueError("Historical v5 Actions job has failed or non-executed steps")
    if set(by_name) != set(HISTORICAL_JOB_IDS):
        raise ValueError("Historical v5 Actions job set differs from its pinned inventory")
    live_steps = by_name["v5-live-pinned-source-and-github-evidence"]["steps"]
    if sum(step.get("name") == HISTORICAL_V5_STEP for step in live_steps) != 1:
        raise ValueError("Historical v5 live job lacks its unique exact validator step")
    return {
        "run_id": HISTORICAL_RUN_ID,
        "run_attempt": HISTORICAL_RUN_ATTEMPT,
        "jobs": len(jobs),
        "receipts": len(v5.EXPECTED_ORDER),
    }


def verify_historical_receipt_bytes(pr8_root, source_root):
    root = v5.verify_pinned_worktree(pr8_root)
    triage, verifier = v4._load_pinned_validator(root)
    snapshot_root = root / "semantic-snapshots/current"
    queue = triage.read_queue(snapshot_root)
    dossiers = triage.checked_dossiers(snapshot_root, queue)
    receipts, problems = verifier.load_receipts(root / v5.RECEIPT_PATH)
    if problems:
        raise ValueError("; ".join(problems))
    v5.validate_receipt_inventory(receipts)
    if len(queue) != 14834 or len(dossiers) != 14834:
        raise ValueError("Historical queue/dossier inventory is not exactly 14,834")

    queue_by_key = {(record["repo"], record["path"]): record for record in queue}
    source_root = Path(source_root).resolve()
    if not source_root.is_dir():
        raise ValueError("Pinned mGBA source checkout is unavailable")
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

        source_bytes = verifier._verify_source_reference(source, source_root)
        coverage = receipt["review"]["whole_file_coverage"]
        if (
            coverage.get("source_sha256") != hashlib.sha256(source_bytes).hexdigest()
            or coverage.get("source_lines") != len(source_bytes.splitlines())
        ):
            raise ValueError("Historical whole-file source bytes or line coverage mismatch")
        for reference in receipt["review"]["dependency_closure"]["dependencies"]:
            verifier._verify_source_reference(reference, source_root)
        for reference in receipt["review"]["licensing"]["evidence"]:
            verifier._verify_source_reference(reference, source_root)

        line = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        introduction, _ = verifier._find_receipt_introduction(
            root,
            v5.RECEIPT_PATH,
            line,
            receipt["target"]["evidence_commit"],
            v5.PR8_HEAD,
        )
        expected = v5.EXPECTED_RECEIPTS[key]
        if introduction != expected["receipt_commit"]:
            raise ValueError("Historical receipt introduction differs from its immutable pin")
    return len(receipts)


def run_historical_replay(pr8_root, source_root, pr2_root, token=None, api=None):
    verify_historical_pr2_ancestry(pr2_root)
    count = verify_historical_receipt_bytes(pr8_root, source_root)
    receipt_head_time = _git(
        pr8_root, "show", "-s", "--format=%cI", v5.PR8_HEAD
    )
    _, verifier = v4._load_pinned_validator(pr8_root)
    token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    api = api or v4.github_api_client(verifier, token=token)
    evidence = validate_historical_actions(api, not_before=receipt_head_time)
    if evidence["receipts"] != count:
        raise ValueError("Historical Actions evidence does not cover the pinned receipt count")
    return {
        "status": "HISTORICAL_V5_REPLAY_VERIFIED",
        "scope": "historical only; not current PR8 validation or a new approval",
        "pr8_head": v5.PR8_HEAD,
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
