#!/usr/bin/env python3
"""Verify source-only objection receipts against the existing pinned review."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import copilot_mgba_cross_tranche_matrix_verify as matrix_verify

RECORD = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata/"
    "source-objection-receipts.json"
)
RECORD_SHA256 = "f8345bfd99798c84bd8a4f2b889d52e00ecce888f72bc257d0996b36c6dd31a0"
MATRIX_SHA256 = "f7ce0e81169b6b4a3724e7d0d8385ad6bd80b3f2c50e3a5243402fafecd0d084"
EXPECTED_RECEIPTS = {
    "fd-close-result",
    "fd-unmap-is-not-a-durability-result",
    "memory-ownership-and-persistence",
    "stdio-flush-close-and-short-io",
    "backend-selection-and-count-contract",
    "savedata-read-write-and-teardown-sinks",
    "unload-close-and-callback-separation",
    "core-savedata-return-sinks",
    "script-state-and-callback-result-contract",
    "callback-documentation-is-not-persistence",
    "vfile-return-type-contract",
    "mcore-api-return-contract",
    "gba-destroy-return-contract",
    "savedata-layout-and-api",
    "dirty-state-is-not-sync-result",
}
EXPECTED_CONTROLS = [
    "receipt-source-byte-mutation",
    "receipt-source-digest-mismatch",
    "receipt-dossier-row-mismatch",
    "receipt-incomplete-citation",
    "receipt-unlicensed-file",
    "receipt-unexpected-objection",
    "receipt-promote-disposition",
    "receipt-native-gameplay-overclaim",
    "receipt-drop-unresolved-objection",
    "receipt-phase1-promotion",
]


class Rejected(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Rejected(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(checkout: Path, *args: str) -> str:
    import subprocess

    return subprocess.check_output(
        ["git", "-C", str(checkout), *args], text=True
    ).strip()


def citation_lines(citation: str, available: set[str], counts: dict[str, int]) -> None:
    match = re.fullmatch(r"(.+):([1-9][0-9]*)-([1-9][0-9]*)", citation)
    require(match is not None, f"invalid source citation: {citation}")
    path, start, end = match.group(1), int(match.group(2)), int(match.group(3))
    require(path in available and start <= end <= counts[path],
            f"citation outside verified source closure: {citation}")


def validate(record: dict, matrix_context, source_bytes=None) -> None:
    matrix, base, original_files, fd, lifecycle, final, review, gate, rows, pinned_sources = matrix_context
    matrix_verify.validate(
        matrix, base, original_files, fd, lifecycle, final, review, gate, rows, pinned_sources
    )
    source_bytes = source_bytes if source_bytes is not None else pinned_sources
    require(source_bytes is not None, "pinned sources or a verified source cache are required")
    require(record.get("schema") == "xgba.copilot.mgba_savedata_source_objection_receipts.v1",
            "receipt schema mismatch")
    review_meta = record.get("review", {})
    require(
        review_meta.get("pull_request") == 35
        and review_meta.get("request_comment_id") == 6653540662
        and review_meta.get("expected_parent_head") == "88fffdf44c5c452abf6119f0ac0e7278d1704afc"
        and review_meta.get("approval_eligible") is False
        and review_meta.get("source_census_repeated") is False
        and "not a distinct reviewer" in review_meta.get("identity_limit", ""),
        "review attribution or scope widened",
    )
    pin = record.get("source_pin", {})
    require(
        pin.get("repository") == "mgba-emu/mgba"
        and pin.get("revision") == matrix_verify.PIN
        and pin.get("matrix_sha256") == MATRIX_SHA256
        and pin.get("dossier_sha256") == matrix_verify.DOSSIER_SHA256
        and pin.get("dossier_git_blob_sha1") == matrix_verify.DOSSIER_BLOB
        and pin.get("original_inventory_sha256") == matrix_verify.BASE_SHA256,
        "pinned source/matrix/dossier identity mismatch",
    )
    require(RECORD_SHA256 != "PENDING", "receipt digest is not pinned in verifier")

    disposition_by_path = {item["path"]: item for item in matrix["file_dispositions"]}
    catalog = record.get("source_files", [])
    catalog_by_path = {item.get("path"): item for item in catalog}
    require(len(catalog) == 14 and len(catalog_by_path) == 14,
            "receipt source catalog must contain exactly 14 unique files")
    counts = {}
    for path, item in catalog_by_path.items():
        require(path in disposition_by_path and path in source_bytes,
                f"source not in pinned 20-file closure: {path}")
        source = source_bytes[path]
        original = disposition_by_path[path]
        row = rows[path]
        line_count = len(source.decode("utf-8").splitlines())
        require(
            item.get("git_blob_sha1") == original.get("git_blob_sha1") == row[1]
            and item.get("source_sha256") == original.get("source_sha256") == row[2]
            and item.get("dossier_row_sha256") == row[0]
            and item.get("byte_length") == len(source)
            and item.get("line_count") == line_count
            and item.get("license_notice") == original.get("license_notice") == "MPL-2.0"
            and item.get("license_notice_checked_first_bytes") == 800
            and b"Mozilla Public" in source[:800]
            and b"License, v. 2.0." in source[:800]
            and b"mozilla.org/MPL/2.0/" in source[:800],
            f"pinned file, dossier row, full-byte, or license identity mismatch: {path}",
        )
        counts[path] = line_count

    receipts = record.get("objection_receipts", [])
    receipt_ids = {item.get("receipt_id") for item in receipts}
    expected_source_only = {
        objection["id"]
        for item in matrix["file_dispositions"]
        for objection in item["objections"]
        if objection["disposition"] == "RESOLVED_SOURCE_ONLY"
    }
    require(receipt_ids == EXPECTED_RECEIPTS == expected_source_only,
            "receipt set is incomplete, unexpected, or differs from source-only matrix objections")
    for item in receipts:
        path = item.get("source_path")
        require(
            path in catalog_by_path
            and item.get("matrix_objection_id") == item.get("receipt_id")
            and item.get("disposition") == "RESOLVED_SOURCE_ONLY"
            and item.get("evidence")
            and item.get("limitation")
            and item.get("caller_sink"),
            f"incomplete or non-source-only receipt: {item.get('receipt_id')}",
        )
        evidence_claim = item["evidence"].casefold()
        require(
            not any(
                phrase in evidence_claim
                for phrase in ("physical", "gameplay", "cold restart", "durable", "approved")
            ),
            f"receipt evidence makes a runtime or approval claim: {item['receipt_id']}",
        )
        matrix_file = disposition_by_path[path]
        matrix_objections = {entry["id"]: entry for entry in matrix_file["objections"]}
        require(
            matrix_objections.get(item["receipt_id"], {}).get("disposition")
            == "RESOLVED_SOURCE_ONLY",
            f"receipt attempts to resolve unsupported matrix objection: {item['receipt_id']}",
        )
        citations = item.get("source_lines", []) + item["caller_sink"]
        require(item.get("source_lines") and item["caller_sink"],
                f"missing source or caller citation: {item['receipt_id']}")
        for citation in citations:
            citation_lines(citation, set(counts), counts)
        require(any(ref.startswith(path + ":") for ref in item["source_lines"]),
                f"receipt has no citation to its own file: {item['receipt_id']}")

    unresolved = record.get("unresolved_objections", [])
    expected_open = {
        objection["id"]: objection
        for item in matrix["file_dispositions"]
        for objection in item["objections"]
        if objection["disposition"] == "NEEDS_EVIDENCE"
    }
    unresolved_by_id = {item.get("matrix_objection_id"): item for item in unresolved}
    require(
        set(unresolved_by_id) == set(expected_open)
        and len(unresolved_by_id) == len(unresolved)
        and all(item.get("disposition") == "NEEDS_EVIDENCE" and item.get("reason")
                for item in unresolved),
        "unresolved obligations were dropped, duplicated, or promoted",
    )
    for objection_id, item in unresolved_by_id.items():
        require(expected_open[objection_id]["disposition"] == item["disposition"],
                f"open matrix objection changed: {objection_id}")

    license_boundary = record.get("license_boundary", {})
    require(
        license_boundary.get("all_receipted_source_files_notice") == "MPL-2.0"
        and license_boundary.get("transitive_dependency_closure_complete") is False
        and license_boundary.get("combined_distribution_legal_conclusion") is False
        and license_boundary.get("license_disposition") == "NEEDS_EVIDENCE",
        "license coverage or conclusion overclaimed",
    )
    phase = record.get("phase1_state", {})
    require(
        phase == {
            "decision": "FAIL_INCOMPLETE",
            "p0_approved_before": 0,
            "p0_approved_after": 0,
            "approved_before": 0,
            "approved_after": 0,
            "phase2_started": False,
            "shared_gate_or_register_edited": False,
            "semantic_approval": False,
        },
        "Phase 1 or approval invariant changed",
    )
    policy = record.get("receipt_policy", {})
    require(
        policy.get("supported_disposition") == "RESOLVED_SOURCE_ONLY"
        and policy.get("unsupported_disposition") == "NEEDS_EVIDENCE"
        and policy.get("APPROVED") is False
        and policy.get("COPILOT_REVIEWED/PASSED") is False
        and policy.get("source_only_is_semantic_approval") is False
        and policy.get("workflow_is_reviewer") is False,
        "approval policy was widened",
    )
    require(record.get("negative_control_inventory") == EXPECTED_CONTROLS,
            "negative-control inventory mismatch")
    provenance = record.get("test_provenance", {})
    parent_run = provenance.get("pr35_parent_workflow", {})
    push = provenance.get("push_coverage", {})
    require(
        provenance.get("pr13_host_workpapers", {}).get("status")
        == "HISTORICAL_WORKPAPER_REPORTED_NOT_REPRODUCED"
        and provenance["pr13_host_workpapers"].get("fixture_sources_present_in_checkout") is False
        and parent_run.get("run_id") == 41963795822
        and parent_run.get("run_attempt") == 2
        and parent_run.get("job_id") == 127105016383
        and parent_run.get("event") == "pull_request"
        and parent_run.get("head_sha") == "88fffdf44c5c452abf6119f0ac0e7278d1704afc"
        and parent_run.get("conclusion") == "success"
        and parent_run.get("verified_workflow_steps") == 14
        and parent_run.get("native_assertions") == 43
        and parent_run.get("savedata_assertions") == 9
        and parent_run.get("hazard_observations") == 4
        and parent_run.get("artifact_id") == 13396110926
        and parent_run.get("artifact_zip_sha256")
        == "03ec55b9441edf17a54d8cea6c0d284fb09e9501130a65ffa17799d10891e621"
        and "not this receipt change" in parent_run.get("limits", "")
        and push.get("event") == "push"
        and push.get("run_count") == 0
        and provenance.get("new_receipt_test_claim")
        == "Exact-head PR run 41997123172 is action_required with zero jobs; no receipt verifier or native tests executed.",
        "test provenance is missing or overclaims PR13/PR35 execution",
    )


def verify_workflow(root: Path) -> None:
    text = (root / matrix_verify.WORKFLOW).read_text(encoding="utf-8")
    pull_request = text.split("workflow_dispatch:", 1)[0]
    script = "tools/copilot_mgba_source_objection_receipts_verify.py"
    require(
        script in pull_request
        and script in text
        and "--checkout upstream/mgba" in text
        and "--self-test" in text,
        "existing scoped PR workflow does not select and execute the receipt verifier",
    )


def run_controls(record: dict, matrix_context, source_bytes=None) -> list[str]:
    passed = []
    source_bytes = source_bytes if source_bytes is not None else matrix_context[-1]

    def control(name: str, mutate_record=None, mutate_sources=None) -> None:
        candidate = copy.deepcopy(record)
        context = matrix_context
        candidate_sources = dict(source_bytes)
        if mutate_record:
            mutate_record(candidate)
        if mutate_sources:
            mutate_sources(candidate_sources)
        try:
            validate(candidate, context, candidate_sources)
        except (Rejected, matrix_verify.Rejected):
            passed.append(name)
        else:
            raise Rejected(f"negative control accepted: {name}")

    control(
        EXPECTED_CONTROLS[0],
        mutate_sources=lambda sources: sources.__setitem__(
            "src/gba/savedata.c", sources["src/gba/savedata.c"] + b"\n"
        ),
    )
    control(
        EXPECTED_CONTROLS[1],
        mutate_record=lambda value: value["source_files"][0].update(source_sha256="0" * 64),
    )
    control(
        EXPECTED_CONTROLS[2],
        mutate_record=lambda value: value["source_files"][0].update(dossier_row_sha256="0" * 64),
    )
    control(
        EXPECTED_CONTROLS[3],
        mutate_record=lambda value: value["objection_receipts"][0].update(source_lines=[]),
    )
    control(
        EXPECTED_CONTROLS[4],
        mutate_record=lambda value: value["source_files"][0].update(license_notice=""),
    )
    control(
        EXPECTED_CONTROLS[5],
        mutate_record=lambda value: value["objection_receipts"][0].update(
            matrix_objection_id="unreviewed-objection"
        ),
    )
    control(
        EXPECTED_CONTROLS[6],
        mutate_record=lambda value: value["objection_receipts"][0].update(
            disposition="COPILOT_REVIEWED/PASSED"
        ),
    )
    control(
        EXPECTED_CONTROLS[7],
        mutate_record=lambda value: value["objection_receipts"][0].update(
            evidence="The physical game and Flash were validated."
        ),
    )
    control(
        EXPECTED_CONTROLS[8],
        mutate_record=lambda value: value["unresolved_objections"].pop(),
    )
    control(
        EXPECTED_CONTROLS[9],
        mutate_record=lambda value: value["phase1_state"].update(
            {"decision": "PASS", "approved_after": 1, "phase2_started": True}
        ),
    )
    return passed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--checkout", type=Path)
    parser.add_argument("--source-directory", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    record_path = root / RECORD
    raw = record_path.read_bytes()
    require(sha256(raw) == RECORD_SHA256, "receipt record SHA-256 mismatch")
    record = json.loads(raw)
    checkout = args.checkout.resolve() if args.checkout else None
    if checkout:
        require(git(checkout, "rev-parse", "HEAD") == matrix_verify.PIN,
                "mGBA checkout does not match immutable revision")
    context = matrix_verify.load_context(root, checkout)
    sources = context[-1]
    if args.source_directory:
        source_root = args.source_directory.resolve()
        catalog = json.loads(raw).get("source_files", [])
        sources = {item["path"]: (source_root / item["path"]).read_bytes() for item in catalog}
    matrix_verify.verify_workflow(root)
    verify_workflow(root)
    validate(record, context, sources)
    rejected = run_controls(record, context, sources) if args.self_test else []
    print(
        f"PASS source objection receipts: {len(record['objection_receipts'])} source-only "
        f"objections across {len(record['source_files'])} pinned files; "
        f"{len(record['unresolved_objections'])} remain NEEDS_EVIDENCE; "
        f"{len(rejected)} negative controls rejected"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Rejected, matrix_verify.Rejected, OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"REJECTED: {error}")
