#!/usr/bin/env python3
"""Validate attributable, evidence-complete Copilot Phase 1 review receipts."""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlencode, urlparse

from phase1_bulk_triage import PINS, canonical, digest, git_blob, source_bytes

SCHEMA = "xgba.phase1.copilot_semantic_review_receipt.v3"
SHA1 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
RECEIPT_MARKER = "XGBA-Phase1-Receipt-SHA256: "
DECISION_MARKER = "XGBA-Phase1-Decision: APPROVED"
CENSUS_WORKFLOW_PATH = ".github/workflows/phase1-census.yml"
PR_WORKFLOW_NAME = "Phase 1 consolidated PR checks"
EVIDENCE_STATES = {"VERIFIED", "NOT_APPLICABLE", "NOT_CLAIMED", "NOT_RUN"}
EVIDENCE_KINDS = {
    "synthetic": {"synthetic_test"},
    "compiled_native": {"build_artifact"},
    "runtime_gameplay": {"runtime_trace", "runtime_capture"},
    "save_restart": {"save_image", "save_restart_trace"},
    "physical_flash": {"physical_flash_capture"},
}


def receipt_digest(receipt):
    """Hash the durable receipt body, excluding its GitHub review attestation."""
    return digest(canonical({k: v for k, v in receipt.items() if k != "attestation"}))


def github_get_json(url, token=None):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "api.github.com" or parsed.fragment:
        raise ValueError("GitHub attestation URL is not an allowed API URL")
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = token or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ValueError("Unable to verify GitHub receipt attestation") from exc


def _verify_source_reference(ref, source_root):
    if not isinstance(ref, dict):
        raise ValueError("Evidence source identity is not an object")
    repo, revision = ref.get("repository"), ref.get("revision")
    path, blob = ref.get("path"), ref.get("git_blob_sha1")
    expected_sha = ref.get("source_sha256")
    if repo not in PINS or revision != PINS[repo] or not isinstance(path, str) or not path:
        raise ValueError("Evidence source is not an exact supported pin")
    if not isinstance(blob, str) or not SHA1.fullmatch(blob):
        raise ValueError("Evidence source has an invalid Git blob identity")
    if not isinstance(expected_sha, str) or not SHA256.fullmatch(expected_sha):
        raise ValueError("Evidence source has an invalid content SHA-256")
    data = source_bytes(Path(source_root), repo, revision, path, blob)
    if git_blob(data) != blob or hashlib.sha256(data).hexdigest() != expected_sha:
        raise ValueError("Evidence source bytes do not match their recorded hashes")
    return data


def _verify_file_authorship(review, repository, pull_number, evidence_commit,
                            repository_root, github_api):
    authorship = review.get("authorship")
    if not isinstance(authorship, dict):
        raise ValueError("Missing dossier and substantive-evidence authorship provenance")
    dossier = authorship.get("dossier")
    evidence = authorship.get("substantive_evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("Substantive-evidence authorship provenance is incomplete")
    entries = [dossier, *evidence]
    root = Path(repository_root).resolve()
    api_root = f"https://api.github.com/repos/{repository}"
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("Authorship provenance is not an object")
        path, expected_sha = item.get("path"), item.get("sha256")
        if (not isinstance(path, str) or not path or Path(path).is_absolute()
                or ".." in Path(path).parts or not isinstance(expected_sha, str)
                or not SHA256.fullmatch(expected_sha)):
            raise ValueError("Authorship provenance has an invalid path or content hash")
        candidate = root
        for part in Path(path).parts:
            candidate = candidate / part
            if candidate.is_symlink():
                raise ValueError("Authorship evidence file cannot traverse symbolic links")
        file_path = candidate.resolve()
        if root not in file_path.parents or not file_path.is_file():
            raise ValueError("Authorship evidence file is missing or outside the checkout")
        if hashlib.sha256(file_path.read_bytes()).hexdigest() != expected_sha:
            raise ValueError("Authorship evidence file hash differs from the exact checkout")
        query = urlencode({"path": path, "sha": evidence_commit, "per_page": 1})
        commits = github_api(f"{api_root}/commits?{query}")
        if not isinstance(commits, list) or not commits:
            raise ValueError("No exact-head Git commit provenance for " + path)
        commit_sha = commits[0].get("sha")
        if not isinstance(commit_sha, str) or not SHA1.fullmatch(commit_sha):
            raise ValueError("GitHub returned invalid file authorship commit for " + path)
        commit = github_api(f"{api_root}/commits/{commit_sha}")
        if (not isinstance(commit, dict) or commit.get("sha") != commit_sha
                or not any(file.get("filename") == path for file in commit.get("files", []))):
            raise ValueError("GitHub commit does not attest the cited file path")
        author = commit.get("author", {}).get("login")
        committer = commit.get("committer", {}).get("login")
        if (not isinstance(author, str) or not author or "copilot" in author.casefold()
                or (isinstance(committer, str) and "copilot" in committer.casefold())):
            raise ValueError("Copilot cannot review its own dossier or substantive evidence")


def _verify_attestation(receipt, expected_head, repository, repository_root, github_api):
    attestation = receipt.get("attestation")
    if not isinstance(attestation, dict):
        raise ValueError("Missing attributable GitHub review signature")
    body_hash = receipt_digest(receipt)
    if attestation.get("receipt_sha256") != body_hash:
        raise ValueError("Receipt signature digest mismatch")
    target = receipt.get("target", {})
    pull_number = target.get("pull_number")
    evidence_commit = target.get("evidence_commit")
    receipt_path = target.get("receipt_path")
    if (not isinstance(pull_number, int) or pull_number < 1
            or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", str(repository))
            or target.get("repository") != repository
            or not isinstance(evidence_commit, str) or not SHA1.fullmatch(evidence_commit)
            or evidence_commit == expected_head
            or receipt_path != "docs/phase1-review-readiness/copilot-semantic-review-receipts.jsonl"):
        raise ValueError("Receipt evidence target is stale or belongs to another repository")

    api_root = f"https://api.github.com/repos/{repository}"
    pull = github_api(f"{api_root}/pulls/{pull_number}")
    review_list = github_api(f"{api_root}/pulls/{pull_number}/reviews?per_page=100")
    run_list = github_api(f"{api_root}/actions/runs?head_sha={expected_head}&per_page=100")
    final_commit = github_api(f"{api_root}/commits/{expected_head}")
    if not isinstance(review_list, list) or len(review_list) >= 100:
        raise ValueError("GitHub review list is missing or exceeds the fail-closed lookup limit")
    runs = run_list.get("workflow_runs") if isinstance(run_list, dict) else None
    if not isinstance(runs, list) or len(runs) >= 100:
        raise ValueError("Exact-head workflow run list is missing or exceeds the fail-closed lookup limit")
    matching_reviews = [
        review for review in review_list
        if review.get("user", {}).get("login") == "Copilot"
        and review.get("commit_id") == expected_head
        and review.get("state") == "COMMENTED"
        and review.get("submitted_at")
        and RECEIPT_MARKER + body_hash in (review.get("body") or "")
        and DECISION_MARKER in (review.get("body") or "")
    ]
    author = pull.get("user", {}).get("login")
    if pull.get("head", {}).get("sha") != expected_head:
        raise ValueError("Pull request head differs from exact validation head")
    parents = final_commit.get("parents", []) if isinstance(final_commit, dict) else []
    changed_files = final_commit.get("files", []) if isinstance(final_commit, dict) else []
    if (final_commit.get("sha") != expected_head
            or [parent.get("sha") for parent in parents] != [evidence_commit]
            or len(changed_files) != 1
            or changed_files[0].get("filename") != receipt_path):
        raise ValueError(
            "Receipt commit must be the exact-head child of the evidence commit and change only the receipt file"
        )
    if not author or author.casefold() == "copilot" or len(matching_reviews) != 1:
        raise ValueError("Missing Copilot identity or reviewer conflicts with pull request author")
    _verify_file_authorship(
        receipt.get("review", {}), repository, pull_number, evidence_commit,
        repository_root, github_api,
    )
    if any(run.get("head_sha") == expected_head
           and run.get("name") == PR_WORKFLOW_NAME
           and run.get("event") == "pull_request"
           and run.get("status") == "completed"
           and run.get("conclusion") == "success"
           and any(
               isinstance(workflow.get("path"), str)
               and workflow["path"].split("@", 1)[0].endswith(
                   f"{repository}/{CENSUS_WORKFLOW_PATH}"
               )
               for workflow in run.get("referenced_workflows", [])
           )
           and any(pr.get("number") == pull_number
                   and pr.get("head", {}).get("sha") == expected_head
                   for pr in run.get("pull_requests", []))
           for run in runs):
        return "Copilot"
    else:
        raise ValueError("Exact-head validation run is missing or unsuccessful")


def validate_receipt(receipt, *, queue, dossiers, source_root, expected_head,
                     repository_root=None,
                     repository, github_api=github_get_json):
    """Return (source key, problems) after independently checking receipt evidence."""
    key = None
    problems = []
    try:
        if not isinstance(receipt, dict) or receipt.get("schema") != SCHEMA:
            raise ValueError("Unknown Copilot receipt schema")
        target = receipt.get("target")
        if not isinstance(target, dict):
            raise ValueError("Missing receipt lifecycle target")
        receipt_path = target.get("receipt_path")
        root = Path(repository_root or Path.cwd()).resolve()
        if receipt_path != "docs/phase1-review-readiness/copilot-semantic-review-receipts.jsonl":
            raise ValueError("Receipt lifecycle path is not the canonical receipt register")
        register = root
        for part in Path(receipt_path).parts:
            register = register / part
            if register.is_symlink():
                raise ValueError("Receipt register cannot traverse symbolic links")
        if not register.is_file():
            raise ValueError("Receipt is missing from the checked-out receipt register")
        receipt_line = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        if receipt_line not in register.read_text(encoding="utf-8").splitlines():
            raise ValueError("Receipt bytes are missing or differ from the checked-out register")
        source = receipt.get("source")
        if not isinstance(source, dict):
            raise ValueError("Missing pinned source identity")
        repo, path = source.get("repository"), source.get("path")
        if not isinstance(repo, str) or not isinstance(path, str):
            raise ValueError("Source repository and path must be strings")
        key = (repo, path)
        q = queue.get(key)
        dossier = dossiers.get(key)
        if q is None or dossier is None:
            raise ValueError("Receipt references an unknown inventory item")
        provenance = dossier.get("provenance", {})
        if (repo, source.get("revision"), path, source.get("git_blob_sha1")) != (
                q["repo"], PINS.get(q["repo"]), q["path"], q["blob_sha"]):
            raise ValueError("Receipt source identity differs from original pinned dossier")
        if source.get("source_sha256") != provenance.get("source_content_sha256"):
            raise ValueError("Receipt source SHA-256 differs from original machine dossier")
        original_dossier_hash = digest(canonical(dossier))
        if receipt.get("machine_dossier_sha256") != original_dossier_hash or q.get("evidence_sha256") != original_dossier_hash:
            raise ValueError("Original machine dossier bytes or SHA-256 do not match")
        source_data = _verify_source_reference(source, source_root)
        source_sha = hashlib.sha256(source_data).hexdigest()
        line_count = len(source_data.splitlines())

        review = receipt.get("review")
        if not isinstance(review, dict) or review.get("decision") != "APPROVED":
            raise ValueError("Receipt has no semantic approval decision")
        if len((review.get("semantic_rationale") or "").strip()) < 40:
            raise ValueError("Receipt lacks substantive semantic rationale")
        findings = review.get("findings")
        if not isinstance(findings, list) or not findings:
            raise ValueError("Receipt lacks source-grounded semantic findings")
        for finding in findings:
            if not isinstance(finding, dict) or len((finding.get("claim") or "").strip()) < 12:
                raise ValueError("Receipt contains an unsupported or empty finding")
            anchors = finding.get("source_lines")
            if not isinstance(anchors, list) or not anchors or any(
                    not isinstance(n, int) or n < 1 or n > line_count for n in anchors):
                raise ValueError("Finding lacks valid whole-file source line anchors")

        coverage = review.get("whole_file_coverage", {})
        ranges = coverage.get("reviewed_line_ranges") if isinstance(coverage, dict) else None
        if (coverage.get("scope") != "WHOLE_FILE" or coverage.get("source_sha256") != source_sha
                or coverage.get("source_lines") != line_count or not isinstance(ranges, list)):
            raise ValueError("Receipt does not bind complete source-file coverage")
        cursor = 1
        for span in ranges:
            if (not isinstance(span, list) or len(span) != 2 or span[0] != cursor
                    or not isinstance(span[1], int) or span[1] < span[0]):
                raise ValueError("Whole-file line coverage has gaps or invalid ranges")
            cursor = span[1] + 1
        if cursor != line_count + 1:
            raise ValueError("Whole-file line coverage is incomplete")

        closure = review.get("dependency_closure", {})
        if not isinstance(closure, dict) or closure.get("status") != "COMPLETE":
            raise ValueError("Dependency closure is incomplete")
        if len((closure.get("rationale") or "").strip()) < 20:
            raise ValueError("Dependency closure lacks review rationale")
        dependencies = closure.get("dependencies")
        if not isinstance(dependencies, list):
            raise ValueError("Dependency closure inventory is missing")
        for dependency in dependencies:
            _verify_source_reference(dependency, source_root)

        licensing = review.get("licensing", {})
        if (not isinstance(licensing, dict) or licensing.get("status") != "CLEARED"
                or len((licensing.get("rationale") or "").strip()) < 20):
            raise ValueError("Licensing is unresolved or lacks rationale")
        license_evidence = licensing.get("evidence")
        if not isinstance(license_evidence, list) or not license_evidence:
            raise ValueError("Licensing clearance lacks pinned evidence")
        for evidence in license_evidence:
            _verify_source_reference(evidence, source_root)

        distinctions = review.get("evidence_distinctions")
        required = {"source", "synthetic", "compiled_native", "runtime_gameplay", "save_restart", "physical_flash"}
        if not isinstance(distinctions, dict) or not required.issubset(distinctions):
            raise ValueError("Evidence distinctions are incomplete")
        source_evidence = distinctions["source"]
        if (not isinstance(source_evidence, dict) or source_evidence.get("status") != "VERIFIED"
                or source_evidence.get("source_sha256") != source_sha):
            raise ValueError("Full pinned source evidence is not verified")
        for category in required - {"source"}:
            item = distinctions[category]
            if not isinstance(item, dict) or item.get("status") not in EVIDENCE_STATES:
                raise ValueError("Evidence distinction has an unsupported status: " + category)
            if item["status"] == "VERIFIED":
                artifacts = item.get("artifacts")
                if not isinstance(artifacts, list) or not artifacts:
                    raise ValueError("Claimed evidence lacks hashed artifacts: " + category)
                for artifact in artifacts:
                    if (not isinstance(artifact, dict) or not SHA256.fullmatch(str(artifact.get("sha256", "")))
                            or not isinstance(artifact.get("uri"), str) or not artifact["uri"].strip()
                            or artifact.get("kind") not in EVIDENCE_KINDS[category]):
                        raise ValueError("Unsupported or unhashed evidence artifact: " + category)
                raise ValueError(
                    "Non-source VERIFIED artifacts require independent byte verification: " + category
                )
            elif len((item.get("reason") or "").strip()) < 12:
                raise ValueError("Unrun or unclaimed evidence lacks an explicit reason: " + category)

        objections = review.get("objections")
        if not isinstance(objections, list):
            raise ValueError("Objection disposition is missing")
        for objection in objections:
            if (not isinstance(objection, dict) or objection.get("status") != "RESOLVED"
                    or len((objection.get("resolution") or "").strip()) < 12):
                raise ValueError("Unresolved substantive objection")
        _verify_attestation(
            receipt, expected_head, repository,
            root, github_api,
        )
    except (AttributeError, KeyError, TypeError, ValueError, OSError) as exc:
        problems.append(str(exc))
    return key, problems


def load_receipts(path):
    """Load JSONL receipts; malformed lines are reported rather than ignored."""
    receipts = []
    problems = []
    try:
        with Path(path).open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    receipts.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    problems.append(f"Invalid Copilot receipt JSON at line {line_number}: {exc}")
    except OSError as exc:
        problems.append(f"Unable to read Copilot receipt file: {exc}")
    return receipts, problems
