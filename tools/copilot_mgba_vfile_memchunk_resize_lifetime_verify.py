#!/usr/bin/env python3
"""Verify bounded pinned VFileMemChunk resize-lifetime evidence."""
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
    "vfile-memchunk-resize-lifetime.json"
)
RECORD_SHA256 = "0184dc872c3ba418e912ea7f2770e362388c54474b6abccc2566eacb394b2c37"
MATRIX = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata/"
    "cross-tranche-objection-matrix.json"
)
MATRIX_SHA256 = "f7ce0e81169b6b4a3724e7d0d8385ad6bd80b3f2c50e3a5243402fafecd0d084"
DOSSIER = Path("semantic-snapshots/current/candidate_review_dossiers.jsonl.gz")
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
TEST_SOURCE = Path("tests/mgba_vfile_memchunk_resize_lifetime.c")
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
    "src/util/test/vfs.c",
}
EXPECTED_LOG = (
    "SCOPE unchanged pinned memory.c and vfs-mem.c; owned VFileMemChunk growth, "
    "shrink/regrow within capacity, and close; GBA caller not executed\n"
    "PASS constructor owns a copied four-byte buffer\n"
    "PASS growth replaces backing, preserves old bytes, and exposes a zero-filled byte\n"
    "PASS write places a marker in spare owned capacity\n"
    "PASS shrink clamps the cursor to the new logical end\n"
    "PASS regrowth within retained capacity makes the truncated marker visible again\n"
    "PASS owned chunk closes successfully and the caller seed remains unchanged\n"
    "SUMMARY assertions=6 failures=0\n"
)
EXPECTED_ASSERTIONS = [
    "constructor owns a copied four-byte buffer",
    "growth replaces backing, preserves old bytes, and exposes a zero-filled byte",
    "write places a marker in spare owned capacity",
    "shrink clamps the cursor to the new logical end",
    "regrowth within retained capacity makes the truncated marker visible again",
    "owned chunk closes successfully and the caller seed remains unchanged",
]
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
    "false-full-emulator-or-gameplay-label",
    "false-physical-flash-or-durability-claim",
    "false-upstream-test-execution-claim",
    "hidden-tail-semantics-reversal",
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
        record.get("schema")
        == "xgba.copilot.mgba_savedata_vfile_memchunk_resize_lifetime.v1",
        "record schema mismatch",
    )
    review = record.get("review", {})
    require(
        review.get("repository") == "xbaconator9000x/XGBA-ROM-Expansion"
        and review.get("pull_request") == 35
        and review.get("request_comment_id") == 6705149862
        and review.get("expected_parent_head")
        == "66a3b87f9c778093016d10743250e65727ee88fe"
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

    raw_matrix = (root / MATRIX).read_bytes()
    require(sha256(raw_matrix) == MATRIX_SHA256, "parent matrix hash mismatch")
    matrix_file = next(
        (
            item
            for item in matrix.get("file_dispositions", [])
            if item.get("path") == "src/util/vfs/vfs-mem.c"
        ),
        None,
    )
    require(
        matrix_file is not None
        and matrix_file.get("git_blob_sha1")
        == "048194e2dd2d0b3b395a852d2092c694663c88a2"
        and matrix_file.get("source_sha256")
        == "6b5951a0cd634d398a69ce57766298bd32d5e6410ee0aa4e8b8894c6aaa5829b"
        and any(
            item.get("id") == "memory-ownership-and-persistence"
            and item.get("disposition") == "RESOLVED_SOURCE_ONLY"
            for item in matrix_file.get("objections", [])
        ),
        "parent matrix source identity or disposition mismatch",
    )

    path_info = record.get("fault_path", {})
    existing_test = path_info.get("existing_upstream_test_review", {})
    require(
        path_info.get("id") == "owned-vfilememchunk-shrink-regrow-within-capacity"
        and "without clearing backing bytes" in path_info.get("source_contract", "")
        and "not a security or gameplay impact" in path_info.get("finding", "")
        and existing_test.get("path") == "src/util/test/vfs.c"
        and existing_test.get("source_lines") == ["src/util/test/vfs.c:122-136"]
        and "does not check whether a byte hidden by shrink is exposed again"
        in existing_test.get("coverage_difference", ""),
        "selected fault path or existing test distinction mismatch",
    )
    caller = path_info.get("caller_trace", {})
    require(
        caller.get("api") == "include/mgba-util/vfs.h:83-85"
        and caller.get("constructor_and_callback_binding")
        == "src/util/vfs/vfs-mem.c:90-118"
        and caller.get("resize_and_ownership")
        == "src/util/vfs/vfs-mem.c:121-152,290-296"
        and caller.get("production_callsite", {}).get("source")
        == "src/gba/core.c:1493-1506"
        and "not executed here"
        in caller.get("production_callsite", {}).get("contract", ""),
        "caller chain or non-execution boundary mismatch",
    )

    catalog = record.get("source_files", [])
    by_path = {item.get("path"): item for item in catalog}
    require(
        len(by_path) == len(catalog) == len(EXPECTED_PATHS)
        and set(by_path) == EXPECTED_PATHS
        and set(sources) == EXPECTED_PATHS,
        "source catalog or supplied closure incomplete",
    )
    roles = {
        "src/util/vfs/vfs-mem.c": "compiled_translation_unit",
        "src/util/memory.c": "compiled_translation_unit",
        "include/mgba-util/vfs.h": "included_header",
        "include/mgba-util/memory.h": "included_header",
        "include/mgba-util/math.h": "included_header",
        "include/mgba-util/common.h": "included_header",
        "include/mgba-util/dllexports.h": "included_header",
        "src/gba/core.c": "production_callsite_source_traced_only",
        "src/util/test/vfs.c": "existing_test_compared_not_executed",
    }
    for path, item in by_path.items():
        source = sources[path]
        text = source.decode("utf-8")
        require(
            item.get("git_blob_sha1") == blob_sha1(source)
            and item.get("source_sha256") == sha256(source)
            and item.get("license_notice") == "MPL-2.0"
            and item.get("build_role") == roles[path]
            and item.get("verdict") == "NEEDS_EVIDENCE"
            and b"Mozilla Public" in source
            and b"License, v. 2.0." in source,
            f"pinned source identity/license/disposition mismatch: {path}",
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

    upstream_test = sources["src/util/test/vfs.c"].decode("utf-8")
    resize_test = upstream_test[
        upstream_test.index("M_TEST_DEFINE(resizeMemChunk)"):
        upstream_test.index("M_TEST_DEFINE(mapMem)")
    ]
    require(
        "vf->truncate(vf, 64);" in resize_test
        and "vf->truncate(vf, 16);" in resize_test
        and "0xE7" not in resize_test
        and "memcmp" not in resize_test,
        "original mGBA resize test comparison no longer matches",
    )
    backend = sources["src/util/vfs/vfs-mem.c"].decode("utf-8")
    require(
        "vfm->d.truncate = _vfmTruncate;" in backend
        and "if (alignedSize > vfm->bufferSize)" in backend
        and "vfm->size = newSize;" in backend
        and "void _vfmTruncate(struct VFile* vf, size_t size)" in backend,
        "pinned resize callback structure mismatch",
    )

    evidence = record.get("test_evidence", {})
    require(
        evidence.get("source_path") == str(TEST_SOURCE)
        and evidence.get("build_path") == str(BUILD_SOURCE)
        and sha256(test_source) == evidence.get("source_sha256")
        and sha256(build_source) == evidence.get("build_sha256"),
        "test or build source SHA-256 mismatch",
    )
    limits = evidence.get("limits", {})
    require(
        evidence.get("execution_kind")
        == "PINNED_ORIGINAL_VFILE_MEMORY_SOURCES_NATIVE_HOST_TEST"
        and limits.get("seed_bytes") == 4
        and limits.get("growth_size") == 5
        and limits.get("retained_capacity_bytes") == 8
        and limits.get("gba_core_caller_compiled_or_executed") is False
        and limits.get("original_mgba_vfs_test_fixture_executed") is False
        and limits.get("full_mgba_runtime_executed") is False
        and limits.get("gameplay_or_real_save_executed") is False
        and limits.get("physical_flash_or_durability_tested") is False
        and limits.get("allocation_failure_injected") is False,
        "native scope, size bound, or caller claim overstates evidence",
    )
    require(
        evidence.get("assertions") == EXPECTED_ASSERTIONS
        and evidence.get("result")
        == "PASS_BOUNDED_OWNED_VFILEMEMCHUNK_RESIZE_LIFETIME_CHARACTERIZATION"
        and native_log.decode("utf-8") == EXPECTED_LOG
        and evidence.get("local_log_sha256") == sha256(native_log),
        "native evidence assertions, log, or digest mismatch",
    )

    licensing = record.get("licensing", {})
    require(
        licensing.get("selected_source_notice")
        == "MPL-2.0 verified for all nine pinned original source/header files."
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
    control(EXPECTED_CONTROLS[7], log=native_log.replace(b"PASS shrink clamps", b"SKIP shrink clamps"))
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
        lambda value: value["test_evidence"]["limits"].update(
            physical_flash_or_durability_tested=True
        ),
    )
    control(
        EXPECTED_CONTROLS[11],
        lambda value: value["test_evidence"]["limits"].update(
            original_mgba_vfs_test_fixture_executed=True
        ),
    )
    control(
        EXPECTED_CONTROLS[12],
        lambda value: value["fault_path"].update(
            finding="Shrinking and regrowing clears the prior marker."
        ),
    )
    control(
        EXPECTED_CONTROLS[13],
        lambda value: value["licensing"].update(
            combined_distribution_legal_conclusion=True
        ),
    )
    control(
        EXPECTED_CONTROLS[14],
        lambda value: value["phase1_state"].update(
            {"decision": "PASS", "approved_after": 1, "semantic_approval": True}
        ),
    )
    control(
        EXPECTED_CONTROLS[15],
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
    validate(
        root, record, rows, sources, matrix, test_source, build_source, native_log,
        revision
    )
    controls = (
        run_controls(root, record, rows, sources, matrix, test_source, build_source, native_log)
        if args.self_test else []
    )
    require(
        not args.self_test or controls == EXPECTED_CONTROLS,
        "negative controls incomplete",
    )
    print(f"PASS pinned resize evidence: {len(EXPECTED_PATHS)} source files")
    print(f"PASS native-host resize assertions: {len(EXPECTED_ASSERTIONS)}")
    if args.self_test:
        print(f"PASS negative controls rejected: {len(controls)}")
    print("NON_APPROVING Phase 1 remains FAIL_INCOMPLETE; approved count unchanged at zero")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Rejected, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"REJECTED {error}")
