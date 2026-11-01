#!/usr/bin/env python3
"""Read-only, fail-closed evaluator for prospective upstream congruence evidence."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath

from pinned_source_census import PINS

SCHEMA = "xgba.phase1.upstream_verified.v1"
MAPPING_SCHEMA = "xgba.phase1.upstream_semantic_mapping.v1"
REGISTER_SCHEMA = "xgba.phase1.upstream_congruence_register.v1"
PASSED = "UPSTREAM_VERIFIED/PASSED"
NEEDS_REVIEW = "NEEDS_REVIEW"
BLOCKED = "BLOCKED"
INVENTORY_SIZE = 14834
P0_CANDIDATES = 338
DOSSIER_PATH = "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
DOSSIER_SHA256 = "c47d1fea819e7df59f67bfe8d1bc4dc2650483d03563957145f7331ed099005b"
DOSSIER_BLOB = "143c373f9aae5b9cb24af39abb7d8244362d23b5"
QUEUE_PATH = "semantic-snapshots/current/semantic_review_queue.csv.gz"
QUEUE_SHA256 = "b2e418f75645714ad780d004203dc3ce67189eb956db0cfd48f670997b8afb5d"
QUEUE_BLOB = "777901c5f714764978de3f0623abd35ec21889f7"
GATE_PATH = "semantic-snapshots/current/phase1_mapping_gate.json"
GATE_SHA256 = "7df6ceb6641ccb24cdc114f0ed6af10bc0ecbf3b42db484b26be41907e96d953"
GATE_BLOB = "dab5789433dc55cf325a917a220d060088bf1d29"
REGISTER_PATH = "semantic-snapshots/proposals/upstream_verified_evidence_v1.json"
REGISTER_SHA256 = "df0e37cbc42df1cb3b10ed008ca8b8a6a73656dd4cb9fd82a76934f7976851fd"
REGISTER_BLOB = "911b009ec64ee3ecbb72a81b44ffe00c9caaa44d"
SPDX_ALLOWLIST = {
    "AGPL-3.0-only", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause",
    "CC0-1.0", "GPL-2.0-only", "GPL-3.0-only", "ISC", "MIT",
    "MPL-2.0", "Zlib",
}
INCLUDE = re.compile(rb'^\s*#\s*include\s*[<"]([^>"]+)[>"]', re.MULTILINE)
SOURCE_EXTENSIONS = {".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh"}
API_ROOT = "https://api.github.com/repos"


class EvidenceError(ValueError):
    def __init__(self, message, disposition=NEEDS_REVIEW):
        super().__init__(message)
        self.disposition = disposition


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git_blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args], stderr=subprocess.PIPE
    ).decode().strip()


def _safe_path(value):
    if not isinstance(value, str) or not value:
        raise EvidenceError("Evidence path is missing or invalid", BLOCKED)
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or str(path) != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise EvidenceError("Evidence path is not a normalized repository path", BLOCKED)
    return str(path)


class PinnedContext:
    def __init__(self, repository_root, source_root, api_get):
        self.repository_root = Path(repository_root).resolve()
        self.source_root = Path(source_root).resolve()
        self.api_get = api_get
        self.pins = {repo: (revision, count) for repo, revision, count in PINS}
        self.queue = {}
        self.dossiers = {}
        self.legacy_counts = {}
        self._load_snapshot()
        self.register_bytes = self._verify_snapshot_file(
            REGISTER_PATH, REGISTER_BLOB, REGISTER_SHA256
        )

    def _verify_snapshot_file(self, path, expected_blob, expected_sha256):
        absolute = self.repository_root / path
        if absolute.is_symlink() or not absolute.is_file():
            raise EvidenceError(f"Pinned original snapshot is missing or unsafe: {path}", BLOCKED)
        data = absolute.read_bytes()
        if sha256(data) != expected_sha256 or git_blob_sha(data) != expected_blob:
            raise EvidenceError(f"Pinned original snapshot digest mismatch: {path}", BLOCKED)
        if git(self.repository_root, "rev-parse", f"HEAD:{path}") != expected_blob:
            raise EvidenceError(f"Original snapshot Git blob changed: {path}", BLOCKED)
        return data

    def _load_snapshot(self):
        gate_bytes = self._verify_snapshot_file(GATE_PATH, GATE_BLOB, GATE_SHA256)
        gate = json.loads(gate_bytes)
        if (
            gate.get("decision") != "FAIL_INCOMPLETE"
            or gate.get("verified_source_manifest_entries") != INVENTORY_SIZE
            or gate.get("machine_generated_dossiers") != INVENTORY_SIZE
            or gate.get("p0_review_candidates") != P0_CANDIDATES
            or gate.get("approved_semantic_dispositions") != 0
        ):
            raise EvidenceError("Historical legacy gate baseline changed", BLOCKED)
        self.legacy_counts = {
            "legacy_external_independent_approved": gate["approved_semantic_dispositions"],
            "legacy_p0_external_independent_approved": 0,
            "legacy_p0_review_candidates": gate["p0_review_candidates"],
        }
        queue_bytes = self._verify_snapshot_file(QUEUE_PATH, QUEUE_BLOB, QUEUE_SHA256)
        dossier_bytes = self._verify_snapshot_file(DOSSIER_PATH, DOSSIER_BLOB, DOSSIER_SHA256)
        with gzip.open(__import__("io").BytesIO(queue_bytes), "rt", encoding="utf-8", newline="") as stream:
            queue_rows = list(csv.DictReader(stream))
        with gzip.open(__import__("io").BytesIO(dossier_bytes), "rt", encoding="utf-8") as stream:
            dossier_rows = [json.loads(line) for line in stream]
        if (
            len(queue_rows) != INVENTORY_SIZE
            or len(dossier_rows) != INVENTORY_SIZE
            or len({(row.get("repo"), row.get("path")) for row in queue_rows}) != INVENTORY_SIZE
        ):
            raise EvidenceError("Pinned source/dossier inventory is incomplete or duplicated", BLOCKED)
        for index, (queue, dossier) in enumerate(zip(queue_rows, dossier_rows)):
            repo = queue.get("repo")
            expected_revision = self.pins.get(repo, (None,))[0]
            canonical_digest = sha256(canonical_bytes(dossier))
            provenance = dossier.get("provenance", {})
            if (
                canonical_digest != queue.get("evidence_sha256")
                or provenance.get("repository") != repo
                or provenance.get("path") != queue.get("path")
                or provenance.get("pinned_revision") != expected_revision
                or provenance.get("git_blob_sha") != queue.get("blob_sha")
                or dossier.get("review", {}).get("semantic_signoff") is not False
            ):
                raise EvidenceError(f"Original machine dossier identity mismatch at row {index}", BLOCKED)
            key = (repo, queue["path"])
            self.queue[key] = queue
            self.dossiers[key] = {
                "sha256": canonical_digest,
                "record": dossier,
            }

    def source_bytes(self, reference):
        if not isinstance(reference, dict):
            raise EvidenceError("Source identity is not an object", BLOCKED)
        repository = reference.get("repository")
        revision = reference.get("revision")
        path = _safe_path(reference.get("path"))
        pinned = self.pins.get(repository)
        if not pinned or revision != pinned[0]:
            raise EvidenceError("Source reference is not at an immutable configured pin", BLOCKED)
        checkout = self.source_root / repository.split("/")[-1]
        if checkout.is_symlink() or not checkout.is_dir():
            raise EvidenceError(f"Pinned source checkout is unavailable: {repository}", BLOCKED)
        if git(checkout, "rev-parse", "HEAD") != revision:
            raise EvidenceError(f"Pinned source checkout revision mismatch: {repository}", BLOCKED)
        remote = git(checkout, "remote", "get-url", "origin")
        if remote.startswith("https://github.com/"):
            remote_repository = remote[len("https://github.com/"):]
        elif remote.startswith("git@github.com:"):
            remote_repository = remote[len("git@github.com:"):]
        elif remote.startswith("ssh://git@github.com/"):
            remote_repository = remote[len("ssh://git@github.com/"):]
        else:
            raise EvidenceError(f"Pinned checkout origin is not GitHub: {repository}", BLOCKED)
        if remote_repository.removesuffix(".git").lower() != repository.lower():
            raise EvidenceError(f"Pinned checkout origin repository mismatch: {repository}", BLOCKED)
        try:
            tree_entry = git(checkout, "ls-tree", revision, "--", path)
            mode = tree_entry.split(" ", 1)[0]
            if mode not in {"100644", "100755"}:
                raise EvidenceError(f"Evidence path is not a regular tracked file: {repository}:{path}", BLOCKED)
            blob = git(checkout, "rev-parse", f"{revision}:{path}")
            data = subprocess.check_output(
                ["git", "-C", str(checkout), "cat-file", "blob", blob],
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as exc:
            raise EvidenceError(f"Pinned source file is unavailable: {repository}:{path}", BLOCKED) from exc
        if (
            blob != reference.get("git_blob_sha1")
            or git_blob_sha(data) != blob
            or sha256(data) != reference.get("source_sha256")
        ):
            raise EvidenceError(f"Pinned source hash mismatch: {repository}:{path}", BLOCKED)
        return data

    def verify_target(self, reference, dossier):
        key = (reference.get("repository"), reference.get("path"))
        row = self.queue.get(key)
        dossier_row = self.dossiers.get(key)
        if row is None or dossier_row is None:
            raise EvidenceError("Target is absent from the pinned inventory", BLOCKED)
        revision = self.pins[key[0]][0]
        if (
            reference.get("revision") != revision
            or reference.get("git_blob_sha1") != row.get("blob_sha")
            or dossier.get("archive_sha256") != DOSSIER_SHA256
            or dossier.get("canonical_sha256") != dossier_row["sha256"]
            or row.get("evidence_sha256") != dossier_row["sha256"]
        ):
            raise EvidenceError("Target or original machine dossier identity mismatch", BLOCKED)
        raw = self.source_bytes(reference)
        if str(len(raw)) != str(dossier_row["record"]["provenance"].get("tracked_bytes")):
            raise EvidenceError("Pinned target byte count does not match the original manifest", BLOCKED)
        return raw, dossier_row["record"]


def _include_closure(context, root_reference):
    if PurePosixPath(root_reference["path"]).suffix.lower() not in SOURCE_EXTENSIONS:
        raise EvidenceError("Exact-byte proof is unsupported for this source language")
    root_repo = root_reference["repository"]
    root_revision = root_reference["revision"]
    pending = [root_reference["path"]]
    visited = set()
    contents = {}
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        # A dependency may not be a candidate queue entry; validate its committed blob directly.
        if path == root_reference["path"]:
            data = context.source_bytes(root_reference)
        else:
            try:
                checkout = context.source_root / root_repo.split("/")[-1]
                blob = git(checkout, "rev-parse", f"{root_revision}:{path}")
                data = subprocess.check_output(
                    ["git", "-C", str(checkout), "cat-file", "blob", blob],
                    stderr=subprocess.PIPE,
                )
            except subprocess.CalledProcessError as exc:
                raise EvidenceError(f"Unresolved include dependency: {root_repo}:{path}") from exc
            reference = {
                "repository": root_repo,
                "revision": root_revision,
                "path": path,
                "git_blob_sha1": blob,
                "source_sha256": sha256(data),
            }
            data = context.source_bytes(reference)
        contents[path] = data
        for line in data.splitlines():
            if re.match(rb'^\s*#\s*include\b', line) and not INCLUDE.fullmatch(line.strip()):
                raise EvidenceError(f"Unsupported include form in dependency closure: {root_repo}:{path}")
        for match in INCLUDE.finditer(data):
            include = match.group(1).decode("utf-8", "strict")
            candidate_paths = {
                str(PurePosixPath(path).parent / include),
                include,
                str(PurePosixPath("include") / include),
            }
            matches = []
            checkout = context.source_root / root_repo.split("/")[-1]
            for candidate in candidate_paths:
                candidate = _safe_path(candidate)
                try:
                    git(checkout, "cat-file", "-e", f"{root_revision}:{candidate}")
                    matches.append(candidate)
                except subprocess.CalledProcessError:
                    pass
            if len(set(matches)) != 1:
                raise EvidenceError(
                    f"Include is unresolved or ambiguous ({root_repo}:{path}: {include})"
                )
            pending.append(matches[0])
    return contents


def _verify_actions_run(run_reference, api_get):
    if not isinstance(run_reference, dict):
        raise EvidenceError("Required successful upstream test run is missing", BLOCKED)
    repository = run_reference.get("repository")
    if not isinstance(repository, str) or repository not in {repo for repo, _, _ in PINS}:
        raise EvidenceError("Test run repository is not one of the pinned repositories", BLOCKED)
    run_id = run_reference.get("run_id")
    expected_head = run_reference.get("head_sha")
    workflow_path = run_reference.get("workflow_path")
    if type(run_id) is not int or run_id < 1 or not isinstance(expected_head, str):
        raise EvidenceError("Test run identity is malformed", BLOCKED)
    if not isinstance(workflow_path, str) or not workflow_path.startswith(".github/workflows/"):
        raise EvidenceError("Test workflow path is malformed", BLOCKED)
    base = f"{API_ROOT}/{repository}/actions/runs/{run_id}"
    run = api_get(base)
    if (
        not isinstance(run, dict)
        or run.get("id") != run_id
        or run.get("head_sha") != expected_head
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or str(run.get("path", "")).split("@", 1)[0] != workflow_path
    ):
        raise EvidenceError("Pinned upstream test run is stale, mismatched, or unsuccessful", BLOCKED)
    attempt = run.get("run_attempt")
    if type(attempt) is not int or attempt < 1:
        raise EvidenceError("Pinned upstream test run has an invalid attempt", BLOCKED)
    jobs = []
    seen = set()
    page = 1
    total = None
    while True:
        response = api_get(f"{base}/attempts/{attempt}/jobs?per_page=100&page={page}")
        page_jobs = response.get("jobs") if isinstance(response, dict) else None
        reported = response.get("total_count") if isinstance(response, dict) else None
        if not isinstance(page_jobs, list) or type(reported) is not int or reported < 0:
            raise EvidenceError("Upstream test job response is invalid", BLOCKED)
        if total is None:
            total = reported
        elif total != reported:
            raise EvidenceError("Upstream test job count changed during pagination", BLOCKED)
        for job in page_jobs:
            job_id = job.get("id") if isinstance(job, dict) else None
            if type(job_id) is not int or job_id < 1 or job_id in seen:
                raise EvidenceError("Upstream test jobs are malformed or duplicated", BLOCKED)
            seen.add(job_id)
        jobs.extend(page_jobs)
        if len(page_jobs) < 100:
            break
        page += 1
    if total < 1 or len(jobs) != total:
        raise EvidenceError("Upstream test run has zero or incomplete jobs", BLOCKED)
    for job in jobs:
        steps = job.get("steps")
        if (
            job.get("status") != "completed"
            or job.get("conclusion") != "success"
            or not isinstance(steps, list)
            or not any(
                isinstance(step, dict)
                and step.get("status") == "completed"
                and step.get("conclusion") == "success"
                and step.get("started_at")
                and step.get("completed_at")
                for step in steps
            )
        ):
            raise EvidenceError("Upstream test run contains a failed or unexecuted job", BLOCKED)
    return total


def github_get(url, token=None):
    if not url.startswith(API_ROOT + "/"):
        raise ValueError("Only read-only requests to pinned public GitHub repositories are allowed")
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "XGBA-Phase1-upstream-verifier-v1",
            **({"Authorization": "Bearer " + token} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"GitHub Actions provenance unavailable: {exc}", BLOCKED) from exc


def _verify_reference(context, reference):
    if not isinstance(reference, dict):
        raise EvidenceError("Required immutable evidence reference is missing", BLOCKED)
    data = context.source_bytes(reference)
    return data


def _record_result(record, context, api_get):
    if not isinstance(record, dict) or record.get("schema") != MAPPING_SCHEMA:
        raise EvidenceError("Unsupported or malformed upstream mapping schema", BLOCKED)
    record_body = {key: value for key, value in record.items() if key != "record_sha256"}
    if record.get("record_sha256") != sha256(canonical_bytes(record_body)):
        raise EvidenceError("Canonical mapping record digest mismatch", BLOCKED)
    target = record.get("target")
    dossier = record.get("dossier")
    target_data, machine_dossier = context.verify_target(target, dossier)
    implementation = record.get("implementation")
    implementation_data = _verify_reference(context, implementation)
    if (
        implementation.get("repository") == target.get("repository")
        and implementation.get("path") == target.get("path")
    ):
        raise EvidenceError("Upstream implementation cannot be the target itself", BLOCKED)

    proof_mode = record.get("proof_mode")
    if proof_mode == "behavioral_equivalence":
        raise EvidenceError(
            "Behavioral equivalence requires a separately pinned conformance harness; v1 does not qualify it"
        )
    if proof_mode != "exact_bytes":
        raise EvidenceError("Unsupported congruence proof mode")
    if target_data != implementation_data:
        raise EvidenceError("Exact-byte congruence failed for target and upstream implementation")

    scope = record.get("scope")
    line_count = len(target_data.splitlines())
    if (
        not isinstance(scope, dict)
        or scope.get("claim_level") != "source"
        or scope.get("semantic_claim") != "exact_pinned_bytes_and_include_closure"
        or scope.get("covered_lines") != [[1, line_count]]
        or type(scope.get("whole_file")) is not bool
        or scope.get("whole_file") is not True
        or line_count < 1
    ):
        raise EvidenceError("Whole-file semantic scope is incomplete")

    closure = record.get("dependency_closure")
    if not isinstance(closure, dict) or closure.get("complete") is not True:
        raise EvidenceError("Dependency closure is incomplete")
    target_closure = _include_closure(context, target)
    implementation_closure = _include_closure(context, implementation)
    pairs = closure.get("pairs")
    if not isinstance(pairs, list):
        raise EvidenceError("Dependency closure pairs are missing")
    target_paths = set(target_closure) - {target["path"]}
    implementation_paths = set(implementation_closure) - {implementation["path"]}
    mapped_target = set()
    mapped_implementation = set()
    pair_rows = []
    for pair in pairs:
        if not isinstance(pair, dict):
            raise EvidenceError("Dependency closure pair is malformed")
        target_ref = pair.get("target")
        implementation_ref = pair.get("implementation")
        target_bytes = _verify_reference(context, target_ref)
        implementation_bytes = _verify_reference(context, implementation_ref)
        if target_ref.get("repository") != target["repository"] or implementation_ref.get("repository") != implementation["repository"]:
            raise EvidenceError("Dependency pair crosses an unpinned repository scope", BLOCKED)
        if target_ref.get("path") in mapped_target or implementation_ref.get("path") in mapped_implementation:
            raise EvidenceError("Dependency closure contains duplicate paths")
        if target_bytes != implementation_bytes:
            raise EvidenceError("Dependency bytes differ between the mapped implementations")
        mapped_target.add(target_ref["path"])
        mapped_implementation.add(implementation_ref["path"])
        pair_rows.append({"target": target_ref, "implementation": implementation_ref})
    if mapped_target != target_paths or mapped_implementation != implementation_paths:
        raise EvidenceError("Dependency closure omits or adds pinned include dependencies")
    pair_rows.sort(key=lambda item: (item["target"]["path"], item["implementation"]["path"]))
    if closure.get("sha256") != sha256(canonical_bytes(pair_rows)):
        raise EvidenceError("Dependency closure digest mismatch", BLOCKED)

    semantic_dependencies = record.get("semantic_dependencies")
    if not isinstance(semantic_dependencies, list) or not semantic_dependencies:
        raise EvidenceError("Semantic dependency/consumer evidence is missing")
    for dependency in semantic_dependencies:
        if (
            not isinstance(dependency, dict)
            or dependency.get("kind") not in {"build", "consumer", "producer", "specification"}
            or not isinstance(dependency.get("evidence"), list)
            or not dependency["evidence"]
        ):
            raise EvidenceError("Semantic dependency/consumer closure is incomplete")
        for reference in dependency["evidence"]:
            _verify_reference(context, reference)

    licensing = record.get("licensing")
    if (
        not isinstance(licensing, dict)
        or licensing.get("status") not in {"compatible", "permitted", "not_applicable"}
        or not isinstance(licensing.get("evidence"), list)
        or not licensing["evidence"]
    ):
        raise EvidenceError("Licensing clearance is missing, unsupported, or incompatible")
    license_repositories = set()
    for item in licensing["evidence"]:
        if not isinstance(item, dict):
            raise EvidenceError("License evidence reference is malformed", BLOCKED)
        license_ref = item.get("source")
        license_bytes = _verify_reference(context, license_ref)
        spdx_id = item.get("spdx_id")
        if item.get("sha256") != sha256(license_bytes):
            raise EvidenceError("License evidence digest mismatch", BLOCKED)
        if spdx_id not in SPDX_ALLOWLIST:
            raise EvidenceError("Licensing uses an unsupported or incompatible SPDX identifier")
        marker = f"SPDX-License-Identifier: {spdx_id}".encode()
        if marker not in license_bytes:
            raise EvidenceError("License file does not substantiate the declared SPDX identifier")
        license_repositories.add(license_ref["repository"])
    expected_licenses = {
        target["repository"],
        implementation["repository"],
        *(pair["target"]["repository"] for pair in pair_rows),
        *(pair["implementation"]["repository"] for pair in pair_rows),
        *(
            evidence_reference["repository"]
            for dependency in semantic_dependencies
            for evidence_reference in dependency["evidence"]
        ),
    }
    objections = record.get("objections")
    if not isinstance(objections, list) or objections:
        raise EvidenceError("Unresolved or malformed substantive objections remain")
    tests = record.get("tests")
    if (
        not isinstance(tests, dict)
        or not isinstance(tests.get("test_files"), list)
        or not tests["test_files"]
    ):
        raise EvidenceError("Required test/spec evidence is missing")
    specification = _verify_reference(context, tests.get("specification"))
    workflow_reference = tests.get("workflow")
    workflow_bytes = _verify_reference(context, workflow_reference)
    if not specification or not isinstance(tests.get("specification"), dict):
        raise EvidenceError("Pinned test specification is missing")
    if not workflow_reference["path"].startswith(".github/workflows/"):
        raise EvidenceError("Pinned test workflow reference is outside the GitHub workflow tree", BLOCKED)
    for reference in tests["test_files"]:
        _verify_reference(context, reference)
        if reference["path"].encode() not in workflow_bytes:
            raise EvidenceError("Pinned test workflow does not name a required test artifact")
    test_repositories = {
        tests["specification"]["repository"],
        workflow_reference["repository"],
        *(reference["repository"] for reference in tests["test_files"]),
    }
    if not expected_licenses.union(test_repositories).issubset(license_repositories):
        raise EvidenceError("License evidence does not cover the complete pinned test/dependency scope")
    test_jobs = _verify_actions_run(tests.get("actions_run"), api_get)
    run = tests["actions_run"]
    if (
        run["head_sha"] != tests["specification"]["revision"]
        or run["repository"] != tests["specification"]["repository"]
        or run["workflow_path"] != workflow_reference["path"]
        or workflow_reference["repository"] != tests["specification"]["repository"]
        or workflow_reference["revision"] != run["head_sha"]
        or any(
            reference.get("repository") != run["repository"]
            or reference.get("revision") != run["head_sha"]
            for reference in tests["test_files"]
        )
    ):
        raise EvidenceError("Successful test run does not match the pinned specification revision", BLOCKED)

    return {
        "source": f"{target['repository']}:{target['path']}",
        "disposition": PASSED,
        "reason": "Pinned exact-byte implementation, dossier, include closure, semantic evidence, licensing, objections, and executed upstream tests verified",
        "test_jobs": test_jobs,
        "proof_mode": proof_mode,
    }


def evaluate_records(records, context, api_get):
    if not isinstance(records, list):
        records = []
        parse_error = "Evidence register is not a JSONL record list"
    else:
        parse_error = None
    results = {}
    duplicates = set()
    global_error = None
    for record in records:
        target = record.get("target", {}) if isinstance(record, dict) else {}
        key = (target.get("repository"), target.get("path"))
        label = f"{key[0]}:{key[1]}" if all(key) else "unknown"
        if key not in context.queue:
            global_error = "Upstream mapping artifact names a target outside the pinned inventory"
            continue
        if key in results:
            duplicates.add(key)
            continue
        try:
            result = _record_result(record, context, api_get)
            results[key] = result
        except EvidenceError as exc:
            results[key] = {
                "source": label,
                "disposition": exc.disposition,
                "reason": str(exc),
            }
        except Exception as exc:
            results[key] = {
                "source": label,
                "disposition": BLOCKED,
                "reason": f"Unexpected evidence validation error: {exc}",
            }
    for key in duplicates:
        results[key] = {
            "source": f"{key[0]}:{key[1]}",
            "disposition": BLOCKED,
            "reason": "Duplicate evidence records for the same pinned source",
        }
    if global_error:
        results = {
            key: {
                "source": f"{key[0]}:{key[1]}",
                "disposition": BLOCKED,
                "reason": global_error,
            }
            for key in context.queue
        }
    if parse_error:
        results = {
            key: {
                "source": f"{key[0]}:{key[1]}",
                "disposition": BLOCKED,
                "reason": parse_error,
            }
            for key in context.queue
        }
    for key in context.queue:
        if key not in results:
            results[key] = {
                "source": f"{key[0]}:{key[1]}",
                "disposition": NEEDS_REVIEW,
                "reason": "No upstream congruence evidence record exists",
            }
    ordered = [results[key] for key in sorted(context.queue)]
    passed = {item["source"] for item in ordered if item["disposition"] == PASSED}
    counts = {
        "upstream_verified_passed_count": len(passed),
        "needs_review_count": sum(item["disposition"] == NEEDS_REVIEW for item in ordered),
        "blocked_count": sum(item["disposition"] == BLOCKED for item in ordered),
        "inventory_total": len(context.queue),
        "inventory_remaining": len(context.queue) - len(passed),
    }
    return {
        "schema": SCHEMA,
        "policy_status": "PROPOSAL_NOT_ACTIVATED",
        **context.legacy_counts,
        "upstream_verified_passed_count": counts["upstream_verified_passed_count"],
        "needs_review_count": counts["needs_review_count"],
        "blocked_count": counts["blocked_count"],
        "inventory_total": counts["inventory_total"],
        "inventory_remaining": counts["inventory_remaining"],
        "prospective_completion_gate": "FAIL_INCOMPLETE",
        "dispositions": ordered,
    }


def load_evidence(data):
    try:
        register = json.loads(data)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Pinned upstream evidence register is not valid JSON") from exc
    if (
        not isinstance(register, dict)
        or register.get("schema") != REGISTER_SCHEMA
        or not isinstance(register.get("records"), list)
    ):
        raise ValueError("Pinned upstream evidence register has an unsupported schema")
    return register["records"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source-root", type=Path, required=True,
                        help="read-only checkouts of all five repositories at configured pins")
    args = parser.parse_args(argv)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    try:
        context = PinnedContext(args.repository_root, args.source_root,
                                lambda url: github_get(url, token=token))
        records = load_evidence(context.register_bytes)
        report = evaluate_records(records, context, context.api_get)
        print(json.dumps(report, sort_keys=True))
        return 0 if report["upstream_verified_passed_count"] == report["inventory_total"] else 2
    except Exception as exc:
        print(json.dumps({
            "schema": SCHEMA,
            "policy_status": "PROPOSAL_NOT_ACTIVATED",
            "legacy_external_independent_approved": None,
            "legacy_p0_external_independent_approved": None,
            "legacy_p0_review_candidates": P0_CANDIDATES,
            "upstream_verified_passed_count": 0,
            "needs_review_count": 0,
            "blocked_count": INVENTORY_SIZE,
            "inventory_total": INVENTORY_SIZE,
            "inventory_remaining": INVENTORY_SIZE,
            "prospective_completion_gate": "FAIL_INCOMPLETE",
            "dispositions": [],
            "blocker": str(exc),
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
