#!/usr/bin/env python3
"""Read-only adapter for the pinned PR #8 Copilot v4 receipt register."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

PR8_HEAD = "3aec481a15bd821122314bc441e7bb7954d65b40"
PR8_PROTOCOL_BLOB = "16382c1146a191f3027347644696b9444251303b"
RECEIPT_PATH = "docs/phase1-review-readiness/copilot-semantic-review-receipts.jsonl"
RECEIPT_BLOB = "b5dcfad9a428a9838cf5e29e3b44f390d491c360"
VALIDATOR_PATH = "tools/phase1_copilot_receipts.py"
VALIDATOR_BLOB = "c68a11e0de846a12179cf71171b3c3a15fc65764"
TRIAGE_PATH = "tools/phase1_bulk_triage.py"
TRIAGE_BLOB = "56eff6d4b5a6b1a566d5c5b00ca670bed219b4f8"
DOSSIERS_PATH = "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
DOSSIERS_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
DOSSIERS_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
QUEUE_PATH = "semantic-snapshots/current/semantic_review_queue.csv.gz"
QUEUE_SHA256 = "c50498b751ecbe38d7a5939e06fa85cf4e62d529a943983710d4c5b9095d2eff"
QUEUE_BLOB = "52fe1a9b8498dd4fa3ea0e6e0236ae1cdeda7268"
PROTOCOL_PATH = "docs/PHASE1_SYSTEM_BATCH_REVIEW_PROTOCOL_2026-10-27.md"
OWNER_REPOSITORY = "xbaconator9000x/XGBA-ROM-Expansion"
API_ROOT = f"https://api.github.com/repos/{OWNER_REPOSITORY}"
PR_NUMBER = 8
CENSUS_WORKFLOW = ".github/workflows/phase1-census.yml"
PR_WORKFLOW = ".github/workflows/phase1-pr-checks.yml"
PR_WORKFLOW_NAME = "Phase 1 consolidated PR checks"
RECEIPT_SCHEMA = "xgba.phase1.copilot_semantic_review_receipt.v4"
BOT_ID = 198982749
BOT_NODE_ID = "BOT_kgDOC9w8XQ"
BOT_LOGINS = {"Copilot", "copilot-swe-agent[bot]"}
EXPECTED_RECEIPTS = {
    ("mgba-emu/mgba", "include/mgba/internal/arm/debugger/cli-debugger.h"): {
        "blob": "70f9b188572137479cb3e9bf26ab12f40707e1f9",
        "source_sha256": "27ef2fed80894cc662aae2793cb6459b2aac86b3d5a7dd410282411f83bd05a5",
        "dossier_sha256": "ebcf0db23dc12aa3f58016584e81ddea8adcc3701c1f52a51759fcd8909bbdcf",
        "receipt_sha256": "49924b5437aecfc88ebdf335fbd6fe05a68fa13987f61d87e0a7ee62809f0c64",
        "comment_id": 6537324570,
        "evidence_commit": "4ea9dbd09118530a986f9bf5828b6c258f279d40",
        "receipt_commit": "9204256b66558864efb32884d5b8228543f0bf97",
    },
    ("mgba-emu/mgba", "include/mgba/internal/arm/debugger/memory-debugger.h"): {
        "blob": "1ec675992e79d37321c358ffd0ff1c691118993d",
        "source_sha256": "7ba8c726198d604bcfcd85d97b9aab4087e44e5355fcae8407d02235b58d0da3",
        "dossier_sha256": "413ba90e50188b2356db3617be4022a75bbe3f22a5e1fbb1343035cf13cd6182",
        "receipt_sha256": "2d30b0f6d533f5091f0e0b58233032707c3fdb07b81984cc8aa85a5a6516cc53",
        "comment_id": 6540744914,
        "evidence_commit": "e16cd30e0a302824a8626279531de44b240dc138",
        "receipt_commit": "e349407d5e2cdfeb030f976ab716545875e0f3eb",
    },
    ("mgba-emu/mgba", "src/arm/CMakeLists.txt"): {
        "blob": "a86f0bea1f38aeb88222fb5b532b4ea9e256767f",
        "source_sha256": "37d9b15aa461a72eba64465856d9377085d6dde56b8ba888e3a4e30f6859390e",
        "dossier_sha256": "821659a5c9436e3472b409a43e08f66e703a8daff07e0b6cf70d46eaed1d491a",
        "receipt_sha256": "e410f88c79a6b3dfb2612f1228c6f7ae0bda83e4eb7d896fbc6221aa2903a0d0",
        "comment_id": 6547559949,
        "evidence_commit": "724a8e0bfa48a8d8f7826f13b120cb9a383d7d9a",
        "receipt_commit": PR8_HEAD,
    },
}


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def receipt_digest(receipt):
    body = {key: value for key, value in receipt.items() if key != "attestation"}
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


def git_blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def _git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args], stderr=subprocess.PIPE, text=True
    ).strip()


def verify_pinned_worktree(root):
    root = Path(root).resolve()
    if _git(root, "rev-parse", "HEAD") != PR8_HEAD:
        raise ValueError(f"PR #8 worktree must be exact pinned head {PR8_HEAD}")
    expected_blobs = {
        PROTOCOL_PATH: PR8_PROTOCOL_BLOB,
        RECEIPT_PATH: RECEIPT_BLOB,
        VALIDATOR_PATH: VALIDATOR_BLOB,
        TRIAGE_PATH: TRIAGE_BLOB,
        DOSSIERS_PATH: DOSSIERS_BLOB,
        QUEUE_PATH: QUEUE_BLOB,
    }
    for path, expected in expected_blobs.items():
        if _git(root, "rev-parse", f"{PR8_HEAD}:{path}") != expected:
            raise ValueError(f"Pinned PR #8 blob mismatch: {path}")
        candidate = root / path
        if candidate.is_symlink() or not candidate.is_file():
            raise ValueError(f"Pinned PR #8 file is missing or unsafe: {path}")
        committed = subprocess.check_output(
            ["git", "-C", str(root), "show", f"{PR8_HEAD}:{path}"]
        )
        if candidate.read_bytes() != committed:
            raise ValueError(f"Working tree differs from pinned PR #8 bytes: {path}")
    if hashlib.sha256((root / DOSSIERS_PATH).read_bytes()).hexdigest() != DOSSIERS_SHA256:
        raise ValueError("Original compressed machine dossier archive SHA-256 mismatch")
    if hashlib.sha256((root / QUEUE_PATH).read_bytes()).hexdigest() != QUEUE_SHA256:
        raise ValueError("Original compressed review queue SHA-256 mismatch")
    return root


def validate_receipt_inventory(receipts):
    if not isinstance(receipts, list) or len(receipts) != len(EXPECTED_RECEIPTS):
        raise ValueError("Receipt register must contain exactly the three pinned v4 records")
    seen = set()
    for receipt in receipts:
        if not isinstance(receipt, dict) or receipt.get("schema") != RECEIPT_SCHEMA:
            raise ValueError("Receipt register contains an unsupported schema")
        source = receipt.get("source")
        if not isinstance(source, dict):
            raise ValueError("Receipt lacks its pinned source identity")
        key = (source.get("repository"), source.get("path"))
        expected = EXPECTED_RECEIPTS.get(key)
        if expected is None or key in seen:
            raise ValueError("Receipt register contains an unknown or duplicate source")
        seen.add(key)
        attestation = receipt.get("attestation")
        target = receipt.get("target")
        if (
            source.get("revision") != "fd9dc5c2cbf234365068855851107e762fc6211b"
            or source.get("git_blob_sha1") != expected["blob"]
            or source.get("source_sha256") != expected["source_sha256"]
            or receipt.get("machine_dossier_sha256") != expected["dossier_sha256"]
            or not isinstance(attestation, dict)
            or attestation.get("mode") != "conversation_comment"
            or attestation.get("receipt_sha256") != expected["receipt_sha256"]
            or receipt_digest(receipt) != expected["receipt_sha256"]
            or not isinstance(target, dict)
            or target.get("repository") != OWNER_REPOSITORY
            or target.get("pull_number") != PR_NUMBER
            or target.get("receipt_path") != RECEIPT_PATH
            or target.get("evidence_commit") != expected["evidence_commit"]
        ):
            raise ValueError("Receipt has a mismatched pinned source, dossier, target, or digest")
    if seen != set(EXPECTED_RECEIPTS):
        raise ValueError("Receipt register is missing one or more pinned v4 records")
    return True


def _load_pinned_validator(root):
    pinned_modules = (
        ("phase1_bulk_triage", TRIAGE_PATH, TRIAGE_BLOB),
        ("phase1_copilot_receipts", VALIDATOR_PATH, VALIDATOR_BLOB),
    )
    previous_modules = {
        name: sys.modules.get(name) for name in ("phase1_bulk_triage", "phase1_copilot_receipts")
    }
    try:
        loaded = {}
        for name, path, expected_blob in pinned_modules:
            source = (root / path).read_bytes()
            if git_blob_sha(source) != expected_blob:
                raise ValueError(f"Pinned validator source changed: {path}")
            module = ModuleType(name)
            module.__file__ = str(root / path)
            sys.modules[name] = module
            exec(compile(source, module.__file__, "exec"), module.__dict__)
            loaded[name] = module
        return loaded["phase1_bulk_triage"], loaded["phase1_copilot_receipts"]
    except Exception as exc:
        raise ValueError("Unable to load the exact pinned PR #8 v4 validator") from exc
    finally:
        for name, module in previous_modules.items():
            sys.modules.pop(name, None)
            if module is not None:
                sys.modules[name] = module


def _bot_identity(user):
    return (
        isinstance(user, dict)
        and user.get("login") in BOT_LOGINS
        and user.get("id") == BOT_ID
        and user.get("node_id") == BOT_NODE_ID
        and user.get("type") == "Bot"
    )


def validate_exact_ci(api, pull_number=PR_NUMBER, expected_head=PR8_HEAD, not_before=None):
    runs = api.paginate(
        f"{API_ROOT}/actions/runs?head_sha={expected_head}", result_key="workflow_runs"
    )
    requirements = {
        "pull_request": {
            "path": PR_WORKFLOW,
            "name": PR_WORKFLOW_NAME,
        },
        "push": {
            "path": CENSUS_WORKFLOW,
        },
    }
    selected = {}
    for event, required in requirements.items():
        candidates = [
            run for run in runs
            if run.get("head_sha") == expected_head
            and run.get("event") == event
            and run.get("path") == required["path"]
            and (event != "pull_request" or run.get("name") == required["name"])
            and (
                event != "pull_request"
                or any(
                    pr.get("number") == pull_number
                    and pr.get("head", {}).get("sha") == expected_head
                    for pr in run.get("pull_requests", [])
                )
            )
        ]
        if not candidates:
            raise ValueError(f"Exact-head {event} Actions run is missing")
        run = max(candidates, key=lambda item: item.get("created_at", ""))
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            raise ValueError(f"Latest exact-head {event} Actions run is not successful")
        if not_before:
            try:
                run_started = datetime.fromisoformat(run["run_started_at"].replace("Z", "+00:00"))
                receipt_time = datetime.fromisoformat(not_before.replace("Z", "+00:00"))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Exact-head {event} Actions timestamp is invalid") from exc
            if (
                run_started.tzinfo is None
                or receipt_time.tzinfo is None
                or run_started.astimezone(timezone.utc) <= receipt_time.astimezone(timezone.utc)
            ):
                raise ValueError(f"Exact-head {event} Actions run predates the final receipt commit")
        if not isinstance(run.get("id"), int) or run["id"] < 1:
            raise ValueError(f"Exact-head {event} Actions run has no valid ID")
        selected[event] = run

    pr_run = selected["pull_request"]
    if not any(
        isinstance(workflow.get("path"), str)
        and workflow["path"].split("@", 1)[0].endswith(f"{OWNER_REPOSITORY}/{CENSUS_WORKFLOW}")
        for workflow in pr_run.get("referenced_workflows", [])
    ):
        raise ValueError("Exact-head PR run does not reference the pinned census workflow")

    job_counts = {}
    for event, run in selected.items():
        attempt = run.get("run_attempt")
        if not isinstance(attempt, int) or attempt < 1:
            raise ValueError(f"Exact-head {event} Actions run has invalid attempt")
        jobs = []
        seen = set()
        page = 1
        total = None
        while True:
            response = api(
                f"{API_ROOT}/actions/runs/{run['id']}/attempts/{attempt}/jobs"
                f"?per_page=100&page={page}"
            )
            page_jobs = response.get("jobs") if isinstance(response, dict) else None
            if (
                not isinstance(page_jobs, list)
                or any(not isinstance(job, dict) for job in page_jobs)
                or len(page_jobs) > 100
            ):
                raise ValueError(f"Exact-head {event} Actions job response is invalid")
            reported = response.get("total_count")
            if not isinstance(reported, int) or reported < 0:
                raise ValueError(f"Exact-head {event} Actions job count is invalid")
            if total is None:
                total = reported
            elif total != reported:
                raise ValueError(f"Exact-head {event} Actions job count changed during pagination")
            for job in page_jobs:
                job_id = job.get("id")
                if not isinstance(job_id, int) or job_id < 1 or job_id in seen:
                    raise ValueError(f"Exact-head {event} Actions jobs are missing or duplicated")
                seen.add(job_id)
                jobs.append(job)
            if len(page_jobs) < 100:
                break
            page += 1
        if not jobs or len(jobs) != total:
            raise ValueError(f"Exact-head {event} Actions run has zero or incomplete jobs")
        for job in jobs:
            steps = job.get("steps")
            if (
                job.get("status") != "completed"
                or job.get("conclusion") != "success"
                or not isinstance(steps, list)
                or not any(
                    step.get("status") == "completed"
                    and step.get("conclusion") == "success"
                    and step.get("started_at")
                    and step.get("completed_at")
                    for step in steps
                    if isinstance(step, dict)
                )
            ):
                raise ValueError(f"Exact-head {event} run contains a failed or non-executed job")
        job_counts[event] = len(jobs)
    return job_counts


def verify_expected_comment(receipt, verifier, api, repository_root):
    source = receipt["source"]
    expected = EXPECTED_RECEIPTS[(source["repository"], source["path"])]
    comments = api.paginate(f"{API_ROOT}/issues/{PR_NUMBER}/comments")
    digest = expected["receipt_sha256"]
    markers = (
        verifier.RECEIPT_MARKER + digest,
        verifier.INTRO_COMMIT_MARKER + expected["receipt_commit"],
        verifier.EVIDENCE_COMMIT_MARKER + expected["evidence_commit"],
        verifier.DECISION_MARKER,
    )
    matches = [
        comment for comment in comments
        if comment.get("id") == expected["comment_id"]
        and _bot_identity(comment.get("user"))
        and comment.get("issue_url") == f"{API_ROOT}/issues/{PR_NUMBER}"
        and comment.get("html_url")
        == f"https://github.com/{OWNER_REPOSITORY}/pull/{PR_NUMBER}"
        f"#issuecomment-{expected['comment_id']}"
        and verifier._attestation_section_is_valid(comment.get("body"), markers)
    ]
    if len(matches) != 1:
        raise ValueError("Expected authenticated Copilot comment ID/identity/markers did not match")
    try:
        timestamp = _git(repository_root, "show", "-s", "--format=%cI", expected["receipt_commit"])
    except Exception as exc:
        raise ValueError("Pinned receipt-introduction commit is unavailable") from exc
    try:
        comment_time = datetime.fromisoformat(matches[0]["created_at"].replace("Z", "+00:00"))
        commit_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Authenticated Copilot comment or introduction timestamp is invalid") from exc
    if (
        comment_time.tzinfo is None
        or commit_time.tzinfo is None
        or comment_time.astimezone(timezone.utc) <= commit_time.astimezone(timezone.utc)
    ):
        raise ValueError("Authenticated Copilot comment predates the receipt introduction")
    return matches[0]


def run_live(pr8_root, source_root, token=None):
    root = verify_pinned_worktree(pr8_root)
    triage, verifier = _load_pinned_validator(root)
    snapshot_root = root / "semantic-snapshots/current"
    queue = triage.read_queue(snapshot_root)
    dossiers = triage.checked_dossiers(snapshot_root, queue)
    receipt_path = root / RECEIPT_PATH
    receipts, parse_problems = verifier.load_receipts(receipt_path)
    if parse_problems:
        raise ValueError("; ".join(parse_problems))
    validate_receipt_inventory(receipts)
    queue_by_key = {(record["repo"], record["path"]): record for record in queue}
    if len(queue_by_key) != 14834 or len(dossiers) != 14834:
        raise ValueError("Original pinned queue/dossier inventory is not exactly 14,834")
    source_path = Path(source_root).resolve()
    if not source_path.is_dir():
        return [
            {
                "source": f"{receipt['source']['repository']}:{receipt['source']['path']}",
                "status": "BLOCKED",
                "blocker": "Pinned upstream source checkout is unavailable; "
                "whole-source, dependency, and licensing bytes cannot be verified."
                + (
                    " Authenticated GitHub API token missing; reviewer identity and Actions also cannot be verified."
                    if not (token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")) else ""
                ),
            }
            for receipt in receipts
        ]
    source_blockers = {}
    for receipt in receipts:
        key = (receipt["source"]["repository"], receipt["source"]["path"])
        try:
            review = receipt["review"]
            verifier._verify_source_reference(receipt["source"], source_path)
            for dependency in review["dependency_closure"]["dependencies"]:
                verifier._verify_source_reference(dependency, source_path)
            for license_evidence in review["licensing"]["evidence"]:
                verifier._verify_source_reference(license_evidence, source_path)
        except Exception as exc:
            source_blockers[key] = str(exc)
    token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        blocked = []
        for receipt in receipts:
            key = (receipt["source"]["repository"], receipt["source"]["path"])
            local_problems = []
            if key not in source_blockers:
                _, local_problems = verifier.validate_receipt(
                    receipt,
                    queue=queue_by_key,
                    dossiers=dossiers,
                    source_root=source_path,
                    expected_head=PR8_HEAD,
                    repository_root=root,
                    repository=OWNER_REPOSITORY,
                    github_api=lambda _url: (_ for _ in ()).throw(
                        ValueError("Authenticated GitHub API token missing")
                    ),
                )
                local_problems = [
                    problem for problem in local_problems
                    if "GitHub API response" not in problem
                    and "GitHub review signature" not in problem
                ]
            blocker = source_blockers.get(key)
            if not blocker and local_problems:
                blocker = "; ".join(local_problems)
            if not blocker:
                blocker = (
                    "Pinned sources, original compressed archives, canonical per-file dossiers, "
                    "dependency/license closure, whole-file scope, objections, and ancestry verified."
                )
            blocked.append({
                "source": f"{receipt['source']['repository']}:{receipt['source']['path']}",
                "status": "BLOCKED",
                "blocker": blocker
                + " Authenticated GitHub API token missing; reviewer identity, evidence authorship, and exact-head Actions cannot be verified.",
            })
        return blocked
    api = verifier.GitHubAPICache(
        lambda url: verifier.github_get_json(url, token=token)
    )
    user = api("https://api.github.com/user")
    if not isinstance(user, dict) or not isinstance(user.get("id"), int):
        raise ValueError("GitHub token did not authenticate an API user")
    results = []
    for receipt in receipts:
        key = (receipt["source"]["repository"], receipt["source"]["path"])
        label = f"{key[0]}:{key[1]}"
        try:
            key_result, problems = verifier.validate_receipt(
                receipt,
                queue=queue_by_key,
                dossiers=dossiers,
                source_root=source_root,
                expected_head=PR8_HEAD,
                repository_root=root,
                repository=OWNER_REPOSITORY,
                github_api=api,
            )
            if key_result != key or problems:
                raise ValueError("; ".join(problems) or "Receipt validator returned a different identity")
            verify_expected_comment(receipt, verifier, api, root)
            last_receipt_time = _git(root, "show", "-s", "--format=%cI", PR8_HEAD)
            job_counts = validate_exact_ci(api, not_before=last_receipt_time)
            results.append({
                "source": label,
                "status": "COPILOT_RECEIPT_VALIDATED",
                "pr_jobs": job_counts["pull_request"],
                "push_jobs": job_counts["push"],
            })
        except Exception as exc:
            results.append({"source": label, "status": "BLOCKED", "blocker": str(exc)})
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr8-root", type=Path, required=True,
                        help="full-history worktree at the exact pinned PR #8 head")
    parser.add_argument("--source-root", type=Path, required=True,
                        help="read-only upstream checkouts at their pinned revisions")
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
