#!/usr/bin/env python3
"""Emit a fail-closed, non-approving status report for the three ARM receipts."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlencode

from phase1_bulk_triage import canonical, digest
from phase1_copilot_receipts import (
    CENSUS_WORKFLOW_PATH,
    GitHubAPICache,
    PR_WORKFLOW_NAME,
    _authenticated_copilot_bot,
    _attestation_section_is_valid,
    _verify_file_authorship,
    _verify_source_reference,
    github_get_json,
    load_receipts,
    receipt_digest,
)

RECEIPT_PATH = "docs/phase1-review-readiness/copilot-semantic-review-receipts.jsonl"
SCHEMA = "xgba.phase1.arm_receipt_status.v1"
DOSSIER_ARCHIVE_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
TARGETS = {
    "68d40e2e26b63751fd5ebe5b2c6d8088d1ee4435174946782d87c24dc2eb7361": {
        "path": "include/mgba/internal/arm/decoder-inlines.h",
        "blob": "11d41d520f1c9661eb56352f1a0b7a651fd99577",
        "source_sha256": "216481c93aec0456cba015fcb224ac737d727534fc98243d61bfd91ccde7a84c",
        "dossier_sha256": "05d586e5055c29f4b983f57b1e4b16a1ed4f13c1ad3279c14abfaecb77e7f419",
    },
    "a9a92f196fb14985d9d7dbe36e647ed5bc17ab67c74c9426c0b7c2f92dfe3bf8": {
        "path": "include/mgba/internal/arm/emitter-inlines.h",
        "blob": "38bab70bddf08f6160461ab73a1649a2bdbd256f",
        "source_sha256": "693c06f0336b5b47222529a4125d04f60ba855d3d559ea256611c7c2cf7bbaac",
        "dossier_sha256": "8f51aeccbdc79e89725255663e8467bdc9f7f2441637edb069b222efce8cd441",
    },
    "f4fa4d806cb13b7b8518a675e244bb476fe9ac73d31ef1f04e7c3fdbdbcec2ad": {
        "path": "include/mgba/internal/arm/isa-thumb.h",
        "blob": "69839d47a0f67d6b9c10eb635da388d0cf88cfb9",
        "source_sha256": "a3c88e85789f261947ad3eb2c3831b51ddc193d750be24acc6eb5de069ffc7a0",
        "dossier_sha256": "3c8da4a3778cfdf0a1a3897e28db762f1bcb031a217e5aa30b9ffbed8a9cc4c6",
    },
}
OUTSTANDING_CLOSURE_OBJECTIONS = [
    "Typed little-endian accesses through uint16_t video backing remain an effective-type/alignment concern.",
    "ARM_SXT_8/16 and Thumb branch paths retain signed-left-shift undefined-behavior cases.",
    "decoder.h bitfield/ABI evidence is host-only; ARMResolveMemoryAccess has unresolved signed-shift and INT32_MIN negation cases.",
    "ARM branch decode uses implementation-defined signed conversion/right shift; reserved-NV debugger interpretation remains open.",
    "No independent ARMv4T oracle covers every emitted table slot and handler.",
    "Source and file-level MPL-2.0 notice checks are not combined-distribution licensing clearance.",
]
REQUIRED_CENSUS_STEPS = {
    "Verify pinned mGBA ARM decode/emit review evidence",
    "Evaluate Phase 1 semantic gate (incomplete is expected until signed review)",
}
VALIDATOR_RUN_BLOCKER = "Exact-head validation run is missing or unsuccessful"


def _read_rows(path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _load_dossiers(path, queue):
    dossiers = {}
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for index, line in enumerate(stream):
            if index >= len(queue):
                raise ValueError("Dossier archive contains extra rows")
            dossier = json.loads(line)
            row = queue[index]
            row_digest = digest(canonical(dossier))
            provenance = dossier.get("provenance", {})
            if row_digest != row["evidence_sha256"]:
                raise ValueError("Dossier archive row digest does not match the queue")
            if (provenance.get("repository"), provenance.get("path"), provenance.get("git_blob_sha")) != (
                row["repo"], row["path"], row["blob_sha"]
            ):
                raise ValueError("Dossier archive identity does not match the queue")
            dossiers[(row["repo"], row["path"])] = dossier
    if len(dossiers) != len(queue):
        raise ValueError("Dossier archive is incomplete")
    return dossiers


def _find_target_receipt(receipts, receipt_sha256):
    matches = [
        receipt for receipt in receipts
        if receipt.get("attestation", {}).get("receipt_sha256") == receipt_sha256
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one register row for {receipt_sha256}; found {len(matches)}")
    return matches[0]


def _receipt_identity_problems(receipt, expected_digest, expected, row, dossier):
    problems = []
    if receipt_digest(receipt) != expected_digest:
        problems.append("Canonical receipt digest mismatch")
    source = receipt.get("source", {})
    target = receipt.get("target", {})
    if (
        source.get("repository") != "mgba-emu/mgba"
        or source.get("path") != expected["path"]
        or source.get("git_blob_sha1") != expected["blob"]
        or source.get("source_sha256") != expected["source_sha256"]
        or target.get("repository") != "xbaconator9000x/XGBA-ROM-Expansion"
        or target.get("pull_number") != 8
        or target.get("receipt_path") != RECEIPT_PATH
        or target.get("evidence_commit") != "e2cae6f1c073be4ee04691a57915adf740868279"
    ):
        problems.append("Receipt identity or immutable lifecycle binding mismatch")
    if row.get("blob_sha") != expected["blob"]:
        problems.append("Inventory Git blob differs from the canonical receipt identity")
    if digest(canonical(dossier)) != expected["dossier_sha256"]:
        problems.append("Original dossier row SHA-256 mismatch")
    if receipt.get("machine_dossier_sha256") != expected["dossier_sha256"]:
        problems.append("Receipt machine dossier SHA-256 mismatch")
    provenance = dossier.get("provenance", {})
    if provenance.get("source_content_sha256") != expected["source_sha256"]:
        problems.append("Original dossier source SHA-256 mismatch")
    return problems


def _nonapproving_status(review):
    blockers = _nonapproving_policy_blockers(review)
    blockers.extend(OUTSTANDING_CLOSURE_OBJECTIONS)
    return {
        "status": "NEEDS_EVIDENCE",
        "gate_contribution": 0,
        "external_human_approval": False,
        "blockers": blockers,
    }


def _verify_receipt_evidence(
    receipt, expected_digest, expected, dossiers, queue, source_root, dossier_archive,
):
    problems = []
    source = receipt.get("source", {})
    key = (source.get("repository"), source.get("path"))
    row = queue.get(key)
    dossier = dossiers.get(key)
    if row is None or dossier is None:
        problems.append("Pinned source or original dossier row is absent from the inventory")
        return problems
    problems.extend(_receipt_identity_problems(receipt, expected_digest, expected, row, dossier))

    try:
        if hashlib.sha256(Path(dossier_archive).read_bytes()).hexdigest() != DOSSIER_ARCHIVE_SHA256:
            problems.append("Original compressed dossier archive SHA-256 mismatch")
    except OSError:
        problems.append("Original compressed dossier archive is unavailable")

    try:
        source_bytes = _verify_source_reference(source, source_root)
        if hashlib.sha256(source_bytes).hexdigest() != expected["source_sha256"]:
            problems.append("Pinned source SHA-256 mismatch")
    except (OSError, ValueError, TypeError) as exc:
        problems.append("Pinned source verification failed: " + str(exc))

    review = receipt.get("review", {})
    if len((review.get("semantic_rationale") or "").strip()) < 40:
        problems.append("Receipt semantic rationale is missing or too short")
    findings = review.get("findings")
    if not isinstance(findings, list) or not findings:
        problems.append("Receipt source-grounded findings are missing")
    coverage = review.get("whole_file_coverage", {})
    lines = len(source_bytes.splitlines()) if "source_bytes" in locals() else None
    if (
        coverage.get("scope") != "WHOLE_FILE"
        or coverage.get("source_sha256") != expected["source_sha256"]
        or coverage.get("source_lines") != lines
        or coverage.get("reviewed_line_ranges") != [[1, lines]]
    ):
        problems.append("Receipt does not bind contiguous whole-file source coverage")
    if isinstance(findings, list):
        for finding in findings:
            anchors = finding.get("source_lines") if isinstance(finding, dict) else None
            if (
                not isinstance(finding, dict)
                or len((finding.get("claim") or "").strip()) < 12
                or not isinstance(anchors, list) or not anchors
                or lines is None
                or any(not isinstance(anchor, int) or anchor < 1 or anchor > lines for anchor in anchors)
            ):
                problems.append("Receipt finding lacks a substantive, in-file source anchor")
                break

    closure = review.get("dependency_closure", {})
    if (
        closure.get("status") != "COMPLETE"
        or len((closure.get("rationale") or "").strip()) < 20
        or not isinstance(closure.get("dependencies"), list)
    ):
        problems.append("Dependency closure is not complete")
    else:
        for dependency in closure["dependencies"]:
            try:
                _verify_source_reference(dependency, source_root)
            except (OSError, ValueError, TypeError) as exc:
                problems.append("Dependency identity failed: " + str(exc))
    licensing = review.get("licensing", {})
    if (
        licensing.get("status") != "CLEARED"
        or len((licensing.get("rationale") or "").strip()) < 20
        or not licensing.get("evidence")
    ):
        problems.append("Pinned file-level license evidence is incomplete")
    else:
        for evidence in licensing["evidence"]:
            try:
                _verify_source_reference(evidence, source_root)
            except (OSError, ValueError, TypeError) as exc:
                problems.append("License evidence identity failed: " + str(exc))
    objections = review.get("objections")
    if not isinstance(objections, list) or any(
        not isinstance(item, dict) or item.get("status") != "RESOLVED"
        or len((item.get("resolution") or "").strip()) < 12
        for item in objections
    ):
        problems.append("Receipt has missing or unresolved per-file objections")
    distinctions = review.get("evidence_distinctions", {})
    for kind in ("compiled_native", "runtime_gameplay", "save_restart", "physical_flash"):
        evidence = distinctions.get(kind, {})
        if evidence.get("status") == "VERIFIED":
            problems.append("Unsupported non-source VERIFIED claim: " + kind)
    if review.get("armv4t_oracle", {}).get("status") == "VERIFIED":
        problems.append("Unsupported ARMv4T oracle verification claim")
    return problems


def _nonapproving_policy_blockers(review):
    blockers = []
    decision = review.get("decision")
    if decision == "APPROVED":
        blockers.append(
            "Legacy v4 APPROVED token is gate-affecting and cannot be relabeled as non-approving"
        )
    elif decision != "COPILOT_REVIEWED":
        blockers.append("Receipt has no explicit non-approving COPILOT_REVIEWED decision")
    for kind in ("compiled_native", "runtime_gameplay", "save_restart", "physical_flash"):
        if review.get("evidence_distinctions", {}).get(kind, {}).get("status") == "VERIFIED":
            blockers.append("Unsupported non-source VERIFIED claim: " + kind)
    if review.get("armv4t_oracle", {}).get("status") == "VERIFIED":
        blockers.append("Unsupported ARMv4T oracle verification claim")
    return blockers


def _validate_standalone_attribution(receipt, expected_digest, repository_root, api):
    import phase1_copilot_receipts as receipt_validator

    target = receipt.get("target", {})
    if receipt.get("attestation", {}).get("mode") != "conversation_comment":
        raise ValueError("This receipt does not declare per-file conversation-comment attribution")
    repository = target.get("repository")
    pull_number = target.get("pull_number")
    receipt_line = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    introduction, introduction_time = receipt_validator._find_receipt_introduction(
        repository_root, RECEIPT_PATH, receipt_line, target.get("evidence_commit"), api.expected_head
    )
    api_root = f"https://api.github.com/repos/{repository}"
    pull = api(f"{api_root}/pulls/{pull_number}")
    if pull.get("head", {}).get("sha") != api.expected_head:
        raise ValueError("Pull request head differs from exact validation head")
    if pull.get("user", {}).get("login", "").casefold() in {
        "copilot", receipt_validator.COPILOT_BOT_LOGIN.casefold()
    }:
        raise ValueError("Copilot cannot attest to a PR authored by Copilot")
    comments = api.paginate(f"{api_root}/issues/{pull_number}/comments")
    markers = (
        receipt_validator.RECEIPT_MARKER + expected_digest,
        receipt_validator.INTRO_COMMIT_MARKER + introduction,
        receipt_validator.EVIDENCE_COMMIT_MARKER + target["evidence_commit"],
        receipt_validator.DECISION_MARKER,
    )
    matching = []
    for comment in comments:
        if not _authenticated_copilot_bot(comment.get("user")):
            continue
        if comment.get("issue_url") != f"{api_root}/issues/{pull_number}":
            continue
        if comment.get("html_url") != (
            f"https://github.com/{repository}/pull/{pull_number}#issuecomment-{comment.get('id')}"
        ):
            continue
        try:
            created = receipt_validator.datetime.fromisoformat(
                comment.get("created_at", "").replace("Z", "+00:00")
            )
        except ValueError:
            continue
        comment_id = comment.get("id")
        if (
            not isinstance(comment_id, int) or comment_id < 1
            or created.tzinfo is None or created <= introduction_time
        ):
            continue
        if _attestation_section_is_valid(comment.get("body"), markers):
            matching.append(comment)
    if len(matching) != 1 or len({item.get("id") for item in matching}) != 1:
        raise ValueError("Missing or non-unique per-file standalone Copilot attestation")
    _verify_file_authorship(
        receipt.get("review", {}), repository, pull_number,
        target["evidence_commit"], repository_root, api,
    )
    return {
        "verified": True,
        "comment_id": matching[0]["id"],
        "introduction_commit": introduction,
        "reviewer_login": matching[0]["user"]["login"],
        "reviewer_id": matching[0]["user"]["id"],
    }


def _matching_pull_request(run, pull_number):
    for item in run.get("pull_requests", []):
        if item == pull_number or (
            isinstance(item, dict) and item.get("number") == pull_number
        ):
            return True
    return False


def _validate_run_job(run, api, *, expected_head, expected_event, expected_workflow_name,
                      expected_path, expected_job_names, pull_number=None):
    if run.get("head_sha") != expected_head:
        return None, "Run head SHA is stale or mismatched"
    if run.get("event") != expected_event:
        return None, "Run event is not " + expected_event
    if run.get("name") != expected_workflow_name or run.get("path") != expected_path:
        return None, "Run workflow identity is mismatched"
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        return None, "Matching workflow run has not completed successfully"
    if pull_number is not None and not _matching_pull_request(run, pull_number):
        return None, "Pull request run does not identify PR #" + str(pull_number)
    jobs = api.paginate(
        f"https://api.github.com/repos/{api.repository}/actions/runs/{run['id']}/jobs",
        result_key="jobs",
    )
    job = next(
        (item for item in jobs if item.get("name") in expected_job_names
         and item.get("conclusion") == "success"),
        None,
    )
    if job is None:
        return None, "Matching successful census job is missing"
    step_records = []
    step_map = {step.get("name"): step for step in job.get("steps", [])}
    for required in sorted(REQUIRED_CENSUS_STEPS):
        step = step_map.get(required)
        if step is None or step.get("status") != "completed" or step.get("conclusion") != "success":
            return None, "Required successful step is missing: " + required
        step_records.append({
            "number": step.get("number"),
            "name": step["name"],
            "status": step["status"],
            "conclusion": step["conclusion"],
        })
    return {
        "run_id": run["id"],
        "run_attempt": run.get("run_attempt"),
        "head_sha": run["head_sha"],
        "event": run["event"],
        "workflow_name": run["name"],
        "job_id": job["id"],
        "job_name": job["name"],
        "steps": step_records,
    }, None


def _has_census_reference(run, repository):
    suffix = f"{repository}/{CENSUS_WORKFLOW_PATH}"
    return any(
        isinstance(item.get("path"), str)
        and item["path"].split("@", 1)[0].endswith(suffix)
        for item in run.get("referenced_workflows", [])
    )


def verify_exact_head_ci(api, expected_head, repository, pull_number):
    try:
        runs = api.paginate(
            f"https://api.github.com/repos/{repository}/actions/runs?"
            + urlencode({"head_sha": expected_head}),
            result_key="workflow_runs",
        )
    except (ValueError, KeyError, TypeError) as exc:
        return {"verified": False, "blocker": "Unable to enumerate exact-head workflow runs: " + str(exc)}

    pull_api = f"https://api.github.com/repos/{repository}/pulls/{pull_number}"
    try:
        pull = api(pull_api)
    except (ValueError, KeyError, TypeError) as exc:
        return {"verified": False, "blocker": "Unable to read target pull request: " + str(exc)}
    if pull.get("head", {}).get("sha") != expected_head:
        return {"verified": False, "blocker": "Live pull request head differs from requested head"}

    pr_candidates = [
        run for run in runs
        if run.get("name") == PR_WORKFLOW_NAME and run.get("event") == "pull_request"
        and run.get("head_sha") == expected_head and _matching_pull_request(run, pull_number)
        and _has_census_reference(run, repository)
    ]
    push_candidates = [
        run for run in runs
        if run.get("name") == "Phase 1 pinned source census and review dossiers"
        and run.get("path") == CENSUS_WORKFLOW_PATH and run.get("event") == "push"
        and run.get("head_sha") == expected_head
    ]
    errors = []
    details = {}
    checks = (
        ("pull_request", pr_candidates, "pull_request", PR_WORKFLOW_NAME,
         ".github/workflows/phase1-pr-checks.yml",
         {"census / census", "census"}),
        ("push_census", push_candidates, "push",
         "Phase 1 pinned source census and review dossiers",
         CENSUS_WORKFLOW_PATH, {"census"}),
    )
    for label, candidates, event, name, path, job_names in checks:
        verified = None
        candidate_errors = []
        for run in sorted(candidates, key=lambda item: item.get("id", 0), reverse=True):
            if label == "pull_request" and not _has_census_reference(run, repository):
                continue
            if label == "pull_request" and run.get("path") != path:
                continue
            try:
                result, error = _validate_run_job(
                    run, api, expected_head=expected_head, expected_event=event,
                    expected_workflow_name=name, expected_path=path,
                    expected_job_names=job_names,
                    pull_number=pull_number if label == "pull_request" else None,
                )
            except (ValueError, KeyError, TypeError) as exc:
                result, error = None, "Unable to inspect candidate run jobs: " + str(exc)
            if result is not None:
                verified = result
                break
            candidate_errors.append(error)
        if verified is None:
            errors.append(label + ": " + (
                candidate_errors[0] if candidate_errors else "No matching run found"
            ))
        else:
            details[label] = verified
    return {
        "verified": not errors,
        "runs": details,
        "blockers": errors,
    }


def build_report(receipts, *, expected_head, repository, pull_number, repository_root,
                 source_root, audit_root, dossier_archive, api):
    audit_root = Path(audit_root)
    queue_rows = _read_rows(audit_root / "semantic_review_queue.csv.gz")
    queue = {(item["repo"], item["path"]): item for item in queue_rows}
    if len(queue) != len(queue_rows):
        raise ValueError("Semantic queue contains duplicate source identities")
    dossiers = _load_dossiers(audit_root / "candidate_review_dossiers.jsonl.gz", queue_rows)
    run_status = verify_exact_head_ci(api, expected_head, repository, pull_number)
    result_rows = []
    for receipt_digest_value, expected in TARGETS.items():
        problems = []
        try:
            receipt = _find_target_receipt(receipts, receipt_digest_value)
        except ValueError as exc:
            result_rows.append({
                "receipt_sha256": receipt_digest_value,
                "source_path": expected["path"],
                "status": "NEEDS_EVIDENCE",
                "gate_contribution": 0,
                "blockers": [str(exc)],
            })
            continue

        evidence_problems = _verify_receipt_evidence(
            receipt, receipt_digest_value, expected, dossiers, queue, source_root,
            dossier_archive,
        )
        problems.extend(evidence_problems)
        source_status = {
            "git_blob_sha1": receipt.get("source", {}).get("git_blob_sha1"),
            "source_sha256": receipt.get("source", {}).get("source_sha256"),
            "dossier_sha256": receipt.get("machine_dossier_sha256"),
            "verified": not evidence_problems,
        }
        try:
            attribution = _validate_standalone_attribution(
                receipt, receipt_digest_value, repository_root, api
            )
        except (ValueError, OSError, KeyError, TypeError) as exc:
            attribution = {"verified": False}
            problems.append("Attribution validation failed: " + str(exc))

        proposed_decision = receipt.get("review", {}).get("decision")
        problems.extend(_nonapproving_policy_blockers(receipt.get("review", {})))
        if not run_status["verified"]:
            problems.extend(run_status["blockers"])
        problems.extend(OUTSTANDING_CLOSURE_OBJECTIONS)
        result_rows.append({
            "receipt_sha256": receipt_digest_value,
            "source_path": expected["path"],
            "registered_decision_not_imported": proposed_decision,
            "receipt_evidence": {
                "verified": not evidence_problems,
                "source_identity": source_status,
                "validation_errors": evidence_problems,
            },
            "standalone_attribution": attribution,
            "exact_head_ci": run_status,
            **_nonapproving_status(receipt.get("review", {})),
            "blockers": list(dict.fromkeys(
                problems + _nonapproving_policy_blockers(receipt.get("review", {}))
                + OUTSTANDING_CLOSURE_OBJECTIONS
            )),
        })
    return {
        "schema": SCHEMA,
        "head": expected_head,
        "repository": repository,
        "pull_number": pull_number,
        "disposition": "NON_APPROVING_NEEDS_EVIDENCE",
        "gate_mutated": False,
        "approval_counts_mutated": False,
        "exact_head_ci": run_status,
        "rows": result_rows,
        "limitations": [
            "This status report never converts a v4 APPROVED receipt token into an approval.",
            "The original Phase 1 gate remains authoritative and is not modified by this checker.",
            "Source/build evidence is not complete emulator, gameplay, save/restart, or physical-flash proof.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--receipts", type=Path, default=Path(RECEIPT_PATH))
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--expected-head", default=os.environ.get("GITHUB_SHA"))
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--pull-number", type=int, default=8)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not args.expected_head or len(args.expected_head) != 40:
        parser.error("--expected-head must be a full Git commit SHA")
    if not re.fullmatch(r"[0-9a-f]{40}", args.expected_head):
        parser.error("--expected-head must be a lowercase hexadecimal Git commit SHA")
    if not args.repository:
        parser.error("--repository or GITHUB_REPOSITORY is required")
    receipts, load_problems = load_receipts(args.receipts)
    if load_problems:
        parser.error("; ".join(load_problems))
    api = GitHubAPICache(github_get_json)
    api.expected_head = args.expected_head
    api.repository = args.repository
    report = build_report(
        receipts, expected_head=args.expected_head, repository=args.repository,
        pull_number=args.pull_number, repository_root=args.repository_root,
        source_root=args.source_root, audit_root=args.audit_root,
        dossier_archive=args.repository_root / "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz",
        api=api,
    )
    output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
