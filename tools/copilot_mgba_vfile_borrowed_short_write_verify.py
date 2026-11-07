#!/usr/bin/env python3
"""Verify bounded borrowed-memory VFile short-write evidence."""
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
    "vfile-borrowed-short-write.json"
)
RECORD_SHA256 = "d179bbb736dad3848bba25d01884606a4fffd481f06bfe93bb9793ebe1611860"
MATRIX = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata/"
    "cross-tranche-objection-matrix.json"
)
MATRIX_SHA256 = "f7ce0e81169b6b4a3724e7d0d8385ad6bd80b3f2c50e3a5243402fafecd0d084"
DOSSIER = Path("semantic-snapshots/current/candidate_review_dossiers.jsonl.gz")
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
TEST_SOURCE = Path("tests/mgba_vfile_borrowed_short_write.c")
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
EXPECTED_CONTROLS = [
    "pinned-revision-mismatch",
    "source-blob-mismatch",
    "source-byte-sha256-mismatch",
    "dossier-row-mismatch",
    "source-closure-incomplete",
    "test-source-hash-mismatch",
    "build-source-hash-mismatch",
    "native-log-assertion-mismatch",
    "false-gba-caller-execution-claim",
    "false-full-emulator-claim",
    "false-borrowed-buffer-ownership-claim",
    "unbounded-test-size",
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
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def load_dossier(root: Path) -> dict[str, tuple[str, str, str]]:
    raw = (root / DOSSIER).read_bytes()
    require(sha256(raw) == DOSSIER_SHA256, "dossier SHA-256 mismatch")
    require(blob_sha1(raw) == DOSSIER_BLOB, "dossier Git blob mismatch")
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
        record.get("schema")
        == "xgba.copilot.mgba_savedata_vfile_borrowed_short_write.v1",
        "record schema mismatch",
    )
    review = record.get("review", {})
    require(
        review.get("repository") == "xbaconator9000x/XGBA-ROM-Expansion"
        and review.get("pull_request") == 35
        and review.get("request_comment_id") == 6704045884
        and review.get("expected_parent_head")
        == "d4e26e193ab93b48e95379352521316adeadb272"
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
        and pin.get("dossier_git_blob_sha1") == DOSSIER_BLOB,
        "pinned source/dossier identity mismatch",
    )
    if checkout_revision is not None:
        require(checkout_revision == PIN, "source checkout revision mismatch")

    path_info = record.get("distinct_path", {})
    parent = path_info.get("parent_matrix", {})
    objection = next(
        (
            item
            for entry in matrix.get("file_dispositions", [])
            if entry.get("path") == "src/util/vfs/vfs-mem.c"
            for item in entry.get("objections", [])
            if item.get("id") == "memory-ownership-and-persistence"
        ),
        None,
    )
    require(
        parent.get("path") == str(MATRIX)
        and parent.get("sha256") == MATRIX_SHA256
        and parent.get("related_existing_objection") == "memory-ownership-and-persistence"
        and parent.get("parent_disposition_remains") == "RESOLVED_SOURCE_ONLY"
        and parent.get("remaining_matrix_gap")
        == "Allocation failure, large-size overflow, zero-size and short-write caller recovery."
        and objection is not None
        and objection.get("disposition") == "RESOLVED_SOURCE_ONLY",
        "parent matrix binding or disposition mismatch",
    )
    matrix_file = next(
        entry
        for entry in matrix.get("file_dispositions", [])
        if entry.get("path") == "src/util/vfs/vfs-mem.c"
    )
    require(
        any(
            "zero-size and short-write caller recovery" in item
            for item in matrix_file.get("unresolved", [])
        ),
        "the selected matrix gap is no longer present",
    )
    require(
        path_info.get("id") == "borrowed-vfile-boundary-short-write-no-expand"
        and "_vfmClose frees only the wrapper" in path_info.get("source_contract", "")
        and path_info.get("caller_trace", {}).get("source")
        == "src/gba/core.c:1469-1490"
        and path_info.get("caller_trace", {}).get("claim")
        and "does not compile or execute this GBA caller"
        in path_info["caller_trace"]["claim"]
        and path_info.get("resolution_scope"),
        "fault path or source/runtime boundary overclaim",
    )

    catalog = record.get("source_files", [])
    by_path = {item.get("path"): item for item in catalog}
    require(
        len(by_path) == len(catalog) == len(EXPECTED_PATHS)
        and set(by_path) == EXPECTED_PATHS
        and set(sources) == EXPECTED_PATHS,
        "source catalog or supplied closure incomplete",
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
            rows.get(path)
            == (
                item.get("dossier_row_sha256"),
                item.get("git_blob_sha1"),
                item.get("source_sha256"),
            ),
            f"dossier row mismatch: {path}",
        )
        for citation in item.get("source_lines", []):
            match = re.fullmatch(r"(.+):(\d+)-(\d+)", citation)
            require(
                match is not None and match.group(1) == path,
                f"invalid source citation: {citation}",
            )
            first, last = int(match.group(2)), int(match.group(3))
            require(
                1 <= first <= last <= len(text.splitlines()),
                f"citation out of range: {citation}",
            )

    compiled = {
        item["path"] for item in catalog if item.get("compiled_unchanged") is True
    }
    require(
        compiled == EXPECTED_PATHS - {"src/gba/core.c"}
        and all(
            item.get("verdict") == "NEEDS_EVIDENCE"
            for item in catalog
        ),
        "compiled-source scope or per-file verdict mismatch",
    )

    evidence = record.get("test_evidence", {})
    require(
        sha256(test_source) == evidence.get("source_sha256")
        and sha256(build_source) == evidence.get("build_sha256"),
        "test or build source SHA-256 mismatch",
    )
    require(
        evidence.get("execution_kind")
        == "PINNED_ORIGINAL_VFILE_MEMORY_SOURCES_NATIVE_HOST_TEST"
        and evidence.get("limits", {}).get("tested_storage_bytes") == 4
        and evidence.get("limits", {}).get("guard_bytes_checked") == 2
        and evidence.get("limits", {}).get("gba_core_caller_compiled_or_executed") is False
        and evidence.get("limits", {}).get("full_mgba_runtime_executed") is False
        and evidence.get("limits", {}).get("physical_flash_or_durability_tested") is False
        and evidence.get("limits", {}).get("failure_injection_used") is False,
        "native scope, bounds, or caller claim overstate evidence",
    )
    require(
        sha256(native_log) == evidence.get("local_log_sha256"),
        "native log SHA-256 mismatch",
    )
    log = native_log.decode("utf-8")
    require(
        log.count("\nPASS ") == 5
        and "\nFAIL " not in log
        and log.startswith(
            "SCOPE unchanged pinned vfs-mem.c; borrowed-memory VFile short-write"
        )
        and log.endswith(
            "SUMMARY assertions=5 failures=0 complete_write=2 boundary_write=1 end_write=0\n"
        ),
        "native log contents or assertion count mismatch",
    )
    assertions = evidence.get("assertions", [])
    require(
        len(assertions) == 5
        and "boundary-crossing write reports a one-byte short write" in assertions[2]
        and "caller-owned storage intact" in assertions[4],
        "behavioral assertions missing or reclassified",
    )

    licensing = record.get("licensing", {})
    require(
        licensing.get("selected_source_notice")
        == "MPL-2.0 verified for all eight pinned original files."
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
        and phase.get("semantic_approval") is False,
        "Phase 1 protected-state invariant mismatch",
    )
    matrix_effect = record.get("parent_matrix_effect", {})
    require(
        matrix_effect.get("matrix_changed") is False
        and matrix_effect.get("memory_ownership_disposition_changed") is False
        and matrix_effect.get("short_write_caller_recovery") == "NEEDS_EVIDENCE"
        and record.get("negative_control_inventory") == EXPECTED_CONTROLS,
        "parent state or negative-control inventory mismatch",
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

    def control(name: str, mutate_record=None, mutate_sources=None, log=None) -> None:
        candidate = copy.deepcopy(record)
        candidate_sources = dict(sources)
        if mutate_record:
            mutate_record(candidate)
        if mutate_sources:
            mutate_sources(candidate_sources)
        try:
            validate(
                candidate,
                rows,
                candidate_sources,
                matrix,
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
    control(EXPECTED_CONTROLS[5], lambda value: value["test_evidence"].update(source_sha256="0" * 64))
    control(EXPECTED_CONTROLS[6], lambda value: value["test_evidence"].update(build_sha256="0" * 64))
    control(
        EXPECTED_CONTROLS[7],
        log=native_log.replace(b"PASS in-bounds write completes", b"SKIP in-bounds write completes"),
    )
    control(
        EXPECTED_CONTROLS[8],
        lambda value: value["test_evidence"]["limits"].update(
            gba_core_caller_compiled_or_executed=True
        ),
    )
    control(
        EXPECTED_CONTROLS[9],
        lambda value: value["test_evidence"]["limits"].update(
            full_mgba_runtime_executed=True
        ),
    )
    control(
        EXPECTED_CONTROLS[10],
        lambda value: value["distinct_path"].update(
            source_contract="The borrowed buffer is owned and freed by _vfmClose."
        ),
    )
    control(
        EXPECTED_CONTROLS[11],
        lambda value: value["test_evidence"]["limits"].update(tested_storage_bytes=4096),
    )
    control(
        EXPECTED_CONTROLS[12],
        lambda value: value["licensing"].update(
            combined_distribution_legal_conclusion=True
        ),
    )
    control(
        EXPECTED_CONTROLS[13],
        lambda value: value["phase1_state"].update(
            {"decision": "PASS", "approved_after": 1, "semantic_approval": True}
        ),
    )
    control(
        EXPECTED_CONTROLS[14],
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
    checkout_revision = None
    if checkout:
        checkout_revision = subprocess.check_output(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
        ).strip()
    record_raw = (root / RECORD).read_bytes()
    require(
        RECORD_SHA256 != "PENDING" and sha256(record_raw) == RECORD_SHA256,
        "record SHA-256 mismatch",
    )
    record = json.loads(record_raw)
    rows = load_dossier(root)
    matrix_raw = (root / MATRIX).read_bytes()
    require(sha256(matrix_raw) == MATRIX_SHA256, "parent matrix SHA-256 mismatch")
    matrix = json.loads(matrix_raw)
    source_root = checkout or source_directory
    assert source_root is not None
    sources = {path: (source_root / path).read_bytes() for path in EXPECTED_PATHS}
    test_source = (root / TEST_SOURCE).read_bytes()
    build_source = (root / BUILD_SOURCE).read_bytes()
    native_log = args.native_log.read_bytes()
    validate(
        record, rows, sources, matrix, test_source, build_source, native_log,
        checkout_revision,
    )
    rejected = (
        run_controls(
            record, rows, sources, matrix, test_source, build_source, native_log
        )
        if args.self_test
        else []
    )
    print(
        f"PASS borrowed-memory VFile short-write evidence: {len(sources)} pinned files; "
        f"5 native host assertions; caller remains source-traced only; "
        f"{len(rejected)} negative controls rejected"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Rejected, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"REJECTED: {error}")
