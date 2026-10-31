#!/usr/bin/env python3
"""Standalone proposal validator for versioned Phase 1 Copilot review receipts.

This tool is intentionally not called by the legacy mapping or Ed25519 gates.
Synthetic fixtures exercise validation only and never create review receipts.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

SCHEMA = "xgba.phase1.copilot_review_receipt.v1"
PIN_SCHEMA = "xgba.phase1.source_pin.v1"
BOT_ID = 198982749
BOT_NODE_ID = "BOT_kgDOC9w8XQ"
BOT_LOGINS = {"Copilot", "copilot-swe-agent[bot]"}
MARKER = "COPILOT_REVIEWED/PASSED"
REQUIRED_CHECK_WORKFLOW = ".github/workflows/phase1-copilot-receipts-v1.yml"
SHA1 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
HEX_ID = re.compile(r"^[0-9a-f]{40,64}$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
EVIDENCE_KINDS = {"source", "compiled", "native", "runtime"}
EVIDENCE_WORKFLOWS = {
    "compiled": ("compiled-",),
    "native": ("compiled-mgba-semantics.yml",),
    "runtime": ("compiled-mgba-semantics.yml", "archive-v28-runtime-rom.yml"),
}
MAX_ARTIFACT_SIZE = 100_000_000
MAX_ARTIFACT_MEMBER_SIZE = 32_000_000
UNSET = object()


def canonical_bytes(record):
    payload = copy.deepcopy(record)
    payload.pop("canonical_sha256", None)
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True) + "\n").encode("utf-8")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git_blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def decompress_dossier(data):
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
        decoded = stream.read(32_000_001)
    if len(decoded) > 32_000_000:
        raise ValueError("Machine dossier exceeds the decompression size limit")
    return decoded


def safe_relative(value):
    if not isinstance(value, str) or not value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and "\\" not in value


def valid_bot(user):
    return (
        isinstance(user, dict)
        and user.get("id") == BOT_ID
        and user.get("node_id") == BOT_NODE_ID
        and user.get("type") == "Bot"
        and user.get("login") in BOT_LOGINS
    )


def unquoted_marker(body):
    if not isinstance(body, str):
        return False
    marker_lines = 0
    fence = None
    html_comment = False
    blockquote = False
    for line in body.splitlines():
        stripped = line.strip()
        if fence:
            if MARKER in line:
                return False
            if (stripped.startswith(fence[0] * fence[1])
                    and len(stripped) >= fence[1]
                    and stripped.strip(fence[0]).strip() == ""):
                fence = None
            continue
        html_comment, hidden_marker = parse_html_comment_line(line, html_comment)
        if hidden_marker:
            return False
        if html_comment:
            continue
        if stripped.startswith("```") or stripped.startswith("~~~"):
            if MARKER in line:
                return False
            char = stripped[0]
            fence = (char, len(stripped) - len(stripped.lstrip(char)))
            continue
        if "<!--" in line or "-->" in line:
            continue
        if blockquote:
            if not stripped:
                blockquote = False
            elif MARKER in line:
                return False
            else:
                continue
        if stripped.startswith(">"):
            if MARKER in line:
                return False
            blockquote = True
            continue
        if MARKER in line:
            if line != MARKER:
                return False
            marker_lines += 1
    return marker_lines == 1 and not fence


def parse_html_comment_line(line, in_comment):
    offset = 0
    while offset < len(line):
        if in_comment:
            close = line.find("-->", offset)
            marker = line.find(MARKER, offset)
            if marker >= 0 and (close < 0 or marker < close):
                return True, True
            if close < 0:
                return True, False
            offset = close + 3
            in_comment = False
        else:
            opening = line.find("<!--", offset)
            if opening < 0:
                break
            offset = opening + 4
            in_comment = True
    return in_comment, False


class GitRepo:
    def __init__(self, root):
        self.root = Path(root)

    def run(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            check=True, capture_output=True, text=True, timeout=15,
        ).stdout.strip()

    def commit(self, revision):
        return self.run("rev-parse", "--verify", f"{revision}^{{commit}}")

    def parents(self, revision):
        return self.run("show", "-s", "--format=%P", revision).split()

    def is_ancestor(self, older, newer):
        return subprocess.run(
            ["git", "-C", str(self.root), "merge-base", "--is-ancestor", older, newer],
            check=False, capture_output=True, timeout=15,
        ).returncode == 0

    def show(self, revision, path):
        return subprocess.run(
            ["git", "-C", str(self.root), "show", f"{revision}:{path}"],
            check=True, capture_output=True, timeout=15,
        ).stdout

    def commit_timestamp(self, revision):
        return int(self.run("show", "-s", "--format=%ct", revision))


class GitHubAPI:
    def __init__(self, repo, token=None):
        if not REPO.fullmatch(repo):
            raise ValueError("Expected GitHub repository as OWNER/REPO")
        self.repo = repo
        self.token = token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("Set GH_TOKEN or GITHUB_TOKEN for authenticated GitHub evidence")

    def get(self, endpoint):
        url = f"https://api.github.com/repos/{self.repo}/{endpoint.lstrip('/')}"
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer " + self.token,
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "xgba-phase1-copilot-receipt-validator",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                if response.status != 200:
                    raise ValueError("GitHub API did not return HTTP 200")
                payload = response.read(4_000_001)
                if len(payload) > 4_000_000:
                    raise ValueError("GitHub API evidence exceeds the response size limit")
                return json.loads(payload)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ValueError("Unable to obtain authenticated GitHub evidence") from exc

    def download_artifact(self, artifact_id):
        request = urllib.request.Request(
            f"https://api.github.com/repos/{self.repo}/actions/artifacts/{artifact_id}/zip",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer " + self.token,
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "xgba-phase1-copilot-receipt-validator",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read(MAX_ARTIFACT_SIZE + 1)
                if response.status != 200 or len(payload) > MAX_ARTIFACT_SIZE:
                    raise ValueError("GitHub artifact is unavailable or exceeds the size limit")
                return payload
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ValueError("Unable to obtain authenticated GitHub artifact") from exc


def api_identity_errors(user):
    if not valid_bot(user):
        return ["GitHub attribution does not match the verified Copilot Bot identity"]
    return []


def job_executed_successfully(job):
    if (not isinstance(job, dict) or job.get("status") != "completed"
            or job.get("conclusion") != "success"
            or not job.get("started_at") or not job.get("completed_at")):
        return False
    steps = job.get("steps")
    return isinstance(steps, list) and any(
        isinstance(step, dict) and step.get("status") == "completed"
        and step.get("conclusion") == "success"
        and step.get("started_at") and step.get("completed_at")
        for step in steps
    )


def validate_api_evidence(record, repo, git, api, receipt_commit_ref):
    errors = []
    pr_number = record.get("github", {}).get("pull_request")
    review_id = record.get("github", {}).get("review_id")
    target_sha = record.get("github", {}).get("head_sha")
    if not isinstance(pr_number, int) or isinstance(pr_number, bool) or pr_number <= 0:
        return ["Invalid GitHub pull request number"]
    if not isinstance(review_id, int) or isinstance(review_id, bool) or review_id <= 0:
        return ["Invalid GitHub review ID"]
    if not isinstance(target_sha, str) or not SHA1.fullmatch(target_sha):
        return ["Invalid exact-head SHA"]
    target_sha = target_sha.lower()

    pr = api.get(f"pulls/{pr_number}")
    head = (pr.get("head") or {}).get("sha")
    if head != target_sha:
        errors.append("Pull request head is not the receipt's exact validated head")
    if (pr.get("head") or {}).get("repo", {}).get("full_name") != repo:
        errors.append("Pull request belongs to a different repository")

    reviews = []
    for page in range(1, 11):
        response = api.get(f"pulls/{pr_number}/reviews?per_page=100&page={page}")
        if not isinstance(response, list):
            return errors + ["Malformed GitHub review response"]
        reviews.extend(response)
        if len(response) < 100:
            break
    else:
        return errors + ["GitHub review pagination exceeds the verifier limit"]
    matches = [item for item in reviews if item.get("id") == review_id]
    verified_review = None
    if len(matches) != 1:
        errors.append("Attributable durable Copilot review receipt is missing or duplicated")
    else:
        review = matches[0]
        verified_review = review
        errors.extend(api_identity_errors(review.get("user")))
        if review.get("commit_id") != target_sha:
            errors.append("Copilot review is not attached to the exact validated head")
        if review.get("state") != "COMMENTED":
            errors.append("Copilot receipt must be a comment, not a legacy GitHub approval")
        if not unquoted_marker(review.get("body")):
            errors.append("Missing, quoted, duplicated, or malformed Copilot attestation marker")
        if review.get("submitted_at") is None:
            errors.append("GitHub review has no submitted timestamp")

    evidence_commit = record.get("ancestry", {}).get("evidence_commit")
    try:
        receipt_commit = git.commit(receipt_commit_ref)
        evidence_commit = git.commit(evidence_commit)
        target_sha = git.commit(target_sha)
        if evidence_commit not in git.parents(receipt_commit):
            errors.append("Evidence commit is not the direct parent of the receipt commit")
        if not git.is_ancestor(receipt_commit, target_sha):
            errors.append("Receipt commit is not an ancestor of the exact PR head")
        evidence_author = api.get(f"commits/{evidence_commit}").get("author") or {}
        analyst_ids = (record.get("authorship") or {}).get("analyst_user_ids", [])
        if (not isinstance(evidence_author.get("id"), int)
                or isinstance(evidence_author.get("id"), bool)
                or evidence_author.get("id") <= 0):
            errors.append("Evidence commit has no attributable GitHub analyst identity")
        else:
            if evidence_author.get("id") not in analyst_ids:
                errors.append("Recorded analyst identity does not match the evidence commit author")
            if evidence_author.get("id") == (record.get("reviewer") or {}).get("id"):
                errors.append("Copilot reviewer authored the semantic evidence commit")
        receipt_path = record.get("receipt_path")
        if not safe_relative(receipt_path):
            errors.append("Unsafe or missing receipt path")
        elif git.show(receipt_commit, receipt_path) != canonical_receipt_file(record):
            errors.append("Receipt commit does not contain these canonical receipt bytes")
    except (subprocess.SubprocessError, OSError, TypeError, ValueError):
        errors.append("Missing or unverifiable evidence/receipt Git ancestry")

    runs = record.get("github", {}).get("ci_runs")
    if not isinstance(runs, list) or len(runs) != 2:
        return errors + ["Exactly one PR and one push CI attempt are required"]
    events = [item.get("event") for item in runs if isinstance(item, dict)]
    if sorted(events) != ["pull_request", "push"]:
        errors.append("CI evidence must include one pull_request run and one push run")
    try:
        created_after = git.commit_timestamp(receipt_commit)
    except (subprocess.SubprocessError, OSError, ValueError):
        created_after = 0
        errors.append("Unable to establish receipt commit time for stale-run checks")
    if verified_review and parse_timestamp(verified_review.get("submitted_at")) < created_after:
        errors.append("Copilot review predates the receipt commit")

    for item in runs:
        if not isinstance(item, dict):
            errors.append("Malformed CI run reference")
            continue
        run_id = item.get("run_id")
        attempt = item.get("attempt")
        event = item.get("event")
        if (not isinstance(run_id, int) or isinstance(run_id, bool) or run_id <= 0
                or not isinstance(attempt, int) or isinstance(attempt, bool) or attempt <= 0):
            errors.append("Invalid CI run ID or attempt")
            continue
        run = api.get(f"actions/runs/{run_id}/attempts/{attempt}")
        if run.get("run_attempt") != attempt:
            errors.append("CI run attempt is stale")
        if (run.get("event") != event or run.get("head_sha") != target_sha
                or run.get("path") != REQUIRED_CHECK_WORKFLOW):
            errors.append("CI run does not match its event and exact target head")
        if event == "pull_request":
            if pr_number not in [p.get("number") for p in run.get("pull_requests", [])]:
                errors.append("Pull request CI run is not associated with the receipt PR")
        elif event == "push" and run.get("head_branch") != (pr.get("head") or {}).get("ref"):
            errors.append("Push CI run is not for the exact PR head branch")
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            errors.append("CI run is incomplete, stale, action_required, or unsuccessful")
        if parse_timestamp(run.get("created_at")) < created_after:
            errors.append("CI run predates the receipt commit")
        jobs = []
        total_jobs = None
        for page in range(1, 11):
            job_doc = api.get(
                f"actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100&page={page}"
            )
            page_jobs = job_doc.get("jobs") if isinstance(job_doc, dict) else None
            if not isinstance(page_jobs, list):
                jobs = None
                break
            total_jobs = job_doc.get("total_count")
            jobs.extend(page_jobs)
            if len(page_jobs) < 100:
                break
        if jobs is None or not jobs or total_jobs != len(jobs):
            errors.append("CI attempt has no executed jobs")
        elif any(not job_executed_successfully(job) for job in jobs):
            errors.append("CI attempt contains a missing, skipped, or unsuccessful job")

    evidence = (record.get("review") or {}).get("evidence", [])
    for item in evidence:
        if not isinstance(item, dict) or item.get("kind") == "source":
            continue
        artifact_id = item.get("artifact_id")
        artifact_run_id = item.get("run_id")
        artifact_attempt = item.get("run_attempt")
        artifact_path = item.get("artifact_path")
        if (not isinstance(artifact_id, int) or isinstance(artifact_id, bool) or artifact_id <= 0
                or not isinstance(artifact_run_id, int) or isinstance(artifact_run_id, bool)
                or artifact_run_id <= 0 or not isinstance(artifact_attempt, int)
                or isinstance(artifact_attempt, bool) or artifact_attempt <= 0
                or not safe_relative(artifact_path)):
            errors.append("Compiled/native/runtime evidence requires a pinned Actions artifact")
            continue
        metadata = api.get(f"actions/artifacts/{artifact_id}")
        workflow_run = metadata.get("workflow_run") or {}
        if (metadata.get("expired") is not False
                or metadata.get("id") != artifact_id
                or workflow_run.get("id") != artifact_run_id
                or workflow_run.get("head_sha") != target_sha):
            errors.append("Evidence artifact is expired, unbound, or from another source head")
            continue
        run = api.get(f"actions/runs/{artifact_run_id}/attempts/{artifact_attempt}")
        if (run.get("run_attempt") != artifact_attempt
                or run.get("head_sha") != target_sha
                or run.get("status") != "completed"
                or run.get("conclusion") != "success"):
            errors.append("Evidence artifact workflow did not succeed on the exact source head")
            continue
        artifact_created = parse_timestamp(metadata.get("created_at"))
        attempt_started = parse_timestamp(run.get("run_started_at"))
        attempt_finished = parse_timestamp(run.get("updated_at"))
        if (not artifact_created or not attempt_started or not attempt_finished
                or not attempt_started <= artifact_created <= attempt_finished):
            errors.append("Evidence artifact was not created during the validated run attempt")
            continue
        if parse_timestamp(run.get("created_at")) < created_after:
            errors.append("Evidence artifact workflow predates the receipt commit")
            continue
        workflow_path = run.get("path", "")
        if not supports_evidence_workflow(item.get("kind"), workflow_path):
            errors.append("Evidence artifact came from an unsupported workflow for its kind")
            continue
        job_doc = api.get(
            f"actions/runs/{artifact_run_id}/attempts/{artifact_attempt}/jobs?per_page=100&page=1"
        )
        jobs = job_doc.get("jobs") if isinstance(job_doc, dict) else None
        if (not isinstance(jobs, list) or not jobs
                or job_doc.get("total_count") != len(jobs)
                or any(not job_executed_successfully(job) for job in jobs)):
            errors.append("Evidence artifact has no executed successful workflow jobs")
            continue
        try:
            archive = api.download_artifact(artifact_id)
            with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
                members = [info for info in bundle.infolist()
                           if info.filename == artifact_path and not info.is_dir()]
                if len(members) != 1 or members[0].file_size > MAX_ARTIFACT_MEMBER_SIZE:
                    raise ValueError("Artifact member is missing, duplicated, or too large")
                content = bundle.read(members[0])
        except (OSError, ValueError, zipfile.BadZipFile, RuntimeError):
            errors.append("Evidence artifact archive or member is invalid")
            continue
        if sha256(content) != item.get("sha256"):
            errors.append("Evidence artifact bytes do not match the recorded SHA-256")
            continue
        source_hash = (record.get("source") or {}).get("sha256")
        dossier_hash = (record.get("dossier") or {}).get("compressed_sha256")
        if sha256(content) in {source_hash, dossier_hash}:
            errors.append("Compiled/native/runtime evidence cannot copy source or dossier bytes")
    return errors


def parse_timestamp(value):
    if not isinstance(value, str):
        return 0
    try:
        from datetime import datetime
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return 0


def supports_evidence_workflow(kind, workflow_path):
    name = PurePosixPath(workflow_path).name
    expected = EVIDENCE_WORKFLOWS.get(kind, ())
    return any(
        name.startswith(prefix) if prefix.endswith("-") else name == prefix
        for prefix in expected
    )


def canonical_receipt_file(record):
    payload = copy.deepcopy(record)
    expected = payload.pop("canonical_sha256", None)
    payload["canonical_sha256"] = expected
    return (json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode()


def _validate_record(record, pin, source_bytes=UNSET, dossier_bytes=UNSET,
                     repo_root=".", repo="", api=None, git=None, receipt_commit=None):
    errors = []
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        return ["Unsupported Copilot review receipt schema"]
    if not isinstance(pin, dict) or pin.get("schema") != PIN_SCHEMA:
        return ["Missing or unsupported immutable source-pin record"]
    if record.get("classification") != {"status": "COPILOT_REVIEWED", "verdict": "PASSED"}:
        errors.append("Receipt is not the explicit COPILOT_REVIEWED/PASSED classification")
    if record.get("canonical_sha256") != sha256(canonical_bytes(record)):
        errors.append("Canonical per-file receipt digest mismatch")
    if git is None:
        git = GitRepo(repo_root)
    evidence_commit = (record.get("ancestry") or {}).get("evidence_commit")
    try:
        evidence_commit = git.commit(evidence_commit)
    except (subprocess.SubprocessError, OSError, TypeError, ValueError):
        evidence_commit = None
        errors.append("Missing or unverifiable semantic evidence commit")

    source = record.get("source")
    pinned_source = pin.get("source")
    dossier = record.get("dossier")
    pinned_dossier = pin.get("dossier")
    if not isinstance(source, dict) or not isinstance(pinned_source, dict):
        errors.append("Missing pinned source identity")
        source = {}
        pinned_source = {}
    for field in ("repository", "path", "revision", "git_blob_sha", "sha256"):
        if source.get(field) != pinned_source.get(field):
            errors.append(f"Receipt disagrees with immutable source pin: {field}")
    if source.get("repository") != pin.get("repository"):
        errors.append("Source repository does not match the pinned repository identity")
    if not REPO.fullmatch(str(source.get("repository", ""))):
        errors.append("Invalid upstream repository identity")
    if not safe_relative(source.get("path")) or not safe_relative(pin.get("path")):
        errors.append("Unsafe source path")
    if source.get("path") != pin.get("path"):
        errors.append("Source path does not match pin path")
    if not HEX_ID.fullmatch(str(source.get("revision", ""))):
        errors.append("Invalid immutable upstream source revision")
    if not SHA1.fullmatch(str(source.get("git_blob_sha", ""))):
        errors.append("Invalid pinned Git blob identity")
    if not SHA256.fullmatch(str(source.get("sha256", ""))):
        errors.append("Invalid pinned source SHA-256")
    if source_bytes is UNSET or source_bytes is None:
        errors.append("Original whole-file source bytes are missing")
    elif (git_blob_sha(source_bytes) != source.get("git_blob_sha")
          or sha256(source_bytes) != source.get("sha256")):
        errors.append("Original whole-file source identity/hash mismatch")

    if not isinstance(dossier, dict) or not isinstance(pinned_dossier, dict):
        errors.append("Missing original machine dossier byte identity")
        dossier = {}
        pinned_dossier = {}
    for field in ("path", "compressed_sha256"):
        if dossier.get(field) != pinned_dossier.get(field):
            errors.append(f"Receipt disagrees with original dossier pin: {field}")
    if not safe_relative(dossier.get("path")):
        errors.append("Unsafe original dossier path")
    if not SHA256.fullmatch(str(dossier.get("compressed_sha256", ""))):
        errors.append("Invalid compressed dossier SHA-256")
    if dossier_bytes is UNSET or dossier_bytes is None:
        errors.append("Original compressed machine dossier bytes are missing")
    elif sha256(dossier_bytes) != dossier.get("compressed_sha256"):
        errors.append("Original compressed machine dossier bytes/hash mismatch")
    else:
        try:
            machine = json.loads(decompress_dossier(dossier_bytes))
            provenance = machine["provenance"]
            if (provenance.get("repository"), provenance.get("path"),
                    provenance.get("pinned_revision"), provenance.get("git_blob_sha")) != (
                    source.get("repository"), source.get("path"), source.get("revision"),
                    source.get("git_blob_sha")):
                errors.append("Machine dossier provenance does not match pinned source")
        except (OSError, EOFError, json.JSONDecodeError, KeyError, TypeError):
            errors.append("Original machine dossier is not valid compressed JSON")

    review = record.get("review")
    if not isinstance(review, dict):
        errors.append("Missing semantic review record")
        review = {}
    if review.get("coverage") != "whole_file" or review.get("whole_file") is not True:
        errors.append("Whole-file semantic coverage is not explicit")
    semantics = review.get("semantics")
    if not isinstance(semantics, dict) or not isinstance(semantics.get("summary"), str) or not semantics["summary"].strip():
        errors.append("Missing source-grounded semantic summary")
        semantics = {}
    closure = semantics.get("dependency_closure")
    if (not isinstance(closure, dict) or closure.get("complete") is not True
            or not isinstance(closure.get("edges"), list)
            or not isinstance(closure.get("unresolved"), list)
            or closure.get("unresolved")):
        errors.append("Dependency closure is incomplete or unresolved")
    licensing = semantics.get("licensing")
    if (not isinstance(licensing, dict) or licensing.get("assessed") is not True
            or not isinstance(licensing.get("scope"), str) or not licensing["scope"].strip()
            or licensing.get("status") not in {"compatible", "permitted", "not_applicable"}):
        errors.append("Licensing scope is missing or unresolved")
    objections = semantics.get("objections")
    if (not isinstance(objections, dict) or not isinstance(objections.get("unresolved"), list)
            or objections.get("unresolved")):
        errors.append("Substantive objections remain unresolved or are not recorded")

    evidence = review.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("No hashed semantic evidence is recorded")
        evidence = []
    valid_evidence = []
    source_dossier_hashes = {
        sha256(content) for content in (source_bytes, dossier_bytes)
        if isinstance(content, bytes)
    }
    for item in evidence:
        if not isinstance(item, dict) or item.get("kind") not in EVIDENCE_KINDS:
            errors.append("Malformed or unsupported evidence kind")
            continue
        artifact = item.get("artifact")
        if item.get("kind") != "source":
            if (artifact in {"source", "dossier"} or not SHA256.fullmatch(
                    str(item.get("sha256", "")))
                    or not isinstance(item.get("artifact_id"), int)
                    or isinstance(item.get("artifact_id"), bool)
                    or not isinstance(item.get("run_id"), int)
                    or isinstance(item.get("run_id"), bool)
                    or not isinstance(item.get("run_attempt"), int)
                    or isinstance(item.get("run_attempt"), bool)
                    or not safe_relative(item.get("artifact_path"))):
                errors.append("Compiled/native/runtime evidence requires a pinned Actions artifact")
                continue
            valid_evidence.append(item)
            continue
        if artifact == "source":
            content = source_bytes
        elif artifact == "dossier":
            content = dossier_bytes
        elif safe_relative(item.get("path")) and evidence_commit:
            try:
                content = git.show(evidence_commit, item["path"])
            except (subprocess.SubprocessError, OSError, TypeError, ValueError):
                content = None
        else:
            content = None
        if content is None or content is UNSET:
            errors.append("Evidence bytes are missing or their hash does not match")
            continue
        evidence_hash = sha256(content)
        if not SHA256.fullmatch(str(item.get("sha256", ""))) or evidence_hash != item.get("sha256"):
            errors.append("Evidence bytes are missing or their hash does not match")
            continue
        if item.get("kind") == "source" and artifact != "source":
            if evidence_hash != (source.get("sha256")):
                errors.append("Source evidence path does not match the pinned whole-file bytes")
                continue
        if (item.get("kind") in {"compiled", "native", "runtime"}
                and evidence_hash in source_dossier_hashes):
            errors.append("Compiled/native/runtime evidence cannot copy source or dossier bytes")
            continue
        valid_evidence.append(item)
    claims = review.get("claims")
    if not isinstance(claims, list) or not claims:
        errors.append("No explicit semantic claims are recorded")
    else:
        for claim in claims:
            if not isinstance(claim, dict) or claim.get("kind") not in EVIDENCE_KINDS:
                errors.append("Malformed or unsupported semantic claim")
                continue
            refs = claim.get("evidence")
            if (not isinstance(claim.get("text"), str) or not claim["text"].strip()
                    or not isinstance(refs, list) or not refs
                    or any(not isinstance(i, int) or isinstance(i, bool) or i < 0
                           or i >= len(evidence) for i in refs)):
                errors.append("Semantic claim lacks valid evidence references")
                continue
            for idx in refs:
                cited = evidence[idx]
                if (cited not in valid_evidence or cited.get("kind") != claim["kind"]
                        or cited.get("artifact") == "dossier"
                        or (claim["kind"] in {"compiled", "native", "runtime"}
                            and cited.get("artifact") in {"source", "dossier"})):
                    errors.append("Compiled/native/runtime claim lacks matching hashed evidence")
                    break

    reviewer = record.get("reviewer")
    if not valid_bot(reviewer):
        errors.append("Reviewer is not the attributable verified Copilot Bot identity")
    authorship = record.get("authorship")
    if not isinstance(authorship, dict):
        errors.append("Missing analyst/reviewer authorship separation")
        authorship = {}
    analyst_ids = authorship.get("analyst_user_ids")
    if not isinstance(analyst_ids, list) or not analyst_ids or any(
        not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in analyst_ids
    ):
        errors.append("Missing or invalid analyst_user_ids")
    elif reviewer and reviewer.get("id") in analyst_ids:
        errors.append("Copilot reviewer authored the semantic analysis")

    errors.extend(validate_api_evidence(record, repo, git, api, receipt_commit))
    return errors


def validate_record(record, pin, source_bytes=UNSET, dossier_bytes=UNSET,
                    repo_root=".", repo="", api=None, git=None, receipt_commit=None):
    try:
        return _validate_record(
            record, pin, source_bytes, dossier_bytes, repo_root, repo, api, git, receipt_commit,
        )
    except Exception:
        return ["Malformed receipt or unavailable verification evidence"]


def check_duplicates(records):
    seen_sources = set()
    seen_digests = set()
    errors = []
    for path, record in records:
        key = (
            (record.get("source") or {}).get("repository"),
            (record.get("source") or {}).get("path"),
            (record.get("source") or {}).get("git_blob_sha"),
        )
        digest = record.get("canonical_sha256")
        if key in seen_sources:
            errors.append(f"Duplicate source receipt: {key}")
        if digest in seen_digests:
            errors.append(f"Duplicate receipt digest: {path}")
        seen_sources.add(key)
        seen_digests.add(digest)
    return errors


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--source-pin", type=Path, required=True)
    parser.add_argument("--source-bytes", type=Path, required=True)
    parser.add_argument("--dossier-bytes", type=Path, required=True)
    parser.add_argument("--repo", required=True, help="GitHub repository OWNER/REPO")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--receipt-commit", required=True,
                        help="Git commit containing the receipt; kept outside its canonical bytes")
    args = parser.parse_args(argv)
    try:
        record = load_json(args.receipt)
        pin = load_json(args.source_pin)
        siblings = []
        for path in sorted(args.receipt.parent.glob("*.json")):
            try:
                other = load_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            if other.get("schema") == SCHEMA:
                siblings.append((path, other))
        duplicate_errors = check_duplicates(siblings)
        if duplicate_errors:
            raise ValueError("; ".join(duplicate_errors))
        api = GitHubAPI(args.repo)
        errors = validate_record(
            record, pin, args.source_bytes.read_bytes(), args.dossier_bytes.read_bytes(),
            args.repo_root, args.repo, api, receipt_commit=args.receipt_commit,
        )
        if errors:
            raise ValueError("; ".join(errors))
        print("COPILOT_RECEIPT_VALIDATED; not integrated into approval counts")
        return 0
    except Exception as exc:
        print(f"FAIL_CLOSED: {exc}", file=sys.stderr)
        return 2
if __name__ == "__main__":
    sys.exit(main())
