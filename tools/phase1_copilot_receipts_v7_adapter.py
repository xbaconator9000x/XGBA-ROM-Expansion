#!/usr/bin/env python3
"""Fail-closed adapter for the pinned PR #8 eight-record v7 receipt register."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlencode

import phase1_copilot_receipts_v4_adapter as v4
import phase1_copilot_receipts_v5_adapter as v5
import phase1_copilot_receipts_v6_adapter as v6

PR8_HEAD = "b455f218537f7aad7876f51ced2542486835c3bf"
RECEIPT_COMMIT = "279077f773f0eb472696328ccea2ed3c554c1b0b"
REGISTER_BLOB = "ce4dc0e369d54041caf39306440d519098790f9b"
EVIDENCE_COMMIT = "4fbd104c22d0e3fca64dfd2fe3bbdd2dc6d75b15"
EVIDENCE_PATH = "docs/phase1-review-readiness/mgba-arm-next-three-chatgpt-source-evidence-20261102.md"
EVIDENCE_BLOB = "4ea724684bedaadd15d07610707ed912065039af"
RECEIPT_PATH = v6.RECEIPT_PATH
DOSSIERS_BLOB = v6.DOSSIERS_BLOB
DOSSIERS_SHA256 = v6.DOSSIERS_SHA256
DOSSIERS_PATH = v6.DOSSIERS_PATH
QUEUE_BLOB = v6.QUEUE_BLOB
QUEUE_SHA256 = v6.QUEUE_SHA256
QUEUE_PATH = v6.QUEUE_PATH

EIGHTH_KEY = ("mgba-emu/mgba", "include/mgba/internal/arm/emitter-thumb.h")
EIGHTH_LICENSING_RATIONALE = (
    "The pinned target and included emitter-inlines.h retain MPL-2.0 notices matching "
    "the pinned root LICENSE. This is file-level notice mapping only; combined-work "
    "and distribution clearance is not claimed."
)
EIGHTH_RECEIPT = {
    "blob": "7d27524b2e723696df642a72135bac024bbd8071",
    "source_sha256": "b7a0167782c8fd63665345ed4520bd00a530e792be712e111bd9b056900b7353",
    "dossier_sha256": "482d2a7131cef6f320f3e4786f2d3482e7a4217ca931428dd409e92d3e7da729",
    "receipt_sha256": "18261796a7ce6cb74f884a53a37cdcbe72284cc542b67264e1c41deb691075de",
    "evidence_commit": EVIDENCE_COMMIT,
    "receipt_commit": RECEIPT_COMMIT,
}
EXPECTED_ORDER = (*v6.EXPECTED_ORDER, EIGHTH_KEY)
EXPECTED_RECEIPTS = {
    **{key: dict(value) for key, value in v6.EXPECTED_RECEIPTS.items()},
    EIGHTH_KEY: EIGHTH_RECEIPT,
}
EXPECTED_BLOBS = {
    **v6.EXPECTED_BLOBS,
    RECEIPT_PATH: REGISTER_BLOB,
    EVIDENCE_PATH: EVIDENCE_BLOB,
}
MGBA_REVISION = "fd9dc5c2cbf234365068855851107e762fc6211b"


def _git(root, *args):
    return v4._git(root, *args)


def verify_register_history(
    current_bytes,
    previous_bytes,
    introduced_bytes,
    *,
    expected_digest=EIGHTH_RECEIPT["receipt_sha256"],
):
    current = current_bytes.splitlines(keepends=True)
    previous = previous_bytes.splitlines(keepends=True)
    introduced = introduced_bytes.splitlines(keepends=True)
    if (
        len(previous) != 7
        or len(current) != 8
        or len(introduced) != 8
        or current[:7] != previous
        or introduced[:7] != previous
        or current != introduced
    ):
        raise ValueError("The original seven receipt lines or append-only eighth line changed")
    try:
        receipt = json.loads(introduced[7])
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("The eighth receipt introduction is malformed") from exc
    source = receipt.get("source") if isinstance(receipt, dict) else None
    if (
        not isinstance(source, dict)
        or (source.get("repository"), source.get("path")) != EIGHTH_KEY
        or v4.receipt_digest(receipt) != expected_digest
    ):
        raise ValueError("The appended receipt does not match the immutable eighth identity")


def verify_pinned_worktree(root):
    root = Path(root).resolve()
    if _git(root, "rev-parse", "HEAD") != PR8_HEAD:
        raise ValueError(f"PR #8 worktree must be exact pinned head {PR8_HEAD}")
    for path, expected in EXPECTED_BLOBS.items():
        if _git(root, "rev-parse", f"{PR8_HEAD}:{path}") != expected:
            raise ValueError(f"Pinned PR #8 v7 blob mismatch: {path}")
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

    if _git(root, "rev-parse", f"{v6.PR8_HEAD}:{RECEIPT_PATH}") != v6.REGISTER_BLOB:
        raise ValueError("The pinned seven-receipt v6 register is unavailable")
    previous = subprocess.check_output(
        ["git", "-C", str(root), "show", f"{v6.PR8_HEAD}:{RECEIPT_PATH}"]
    )
    current = (root / RECEIPT_PATH).read_bytes()
    introduced = subprocess.check_output(
        ["git", "-C", str(root), "show", f"{RECEIPT_COMMIT}:{RECEIPT_PATH}"]
    )
    if _git(root, "rev-parse", f"{RECEIPT_COMMIT}:{RECEIPT_PATH}") != REGISTER_BLOB:
        raise ValueError("The eighth-receipt introduction register blob differs from its pin")
    _git(root, "merge-base", "--is-ancestor", v6.PR8_HEAD, RECEIPT_COMMIT)
    _git(root, "merge-base", "--is-ancestor", RECEIPT_COMMIT, PR8_HEAD)
    verify_register_history(current, previous, introduced)

    if hashlib.sha256((root / DOSSIERS_PATH).read_bytes()).hexdigest() != DOSSIERS_SHA256:
        raise ValueError("Original compressed machine dossier archive SHA-256 mismatch")
    if hashlib.sha256((root / QUEUE_PATH).read_bytes()).hexdigest() != QUEUE_SHA256:
        raise ValueError("Original compressed review queue SHA-256 mismatch")
    return root


def validate_semantic_scope(receipt):
    source = receipt.get("source") if isinstance(receipt, dict) else None
    key = (source.get("repository"), source.get("path")) if isinstance(source, dict) else None
    expected = EXPECTED_RECEIPTS.get(key)
    review = receipt.get("review") if isinstance(receipt, dict) else None
    licensing = review.get("licensing") if isinstance(review, dict) else None
    if (
        key == EIGHTH_KEY
        and isinstance(expected, dict)
        and isinstance(licensing, dict)
        and licensing.get("rationale") == EIGHTH_LICENSING_RATIONALE
        and v4.receipt_digest(receipt) == expected.get("receipt_sha256")
    ):
        return v5.validate_semantic_scope(receipt, allow_v7_notice_mapping=True)
    return v6.validate_semantic_scope(receipt)


def validate_receipt_inventory(receipts):
    if not isinstance(receipts, list) or len(receipts) != len(EXPECTED_ORDER):
        raise ValueError("The v7 register must contain exactly eight pinned receipt records")
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
            or source.get("revision") != MGBA_REVISION
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


def _is_copilot_account(user):
    return v6._is_copilot_account(user)


def verify_non_copilot_evidence_authorship(receipt, api, repository_root):
    review = receipt.get("review")
    authorship = review.get("authorship") if isinstance(review, dict) else None
    entries = [authorship.get("dossier")] if isinstance(authorship, dict) else []
    evidence = authorship.get("substantive_evidence") if isinstance(authorship, dict) else None
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("Substantive-evidence authorship provenance is incomplete")
    entries.extend(evidence)
    root = Path(repository_root).resolve()
    evidence_commit = receipt["target"]["evidence_commit"]
    _git(root, "merge-base", "--is-ancestor", evidence_commit, PR8_HEAD)
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("Authorship provenance is not an object")
        path, expected_sha = item.get("path"), item.get("sha256")
        if (
            not isinstance(path, str)
            or not path
            or Path(path).is_absolute()
            or ".." in Path(path).parts
            or not isinstance(expected_sha, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_sha)
        ):
            raise ValueError("Authorship provenance path or digest is invalid")
        candidate = root
        unsafe = False
        for part in Path(path).parts:
            candidate = candidate / part
            unsafe = unsafe or candidate.is_symlink()
        if unsafe or not candidate.is_file():
            raise ValueError("Authorship evidence file is missing or unsafe")
        if hashlib.sha256(candidate.read_bytes()).hexdigest() != expected_sha:
            raise ValueError("Authorship evidence hash differs from the exact checkout")
        try:
            evidence_bytes = subprocess.check_output(
                ["git", "-C", str(root), "show", f"{evidence_commit}:{path}"],
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError as exc:
            raise ValueError("Authorship evidence file is missing at its evidence commit") from exc
        if hashlib.sha256(evidence_bytes).hexdigest() != expected_sha:
            raise ValueError("Authorship evidence hash differs at its evidence commit")
        commits = api(
            f"{v4.API_ROOT}/commits?{urlencode({'path': path, 'sha': evidence_commit, 'per_page': 1})}"
        )
        if not isinstance(commits, list) or len(commits) != 1:
            raise ValueError("No unique Git commit provenance for " + path)
        commit_sha = commits[0].get("sha")
        if not isinstance(commit_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
            raise ValueError("GitHub returned invalid file authorship commit for " + path)
        commit = api(f"{v4.API_ROOT}/commits/{commit_sha}")
        if (
            not isinstance(commit, dict)
            or commit.get("sha") != commit_sha
            or not isinstance(commit.get("files"), list)
            or not any(file.get("filename") == path for file in commit["files"] if isinstance(file, dict))
        ):
            raise ValueError("GitHub commit does not attest the cited file path")
        author = commit.get("author")
        committer = commit.get("committer")
        if (
            not isinstance(author, dict)
            or not isinstance(committer, dict)
            or not isinstance(author.get("login"), str)
            or not isinstance(committer.get("login"), str)
            or _is_copilot_account(author)
            or _is_copilot_account(committer)
        ):
            raise ValueError("Copilot cannot review its own dossier or substantive evidence")


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
            and comment.get("issue_url") == f"{v4.API_ROOT}/issues/{v4.PR_NUMBER}"
            and comment.get("html_url")
            == f"https://github.com/{v4.OWNER_REPOSITORY}/pull/{v4.PR_NUMBER}"
            f"#issuecomment-{comment.get('id')}"
            and verifier._attestation_section_is_valid(comment.get("body"), markers)
        ):
            matching.append(comment)
    if len(matching) != 1:
        raise ValueError("Expected one unique, unquoted receipt-bound Copilot attestation")
    comment = matching[0]
    if not v4._bot_identity(comment.get("user")):
        raise ValueError("Receipt attestation is not from the verified Copilot Bot identity")
    try:
        comment_time = datetime.fromisoformat(comment["created_at"].replace("Z", "+00:00"))
        commit_time = datetime.fromisoformat(
            _git(repository_root, "show", "-s", "--format=%cI", expected["receipt_commit"]).replace(
                "Z", "+00:00"
            )
        )
    except (KeyError, AttributeError, TypeError, ValueError) as exc:
        raise ValueError("Attestation or receipt-introduction timestamp is invalid") from exc
    if (
        comment_time.tzinfo is None
        or commit_time.tzinfo is None
        or comment_time.astimezone(timezone.utc) <= commit_time.astimezone(timezone.utc)
    ):
        raise ValueError("Authenticated Copilot attestation predates its receipt introduction")
    return comment


def validate_exact_ci(api, *, not_before=None):
    return v5.validate_exact_ci(api, expected_head=PR8_HEAD, not_before=not_before)


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
    head_time = _git(root, "show", "-s", "--format=%cI", PR8_HEAD)
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
                raise ValueError(
                    "; ".join(validation_problems)
                    or "Pinned validator returned a different identity"
                )
            verify_non_copilot_evidence_authorship(receipt, api, root)
            verify_expected_comment(receipt, verifier, api, root)
            counts = validate_exact_ci(api, not_before=head_time)
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
