#!/usr/bin/env python3
"""Validate the non-approving B021 Porymap workflow provenance observation."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = (
    ROOT
    / "development/copilot-integration/"
    "porymap-b021-workflow-id-reconciliation-20261107.json"
)
QUEUE_PATH = ROOT / "semantic-snapshots/current/semantic_review_queue.csv.gz"
DOSSIERS_PATH = (
    ROOT / "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
)
MANIFEST_PATH = ROOT / "development/copilot-integration/manifest.json"
TRIAGE_PATH = ROOT / "development/copilot-integration/blocker-triage-20261104.json"
PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
SOURCE_PATHS = {
    "include/lib/orderedjson.h",
    "src/core/map.cpp",
    "src/editor.cpp",
    "src/lib/orderedjson.cpp",
    "src/mainwindow.cpp",
    "src/project.cpp",
}
QUEUE_PATHS = SOURCE_PATHS | {"LICENSE.md"}
BLOCKER_IDS = ("B021", "B020")
RUNS = {
    40490882094: {
        "attempt": 1,
        "event": "push",
        "job_id": 122144214009,
        "job_name": "pinned-qt-writer",
    },
    40490889813: {
        "attempt": 1,
        "event": "pull_request",
        "job_id": 122144238540,
        "job_name": "pinned-qt-writer",
    },
}
CRITICAL_STEPS = [
    "Checkout immutable Porymap source",
    "Verify source syntax and exact pinned provenance",
    "Compile and execute pinned Qt serializer success and failure controls",
    "Archive provenance and negative evidence",
]
SOURCE_PACKET_BLOBS = {
    "document_git_blob_sha1": "441ed685ad645a2076d5bc8b3d36d3edb6d9d8d7",
    "checker_git_blob_sha1": "f24e3659675ffbff016b1f87e63d892b9162876d",
    "test_git_blob_sha1": "92e3dca9f25b6780512c9cd85a519e5b2b6dcf93",
    "workflow_git_blob_sha1": "397b19f7feb8ce8c5d42d35edae28768136fe7dd",
}
LICENSE_IDENTITY = {
    "path": "LICENSE.md",
    "git_blob_sha1": "65c5ca88a67c30becee01c5a8816d964b03862f9",
    "source_sha256": "da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768",
    "dossier_sha256": "a620cf8ec560f8bf6f54e9d96403ec1cb204f3ddad7fef812ce7893059396986",
    "priority": "P3",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return _sha256(encoded)


def load_reference(root: Path = ROOT) -> dict:
    queue_path = root / QUEUE_PATH.relative_to(ROOT)
    dossiers_path = root / DOSSIERS_PATH.relative_to(ROOT)
    queue = {}
    with gzip.open(queue_path, "rt", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("repo") == "huderlem/porymap" and row.get("path") in QUEUE_PATHS:
                queue[row["path"]] = row

    dossiers = {}
    with gzip.open(dossiers_path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            path = provenance.get("path")
            if (
                provenance.get("repository") == "huderlem/porymap"
                and path in QUEUE_PATHS
            ):
                dossiers[path] = row

    manifest_path = root / MANIFEST_PATH.relative_to(ROOT)
    triage_path = root / TRIAGE_PATH.relative_to(ROOT)
    return {
        "queue": queue,
        "dossiers": dossiers,
        "manifest": json.loads(manifest_path.read_text(encoding="utf-8")),
        "triage": json.loads(triage_path.read_text(encoding="utf-8")),
        "source_hashes": {
            str(path.relative_to(root)): _sha256(path.read_bytes())
            for path in (queue_path, dossiers_path, manifest_path, triage_path)
        },
    }


def validate_reconciliation(evidence: dict, reference: dict) -> list[str]:
    findings = []
    if not isinstance(evidence, dict):
        return ["evidence record must be a JSON object"]
    if evidence.get("schema") != "copilot-integration-b021-porymap-workflow-reconciliation-v1":
        findings.append("unsupported evidence schema")
    if evidence.get("repository") != "xbaconator9000x/XGBA-ROM-Expansion":
        findings.append("repository identity mismatch")
    if evidence.get("source_registry", {}).get("repository") != "huderlem/porymap":
        findings.append("upstream repository identity mismatch")
    if evidence.get("source_registry", {}).get("revision") != PIN:
        findings.append("immutable upstream revision mismatch")

    source_registry = evidence.get("source_registry", {})
    expected_hashes = {
        "queue_path": "semantic-snapshots/current/semantic_review_queue.csv.gz",
        "dossiers_path": "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz",
        "manifest_path": "development/copilot-integration/manifest.json",
        "triage_path": "development/copilot-integration/blocker-triage-20261104.json",
    }
    for key, path in expected_hashes.items():
        if source_registry.get(key.replace("_path", "_sha256")) != reference.get(
            "source_hashes", {}
        ).get(path):
            findings.append("%s archive/source hash mismatch" % key)

    source_files = evidence.get("source_files")
    if not isinstance(source_files, list):
        source_files = []
        findings.append("source file identities are missing")
    paths = [row.get("path") for row in source_files if isinstance(row, dict)]
    if len(paths) != len(set(paths)):
        findings.append("source file identities contain duplicates")
    if set(paths) != SOURCE_PATHS:
        findings.append("source file closure is incomplete or contains unrelated files")
    queue = reference.get("queue", {})
    dossiers = reference.get("dossiers", {})
    if not QUEUE_PATHS.issubset(queue) or not QUEUE_PATHS.issubset(dossiers):
        findings.append("pinned queue or dossier does not cover the source/license set")
    for source in source_files:
        if not isinstance(source, dict):
            findings.append("source identity is malformed")
            continue
        path = source.get("path")
        queued = queue.get(path)
        dossier = dossiers.get(path)
        if queued is None or dossier is None:
            findings.append("%s is absent from the source queue or dossier" % path)
            continue
        provenance = dossier.get("provenance", {})
        expected = {
            "git_blob_sha1": queued.get("blob_sha"),
            "source_sha256": provenance.get("source_content_sha256"),
            "dossier_sha256": _canonical_sha256(dossier),
            "priority": queued.get("priority"),
        }
        for key, value in expected.items():
            if source.get(key) != value:
                findings.append("%s %s differs from pinned registry" % (path, key))
        if provenance.get("pinned_revision") != PIN:
            findings.append("%s dossier revision differs from pinned source" % path)
        if queued.get("evidence_sha256") != expected["dossier_sha256"]:
            findings.append("%s original dossier hash differs from queue evidence" % path)

    license_record = evidence.get("source_trace", {}).get("licensing", {})
    license_queued = queue.get("LICENSE.md", {})
    license_dossier = dossiers.get("LICENSE.md", {})
    license_provenance = license_dossier.get("provenance", {})
    license_dossier_sha256 = _canonical_sha256(license_dossier)
    if (
        license_provenance.get("pinned_revision") != PIN
        or license_provenance.get("git_blob_sha") != license_queued.get("blob_sha")
        or license_queued.get("evidence_sha256") != license_dossier_sha256
    ):
        findings.append("pinned license notice dossier provenance mismatch")
    license_identity = {
        "path": license_record.get("pinned_notice_path"),
        "git_blob_sha1": license_queued.get("blob_sha"),
        "source_sha256": license_record.get("source_sha256"),
        "dossier_sha256": license_dossier_sha256,
        "priority": license_queued.get("priority"),
        "notice": license_record.get("notice"),
        "distribution_clearance": license_record.get("distribution_clearance"),
        "legal_determination": license_record.get("legal_determination"),
    }
    expected_license = {
        **LICENSE_IDENTITY,
        "path": "LICENSE.md",
        "notice": "GNU Lesser General Public License, version 3",
        "distribution_clearance": "NEEDS_EVIDENCE",
        "legal_determination": False,
    }
    for key, value in expected_license.items():
        if license_identity.get(key) != value:
            findings.append("pinned license notice identity or status changed: %s" % key)

    triage = reference.get("triage", {}).get("blockers", [])
    original_rows = {
        row.get("id"): row for row in triage if isinstance(row, dict)
    }
    deltas = evidence.get("blocker_deltas", [])
    if [row.get("blocker_id") for row in deltas if isinstance(row, dict)] != list(
        BLOCKER_IDS
    ):
        findings.append("blocker delta scope must contain B021 and B020 exactly once")
    if len(deltas) != len(BLOCKER_IDS):
        findings.append("blocker delta count mismatch")
    for delta in deltas:
        if not isinstance(delta, dict):
            findings.append("blocker delta is malformed")
            continue
        blocker_id = delta.get("blocker_id")
        original = original_rows.get(blocker_id)
        if original is None:
            findings.append("%s original triage row is missing" % blocker_id)
            continue
        if delta.get("original_triage_row_sha256") != _canonical_sha256(original):
            findings.append("%s immutable triage fingerprint mismatch" % blocker_id)
        if delta.get("after") != "BLOCKED" or delta.get("resolved") is not False:
            findings.append("%s must remain BLOCKED and unresolved" % blocker_id)
    b021 = original_rows.get("B021", {})
    b020 = original_rows.get("B020", {})
    if (
        b021.get("category") != "unverified_workflow_id"
        or b021.get("pr_number") != 14
        or b020.get("category") != "stale_dependency_base"
        or b020.get("pr_number") != 14
    ):
        findings.append("selected blocker identities differ from immutable triage")
    delta_by_id = {
        row.get("blocker_id"): row for row in deltas if isinstance(row, dict)
    }
    b021_delta = delta_by_id.get("B021", {})
    b020_delta = delta_by_id.get("B020", {})
    if (
        not str(b021_delta.get("before", "")).startswith(
            "BLOCKED: required workflow ID unverified"
        )
        or "Workflow 398126932" not in b021_delta.get("evidence_delta", "")
        or "run-time base SHA" not in b021_delta.get("remaining_reason", "")
        or not str(b020_delta.get("before", "")).startswith(
            "BLOCKED: PR #14 base does not match"
        )
    ):
        findings.append("blocker before/evidence/remaining deltas changed")

    manifest_rows = {
        row.get("number"): row
        for row in reference.get("manifest", {}).get("pull_requests", [])
        if isinstance(row, dict)
    }
    manifest_14 = manifest_rows.get(14, {})
    live = evidence.get("live_pr_observations", {})
    pr14 = live.get("pr14", {})
    pr8 = live.get("dependency_pr8", {})
    expected_head = "618861ff17a4b9cfbb180f5531cf58d8414cbd03"
    expected_base = "b76a2b686d4acf4302b9dacfad28494660d9b5f9"
    if (
        (manifest_14.get("head") or {}).get("sha") != expected_head
        or (manifest_14.get("base") or {}).get("sha") != expected_base
        or manifest_14.get("observed_runs") != []
    ):
        findings.append("immutable PR #14 manifest identity or prior evidence changed")
    if (
        pr14.get("head_sha") != expected_head
        or pr14.get("base_sha") != expected_base
        or pr8.get("head_sha") != "dddd2fd27371eb8f45b36c0403ba8ed38f5b732a"
        or pr8.get("base_sha") != "03608155216b4f283fd92b7c5d795dd066698244"
    ):
        findings.append("live PR observations do not match captured public metadata")
    if pr14.get("base_sha") == pr8.get("head_sha"):
        findings.append("stale PR #14 dependency base was incorrectly cleared")

    workflow = evidence.get("workflow_observation", {})
    if (
        workflow.get("workflow_id") != 398126932
        or workflow.get("workflow_name") != "Phase 1 pinned Porymap Qt writer failure boundary"
        or workflow.get("workflow_path")
        != ".github/workflows/phase1-porymap-qt-writer-failure.yml"
        or set(workflow.get("configured_events", []))
        != {"push", "pull_request", "workflow_dispatch"}
    ):
        findings.append("workflow identity or configured events mismatch")
    runs = workflow.get("required_runs", [])
    if not isinstance(runs, list) or len(runs) != len(RUNS):
        findings.append("both exact-head push and pull_request runs are required")
        runs = runs if isinstance(runs, list) else []
    seen_runs = set()
    for run in runs:
        if not isinstance(run, dict):
            findings.append("workflow run record is malformed")
            continue
        run_id = run.get("run_id")
        expected = RUNS.get(run_id)
        if expected is None or run_id in seen_runs:
            findings.append("workflow run ID is invented, unexpected, or duplicated")
            continue
        seen_runs.add(run_id)
        if (
            run.get("attempt") != expected["attempt"]
            or run.get("event") != expected["event"]
            or run.get("head_sha") != expected_head
            or run.get("conclusion") != "success"
            or run.get("job_count") != 1
            or run.get("job_count") != 1
            or run.get("job_id") != expected["job_id"]
            or run.get("job_name") != expected["job_name"]
            or run.get("job_conclusion") != "success"
            or run.get("step_count") != 10
            or run.get("successful_step_count") != 10
            or run.get("critical_steps") != CRITICAL_STEPS
        ):
            findings.append("%s run head/event/job/step evidence mismatch" % run_id)
        base_provenance = (
            "not_applicable_to_push_event"
            if expected["event"] == "push"
            else "unavailable_actions_api"
        )
        if run.get("base_provenance") != base_provenance:
            findings.append("%s run-time base provenance was altered" % run_id)
        if not isinstance(run.get("url"), str) or not run["url"].endswith(
            "/actions/runs/%s" % run_id
        ):
            findings.append("%s evidence URL is missing or mismatched" % run_id)
    if seen_runs != set(RUNS):
        findings.append("required exact-head run evidence is incomplete")

    source_trace = evidence.get("source_trace", {})
    packet = source_trace.get("existing_packet", {})
    if (
        packet.get("pr_number") != 14
        or packet.get("head_sha") != expected_head
        or {
            key: packet.get(key) for key in SOURCE_PACKET_BLOBS
        } != SOURCE_PACKET_BLOBS
    ):
        findings.append("existing source packet identity changed")
    analysis = source_trace.get("caller_and_build_analysis", {})
    if (
        not str(analysis.get("whole_file_analysis", "")).startswith("NOT_COMPLETE")
        or analysis.get("independent_whole_file_approvals") != 0
        or not analysis.get("caller_chain")
        or "NEEDS_EVIDENCE"
        not in license_record.get("distribution_clearance", "")
    ):
        findings.append("source coverage or evidence limitations were promoted")

    phase1 = evidence.get("phase1", {})
    if (
        phase1.get("gate") != "FAIL_INCOMPLETE"
        or phase1.get("p0_candidates") != 338
        or phase1.get("p0_approved") != 0
        or phase1.get("total_dispositions") != 14834
        or phase1.get("approved_dispositions") != 0
        or phase1.get("source_pins_changed") is not False
        or phase1.get("semantic_approval_from_ci_or_source_scans") is not False
    ):
        findings.append("Phase 1 gate, approval totals, or source pins were promoted")
    return sorted(set(findings))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE_PATH)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        reference = load_reference(args.root)
        findings = validate_reconciliation(evidence, reference)
    except (OSError, ValueError, KeyError, TypeError) as error:
        findings = ["unable to load B021 reconciliation evidence: %s" % error]
    report = {
        "evidence_validation": "INVALID" if findings else "VALID_NOT_APPROVED",
        "selected_blockers": ["B021", "B020"],
        "selected_blocker_statuses": {"B021": "BLOCKED", "B020": "BLOCKED"},
        "selected_resolved_count": 0,
        "workflow_id_dimension_verified_count": 1 if not findings else 0,
        "phase1_gate": "FAIL_INCOMPLETE",
        "approved_dispositions": 0,
        "findings": findings,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
