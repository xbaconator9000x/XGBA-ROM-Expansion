#!/usr/bin/env python3
"""Fail-closed adapter for the pinned PR #8 seven-record v6 receipt register."""
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

PR8_HEAD = "4c7c09b6257d2e88a2e19bab524e9d7174d3023e"
RECEIPT_COMMIT = "487da72f27dfc4e634cecc11b4dbdd596ec05e00"
REGISTER_BLOB = "0c5b50003b89d346d04c86e52774c4e01e9d321b"
EVIDENCE_COMMIT = "e2cae6f1c073be4ee04691a57915adf740868279"
EVIDENCE_PATH = "docs/phase1-review-readiness/mgba-arm-three-headers-chatgpt-source-evidence-20261102.md"
EVIDENCE_BLOB = "c26ab43096c4b217952cf17840bfc9ddf7ba8b20"
CI_RETRY_PATH = "docs/phase1-review-readiness/analyst-ci-execution-provenance-20261102.md"
CI_RETRY_BLOB = "ddc399dbe9cd05561a2cc25e5c9aeca31fa5b995"
DOSSIERS_BLOB = v5.DOSSIERS_BLOB
DOSSIERS_SHA256 = v5.DOSSIERS_SHA256
DOSSIERS_PATH = v5.DOSSIERS_PATH
QUEUE_BLOB = v5.QUEUE_BLOB
QUEUE_SHA256 = v5.QUEUE_SHA256
QUEUE_PATH = v5.QUEUE_PATH
RECEIPT_PATH = v5.RECEIPT_PATH
EXPECTED_ORDER = (
    *v5.EXPECTED_ORDER,
    ("mgba-emu/mgba", "include/mgba/internal/arm/decoder-inlines.h"),
    ("mgba-emu/mgba", "include/mgba/internal/arm/emitter-inlines.h"),
    ("mgba-emu/mgba", "include/mgba/internal/arm/isa-thumb.h"),
)
EXPECTED_RECEIPTS = {
    key: dict(value) for key, value in v5.EXPECTED_RECEIPTS.items()
}
EXPECTED_RECEIPTS.update({
    ("mgba-emu/mgba", "include/mgba/internal/arm/decoder-inlines.h"): {
        "blob": "11d41d520f1c9661eb56352f1a0b7a651fd99577",
        "source_sha256": "216481c93aec0456cba015fcb224ac737d727534fc98243d61bfd91ccde7a84c",
        "dossier_sha256": "05d586e5055c29f4b983f57b1e4b16a1ed4f13c1ad3279c14abfaecb77e7f419",
        "receipt_sha256": "68d40e2e26b63751fd5ebe5b2c6d8088d1ee4435174946782d87c24dc2eb7361",
        "evidence_commit": EVIDENCE_COMMIT,
        "receipt_commit": RECEIPT_COMMIT,
    },
    ("mgba-emu/mgba", "include/mgba/internal/arm/emitter-inlines.h"): {
        "blob": "38bab70bddf08f6160461ab73a1649a2bdbd256f",
        "source_sha256": "693c06f0336b5b47222529a4125d04f60ba855d3d559ea256611c7c2cf7bbaac",
        "dossier_sha256": "8f51aeccbdc79e89725255663e8467bdc9f7f2441637edb069b222efce8cd441",
        "receipt_sha256": "a9a92f196fb14985d9d7dbe36e647ed5bc17ab67c74c9426c0b7c2f92dfe3bf8",
        "evidence_commit": EVIDENCE_COMMIT,
        "receipt_commit": RECEIPT_COMMIT,
    },
    ("mgba-emu/mgba", "include/mgba/internal/arm/isa-thumb.h"): {
        "blob": "69839d47a0f67d6b9c10eb635da388d0cf88cfb9",
        "source_sha256": "a3c88e85789f261947ad3eb2c3831b51ddc193d750be24acc6eb5de069ffc7a0",
        "dossier_sha256": "3c8da4a3778cfdf0a1a3897e28db762f1bcb031a217e5aa30b9ffbed8a9cc4c6",
        "receipt_sha256": "f4fa4d806cb13b7b8518a675e244bb476fe9ac73d31ef1f04e7c3fdbdbcec2ad",
        "evidence_commit": EVIDENCE_COMMIT,
        "receipt_commit": RECEIPT_COMMIT,
    },
})
EXPECTED_BLOBS = {
    v5.PROTOCOL_PATH: v5.PROTOCOL_BLOB,
    RECEIPT_PATH: REGISTER_BLOB,
    v5.VALIDATOR_PATH: v4.VALIDATOR_BLOB,
    v5.TRIAGE_PATH: v4.TRIAGE_BLOB,
    v5.DOSSIERS_PATH: DOSSIERS_BLOB,
    v5.QUEUE_PATH: QUEUE_BLOB,
    EVIDENCE_PATH: EVIDENCE_BLOB,
    CI_RETRY_PATH: CI_RETRY_BLOB,
}


def verify_pinned_worktree(root):
    root = Path(root).resolve()
    if v4._git(root, "rev-parse", "HEAD") != PR8_HEAD:
        raise ValueError(f"PR #8 worktree must be exact pinned head {PR8_HEAD}")
    for path, expected in EXPECTED_BLOBS.items():
        if v4._git(root, "rev-parse", f"{PR8_HEAD}:{path}") != expected:
            raise ValueError(f"Pinned PR #8 v6 blob mismatch: {path}")
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

    if v4._git(root, "rev-parse", f"{v5.PR8_HEAD}:{RECEIPT_PATH}") != v5.REGISTER_BLOB:
        raise ValueError("Historical four-receipt register blob changed")
    previous = subprocess.check_output(
        ["git", "-C", str(root), "show", f"{v5.PR8_HEAD}:{RECEIPT_PATH}"]
    ).splitlines(keepends=True)
    current = (root / RECEIPT_PATH).read_bytes().splitlines(keepends=True)
    if len(previous) != 4 or current[:4] != previous:
        raise ValueError("The original four receipt lines were not preserved byte-for-byte")
    if v4._git(root, "rev-parse", f"{RECEIPT_COMMIT}^") != EVIDENCE_COMMIT:
        raise ValueError("Seven-receipt introduction does not directly follow its evidence commit")
    if v4._git(root, "rev-parse", f"{PR8_HEAD}^") != RECEIPT_COMMIT:
        raise ValueError("Exact CI retry head is not the direct child of the immutable receipt-introduction commit")
    v4._git(root, "merge-base", "--is-ancestor", EVIDENCE_COMMIT, RECEIPT_COMMIT)
    v4._git(root, "merge-base", "--is-ancestor", RECEIPT_COMMIT, PR8_HEAD)
    if hashlib.sha256((root / DOSSIERS_PATH).read_bytes()).hexdigest() != DOSSIERS_SHA256:
        raise ValueError("Original compressed machine dossier archive SHA-256 mismatch")
    if hashlib.sha256((root / QUEUE_PATH).read_bytes()).hexdigest() != QUEUE_SHA256:
        raise ValueError("Original compressed review queue SHA-256 mismatch")
    return root


def validate_semantic_scope(receipt):
    return v5.validate_semantic_scope(receipt)


def validate_receipt_inventory(receipts):
    if not isinstance(receipts, list) or len(receipts) != len(EXPECTED_ORDER):
        raise ValueError("The v6 register must contain exactly seven pinned receipt records")
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


def _is_copilot_account(user):
    if not isinstance(user, dict):
        return False
    login = user.get("login")
    return (
        user.get("id") == v4.BOT_ID
        or user.get("node_id") == v4.BOT_NODE_ID
        or login in v4.BOT_LOGINS
        or (isinstance(login, str) and "copilot" in login.casefold())
    )


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
    v4._git(root, "merge-base", "--is-ancestor", evidence_commit, PR8_HEAD)
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
        candidate = root / path
        if candidate.is_symlink() or not candidate.is_file():
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
        query = f"{v4.API_ROOT}/commits?{urlencode({'path': path, 'sha': evidence_commit, 'per_page': 1})}"
        commits = api(query)
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
            and v5._bot_identity(comment.get("user"))
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
    receipt_time = v4._git(root, "show", "-s", "--format=%cI", PR8_HEAD)
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
            verify_non_copilot_evidence_authorship(receipt, api, root)
            verify_expected_comment(receipt, verifier, api, root)
            counts = v5.validate_exact_ci(api, expected_head=PR8_HEAD, not_before=receipt_time)
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
