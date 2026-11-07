#!/usr/bin/env python3
"""Verify the bounded pinned VFile wrapper-allocation failure witness."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata/"
    "vfile-wrapper-allocation-failure.json"
)
RECORD_SHA256 = "0553796b2f70ab73e0e2ac0edf3c316d2f7e383766e102062b4bb3e4c941b75c"
MATRIX = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata/"
    "cross-tranche-objection-matrix.json"
)
MATRIX_SHA256 = "f7ce0e81169b6b4a3724e7d0d8385ad6bd80b3f2c50e3a5243402fafecd0d084"
DOSSIER = Path("semantic-snapshots/current/candidate_review_dossiers.jsonl.gz")
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
TEST_SOURCE = Path("tests/mgba_vfile_wrapper_alloc_failure.c")
BUILD_SOURCE = Path("tests/CMakeLists.txt")
EXPECTED_PATHS = {
    "src/util/vfs/vfs-mem.c",
    "src/util/memory.c",
    "include/mgba-util/vfs.h",
    "include/mgba-util/memory.h",
    "include/mgba-util/math.h",
    "include/mgba-util/common.h",
    "include/mgba-util/dllexports.h",
    "src/gba/core.c",
}
EXPECTED_OBLIGATIONS = {
    "gba-restore-caller-execution",
    "caller-consumption-and-logs",
    "full-size-domain-and-platform",
    "savedata-state-and-teardown",
    "license-and-transitive-dependencies",
}
EXPECTED_CONTROLS = [
    "source-revision-mismatch",
    "source-blob-mismatch",
    "source-byte-sha256-mismatch",
    "dossier-row-mismatch",
    "source-closure-incomplete",
    "test-source-hash-mismatch",
    "build-source-hash-mismatch",
    "native-log-hash-or-assertion-mismatch",
    "false-gba-caller-runtime-claim",
    "false-full-emulator-or-gameplay-label",
    "allocation-bound-overclaim",
    "missing-unresolved-teardown-obligation",
    "license-boundary-overclaim",
    "phase1-approval-promotion",
    "source-byte-mutation",
    "parent-matrix-objection-promotion",
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


def load_dossier(root: Path) -> dict[str, tuple[str, str, str]]:
    raw = (root / DOSSIER).read_bytes()
    require(sha256(raw) == DOSSIER_SHA256, "original dossier SHA-256 mismatch")
    require(blob_sha1(raw) == DOSSIER_BLOB, "original dossier Git blob mismatch")
    result = {}
    with gzip.open(root / DOSSIER, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            path = provenance.get("path")
            if (
                provenance.get("repository") == "mgba-emu/mgba"
                and provenance.get("pinned_revision") == PIN
                and path in EXPECTED_PATHS
            ):
                require(path not in result, f"duplicate dossier row: {path}")
                result[path] = (
                    sha256(canonical(row)),
                    provenance.get("git_blob_sha"),
                    provenance.get("source_content_sha256"),
                )
    require(set(result) == EXPECTED_PATHS, "original dossier source closure incomplete")
    return result


def validate(
    record: dict,
    rows: dict[str, tuple[str, str, str]],
    sources: dict[str, bytes],
    matrix: dict,
    test_source: bytes,
    build_source: bytes,
    native_log: bytes,
    checkout_revision: str | None,
) -> None:
    require(
        record.get("schema") == "xgba.copilot.mgba_savedata_vfile_wrapper_alloc_failure.v1",
        "record schema mismatch",
    )
    review = record.get("review", {})
    require(
        review.get("repository") == "xbaconator9000x/XGBA-ROM-Expansion"
        and review.get("pull_request") == 35
        and review.get("request_comment_id") == 6701750871
        and review.get("expected_parent_head")
        == "aedca8d3f82ea920fadac3574169d6772662e2ba"
        and review.get("approval_eligible") is False
        and "not independent semantic approval" in review.get("identity_limit", ""),
        "review attribution or approval scope mismatch",
    )
    pin = record.get("source_pin", {})
    require(
        pin.get("repository") == "mgba-emu/mgba"
        and pin.get("revision") == PIN
        and pin.get("dossier_path") == str(DOSSIER)
        and pin.get("dossier_sha256") == DOSSIER_SHA256
        and pin.get("dossier_git_blob_sha1") == DOSSIER_BLOB,
        "immutable source/dossier identity mismatch",
    )
    if checkout_revision is not None:
        require(checkout_revision == PIN, "mGBA checkout does not match immutable revision")

    overlap = record.get("overlap_check", {})
    require(
        overlap.get("pr13_head") == "032fb33971d9b7f4416e00fcb8a2c4f52bec39c0"
        and overlap.get("pr13_changed_files_reviewed") is True
        and "no malloc-failure injection" in overlap.get("pr13_allocation_failure_overlap", "")
        and overlap.get("pr37_head") == "ad648943bca6794665c7ccc4c77bb2b740c6ddd2"
        and overlap.get("pr37_changed_files_reviewed") is True
        and "no savedata VFile allocation-failure witness"
        in overlap.get("pr37_allocation_failure_overlap", ""),
        "PR #13/#37 overlap evidence missing or overstated",
    )

    binding = record.get("matrix_binding", {})
    require(
        binding.get("path") == str(MATRIX)
        and binding.get("sha256") == MATRIX_SHA256
        and binding.get("objection_id") == "memory-allocation-and-size-bounds"
        and binding.get("source_path") == "src/util/vfs/vfs-mem.c"
        and binding.get("disposition_before") == "NEEDS_EVIDENCE"
        and binding.get("disposition_after") == "NEEDS_EVIDENCE",
        "parent matrix binding must retain NEEDS_EVIDENCE",
    )
    target_objection = next(
        (
            objection
            for entry in matrix.get("file_dispositions", [])
            if entry.get("path") == "src/util/vfs/vfs-mem.c"
            for objection in entry.get("objections", [])
            if objection.get("id") == "memory-allocation-and-size-bounds"
        ),
        None,
    )
    require(
        target_objection is not None
        and target_objection.get("disposition") == "NEEDS_EVIDENCE",
        "parent objection was altered or promoted",
    )

    catalog = record.get("source_files", [])
    by_path = {item.get("path"): item for item in catalog}
    require(
        len(by_path) == len(catalog) == len(EXPECTED_PATHS)
        and set(by_path) == EXPECTED_PATHS
        and set(sources) == EXPECTED_PATHS,
        "source catalog or supplied source closure is incomplete",
    )
    for path, item in by_path.items():
        source = sources[path]
        text = source.decode("utf-8")
        require(
            item.get("git_blob_sha1") == blob_sha1(source)
            and item.get("source_sha256") == sha256(source)
            and item.get("license_notice") == "MPL-2.0"
            and b"Mozilla Public" in source
            and b"License, v. 2.0." in source,
            f"pinned source identity/license mismatch: {path}",
        )
        require(
            item.get("verdict") == "NEEDS_EVIDENCE"
            and "not a whole-file semantic review" in item.get("review_scope", ""),
            f"source review scope/verdict overclaim: {path}",
        )
        require(
            rows.get(path)
            == (
                item.get("dossier_row_sha256"),
                item.get("git_blob_sha1"),
                item.get("source_sha256"),
            ),
            f"original dossier row mismatch: {path}",
        )
        line_count = len(text.splitlines())
        for citation in item.get("source_lines", []):
            match = re.fullmatch(r"(.+):(\d+)-(\d+)", citation)
            require(
                match is not None and match.group(1) == path,
                f"bad source citation: {citation}",
            )
            first, last = int(match.group(2)), int(match.group(3))
            require(1 <= first <= last <= line_count, f"citation out of range: {citation}")

    fault = record.get("fault_path", {})
    require(
        fault.get("id") == "vfilememchunk-wrapper-malloc-failure"
        and fault.get("parent_matrix_objection_id") == "memory-allocation-and-size-bounds"
        and fault.get("parent_matrix_disposition_remains") == "NEEDS_EVIDENCE"
        and "fails the earlier wrapper malloc itself" in fault.get("distinction_from_prior_probe", "")
        and "returns false" in fault.get("source_contract", "")
        and "constructor-level cleanup only" in fault.get("ownership_and_teardown", ""),
        "fault path does not distinguish outer wrapper failure or caller scope",
    )
    closure = record.get("dependency_closure", {})
    nonexecuted = closure.get("nonexecuted_edges", [])
    require(
        closure.get("compiled_original_sources")
        == ["src/util/memory.c", "src/util/vfs/vfs-mem.c"]
        and closure.get("compiled_header_closure")
        == [
            "include/mgba-util/common.h",
            "include/mgba-util/dllexports.h",
            "include/mgba-util/math.h",
            "include/mgba-util/memory.h",
            "include/mgba-util/vfs.h",
        ]
        and closure.get("caller_edge", {}).get("from") == "src/gba/core.c:1493-1506"
        and len(nonexecuted) >= 3
        and "was source-traced, not compiled or called" in nonexecuted[0],
        "dependency/caller closure or nonexecution boundaries incomplete",
    )
    compiled = {item["path"] for item in catalog if item.get("compiled_unchanged") is True}
    require(
        compiled == {"src/util/memory.c", "src/util/vfs/vfs-mem.c"},
        "compiled original source claim mismatch",
    )

    evidence = record.get("test_evidence", {})
    require(
        sha256(test_source) == evidence.get("test_source_sha256")
        and sha256(build_source) == evidence.get("build_source_sha256"),
        "test or build source SHA-256 mismatch",
    )
    require(
        evidence.get("execution_kind")
        == "PINNED_ORIGINAL_VFILE_MEMORY_SOURCES_WITH_SYNTHETIC_LINKER_ALLOCATION_WRAPPERS"
        and evidence.get("limits", {}).get("max_wrapper_allocation_bytes") == 256
        and evidence.get("limits", {}).get("max_backing_allocation_bytes") == 8
        and evidence.get("limits", {}).get("gba_restore_executed") is False
        and evidence.get("limits", {}).get("full_mgba_runtime_executed") is False
        and evidence.get("limits", {}).get("actual_game_or_save_executed") is False
        and evidence.get("limits", {}).get("physical_flash_or_durability_tested") is False,
        "native scope, synthetic seam, or allocation bound overclaim",
    )
    require(
        sha256(native_log) == evidence.get("local_runtime_log_sha256"),
        "local native log SHA-256 mismatch",
    )
    log = native_log.decode("utf-8")
    require(
        log.count("\nPASS ") == 4
        and "\nFAIL " not in log
        and log.startswith("SCOPE original pinned memory.c and vfs-mem.c;")
        and log.endswith(
            "SUMMARY assertions=4 failures=0 max_wrapper_allocation=256 max_backing_allocation=8\n"
        ),
        "local runtime log contents or assertion count mismatch",
    )

    receipt = record.get("objection_receipt", {})
    obligations = {item.get("id"): item for item in receipt.get("unresolved_obligations", [])}
    require(
        receipt.get("disposition") == "RESOLVED_SOURCE_AND_BOUNDED_VFILE_TEST_ONLY"
        and set(obligations) == EXPECTED_OBLIGATIONS
        and all(item.get("disposition") == "NEEDS_EVIDENCE" for item in obligations.values()),
        "supplemental disposition or unresolved obligations were promoted/dropped",
    )
    license_boundary = record.get("license_boundary", {})
    require(
        license_boundary.get("transitive_dependency_closure_complete") is False
        and license_boundary.get("combined_distribution_legal_conclusion") is False
        and license_boundary.get("disposition") == "NEEDS_EVIDENCE",
        "license boundary overclaim",
    )
    phase = record.get("phase1_state", {})
    require(
        phase.get("decision") == "FAIL_INCOMPLETE"
        and phase.get("approved_before") == phase.get("approved_after") == 0
        and phase.get("phase2_started") is False
        and phase.get("shared_gate_or_register_edited") is False
        and phase.get("semantic_approval") is False,
        "Phase 1 protected-state invariant mismatch",
    )
    require(
        evidence.get("ci_provenance", {}).get("push_event_run_count") == 0
        and "ABSENT" in evidence.get("ci_provenance", {}).get("push_event_status", "")
        and record.get("negative_control_inventory") == EXPECTED_CONTROLS,
        "push event or mutation-control inventory was misrepresented",
    )


def run_controls(
    record: dict,
    rows: dict[str, tuple[str, str, str]],
    sources: dict[str, bytes],
    matrix: dict,
    test_source: bytes,
    build_source: bytes,
    native_log: bytes,
) -> list[str]:
    passed = []

    def control(
        name: str,
        mutate_record=None,
        mutate_sources=None,
        mutate_matrix=None,
        log=None,
    ) -> None:
        candidate = copy.deepcopy(record)
        candidate_sources = dict(sources)
        candidate_matrix = copy.deepcopy(matrix)
        if mutate_record:
            mutate_record(candidate)
        if mutate_sources:
            mutate_sources(candidate_sources)
        if mutate_matrix:
            mutate_matrix(candidate_matrix)
        try:
            validate(
                candidate,
                rows,
                candidate_sources,
                candidate_matrix,
                test_source,
                build_source,
                native_log if log is None else log,
                PIN,
            )
        except (Rejected, KeyError, TypeError):
            passed.append(name)
        else:
            raise Rejected(f"negative control accepted: {name}")

    control(EXPECTED_CONTROLS[0], lambda value: value["source_pin"].update(revision="0" * 40))
    control(EXPECTED_CONTROLS[1], lambda value: value["source_files"][0].update(git_blob_sha1="0" * 40))
    control(EXPECTED_CONTROLS[2], lambda value: value["source_files"][0].update(source_sha256="0" * 64))
    control(EXPECTED_CONTROLS[3], lambda value: value["source_files"][0].update(dossier_row_sha256="0" * 64))
    control(EXPECTED_CONTROLS[4], lambda value: value["source_files"].pop())
    control(EXPECTED_CONTROLS[5], lambda value: value["test_evidence"].update(test_source_sha256="0" * 64))
    control(EXPECTED_CONTROLS[6], lambda value: value["test_evidence"].update(build_source_sha256="0" * 64))
    control(EXPECTED_CONTROLS[7], log=native_log.replace(b"PASS positive constructor", b"SKIP positive constructor"))
    control(
        EXPECTED_CONTROLS[8],
        lambda value: value["dependency_closure"]["nonexecuted_edges"].__setitem__(
            0, "src/gba/core.c::_GBACoreSavedataRestore was compiled and called."
        ),
    )
    control(
        EXPECTED_CONTROLS[9],
        lambda value: value["test_evidence"]["limits"].update(full_mgba_runtime_executed=True),
    )
    control(
        EXPECTED_CONTROLS[10],
        lambda value: value["test_evidence"]["limits"].update(max_wrapper_allocation_bytes=2048),
    )
    control(
        EXPECTED_CONTROLS[11],
        lambda value: value["objection_receipt"]["unresolved_obligations"].pop(),
    )
    control(
        EXPECTED_CONTROLS[12],
        lambda value: value["license_boundary"].update(combined_distribution_legal_conclusion=True),
    )
    control(
        EXPECTED_CONTROLS[13],
        lambda value: value["phase1_state"].update(
            {"decision": "PASS", "approved_after": 1, "phase2_started": True}
        ),
    )
    control(
        EXPECTED_CONTROLS[14],
        mutate_sources=lambda value: value.update(
            {"src/util/vfs/vfs-mem.c": value["src/util/vfs/vfs-mem.c"] + b"\n"}
        ),
    )
    control(
        EXPECTED_CONTROLS[15],
        mutate_matrix=lambda value: next(
            objection
            for entry in value["file_dispositions"]
            if entry.get("path") == "src/util/vfs/vfs-mem.c"
            for objection in entry.get("objections", [])
            if objection.get("id") == "memory-allocation-and-size-bounds"
        ).update(disposition="RESOLVED_SOURCE_ONLY"),
    )
    return passed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--checkout", type=Path)
    parser.add_argument("--source-directory", type=Path)
    parser.add_argument("--native-log", type=Path, required=True)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    checkout = args.checkout.resolve() if args.checkout else None
    source_directory = args.source_directory.resolve() if args.source_directory else None
    require(checkout is not None or source_directory is not None,
            "provide a pinned checkout or individually fetched source directory")
    checkout_revision = None
    if checkout:
        checkout_revision = subprocess.check_output(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
        ).strip()
        require(checkout_revision == PIN, "mGBA checkout does not match immutable revision")

    record_raw = (root / RECORD).read_bytes()
    require(RECORD_SHA256 != "PENDING" and sha256(record_raw) == RECORD_SHA256,
            "wrapper-allocation record SHA-256 mismatch")
    record = json.loads(record_raw)
    rows = load_dossier(root)
    matrix_raw = (root / MATRIX).read_bytes()
    require(sha256(matrix_raw) == MATRIX_SHA256, "pinned parent matrix SHA-256 mismatch")
    matrix = json.loads(matrix_raw)
    source_root = checkout or source_directory
    assert source_root is not None
    sources = {path: (source_root / path).read_bytes() for path in EXPECTED_PATHS}
    test_source = (root / TEST_SOURCE).read_bytes()
    build_source = (root / BUILD_SOURCE).read_bytes()
    native_log = args.native_log.read_bytes()
    validate(record, rows, sources, matrix, test_source, build_source, native_log, checkout_revision)
    rejected = (
        run_controls(record, rows, sources, matrix, test_source, build_source, native_log)
        if args.self_test
        else []
    )
    print(
        f"PASS bounded VFile wrapper-allocation evidence: {len(sources)} pinned files; "
        f"4 local native assertions; parent objection remains NEEDS_EVIDENCE; "
        f"{len(rejected)} negative controls rejected"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Rejected, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"REJECTED: {error}")
