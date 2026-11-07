#!/usr/bin/env python3
"""Verify bounded pinned VFileMemChunk map/unmap evidence."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata/"
    "vfile-memchunk-unmap.json"
)
RECORD_SHA256 = "ef26ce0fda5c1213d2e4fc27bae467a6556612e134b4c6b0bcd988a0d62b64d7"
MATRIX = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata/"
    "cross-tranche-objection-matrix.json"
)
MATRIX_SHA256 = "f7ce0e81169b6b4a3724e7d0d8385ad6bd80b3f2c50e3a5243402fafecd0d084"
DOSSIER = Path("semantic-snapshots/current/candidate_review_dossiers.jsonl.gz")
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
TEST_SOURCE = Path("tests/mgba_vfile_memchunk_unmap.c")
BUILD_SOURCE = Path("tests/CMakeLists.txt")
EXPECTED_PATHS = {
    "src/util/vfs/vfs-mem.c",
    "src/util/memory.c",
    "include/mgba-util/vfs.h",
    "include/mgba-util/memory.h",
    "include/mgba-util/math.h",
    "include/mgba-util/common.h",
    "include/mgba-util/dllexports.h",
    "src/core/rewind.c",
}
EXPECTED_ASSERTIONS = [
    "constructor maps an owned copy of the four-byte seed",
    "mapping beyond the logical extent is rejected",
    "read after unmap preserves the mapped bytes",
    "writes remain available after unmap",
    "a fresh mapping exposes the post-unmap write",
    "close succeeds after unmap and leaves the caller seed unchanged",
]
EXPECTED_LOG = (
    "SCOPE unchanged pinned memory.c and vfs-mem.c; owned VFileMemChunk "
    "map/unmap round-trip; production rewind caller source-traced only\n"
    "PASS constructor maps an owned copy of the four-byte seed\n"
    "PASS mapping beyond the logical extent is rejected\n"
    "PASS read after unmap preserves the mapped bytes\n"
    "PASS writes remain available after unmap\n"
    "PASS a fresh mapping exposes the post-unmap write\n"
    "PASS close succeeds after unmap and leaves the caller seed unchanged\n"
    "SUMMARY assertions=6 failures=0\n"
)
EXPECTED_CONTROLS = [
    "pinned-revision-mismatch",
    "source-blob-mismatch",
    "source-byte-sha256-mismatch",
    "dossier-row-mismatch",
    "source-closure-incomplete",
    "test-source-hash-mismatch",
    "build-source-hash-mismatch",
    "native-log-assertion-mismatch",
    "false-rewind-caller-execution-claim",
    "false-gameplay-or-real-save-claim",
    "false-physical-flash-or-durability-claim",
    "license-boundary-overclaim",
    "phase1-approval-promotion",
    "source-mutation",
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
    require(
        sha256(raw) == DOSSIER_SHA256 and blob_sha1(raw) == DOSSIER_BLOB,
        "pinned dossier archive identity mismatch",
    )
    rows = {}
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
                require(path not in rows, f"duplicate dossier row: {path}")
                rows[path] = (
                    sha256(canonical(row)),
                    provenance.get("git_blob_sha"),
                    provenance.get("source_content_sha256"),
                )
    require(set(rows) == EXPECTED_PATHS, "pinned dossier closure incomplete")
    return rows


def validate(
    root: Path,
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
        record.get("schema") == "xgba.copilot.mgba_savedata_vfile_memchunk_unmap.v1",
        "record schema mismatch",
    )
    review = record.get("review", {})
    require(
        review.get("repository") == "xbaconator9000x/XGBA-ROM-Expansion"
        and review.get("pull_request") == 35
        and review.get("request_comment_id") == 6705696990
        and review.get("expected_parent_head")
        == "481bb26695180c1adb74b114097b2a070f672fa3"
        and review.get("approval_eligible") is False
        and "not an independent semantic approval" in review.get("identity_limit", ""),
        "review attribution or approval scope mismatch",
    )
    pin = record.get("source_pin", {})
    require(
        pin.get("repository") == "mgba-emu/mgba"
        and pin.get("revision") == PIN
        and pin.get("dossier_path") == str(DOSSIER)
        and pin.get("dossier_sha256") == DOSSIER_SHA256
        and pin.get("dossier_git_blob_sha1") == DOSSIER_BLOB
        and pin.get("parent_matrix_sha256") == MATRIX_SHA256,
        "source pin or dossier identity mismatch",
    )
    if checkout_revision is not None:
        require(checkout_revision == PIN, "source checkout revision mismatch")

    raw_matrix = (root / MATRIX).read_bytes()
    require(sha256(raw_matrix) == MATRIX_SHA256, "parent matrix hash mismatch")
    memory_row = next(
        (
            item
            for item in matrix.get("file_dispositions", [])
            if item.get("path") == "src/util/vfs/vfs-mem.c"
        ),
        None,
    )
    require(
        memory_row is not None
        and memory_row.get("git_blob_sha1")
        == "048194e2dd2d0b3b395a852d2092c694663c88a2"
        and memory_row.get("source_sha256")
        == "6b5951a0cd634d398a69ce57766298bd32d5e6410ee0aa4e8b8894c6aaa5829b"
        and any(
            item.get("id") == "memory-ownership-and-persistence"
            and item.get("disposition") == "RESOLVED_SOURCE_ONLY"
            for item in memory_row.get("objections", [])
        ),
        "parent matrix source identity or disposition mismatch",
    )

    path_info = record.get("fault_path", {})
    caller = path_info.get("production_caller", {})
    require(
        path_info.get("id") == "owned-vfilememchunk-map-unmap-round-trip"
        and "does not release or mutate" in path_info.get("source_contract", "")
        and "not mCore rewind execution" in path_info.get("finding", "")
        and caller.get("source") == "src/core/rewind.c:30-32,94-120"
        and caller.get("compiled_or_executed") is False
        and "calls unmap on each mapped region" in caller.get("contract", ""),
        "selected boundary or production caller scope mismatch",
    )

    catalog = record.get("source_files", [])
    by_path = {item.get("path"): item for item in catalog}
    require(
        len(by_path) == len(catalog) == len(EXPECTED_PATHS)
        and set(by_path) == EXPECTED_PATHS
        and set(sources) == EXPECTED_PATHS,
        "pinned source catalog or closure incomplete",
    )
    roles = {
        "src/util/vfs/vfs-mem.c": "compiled_translation_unit",
        "src/util/memory.c": "compiled_translation_unit",
        "include/mgba-util/vfs.h": "included_header",
        "include/mgba-util/memory.h": "included_header",
        "include/mgba-util/math.h": "included_header",
        "include/mgba-util/common.h": "included_header",
        "include/mgba-util/dllexports.h": "included_header",
        "src/core/rewind.c": "production_caller_source_traced_only",
    }
    for path, item in by_path.items():
        source = sources[path]
        require(
            item.get("git_blob_sha1") == blob_sha1(source)
            and item.get("source_sha256") == sha256(source)
            and item.get("license_notice") == "MPL-2.0"
            and item.get("build_role") == roles[path]
            and item.get("verdict") == "NEEDS_EVIDENCE"
            and b"Mozilla Public" in source
            and b"License, v. 2.0." in source,
            f"pinned source identity, license, or verdict mismatch: {path}",
        )
        require(
            rows.get(path)
            == (
                item.get("dossier_row_sha256"),
                item.get("git_blob_sha1"),
                item.get("source_sha256"),
            ),
            f"pinned dossier row mismatch: {path}",
        )

    require(
        sha256(test_source) == record["test_evidence"]["source_sha256"]
        and sha256(build_source) == record["test_evidence"]["build_sha256"],
        "test or build source SHA-256 mismatch",
    )
    evidence = record.get("test_evidence", {})
    limits = evidence.get("limits", {})
    require(
        evidence.get("execution_kind")
        == "PINNED_ORIGINAL_VFILE_MEMORY_SOURCES_NATIVE_HOST_TEST"
        and limits.get("seed_bytes") == 4
        and limits.get("production_rewind_caller_compiled_or_executed") is False
        and limits.get("full_mgba_runtime_executed") is False
        and limits.get("gameplay_or_real_save_executed") is False
        and limits.get("physical_flash_or_durability_tested") is False
        and limits.get("combined_distribution_license_conclusion") is False,
        "native scope, caller claim, or test limits overstate evidence",
    )
    require(
        evidence.get("assertions") == EXPECTED_ASSERTIONS
        and evidence.get("result")
        == "PASS_BOUNDED_OWNED_VFILEMEMCHUNK_MAP_UNMAP_CHARACTERIZATION"
        and evidence.get("local_log_sha256") == sha256(native_log)
        and native_log.decode("utf-8") == EXPECTED_LOG,
        "native log, assertions, or digest mismatch",
    )

    licensing = record.get("licensing", {})
    require(
        licensing.get("selected_source_notice")
        == "MPL-2.0 verified for all eight pinned original source/header files."
        and licensing.get("transitive_dependency_closure_complete") is False
        and licensing.get("combined_distribution_legal_conclusion") is False
        and licensing.get("disposition") == "NEEDS_EVIDENCE",
        "license boundary overclaim",
    )
    phase = record.get("phase1_state", {})
    require(
        phase.get("decision") == "FAIL_INCOMPLETE"
        and phase.get("approved_before") == phase.get("approved_after") == 0
        and phase.get("shared_gate_or_register_edited") is False
        and phase.get("semantic_approval") is False
        and record.get("negative_control_inventory") == EXPECTED_CONTROLS,
        "Phase 1 protected-state or negative-control invariant mismatch",
    )


def run_controls(
    root: Path,
    record: dict,
    rows: dict[str, tuple[str, str, str]],
    sources: dict[str, bytes],
    matrix: dict,
    test_source: bytes,
    build_source: bytes,
    native_log: bytes,
) -> list[str]:
    passed = []

    def control(name: str, mutate_record=None, mutate_sources=None, log=None) -> None:
        candidate = copy.deepcopy(record)
        candidate_sources = dict(sources)
        if mutate_record:
            mutate_record(candidate)
        if mutate_sources:
            mutate_sources(candidate_sources)
        try:
            validate(
                root,
                candidate,
                rows,
                candidate_sources,
                matrix,
                test_source,
                build_source,
                native_log if log is None else log,
                PIN,
            )
        except (Rejected, KeyError, TypeError, IndexError, ValueError):
            passed.append(name)
        else:
            raise Rejected(f"negative control accepted: {name}")

    control(EXPECTED_CONTROLS[0], lambda value: value["source_pin"].update(revision="0" * 40))
    control(EXPECTED_CONTROLS[1], lambda value: value["source_files"][0].update(git_blob_sha1="0" * 40))
    control(EXPECTED_CONTROLS[2], lambda value: value["source_files"][0].update(source_sha256="0" * 64))
    control(EXPECTED_CONTROLS[3], lambda value: value["source_files"][0].update(dossier_row_sha256="0" * 64))
    control(EXPECTED_CONTROLS[4], lambda value: value["source_files"].pop())
    control(EXPECTED_CONTROLS[5], lambda value: value["test_evidence"].update(source_sha256="0" * 64))
    control(EXPECTED_CONTROLS[6], lambda value: value["test_evidence"].update(build_sha256="0" * 64))
    control(EXPECTED_CONTROLS[7], log=native_log.replace(b"PASS read after unmap", b"SKIP read after unmap"))
    control(EXPECTED_CONTROLS[8], lambda value: value["test_evidence"]["limits"].update(production_rewind_caller_compiled_or_executed=True))
    control(EXPECTED_CONTROLS[9], lambda value: value["test_evidence"]["limits"].update(gameplay_or_real_save_executed=True))
    control(EXPECTED_CONTROLS[10], lambda value: value["test_evidence"]["limits"].update(physical_flash_or_durability_tested=True))
    control(EXPECTED_CONTROLS[11], lambda value: value["licensing"].update(combined_distribution_legal_conclusion=True))
    control(
        EXPECTED_CONTROLS[12],
        lambda value: value["phase1_state"].update(
            {"decision": "PASS", "approved_after": 1, "semantic_approval": True}
        ),
    )
    control(
        EXPECTED_CONTROLS[13],
        mutate_sources=lambda value: value.update(
            {"src/util/vfs/vfs-mem.c": value["src/util/vfs/vfs-mem.c"] + b"\n"}
        ),
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
    require(
        checkout is not None or source_directory is not None,
        "provide a pinned checkout or individually fetched source directory",
    )
    revision = None
    if checkout:
        revision = subprocess.check_output(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
        ).strip()
    raw_record = (root / RECORD).read_bytes()
    require(
        RECORD_SHA256 != "PENDING" and sha256(raw_record) == RECORD_SHA256,
        "record SHA-256 mismatch",
    )
    record = json.loads(raw_record)
    rows = load_dossier(root)
    raw_matrix = (root / MATRIX).read_bytes()
    require(sha256(raw_matrix) == MATRIX_SHA256, "parent matrix SHA-256 mismatch")
    matrix = json.loads(raw_matrix)
    source_root = checkout or source_directory
    assert source_root is not None
    sources = {path: (source_root / path).read_bytes() for path in EXPECTED_PATHS}
    test_source = (root / TEST_SOURCE).read_bytes()
    build_source = (root / BUILD_SOURCE).read_bytes()
    native_log = args.native_log.read_bytes()
    validate(root, record, rows, sources, matrix, test_source, build_source, native_log, revision)
    controls = (
        run_controls(root, record, rows, sources, matrix, test_source, build_source, native_log)
        if args.self_test else []
    )
    require(not args.self_test or controls == EXPECTED_CONTROLS, "negative controls incomplete")
    print(f"PASS pinned unmap evidence: {len(EXPECTED_PATHS)} source files")
    print(f"PASS native-host map/unmap assertions: {len(EXPECTED_ASSERTIONS)}")
    if args.self_test:
        print(f"PASS negative controls rejected: {len(controls)}")
    print("NON_APPROVING Phase 1 remains FAIL_INCOMPLETE; approved count unchanged at zero")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Rejected, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"REJECTED: {error}")
