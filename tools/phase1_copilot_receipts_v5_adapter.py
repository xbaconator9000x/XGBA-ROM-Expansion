#!/usr/bin/env python3
"""Fail-closed adapter for the pinned PR #8 four-record v5 receipt register."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

import phase1_copilot_receipts_v4_adapter as v4

PR8_HEAD = "3ee4b1117f2976b6ea41098f5456634da18a50f8"
REGISTER_BLOB = "22f47d4e53954e133a6da117c247f25c158e8147"
DOSSIERS_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
DOSSIERS_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
QUEUE_BLOB = "52fe1a9b8498dd4fa3ea0e6e0236ae1cdeda7268"
QUEUE_SHA256 = "c50498b751ecbe38d7a5939e06fa85cf4e62d529a943983710d4c5b9095d2eff"
PROTOCOL_BLOB = "16382c1146a191f3027347644696b9444251303b"
RECEIPT_PATH = v4.RECEIPT_PATH
PROTOCOL_PATH = v4.PROTOCOL_PATH
VALIDATOR_PATH = v4.VALIDATOR_PATH
TRIAGE_PATH = v4.TRIAGE_PATH
DOSSIERS_PATH = v4.DOSSIERS_PATH
QUEUE_PATH = v4.QUEUE_PATH
FOURTH_KEY = ("mgba-emu/mgba", "include/mgba/internal/arm/isa-arm.h")
FOURTH_RECEIPT = {
    "blob": "fb347cd89f97482e0dbbf5fafed129f1679952df",
    "source_sha256": "619d6208fdbee4f15a7120c3e6f8300cc24c4390373d83586b8c883d83b9f65f",
    "dossier_sha256": "ff5d84cb5f4abb74c841d8050e3cea786be27d99c8acc50ea00f3e9fdff3b24e",
    "receipt_sha256": "d59ea911f09d5d5393b36a62d770159293672ab5f774b23c71fcd684e98e0ded",
    "evidence_commit": "be990407135c99de8113df81af7cd91d531a4fc2",
    "receipt_commit": PR8_HEAD,
}
EXPECTED_ORDER = (*v4.EXPECTED_RECEIPTS, FOURTH_KEY)
EXPECTED_RECEIPTS = {
    **v4.EXPECTED_RECEIPTS,
    FOURTH_KEY: FOURTH_RECEIPT,
}
EXPECTED_BLOBS = {
    PROTOCOL_PATH: PROTOCOL_BLOB,
    RECEIPT_PATH: REGISTER_BLOB,
    VALIDATOR_PATH: v4.VALIDATOR_BLOB,
    TRIAGE_PATH: v4.TRIAGE_BLOB,
    DOSSIERS_PATH: DOSSIERS_BLOB,
    QUEUE_PATH: QUEUE_BLOB,
}


def verify_pinned_worktree(root):
    root = Path(root).resolve()
    if v4._git(root, "rev-parse", "HEAD") != PR8_HEAD:
        raise ValueError(f"PR #8 worktree must be exact pinned head {PR8_HEAD}")
    for path, expected in EXPECTED_BLOBS.items():
        if v4._git(root, "rev-parse", f"{PR8_HEAD}:{path}") != expected:
            raise ValueError(f"Pinned PR #8 v5 blob mismatch: {path}")
        candidate = root
        unsafe = False
        for part in Path(path).parts:
            candidate = candidate / part
            unsafe = unsafe or candidate.is_symlink()
        if unsafe or not candidate.is_file():
            raise ValueError(f"Pinned PR #8 file is missing or unsafe: {path}")
        committed = subprocess.check_output(["git", "-C", str(root), "show", f"{PR8_HEAD}:{path}"])
        if candidate.read_bytes() != committed:
            raise ValueError(f"Working tree differs from pinned PR #8 bytes: {path}")
    if hashlib.sha256((root / DOSSIERS_PATH).read_bytes()).hexdigest() != DOSSIERS_SHA256:
        raise ValueError("Original compressed machine dossier archive SHA-256 mismatch")
    if hashlib.sha256((root / QUEUE_PATH).read_bytes()).hexdigest() != QUEUE_SHA256:
        raise ValueError("Original compressed review queue SHA-256 mismatch")
    return root


def validate_semantic_scope(receipt, *, allow_v7_notice_mapping=False):
    if not isinstance(receipt, dict) or receipt.get("schema") != "xgba.phase1.copilot_semantic_review_receipt.v4":
        raise ValueError("Unsupported v5 receipt schema")
    review = receipt.get("review")
    if not isinstance(review, dict) or review.get("decision") != "APPROVED":
        raise ValueError("Receipt lacks the expected source-review decision")
    if review.get("reviewer_classification") not in {
        "COPILOT_REVIEWED/PASSED (user override; not human/external approval)",
        "COPILOT_REVIEWED/PASSED (user-authorized source review; not human or external approval)",
    }:
        raise ValueError("Receipt classification is missing or unsupported")
    source = receipt.get("source")
    coverage = review.get("whole_file_coverage")
    if (
        not isinstance(source, dict)
        or not isinstance(coverage, dict)
        or coverage.get("scope") != "WHOLE_FILE"
        or coverage.get("source_sha256") != source.get("source_sha256")
        or type(coverage.get("source_lines")) is not int
        or coverage["source_lines"] < 1
        or not isinstance(coverage.get("reviewed_line_ranges"), list)
    ):
        raise ValueError("Whole-file source identity or coverage is incomplete")
    cursor = 1
    for span in coverage["reviewed_line_ranges"]:
        if (
            not isinstance(span, list)
            or len(span) != 2
            or type(span[0]) is not int
            or type(span[1]) is not int
            or span[0] != cursor
            or span[1] < span[0]
        ):
            raise ValueError("Whole-file source coverage has gaps or invalid ranges")
        cursor = span[1] + 1
    if cursor != coverage["source_lines"] + 1:
        raise ValueError("Whole-file source coverage is incomplete")

    closure = review.get("dependency_closure")
    if (
        not isinstance(closure, dict)
        or closure.get("status") != "COMPLETE"
        or not isinstance(closure.get("dependencies"), list)
        or not closure["dependencies"]
        or not isinstance(closure.get("rationale"), str)
        or len(closure["rationale"].strip()) < 20
    ):
        raise ValueError("Dependency closure is incomplete or unexplained")

    licensing = review.get("licensing")
    rationale = licensing.get("rationale", "") if isinstance(licensing, dict) else ""
    lower_rationale = rationale.lower() if isinstance(rationale, str) else ""
    file_scope_terms = ("file-scoped", "source-file scoped", "source mapping")
    distribution_limit = "not cleared" in lower_rationale
    if allow_v7_notice_mapping is True:
        file_scope_terms += ("file-level notice mapping",)
        distribution_limit = distribution_limit or "distribution clearance is not claimed" in lower_rationale
    if (
        not isinstance(licensing, dict)
        or licensing.get("status") != "CLEARED"
        or not isinstance(licensing.get("evidence"), list)
        or not licensing["evidence"]
        or not any(term in lower_rationale for term in file_scope_terms)
        or not distribution_limit
        or not any(term in lower_rationale for term in ("combined distribution", "combined-work", "larger work"))
    ):
        raise ValueError("Licensing scope or combined-distribution limitation is missing")

    objections = review.get("objections")
    if not isinstance(objections, list) or any(
        not isinstance(item, dict)
        or item.get("status") != "RESOLVED"
        or not isinstance(item.get("resolution"), str)
        or len(item["resolution"].strip()) < 12
        for item in objections
    ):
        raise ValueError("A substantive objection is unresolved or lacks a disposition")

    distinctions = review.get("evidence_distinctions")
    required = {"source", "synthetic", "compiled_native", "runtime_gameplay", "save_restart", "physical_flash"}
    if not isinstance(distinctions, dict) or not required.issubset(distinctions):
        raise ValueError("Evidence distinctions are incomplete")
    if (
        not isinstance(distinctions["source"], dict)
        or distinctions["source"].get("status") != "VERIFIED"
        or distinctions["source"].get("source_sha256") != source.get("source_sha256")
    ):
        raise ValueError("Pinned source evidence is not verified")
    for category in required - {"source"}:
        item = distinctions[category]
        if (
            not isinstance(item, dict)
            or item.get("status") not in {"NOT_RUN", "NOT_CLAIMED", "NOT_APPLICABLE"}
        ):
            raise ValueError(f"Unsupported or unverified {category} evidence claim")
    return True


def validate_receipt_inventory(receipts):
    if not isinstance(receipts, list) or len(receipts) != len(EXPECTED_ORDER):
        raise ValueError("The v5 register must contain exactly four pinned receipt records")
    for index, (receipt, expected_key) in enumerate(zip(receipts, EXPECTED_ORDER)):
        if not isinstance(receipt, dict):
            raise ValueError("Receipt register contains a non-object record")
        source = receipt.get("source")
        target = receipt.get("target")
        if not isinstance(source, dict) or not isinstance(target, dict):
            raise ValueError("Receipt lacks its pinned source or target identity")
        key = (source.get("repository"), source.get("path"))
        expected = EXPECTED_RECEIPTS[expected_key]
        attestation = receipt.get("attestation")
        if (
            key != expected_key
            or source.get("revision") != "fd9dc5c2cbf234365068855851107e762fc6211b"
            or source.get("git_blob_sha1") != expected["blob"]
            or source.get("source_sha256") != expected["source_sha256"]
            or receipt.get("machine_dossier_sha256") != expected["dossier_sha256"]
            or receipt.get("schema") != "xgba.phase1.copilot_semantic_review_receipt.v4"
            or not isinstance(attestation, dict)
            or attestation.get("mode") != "conversation_comment"
            or attestation.get("receipt_sha256") != expected["receipt_sha256"]
            or v4.receipt_digest(receipt) != expected["receipt_sha256"]
            or target.get("repository") != v4.OWNER_REPOSITORY
            or target.get("pull_number") != v4.PR_NUMBER
            or target.get("receipt_path") != RECEIPT_PATH
            or target.get("evidence_commit") != expected["evidence_commit"]
        ):
            raise ValueError(f"Receipt {index + 1} is reordered, unknown, duplicated, modified, or mismatched")
        validate_semantic_scope(receipt)
    return True


def _bot_identity(user):
    return v4._bot_identity(user)


def verify_expected_comment(receipt, verifier, api, repository_root):
    source = receipt["source"]
    key = (source["repository"], source["path"])
    expected = EXPECTED_RECEIPTS.get(key)
    if expected is None:
        raise ValueError("Attestation targets an unknown receipt")
    markers = (
        verifier.RECEIPT_MARKER + expected["receipt_sha256"],
        verifier.INTRO_COMMIT_MARKER + expected["receipt_commit"],
        verifier.EVIDENCE_COMMIT_MARKER + expected["evidence_commit"],
        verifier.DECISION_MARKER,
    )
    comments = api.paginate(f"{v4.API_ROOT}/issues/{v4.PR_NUMBER}/comments")
    if not isinstance(comments, list):
        raise ValueError("GitHub returned an invalid comment collection")
    matching = []
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        if (
            type(comment.get("id")) is int
            and comment["id"] > 0
            and (expected.get("comment_id") is None or comment.get("id") == expected["comment_id"])
            and _bot_identity(comment.get("user"))
            and comment.get("issue_url") == f"{v4.API_ROOT}/issues/{v4.PR_NUMBER}"
            and comment.get("html_url")
            == f"https://github.com/{v4.OWNER_REPOSITORY}/pull/{v4.PR_NUMBER}"
            f"#issuecomment-{comment.get('id')}"
            and verifier._attestation_section_is_valid(comment.get("body"), markers)
        ):
            matching.append(comment)
    if len(matching) != 1:
        raise ValueError("Expected one authenticated, unquoted Copilot attestation for the receipt digest")
    comment = matching[0]
    timestamp = v4._git(repository_root, "show", "-s", "--format=%cI", expected["receipt_commit"])
    try:
        if not isinstance(comment.get("created_at"), str):
            raise ValueError("invalid comment timestamp")
        comment_time = datetime.fromisoformat(comment["created_at"].replace("Z", "+00:00"))
        commit_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Attestation or receipt-introduction timestamp is invalid") from exc
    if (
        comment_time.tzinfo is None
        or commit_time.tzinfo is None
        or comment_time.astimezone(timezone.utc) <= commit_time.astimezone(timezone.utc)
    ):
        raise ValueError("Authenticated Copilot attestation predates its receipt introduction")
    return comment


def validate_exact_ci(api, *, expected_head=PR8_HEAD, not_before=None, pull_number=v4.PR_NUMBER):
    runs = api.paginate(
        f"{v4.API_ROOT}/actions/runs?head_sha={expected_head}", result_key="workflow_runs"
    )
    requirements = {
        "pull_request": (v4.PR_WORKFLOW, v4.PR_WORKFLOW_NAME),
        "push": (v4.CENSUS_WORKFLOW, None),
    }
    counts = {}
    for event, (workflow_path, workflow_name) in requirements.items():
        candidates = [
            run for run in runs
            if isinstance(run, dict)
            and run.get("head_sha") == expected_head
            and run.get("event") == event
            and run.get("path") == workflow_path
            and (workflow_name is None or run.get("name") == workflow_name)
            and (
                event != "pull_request"
                or (
                    isinstance(run.get("pull_requests"), list)
                    and any(
                        isinstance(pr, dict)
                        and pr.get("number") == pull_number
                        and isinstance(pr.get("head"), dict)
                        and pr["head"].get("sha") == expected_head
                        for pr in run.get("pull_requests", [])
                    )
                )
            )
        ]
        if not candidates:
            raise ValueError(f"Exact-head {event} Actions run is missing")
        if any(not isinstance(run.get("created_at"), str) for run in candidates):
            raise ValueError(f"Exact-head {event} Actions run has an invalid creation timestamp")
        run = max(candidates, key=lambda item: item.get("created_at", ""))
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            raise ValueError(f"Latest exact-head {event} Actions run is not successful")
        run_id = run.get("id")
        attempt = run.get("run_attempt")
        if type(run_id) is not int or run_id < 1 or type(attempt) is not int or attempt < 1:
            raise ValueError(f"Exact-head {event} Actions run has invalid ID or attempt")
        if not_before:
            try:
                if not isinstance(run.get("run_started_at"), str) or not isinstance(not_before, str):
                    raise ValueError("invalid run timestamp")
                started = datetime.fromisoformat(run["run_started_at"].replace("Z", "+00:00"))
                cutoff = datetime.fromisoformat(not_before.replace("Z", "+00:00"))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Exact-head {event} Actions timestamp is invalid") from exc
            if (
                started.tzinfo is None
                or cutoff.tzinfo is None
                or started.astimezone(timezone.utc) <= cutoff.astimezone(timezone.utc)
            ):
                raise ValueError(f"Exact-head {event} Actions run predates the final receipt")
        if event == "pull_request" and not (
            isinstance(run.get("referenced_workflows"), list)
            and any(
                isinstance(workflow, dict)
                and isinstance(workflow.get("path"), str)
                and workflow["path"].split("@", 1)[0].endswith(
                    f"{v4.OWNER_REPOSITORY}/{v4.CENSUS_WORKFLOW}"
                )
                for workflow in run["referenced_workflows"]
            )
        ):
            raise ValueError("Exact-head PR run does not reference the pinned census workflow")

        jobs = []
        seen = set()
        page = 1
        total = None
        while True:
            response = api(
                f"{v4.API_ROOT}/actions/runs/{run_id}/attempts/{attempt}/jobs"
                f"?per_page=100&page={page}"
            )
            page_jobs = response.get("jobs") if isinstance(response, dict) else None
            reported = response.get("total_count") if isinstance(response, dict) else None
            if (
                not isinstance(page_jobs, list)
                or len(page_jobs) > 100
                or any(not isinstance(job, dict) for job in page_jobs)
                or type(reported) is not int
                or reported < 0
                or (total is not None and total != reported)
            ):
                raise ValueError(f"Exact-head {event} Actions job response is invalid")
            total = reported
            for job in page_jobs:
                job_id = job.get("id")
                if type(job_id) is not int or job_id < 1 or job_id in seen:
                    raise ValueError(f"Exact-head {event} Actions jobs are missing or duplicated")
                seen.add(job_id)
                jobs.append(job)
            if len(page_jobs) < 100:
                break
            page += 1
        if not jobs or len(jobs) != total:
            raise ValueError(f"Exact-head {event} run has zero or incomplete jobs")
        for job in jobs:
            steps = job.get("steps")
            if (
                job.get("status") != "completed"
                or job.get("conclusion") != "success"
                or not isinstance(steps, list)
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
                raise ValueError(f"Exact-head {event} run contains failed, skipped, or non-executed steps")
        counts[event] = len(jobs)
    return counts


def run_live(pr8_root, source_root, token=None):
    root = verify_pinned_worktree(pr8_root)
    triage, verifier = v4._load_pinned_validator(root)
    snapshot_root = root / "semantic-snapshots/current"
    queue = triage.read_queue(snapshot_root)
    dossiers = triage.checked_dossiers(snapshot_root, queue)
    receipts, problems = verifier.load_receipts(root / RECEIPT_PATH)
    if problems:
        raise ValueError("; ".join(problems))
    validate_receipt_inventory(receipts)
    queue_by_key = {(record["repo"], record["path"]): record for record in queue}
    if len(queue_by_key) != 14834 or len(dossiers) != 14834:
        raise ValueError("Original pinned queue/dossier inventory is not exactly 14,834")
    source_root = Path(source_root).resolve()
    if not source_root.is_dir():
        return [
            {
                "source": f"{receipt['source']['repository']}:{receipt['source']['path']}",
                "status": "BLOCKED",
                "blocker": "Pinned upstream source checkout is unavailable; original source bytes cannot be verified.",
            }
            for receipt in receipts
        ]
    token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    api = v4.github_api_client(verifier, token=token)
    results = []
    for receipt in receipts:
        source = receipt["source"]
        key = (source["repository"], source["path"])
        label = f"{key[0]}:{key[1]}"
        try:
            returned_key, validation_problems = verifier.validate_receipt(
                receipt,
                queue=queue_by_key,
                dossiers=dossiers,
                source_root=source_root,
                expected_head=PR8_HEAD,
                repository_root=root,
                repository=v4.OWNER_REPOSITORY,
                github_api=api,
            )
            if returned_key != key or validation_problems:
                raise ValueError("; ".join(validation_problems) or "Pinned validator returned a different identity")
            verify_expected_comment(receipt, verifier, api, root)
            receipt_time = v4._git(root, "show", "-s", "--format=%cI", PR8_HEAD)
            counts = validate_exact_ci(api, expected_head=PR8_HEAD, not_before=receipt_time)
            results.append({
                "source": label,
                "status": "COPILOT_RECEIPT_VALIDATED",
                "pr_jobs": counts["pull_request"],
                "push_jobs": counts["push"],
            })
        except Exception as exc:
            results.append({"source": label, "status": "BLOCKED", "blocker": str(exc)})
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr8-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        results = run_live(args.pr8_root, args.source_root)
    except Exception as exc:
        print(json.dumps({"status": "BLOCKED", "blocker": str(exc)}, sort_keys=True))
        return 2
    for result in results:
        print(json.dumps(result, sort_keys=True))
    return 0 if all(item["status"] == "COPILOT_RECEIPT_VALIDATED" for item in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
