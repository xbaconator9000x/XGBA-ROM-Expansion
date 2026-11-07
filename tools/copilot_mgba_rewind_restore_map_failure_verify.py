#!/usr/bin/env python3
"""Verify bounded pinned mCore rewind restore map-failure evidence."""
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
    "rewind-restore-map-failure.json"
)
RECORD_SHA256 = "4e084bd5a48b118304e42e00b272bfb25499b84b10e1fd77c146d65317bd0621"
DOSSIER = Path("semantic-snapshots/current/candidate_review_dossiers.jsonl.gz")
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
TEST_SOURCE = Path("tests/mgba_rewind_restore_map_failure.c")
BUILD_SOURCE = Path("tests/CMakeLists.txt")
EXPECTED_PATHS = {
    "include/mgba-util/common.h",
    "include/mgba-util/configuration.h",
    "include/mgba-util/dllexports.h",
    "include/mgba-util/geometry.h",
    "include/mgba-util/image.h",
    "include/mgba-util/math.h",
    "include/mgba-util/memory.h",
    "include/mgba-util/patch.h",
    "include/mgba-util/patch/fast.h",
    "include/mgba-util/table.h",
    "include/mgba-util/vector.h",
    "include/mgba-util/vfs.h",
    "include/mgba/core/config.h",
    "include/mgba/core/core.h",
    "include/mgba/core/input.h",
    "include/mgba/core/interface.h",
    "include/mgba/core/rewind.h",
    "include/mgba/core/serialize.h",
    "src/core/rewind.c",
    "src/util/memory.c",
    "src/util/patch-fast.c",
    "src/util/vfs/vfs-mem.c",
}
EXPECTED_LOG = (
    "SCOPE unchanged pinned rewind.c, patch-fast.c, memory.c, and vfs-mem.c; "
    "mCoreRewindRestore executes; map-failure adapter, patch observer, and "
    "core-load callback are test doubles\n"
    "PASS positive rewind context initializes\n"
    "PASS valid mappings reach patch callback and both unmaps\n"
    "PASS positive rewind teardown closes both state VFiles\n"
    "PASS fault rewind context initializes\n"
    "PASS failed map reaches patch callback and both unmaps still run\n"
    "PASS restore returns true and consumes the entry after map failure\n"
    "PASS fault rewind teardown closes both state VFiles\n"
    "PASS recovery control context initializes\n"
    "PASS fresh valid restore succeeds after the injected-failure case\n"
    "PASS recovery control teardown closes both state VFiles\n"
    "SUMMARY assertions=10 failures=0\n"
)
EXPECTED_CONTROLS = [
    "source-revision-mismatch",
    "source-blob-mismatch",
    "source-byte-sha256-mismatch",
    "dossier-row-mismatch",
    "dependency-closure-incomplete",
    "test-source-hash-mismatch",
    "build-source-hash-mismatch",
    "runtime-log-mismatch",
    "false-rewind-execution-claim",
    "false-production-patch-or-core-claim",
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
    record: dict,
    rows: dict[str, tuple[str, str, str]],
    sources: dict[str, bytes],
    test_source: bytes,
    build_source: bytes,
    native_log: bytes,
    checkout_revision: str | None,
) -> None:
    require(
        record.get("schema")
        == "xgba.copilot.mgba_savedata_rewind_restore_map_failure.v1",
        "record schema mismatch",
    )
    review = record.get("review", {})
    require(
        review.get("repository") == "xbaconator9000x/XGBA-ROM-Expansion"
        and review.get("pull_request") == 35
        and review.get("request_comment_id") == 6706381637
        and review.get("expected_parent_head")
        == "4ed33a3ea3af4d7bd18e34a5f1da5b92db429d65"
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
        "source pin or dossier identity mismatch",
    )
    if checkout_revision is not None:
        require(checkout_revision == PIN, "source checkout revision mismatch")

    boundary = record.get("boundary", {})
    require(
        boundary.get("id") == "mCoreRewindRestore-currentState-map-failure"
        and boundary.get("production_caller")
        == "src/core/rewind.c:mCoreRewindRestore"
        and boundary.get("source_lines")
        == ["src/core/rewind.c:123-170", "src/core/rewind.c:144-162"]
        and "without checking either pointer" in boundary.get("contract", "")
        and "returns true despite the NULL map" in boundary.get("finding", "")
        and "fresh valid context" in boundary.get("finding", ""),
        "caller boundary or finding mismatch",
    )
    require(
        boundary.get("fault_injection", "").startswith(
            "The harness first initializes real pinned VFileMemChunk state"
        )
        and len(boundary.get("test_doubles", [])) == 3,
        "fault injection or test-double boundary mismatch",
    )

    catalog = record.get("source_files", [])
    by_path = {item.get("path"): item for item in catalog}
    require(
        len(by_path) == len(catalog) == len(EXPECTED_PATHS)
        and set(by_path) == EXPECTED_PATHS
        and set(sources) == EXPECTED_PATHS,
        "compiled dependency closure incomplete",
    )
    for path, item in by_path.items():
        source = sources[path]
        role = item.get("build_role")
        require(
            item.get("git_blob_sha1") == blob_sha1(source)
            and item.get("source_sha256") == sha256(source)
            and item.get("license_notice") == "MPL-2.0"
            and item.get("verdict") == "NEEDS_EVIDENCE"
            and b"Mozilla Public" in source
            and b"License, v. 2.0." in source,
            f"pinned source identity, license, or verdict mismatch: {path}",
        )
        require(
            role
            == (
                "production_caller_compiled_and_executed"
                if path == "src/core/rewind.c"
                else (
                    "compiled_translation_unit"
                    if path.startswith("src/")
                    else "included_header"
                )
            ),
            f"source build role mismatch: {path}",
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

    evidence = record.get("test_evidence", {})
    require(
        evidence.get("source_path") == str(TEST_SOURCE)
        and evidence.get("build_path") == str(BUILD_SOURCE)
        and evidence.get("source_sha256") == sha256(test_source)
        and evidence.get("build_sha256") == sha256(build_source),
        "test or build source identity mismatch",
    )
    limits = evidence.get("limits", {})
    require(
        evidence.get("execution_kind")
        == "PINNED_ORIGINAL_REWIND_CALLER_NATIVE_HOST_FAULT_ADAPTER"
        and evidence.get("assertion_count") == 10
        and limits.get("rewind_caller_compiled_and_executed") is True
        and limits.get("pinned_rewind_translation_unit_unchanged") is True
        and limits.get("full_mgba_runtime_executed") is False
        and limits.get("production_patch_implementation_used_for_fault_case") is False
        and limits.get("production_core_load_callback_executed") is False
        and limits.get("gameplay_or_real_save_executed") is False
        and limits.get("physical_flash_or_durability_tested") is False
        and limits.get("threaded_rewind_tested") is False,
        "runtime class or caller execution limits mismatch",
    )
    require(
        native_log.decode("utf-8") == EXPECTED_LOG
        and evidence.get("local_log_sha256") == sha256(native_log)
        and len(evidence.get("positive_fault_recovery_controls", [])) == 3,
        "native output or positive/fault/recovery controls mismatch",
    )

    licensing = record.get("licensing", {})
    require(
        licensing.get("selected_source_notice")
        == "MPL-2.0 verified for all 22 pinned original source/header files."
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
    record: dict,
    rows: dict[str, tuple[str, str, str]],
    sources: dict[str, bytes],
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
    control(EXPECTED_CONTROLS[7], log=native_log.replace(b"PASS failed map reaches", b"SKIP failed map reaches"))
    control(
        EXPECTED_CONTROLS[8],
        lambda value: value["test_evidence"]["limits"].update(
            rewind_caller_compiled_and_executed=False
        ),
    )
    control(
        EXPECTED_CONTROLS[9],
        lambda value: value["test_evidence"]["limits"].update(
            production_patch_implementation_used_for_fault_case=True,
        ),
    )
    control(
        EXPECTED_CONTROLS[10],
        lambda value: value["test_evidence"]["limits"].update(
            gameplay_or_real_save_executed=True
        ),
    )
    control(
        EXPECTED_CONTROLS[11],
        lambda value: value["test_evidence"]["limits"].update(
            physical_flash_or_durability_tested=True
        ),
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
            {"src/core/rewind.c": value["src/core/rewind.c"] + b"\n"}
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
    source_root = checkout or source_directory
    assert source_root is not None
    sources = {path: (source_root / path).read_bytes() for path in EXPECTED_PATHS}
    test_source = (root / TEST_SOURCE).read_bytes()
    build_source = (root / BUILD_SOURCE).read_bytes()
    native_log = args.native_log.read_bytes()
    validate(record, rows, sources, test_source, build_source, native_log, revision)
    controls = (
        run_controls(record, rows, sources, test_source, build_source, native_log)
        if args.self_test else []
    )
    require(not args.self_test or controls == EXPECTED_CONTROLS, "negative controls incomplete")
    print(f"PASS pinned rewind caller evidence: {len(EXPECTED_PATHS)} source files")
    print("PASS compiled caller fault controls: 10 assertions")
    if args.self_test:
        print(f"PASS negative controls rejected: {len(controls)}")
    print("NON_APPROVING Phase 1 remains FAIL_INCOMPLETE; approved count unchanged at zero")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Rejected, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"REJECTED: {error}")
