#!/usr/bin/env python3
"""Validate attributable, evidence-complete Copilot Phase 1 review receipts."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from phase1_bulk_triage import PINS, canonical, digest, git_blob, source_bytes

SCHEMA = "xgba.phase1.copilot_semantic_review_receipt.v4"
SHA1 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
RECEIPT_MARKER = "XGBA-Phase1-Receipt-SHA256: "
DECISION_MARKER = "XGBA-Phase1-Decision: APPROVED"
INTRO_COMMIT_MARKER = "XGBA-Phase1-Receipt-Commit: "
EVIDENCE_COMMIT_MARKER = "XGBA-Phase1-Evidence-Commit: "
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


def _git(repository_root, *args):
    try:
        return subprocess.check_output(
            ["git", "-C", str(repository_root), *args],
            stderr=subprocess.PIPE,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("Unable to verify receipt Git history") from exc


def _find_receipt_introduction(repository_root, receipt_path, receipt_line,
                               evidence_commit, expected_head):
    root = Path(repository_root).resolve()
    head = _git(root, "rev-parse", "HEAD")
    if head != expected_head:
        raise ValueError("Receipt validation checkout is not the expected exact head")
    _git(root, "merge-base", "--is-ancestor", evidence_commit, expected_head)
    try:
        evidence_register = subprocess.check_output(
            ["git", "-C", str(root), "show", f"{evidence_commit}:{receipt_path}"],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").splitlines()
    except subprocess.CalledProcessError:
        evidence_register = []
    if len(evidence_register) != len(set(evidence_register)):
        raise ValueError("Receipt evidence commit contains duplicate register entries")
    if receipt_line in evidence_register:
        raise ValueError("Receipt already exists at its evidence commit")
    commits = _git(
        root, "rev-list", "--first-parent", "--reverse",
        f"{evidence_commit}..{expected_head}",
    ).splitlines()
    introduction = None
    for commit_sha in commits:
        parents = _git(root, "rev-list", "--parents", "-n", "1", commit_sha).split()
        if len(parents) < 2:
            raise ValueError("Receipt history has invalid first-parent ancestry")
        parent = parents[1]
        changed = _git(root, "diff", "--name-only", parent, commit_sha).splitlines()
        try:
            previous = subprocess.check_output(
                ["git", "-C", str(root), "show", f"{parent}:{receipt_path}"],
                stderr=subprocess.DEVNULL,
            ).decode("utf-8").splitlines()
        except subprocess.CalledProcessError:
            previous = []
        try:
            contents = subprocess.check_output(
                ["git", "-C", str(root), "show", f"{commit_sha}:{receipt_path}"],
                stderr=subprocess.DEVNULL,
            ).decode("utf-8").splitlines()
        except subprocess.CalledProcessError:
            contents = []
        if receipt_path in changed:
            if changed != [receipt_path] or len(parents) != 2:
                raise ValueError("Receipt register changes must be single-parent, receipt-only commits")
            if contents[:len(previous)] != previous or len(contents) != len(set(contents)):
                raise ValueError("Receipt register history is not append-only")
        elif contents != previous:
            raise ValueError("Receipt register changed outside an append-only commit")
        occurrences = contents.count(receipt_line)
        if occurrences > 1:
            raise ValueError("Duplicate receipt bytes in the append-only register")
        if introduction is None and occurrences == 1 and receipt_line not in previous:
            if parent != evidence_commit:
                raise ValueError("Receipt introduction must directly descend from its evidence commit")
            introduction = commit_sha
    if introduction is None:
        raise ValueError("Receipt has no introduction commit after its evidence commit")
    parent_line = _git(root, "rev-list", "--parents", "-n", "1", introduction).split()
    if len(parent_line) != 2 or parent_line[1] != _git(root, "rev-parse", f"{introduction}^1"):
        raise ValueError("Receipt introduction commit has invalid ancestry")
    introduced = False
    for commit_sha in commits:
        if commit_sha == introduction:
            introduced = True
        if not introduced:
            continue
        try:
            contents = subprocess.check_output(
                ["git", "-C", str(root), "show", f"{commit_sha}:{receipt_path}"],
                stderr=subprocess.DEVNULL,
            ).decode("utf-8")
        except subprocess.CalledProcessError as exc:
            raise ValueError("Receipt was removed from the append-only register") from exc
        if contents.splitlines().count(receipt_line) != 1:
            raise ValueError("Receipt was removed or modified after introduction")
    intro_date = _git(root, "show", "-s", "--format=%cI", introduction)
    return introduction, datetime.fromisoformat(intro_date)


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


class GitHubAPICache:
    """Cache GitHub API reads and fetch complete paginated collections."""

    def __init__(self, getter=github_get_json):
        self.getter = getter
        self.responses = {}

    def __call__(self, url):
        if url not in self.responses:
            try:
                result = self.getter(url)
            except Exception as exc:
                raise ValueError("Unable to retrieve complete GitHub API response") from exc
            if result is None:
                raise ValueError("GitHub API returned a missing response")
            self.responses[url] = result
        return self.responses[url]

    def paginate(self, url, *, result_key=None):
        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["per_page"] = "100"
        items = []
        seen_ids = set()
        page = 1
        while True:
            query["page"] = str(page)
            page_url = urlunparse(parsed._replace(query=urlencode(query)))
            response = self(page_url)
            page_items = response.get(result_key) if result_key else response
            if (not isinstance(page_items, list) or len(page_items) > 100
                    or any(not isinstance(item, dict) for item in page_items)):
                raise ValueError("GitHub API returned an invalid paginated response")
            for item in page_items:
                item_id = item.get("id")
                if not isinstance(item_id, int) or item_id < 1 or item_id in seen_ids:
                    raise ValueError("GitHub pagination contains a missing or duplicate record ID")
                seen_ids.add(item_id)
            items.extend(page_items)
            if not page_items:
                return items
            page += 1


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
        try:
            evidence_bytes = subprocess.check_output(
                ["git", "-C", str(root), "show", f"{evidence_commit}:{path}"],
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError as exc:
            raise ValueError("Authorship evidence file is missing at its evidence commit") from exc
        if hashlib.sha256(evidence_bytes).hexdigest() != expected_sha:
            raise ValueError("Authorship evidence hash differs at its evidence commit")
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
    mode = attestation.get("mode")
    if (not isinstance(pull_number, int) or pull_number < 1
            or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", str(repository))
            or target.get("repository") != repository
            or not isinstance(evidence_commit, str) or not SHA1.fullmatch(evidence_commit)
            or evidence_commit == expected_head
            or receipt_path != "docs/phase1-review-readiness/copilot-semantic-review-receipts.jsonl"):
        raise ValueError("Receipt evidence target is stale or belongs to another repository")
    if mode not in {"github_review", "conversation_comment"}:
        raise ValueError("Receipt has no supported authenticated Copilot attestation mode")
    receipt_line = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    introduction, introduction_time = _find_receipt_introduction(
        repository_root, receipt_path, receipt_line, evidence_commit, expected_head,
    )

    api_root = f"https://api.github.com/repos/{repository}"
    api = github_api if isinstance(github_api, GitHubAPICache) else GitHubAPICache(github_api)
    pull = api(f"{api_root}/pulls/{pull_number}")
    review_list = api.paginate(f"{api_root}/pulls/{pull_number}/reviews")
    comment_list = api.paginate(f"{api_root}/issues/{pull_number}/comments")
    runs = api.paginate(
        f"{api_root}/actions/runs?head_sha={expected_head}",
        result_key="workflow_runs",
    )
    receipt_markers = (
        RECEIPT_MARKER + body_hash,
        INTRO_COMMIT_MARKER + introduction,
        EVIDENCE_COMMIT_MARKER + evidence_commit,
        DECISION_MARKER,
    )

    def submitted_after(timestamp):
        if not isinstance(timestamp, str):
            return False
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            return parsed.tzinfo is not None and parsed.astimezone(timezone.utc) > introduction_time.astimezone(timezone.utc)
        except ValueError:
            return False

    matching_reviews = [
        review for review in review_list
        if review.get("user", {}).get("login") == "Copilot"
        and isinstance(review.get("id"), int) and review["id"] > 0
        and review.get("commit_id") == introduction
        and review.get("state") == "COMMENTED"
        and submitted_after(review.get("submitted_at"))
        and all(marker in (review.get("body") or "") for marker in receipt_markers)
    ]
    matching_comments = [
        comment for comment in comment_list
        if comment.get("user", {}).get("login") == "Copilot"
        and comment.get("issue_url") == f"{api_root}/issues/{pull_number}"
        and isinstance(comment.get("id"), int) and comment["id"] > 0
        and comment.get("html_url")
        == f"https://github.com/{repository}/pull/{pull_number}#issuecomment-{comment.get('id')}"
        and submitted_after(comment.get("created_at"))
        and all(marker in (comment.get("body") or "") for marker in receipt_markers)
    ]
    author = pull.get("user", {}).get("login")
    if pull.get("head", {}).get("sha") != expected_head:
        raise ValueError("Pull request head differs from exact validation head")
    matching = matching_reviews if mode == "github_review" else matching_comments
    unique_ids = [record.get("id") for record in matching]
    unique_urls = [
        record.get("html_url") for record in matching
        if mode == "conversation_comment"
    ]
    if (not author or author.casefold() == "copilot" or len(matching) != 1
            or len(set(unique_ids)) != 1
            or (mode == "conversation_comment" and len(set(unique_urls)) != 1)):
        raise ValueError("Missing unique authenticated Copilot attestation or reviewer conflicts with PR author")
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
    api = github_api if isinstance(github_api, GitHubAPICache) else GitHubAPICache(github_api)
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
        register_lines = register.read_text(encoding="utf-8").splitlines()
        if receipt_line not in register_lines:
            raise ValueError("Receipt bytes are missing or differ from the checked-out register")
        source_identities = set()
        for line in register_lines:
            try:
                registered = json.loads(line)
                registered_source = registered["source"]
                identity = (registered_source["repository"], registered_source["path"])
            except (TypeError, KeyError, json.JSONDecodeError) as exc:
                raise ValueError("Receipt register contains a malformed record") from exc
            if identity in source_identities:
                raise ValueError("Receipt register contains duplicate source identities")
            source_identities.add(identity)
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
            root, api,
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
