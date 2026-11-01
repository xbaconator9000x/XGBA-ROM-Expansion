#!/usr/bin/env python3
"""Verify exact-pin native mGBA boundary evidence from its executing Actions job."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_native_mgba_regressions as native_gate

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
REPOSITORY = "xbaconator9000x/XGBA-ROM-Expansion"
WORKFLOW_NAME = "Phase 1 compiled mGBA source semantics"
WORKFLOW_PATH = ".github/workflows/compiled-mgba-semantics.yml"
JOB_NAME = "compile-pinned-mgba"
PROBE_SUITE_REVISION = "native_matrix_vfile_fault_controls_v8"
TEST_PATH = "tests/mgba_bank_boundary.c"
TEST_BLOB = "e37a467ca6479e2864d773001ae7ead2977f08cf"
TEST_SHA256 = "b88f1bb14d8e548f7bf20904ae741b0c97f2d46094d176a9b140f57b62ce744c"
SOURCE_PINS = {
    "src/arm/arm.c": (
        "0b92d7f55f1fb853d4b1b9c9163ee086126066e2",
        "c241587e974ac29aa09ed4992c9244c7ac65fad938e61d45836dc457f57129d2",
    ),
    "src/gba/cart/matrix.c": (
        "9ccbe883235b98bcf56cd609015e7b4003aa832c",
        "6e47afc6992d3631d67f89cb201d7fe9784ef8a9e8dcb305c1ab5de48550ef8f",
    ),
    "src/gba/dma.c": (
        "da2a800ba48cb32d6e10e42c3b3527ef406bad22",
        "cd4c795f69ec16373e475b4c902e863e4a6db61cd2b9f1c4d851496d3202b9d1",
    ),
    "src/gba/gba.c": (
        "c30bd943909dc00df0b5b9932e6d9ddb6e1c404e",
        "e84eaba17f6c96ac7b78431afaee79d7633dd50118f92e31e4432793f80c4c7b",
    ),
    "src/gba/memory.c": (
        "aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc",
        "501dbbca7d5d7cbaa86240de2d6a4e2e1186b50f74dde11bcf2f323c4af8c437",
    ),
    "src/gba/serialize.c": (
        "a307a51e751f412c64a7378323c56758304ebe85",
        "23947295749e6eeb27ab13d2a6d4c18bf88b587bcf3109e6d3e6bab5a5658dc3",
    ),
}


class EvidenceRejected(ValueError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def verify_pinned_sources(repository_root: Path, upstream_root: Path) -> dict:
    if upstream_root.is_symlink() or not (upstream_root / ".git").exists():
        raise EvidenceRejected("PINNED_UPSTREAM_CHECKOUT_MISSING_OR_UNSAFE")
    if _git(upstream_root, "rev-parse", "HEAD") != PIN:
        raise EvidenceRejected("PINNED_UPSTREAM_REVISION_MISMATCH")
    if _git(upstream_root, "status", "--porcelain", "--untracked-files=all"):
        raise EvidenceRejected("PINNED_UPSTREAM_CHECKOUT_DIRTY")

    identities = {}
    for path, (expected_blob, expected_sha) in SOURCE_PINS.items():
        source = upstream_root / path
        if source.is_symlink() or not source.is_file():
            raise EvidenceRejected("PINNED_UPSTREAM_SOURCE_MISSING:" + path)
        data = source.read_bytes()
        if _git(upstream_root, "hash-object", path) != expected_blob:
            raise EvidenceRejected("PINNED_UPSTREAM_GIT_BLOB_MISMATCH:" + path)
        if _sha256(data) != expected_sha:
            raise EvidenceRejected("PINNED_UPSTREAM_SHA256_MISMATCH:" + path)
        identities[path] = {
            "git_blob_sha1": expected_blob,
            "source_sha256": expected_sha,
        }

    test_source = repository_root / TEST_PATH
    if test_source.is_symlink() or not test_source.is_file():
        raise EvidenceRejected("NATIVE_TEST_SOURCE_MISSING")
    test_bytes = test_source.read_bytes()
    if _git(repository_root, "hash-object", TEST_PATH) != TEST_BLOB:
        raise EvidenceRejected("NATIVE_TEST_GIT_BLOB_MISMATCH")
    if _sha256(test_bytes) != TEST_SHA256:
        raise EvidenceRejected("NATIVE_TEST_SHA256_MISMATCH")
    return {
        "pinned_revision": PIN,
        "source_identities": identities,
        "test_source": {
            "path": TEST_PATH,
            "git_blob_sha1": TEST_BLOB,
            "sha256": TEST_SHA256,
        },
    }


def verify_case_log(runtime_log: str, result: dict, test_source: bytes) -> dict:
    if not isinstance(result, dict):
        raise EvidenceRejected("NATIVE_RESULT_RECORD_INVALID")
    if type(result.get("native_probe_exit_code")) is not int or result.get("native_probe_exit_code") != 0:
        raise EvidenceRejected("NATIVE_PROBE_EXIT_CODE_INVALID")
    if result.get("probe_suite_revision") != PROBE_SUITE_REVISION:
        raise EvidenceRejected("NATIVE_PROBE_SUITE_REVISION_MISMATCH")
    if (
        type(result.get("positive_checks_passed")) is not int
        or type(result.get("positive_checks_failed")) is not int
    ):
        raise EvidenceRejected("NATIVE_RESULT_COUNTS_INVALID")
    try:
        native_summary = native_gate.check(runtime_log, result, test_source)
    except native_gate.EvidenceRejected as exc:
        raise EvidenceRejected(str(exc)) from exc
    cases = re.findall(r"^CASE ([^ \r\n]+) exit_code=([0-9]+)$", runtime_log, re.M)
    observations = re.findall(
        r"^CASE_OBSERVATION ([^ \r\n]+) observed=(true|false) exit_code=([0-9]+)$",
        runtime_log,
        re.M,
    )
    case_names = [name for name, _ in cases]
    if len(case_names) != len(set(case_names)):
        raise EvidenceRejected("DUPLICATE_NATIVE_CASE_RECORD")
    if set(case_names) != set(native_gate.extract(runtime_log, "PASS")):
        raise EvidenceRejected("NATIVE_CASES_DO_NOT_MATCH_PASS_ASSERTIONS")
    if any(code != "0" for _, code in cases):
        raise EvidenceRejected("NATIVE_CASE_EXIT_CODE_NONZERO")
    observation_names = [name for name, _, _ in observations]
    if len(observation_names) != len(set(observation_names)):
        raise EvidenceRejected("DUPLICATE_NATIVE_OBSERVATION_RECORD")
    if set(observation_names) != {
        row.split("=", 1)[0] for row in native_gate.extract(runtime_log, "OBSERVATION")
    }:
        raise EvidenceRejected("NATIVE_OBSERVATIONS_DO_NOT_MATCH_RECORDS")
    if any(code != "0" for _, _, code in observations):
        raise EvidenceRejected("NATIVE_OBSERVATION_PROCESS_STATUS_INVALID")
    return {
        "assertions_verified": native_summary["assertions_verified"],
        "case_results": [
            {"case": name, "exit_code": int(code), "stdout": "PASS " + name}
            for name, code in cases
        ],
        "hazard_observations": [
            {"observation": name, "observed": value == "true", "exit_code": int(code)}
            for name, value, code in observations
        ],
        "runtime_stdout_sha256": _sha256(runtime_log.encode()),
        "native_regression_gate": native_summary["decision"],
    }


def verify_actions_provenance(run: dict, jobs: dict, context: dict) -> dict:
    if not isinstance(run, dict) or not isinstance(jobs, dict):
        raise EvidenceRejected("ACTIONS_API_RECORD_INVALID")
    if not isinstance(context, dict):
        raise EvidenceRejected("ACTIONS_CONTEXT_MALFORMED")
    pull_requests = run.get("pull_requests")
    job_rows = jobs.get("jobs")
    if not isinstance(pull_requests, list) or not isinstance(job_rows, list):
        raise EvidenceRejected("ACTIONS_API_RECORD_INVALID")
    head_repository = run.get("head_repository")
    base_repository = run.get("repository")
    if not isinstance(head_repository, dict):
        head_repository = {}
    if not isinstance(base_repository, dict):
        base_repository = {}
    run_id = context.get("run_id")
    attempt = context.get("run_attempt")
    head_sha = context.get("head_sha")
    if (
        type(run_id) is not int
        or type(attempt) is not int
        or not isinstance(head_sha, str)
        or not re.fullmatch(r"[0-9a-f]{40}", head_sha)
    ):
        raise EvidenceRejected("ACTIONS_CONTEXT_MALFORMED")
    if (
        type(run.get("id")) is not int
        or type(run.get("run_attempt")) is not int
        or run.get("id") != run_id
        or run.get("run_attempt") != attempt
        or run.get("head_sha") != head_sha
        or run.get("name") != WORKFLOW_NAME
        or run.get("path") != WORKFLOW_PATH
        or run.get("event") not in {"push", "workflow_dispatch"}
        or run.get("status") != "in_progress"
        or REPOSITORY
        not in {
            head_repository.get("full_name"),
            base_repository.get("full_name"),
        }
        or not any(isinstance(pr, dict) and pr.get("number") == 2 for pr in pull_requests)
    ):
        raise EvidenceRejected("ACTIONS_RUN_PROVENANCE_MISMATCH")
    matches = [
        job
        for job in job_rows
        if isinstance(job, dict)
        and job.get("name") == JOB_NAME and job.get("run_id") == run_id
    ]
    if len(matches) != 1:
        raise EvidenceRejected("ACTIONS_JOB_ID_MISSING_OR_AMBIGUOUS")
    job = matches[0]
    if (
        type(job.get("id")) is not int
        or job.get("head_sha") != head_sha
        or job.get("status") != "in_progress"
        or job.get("conclusion") is not None
    ):
        raise EvidenceRejected("ACTIONS_JOB_PROVENANCE_MISMATCH")
    job_steps = job.get("steps")
    if not isinstance(job_steps, list):
        raise EvidenceRejected("ACTIONS_JOB_STEPS_MISSING")
    steps = {
        step.get("name"): step for step in job_steps if isinstance(step, dict)
    }
    for name in (
        "Configure headless mGBA C core",
        "Compile and link unmodified pinned mGBA",
        "Analyze actual compiler targets and linked symbols",
    ):
        step = steps.get(name)
        if not step or step.get("status") != "completed" or step.get("conclusion") != "success":
            raise EvidenceRejected("ACTIONS_NATIVE_EXECUTION_STEP_NOT_SUCCESSFUL:" + name)
    return {
        "repository": REPOSITORY,
        "run_id": run_id,
        "run_attempt": attempt,
        "head_sha": head_sha,
        "event": run["event"],
        "workflow_name": WORKFLOW_NAME,
        "workflow_path": WORKFLOW_PATH,
        "job_id": job["id"],
        "job_name": JOB_NAME,
        "job_status_when_queried": job["status"],
    }


def _get_api_json(url: str, token: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + token,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "XGBA-Phase1-native-evidence-verifier",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status != 200:
                raise EvidenceRejected("GITHUB_ACTIONS_API_HTTP_STATUS_INVALID")
            data = response.read(2 * 1024 * 1024 + 1)
    except (OSError, urllib.error.URLError) as exc:
        raise EvidenceRejected("GITHUB_ACTIONS_API_UNAVAILABLE") from exc
    if len(data) > 2 * 1024 * 1024:
        raise EvidenceRejected("GITHUB_ACTIONS_API_RESPONSE_TOO_LARGE")
    try:
        value = json.loads(data)
    except json.JSONDecodeError as exc:
        raise EvidenceRejected("GITHUB_ACTIONS_API_RESPONSE_INVALID") from exc
    if not isinstance(value, dict):
        raise EvidenceRejected("GITHUB_ACTIONS_API_RESPONSE_INVALID")
    return value


def verify_live_evidence(repository_root: Path) -> dict:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise EvidenceRejected("MUST_RUN_INSIDE_GITHUB_ACTIONS")
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY:
        raise EvidenceRejected("ACTIONS_REPOSITORY_MISMATCH")
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise EvidenceRejected("READ_ONLY_GITHUB_TOKEN_MISSING")
    try:
        run_id = int(os.environ["GITHUB_RUN_ID"])
        attempt = int(os.environ["GITHUB_RUN_ATTEMPT"])
    except (KeyError, ValueError) as exc:
        raise EvidenceRejected("ACTIONS_RUN_CONTEXT_MISSING") from exc
    head_sha = os.environ.get("GITHUB_SHA", "")
    if _git(repository_root, "rev-parse", "HEAD") != head_sha:
        raise EvidenceRejected("ACTIONS_CHECKOUT_HEAD_MISMATCH")
    api_root = "https://api.github.com/repos/" + REPOSITORY
    run = _get_api_json(f"{api_root}/actions/runs/{run_id}", token)
    jobs = _get_api_json(f"{api_root}/actions/runs/{run_id}/jobs?per_page=100", token)
    provenance = verify_actions_provenance(
        run,
        jobs,
        {"run_id": run_id, "run_attempt": attempt, "head_sha": head_sha},
    )

    evidence_dir = repository_root / "compiler-evidence"
    runtime_path = evidence_dir / "mgba-boundary-runtime.log"
    result_path = evidence_dir / "mgba-native-boundary-result.json"
    configure_path = evidence_dir / "mgba-boundary-configure.log"
    build_path = evidence_dir / "mgba-boundary-build.log"
    if any(not path.is_file() or path.is_symlink() for path in (
        runtime_path, result_path, configure_path, build_path
    )):
        raise EvidenceRejected("NATIVE_EXECUTION_ARTIFACT_MISSING")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    runtime_log = runtime_path.read_text(encoding="utf-8")
    test_source = (repository_root / TEST_PATH).read_bytes()
    sources = verify_pinned_sources(repository_root, repository_root / "upstream/mgba")
    case_report = verify_case_log(runtime_log, result, test_source)
    return {
        "schema": "xgba.phase1.native_mgba_boundary_evidence.v1",
        "disposition": "NATIVE_EVIDENCE_ONLY",
        "provenance": provenance,
        "executed_checkout_sha": head_sha,
        "source_identity": sources,
        "native_execution": {
            **case_report,
            "configure_log_sha256": _sha256(configure_path.read_bytes()),
            "build_log_sha256": _sha256(build_path.read_bytes()),
            "native_probe_exit_code": result.get("native_probe_exit_code"),
        },
        "semantic_dispositions_added": 0,
        "upstream_verified_passed_count": 0,
        "dependency_consumer_closure": "NOT_ESTABLISHED",
        "license_distribution_clearance": "NOT_ASSESSED",
        "phase1_mapping_complete": False,
        "synthetic_fixtures_counted": 0,
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    output = root / "compiler-evidence/mgba-native-boundary-ingestion.json"
    try:
        result = verify_live_evidence(root)
    except (EvidenceRejected, OSError, ValueError, subprocess.CalledProcessError) as exc:
        result = {
            "schema": "xgba.phase1.native_mgba_boundary_evidence.v1",
            "disposition": "BLOCKED",
            "reason": str(exc),
            "semantic_dispositions_added": 0,
            "phase1_mapping_complete": False,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2, sort_keys=True), file=sys.stderr)
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
