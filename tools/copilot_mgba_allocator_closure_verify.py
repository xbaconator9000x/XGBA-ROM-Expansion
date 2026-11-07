#!/usr/bin/env python3
"""Verify the bounded pinned allocator/source-only savedata closure."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import copilot_mgba_cross_tranche_matrix_verify as matrix_verify

RECORD = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata/"
    "allocator-source-closure.json"
)
RECORD_SHA256 = "ac6f02bd8efb9434eaf2025aa0559ec572af33347fbb14e80ec7aae19b230ca0"
PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
MATRIX_SHA256 = "f7ce0e81169b6b4a3724e7d0d8385ad6bd80b3f2c50e3a5243402fafecd0d084"
EXPECTED_PATHS = {
    "src/util/memory.c",
    "src/util/CMakeLists.txt",
    "include/mgba-util/memory.h",
    "src/util/vfs/vfs-mem.c",
    "src/gba/core.c",
}
EXPECTED_CONTROLS = [
    "source-revision-mismatch",
    "source-blob-mismatch",
    "source-byte-sha256-mismatch",
    "dossier-row-mismatch",
    "line-citation-out-of-range",
    "license-notice-missing",
    "false-allocation-failure-test-claim",
    "platform-override-overclaim",
    "drop-runtime-obligation",
    "phase1-approval-promotion",
]


class Rejected(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Rejected(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def blob_sha1(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def load_dossier(path: Path) -> dict[str, tuple[str, str, str]]:
    raw = path.read_bytes()
    require(sha256(raw) == DOSSIER_SHA256, "machine dossier SHA-256 mismatch")
    require(blob_sha1(raw) == DOSSIER_BLOB, "machine dossier Git blob mismatch")
    result = {}
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            file_path = provenance.get("path")
            if (
                provenance.get("repository") == "mgba-emu/mgba"
                and provenance.get("pinned_revision") == PIN
                and file_path in EXPECTED_PATHS
            ):
                require(file_path not in result, f"duplicate dossier row: {file_path}")
                result[file_path] = (
                    sha256(canonical(row)),
                    provenance.get("git_blob_sha"),
                    provenance.get("source_content_sha256"),
                )
    require(set(result) == EXPECTED_PATHS, "pinned source dossier closure incomplete")
    return result


def validate(record: dict, matrix: dict, rows: dict, sources: dict[str, bytes]) -> None:
    require(record.get("schema") == "xgba.copilot.mgba_savedata_allocator_source_closure.v1",
            "record schema mismatch")
    review = record.get("review", {})
    require(
        review.get("pull_request") == 35
        and review.get("request_comment_id") == 6700566308
        and review.get("expected_parent_head") == "1112c64043d36ccc41d099ce4c8188779a53129a"
        and review.get("approval_eligible") is False
        and "not a distinct reviewer" in review.get("identity_limit", "")
        and "absent from the current checkout" in review.get("protocol_status", ""),
        "review attribution, protocol boundary, or scope mismatch",
    )
    pin = record.get("source_pin", {})
    require(
        pin.get("repository") == "mgba-emu/mgba"
        and pin.get("revision") == PIN
        and pin.get("cross_tranche_matrix_sha256") == MATRIX_SHA256
        and pin.get("dossier_sha256") == DOSSIER_SHA256
        and pin.get("dossier_git_blob_sha1") == DOSSIER_BLOB,
        "immutable source/dossier identity mismatch",
    )
    require(RECORD_SHA256 != "PENDING", "allocator closure record hash is not pinned")

    matrix_files = {item["path"]: item for item in matrix.get("file_dispositions", [])}
    memory_objection = next(
        (
            objection
            for item in matrix_files.values()
            for objection in item.get("objections", [])
            if objection.get("id") == "anonymous-memory-implementation"
        ),
        None,
    )
    receipt = record.get("objection_receipt", {})
    require(
        memory_objection is not None
        and memory_objection.get("disposition") == "NEEDS_EVIDENCE"
        and receipt.get("parent_matrix_objection_id") == "anonymous-memory-implementation"
        and receipt.get("supplemental_objection_id")
        == "default-os-memory-implementation-null-propagation"
        and receipt.get("disposition") == "RESOLVED_SOURCE_ONLY"
        and receipt.get("original_matrix_objection_remains_open") is True
        and receipt.get("claim_scope")
        == "Default OS-source implementation and mGBA VFileMemChunk allocation-result flow only.",
        "source-only receipt must not promote the protected matrix disposition",
    )

    catalog = record.get("source_files", [])
    by_path = {item.get("path"): item for item in catalog}
    require(len(by_path) == len(catalog) == len(EXPECTED_PATHS),
            "source catalog must cover five unique closure files")
    line_counts = {}
    for path, item in by_path.items():
        require(path in sources, f"pinned source missing: {path}")
        source = sources[path]
        line_count = len(source.decode("utf-8").splitlines())
        line_counts[path] = line_count
        notice_valid = (
            item.get("license_notice") == "NO_PER_FILE_NOTICE"
            and path == "src/util/CMakeLists.txt"
            and b"Mozilla Public" not in source[:800]
        ) or (
            item.get("license_notice") == "MPL-2.0"
            and b"Mozilla Public" in source[:800]
            and b"License, v. 2.0." in source[:800]
            and b"mozilla.org/MPL/2.0/" in source[:800]
        )
        require(
            item.get("git_blob_sha1") == blob_sha1(source) == rows[path][1]
            and item.get("source_sha256") == sha256(source) == rows[path][2]
            and item.get("dossier_row_sha256") == rows[path][0]
            and item.get("byte_length") == len(source)
            and item.get("line_count") == line_count
            and notice_valid,
            f"pinned source, dossier, or MPL notice mismatch: {path}",
        )

    citations = receipt.get("source_lines", []) + receipt.get("caller_lines", [])
    require(receipt.get("source_lines") and receipt.get("caller_lines"),
            "source/caller citations are incomplete")
    for citation in citations:
        match = re.fullmatch(r"(.+):([1-9][0-9]*)-([1-9][0-9]*)", citation)
        require(match is not None, f"invalid citation: {citation}")
        path, first, last = match.group(1), int(match.group(2)), int(match.group(3))
        require(path in line_counts and first <= last <= line_counts[path],
                f"citation outside verified source: {citation}")
    required_findings = (
        "calloc(1, size)",
        "returns a VFile even if the buffer allocation failed",
        "without a NULL check",
        "checks only whether VFileMemChunk returned a VFile",
    )
    finding = receipt.get("finding", "")
    require(all(text in finding for text in required_findings),
            "source finding no longer describes the verified allocation flow")
    limits = receipt.get("limitations", [])
    require(
        "not an observed crash" in receipt.get("caller_result_contract", "")
        and len(limits) >= 4
        and any("OS_SRC" in text for text in limits)
        and any("allocation-failure injection" in text and "NEEDS_EVIDENCE" in text
                for text in limits)
        and any("toPow2 overflow" in text for text in limits)
        and any("physical Flash" in text and "durability" in text for text in limits),
        "runtime/platform limitations missing or overclaimed",
    )

    evidence = receipt.get("test_evidence", {})
    require(
        evidence.get("native_test_source_sha256")
        == "233206a92473469d5ebcd74cdcdedaf6e49395cb67b0cbe19cb2d3a0e2fead18"
        and evidence.get("native_runtime_log_sha256")
        == "334addf291ce91cd7f2419b7dc8b4780b63825959ce28c8f13af3aa5c7e23000"
        and "no allocation-failure injection" in evidence.get("source_test_scope", ""),
        "native test provenance is incomplete or overclaims allocation testing",
    )
    edges = record.get("dependency_closure", [])
    require(len(edges) == 4, "allocator-to-savedata caller closure incomplete")
    for edge in edges:
        require(edge.get("from") in EXPECTED_PATHS
                and set(edge.get("to", [])) <= EXPECTED_PATHS
                and edge.get("to") and edge.get("contract"),
                "dependency edge outside verified closure")
    unresolved = record.get("unresolved_obligations", [])
    require(
        {item.get("id") for item in unresolved}
        == {
            "runtime-allocation-failure-injection",
            "platform-os-src-implementations",
            "memory-size-and-to-pow2-bounds",
            "combined-license-and-dependency-closure",
        }
        and all(item.get("disposition") == "NEEDS_EVIDENCE" and item.get("reason")
                for item in unresolved),
        "unresolved allocator, platform, size, or license obligation was lost",
    )
    license_boundary = record.get("license_boundary", {})
    require(
        "Four C/header files have explicit MPL-2.0 notices"
        in license_boundary.get("source_notices", "")
        and "no per-file license notice" in license_boundary.get("source_notices", "")
        and license_boundary.get("transitive_dependency_closure_complete") is False
        and license_boundary.get("combined_distribution_legal_conclusion") is False
        and license_boundary.get("disposition") == "NEEDS_EVIDENCE",
        "license boundary overclaimed",
    )
    ci = record.get("ci_provenance", {})
    require(
        ci.get("exact_parent_run_id") == 41997398570
        and ci.get("event") == "pull_request"
        and ci.get("head_sha") == "1112c64043d36ccc41d099ce4c8188779a53129a"
        and ci.get("run_attempt") == 2
        and ci.get("job_id") == 127160335121
        and ci.get("job_conclusion") == "success"
        and ci.get("receipt_verifier_step") == 15
        and ci.get("native_assertions") == 43
        and ci.get("savedata_assertions") == 9
        and ci.get("hazard_observations") == 4
        and ci.get("push_event_run_count") == 0
        and "not this new allocator receipt" in ci.get("limitations", ""),
        "CI evidence identity or claim limit mismatch",
    )
    require(
        record.get("phase1_state")
        == {
            "decision": "FAIL_INCOMPLETE",
            "p0_approved_before": 0,
            "p0_approved_after": 0,
            "approved_before": 0,
            "approved_after": 0,
            "phase2_started": False,
            "shared_gate_or_register_edited": False,
            "semantic_approval": False,
        },
        "Phase 1 / approval accounting invariant changed",
    )
    require(record.get("negative_control_inventory") == EXPECTED_CONTROLS,
            "negative control inventory mismatch")


def run_controls(record: dict, matrix: dict, rows: dict, sources: dict[str, bytes]) -> list[str]:
    passed = []

    def control(name: str, mutate_record=None, mutate_sources=None, mutate_matrix=None) -> None:
        candidate = copy.deepcopy(record)
        candidate_matrix = copy.deepcopy(matrix)
        candidate_rows = dict(rows)
        candidate_sources = dict(sources)
        if mutate_record:
            mutate_record(candidate)
        if mutate_sources:
            mutate_sources(candidate_sources)
        if mutate_matrix:
            mutate_matrix(candidate_matrix)
        try:
            validate(candidate, candidate_matrix, candidate_rows, candidate_sources)
        except Rejected:
            passed.append(name)
        else:
            raise Rejected(f"negative control accepted: {name}")

    control(EXPECTED_CONTROLS[0], lambda value: value["source_pin"].update(revision="0" * 40))
    control(EXPECTED_CONTROLS[1], lambda value: value["source_files"][0].update(git_blob_sha1="0" * 40))
    control(EXPECTED_CONTROLS[2], lambda value: value["source_files"][0].update(source_sha256="0" * 64))
    control(EXPECTED_CONTROLS[3], lambda value: value["source_files"][0].update(dossier_row_sha256="0" * 64))
    control(
        EXPECTED_CONTROLS[4],
        lambda value: value["objection_receipt"]["source_lines"].append(
            "src/util/memory.c:999-1000"
        ),
    )
    control(EXPECTED_CONTROLS[5], lambda value: value["source_files"][0].update(license_notice=""))
    control(
        EXPECTED_CONTROLS[6],
        lambda value: value["objection_receipt"]["test_evidence"].update(
            source_test_scope="A native allocation-failure injection passed."
        ),
    )
    control(
        EXPECTED_CONTROLS[7],
        lambda value: value["objection_receipt"].update(
            limitations=["All platform OS_SRC implementations are verified."]
        ),
    )
    control(EXPECTED_CONTROLS[8], lambda value: value["unresolved_obligations"].pop())
    control(
        EXPECTED_CONTROLS[9],
        lambda value: value["phase1_state"].update(
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
    checkout = args.checkout.resolve() if args.checkout else None
    require(checkout is not None or args.source_directory is not None,
            "provide a pinned checkout or individually fetched source directory")
    if checkout:
        require(
            subprocess.check_output(
                ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
            ).strip()
            == PIN,
            "mGBA checkout does not match immutable revision",
        )
    raw = (root / RECORD).read_bytes()
    require(sha256(raw) == RECORD_SHA256, "allocator closure record SHA-256 mismatch")
    record = json.loads(raw)
    matrix_raw, matrix = matrix_verify.read_json(root / matrix_verify.MATRIX)
    require(sha256(matrix_raw) == MATRIX_SHA256, "cross-tranche matrix hash mismatch")
    matrix_context = matrix_verify.load_context(root, checkout)
    rows = load_dossier(root / matrix_verify.DOSSIER)
    source_root = checkout if checkout else args.source_directory.resolve()
    sources = {
        item["path"]: (source_root / item["path"]).read_bytes()
        for item in record.get("source_files", [])
    }
    validate(record, matrix, rows, sources)
    rejected = run_controls(record, matrix, rows, sources) if args.self_test else []
    print(
        f"PASS allocator source closure: {len(sources)} pinned files; "
        f"source-only receipt retained in matrix as NEEDS_EVIDENCE; "
        f"{len(rejected)} negative controls rejected"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Rejected, matrix_verify.Rejected, OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"REJECTED: {error}")
