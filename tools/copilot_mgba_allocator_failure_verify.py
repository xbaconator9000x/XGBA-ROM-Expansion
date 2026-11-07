#!/usr/bin/env python3
"""Verify bounded allocation-failure evidence against pinned mGBA sources."""
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
    "allocation-failure-probe.json"
)
RECORD_SHA256 = "2b443b22c2998d28f258cb7ce69c1d95d0110e29b3208b625ceda634498771f2"
PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
DOSSIER = Path("semantic-snapshots/current/candidate_review_dossiers.jsonl.gz")
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
TEST_SOURCE = Path("tests/mgba_allocator_failure.c")
BUILD_SOURCE = Path("tests/CMakeLists.txt")
EXPECTED_PATHS = {
    "src/util/memory.c",
    "src/util/vfs/vfs-mem.c",
    "include/mgba-util/memory.h",
    "include/mgba-util/vfs.h",
    "include/mgba-util/common.h",
    "include/mgba-util/dllexports.h",
    "include/mgba-util/math.h",
    "src/gba/core.c",
    "src/gba/savedata.c",
    "include/mgba/internal/gba/savedata.h",
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
    "false-gba-restore-runtime-claim",
    "false-full-emulator-or-gameplay-label",
    "test-size-bound-overclaim",
    "missing-unresolved-caller-obligation",
    "license-boundary-overclaim",
    "phase1-approval-promotion",
    "source-byte-mutation",
]
REQUIRED_OBLIGATIONS = {
    "gba-restore-caller-runtime-and-ownership",
    "uninstrumented-null-copy-outcome",
    "full-size-domain-and-rounding",
    "platform-os-src-allocator-variants",
    "allocation-failure-observability-and-logging",
    "license-and-transitive-dependencies",
}


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
    test_source: bytes,
    build_source: bytes,
    native_log: bytes,
    checkout_revision: str | None,
) -> None:
    require(
        record.get("schema") == "xgba.copilot.mgba_savedata_allocation_failure_probe.v1",
        "record schema mismatch",
    )
    review = record.get("review", {})
    require(
        review.get("repository") == "xbaconator9000x/XGBA-ROM-Expansion"
        and review.get("pull_request") == 35
        and review.get("request_comment_id") == 6701109918
        and review.get("expected_parent_head")
        == "0781388525031cc4a1db3fe72e920d20cdb11f41"
        and review.get("approval_eligible") is False
        and "not an external approval" in review.get("reviewer_identity_limit", ""),
        "review attribution or scope mismatch",
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
            require(match is not None and match.group(1) == path, f"bad source citation: {citation}")
            first, last = int(match.group(2)), int(match.group(3))
            require(1 <= first <= last <= line_count, f"source citation out of range: {citation}")

    trace = record.get("dependency_and_caller_trace", {})
    require(
        trace.get("compiled_original_sources")
        == ["src/util/memory.c", "src/util/vfs/vfs-mem.c"]
        and trace.get("compiled_header_closure")
        == [
            "include/mgba-util/common.h",
            "include/mgba-util/dllexports.h",
            "include/mgba-util/math.h",
            "include/mgba-util/memory.h",
            "include/mgba-util/vfs.h",
        ]
        and trace.get("build_selection")
        == "Direct translation units only; this does not establish production OS_SRC selection or compile src/gba/core.c.",
        "compiled-source scope or build-selection claim mismatch",
    )
    compiled = {item["path"] for item in catalog if item.get("compiled_unchanged") is True}
    require(
        compiled == {"src/util/memory.c", "src/util/vfs/vfs-mem.c"},
        "original compiled source list mismatch",
    )
    require(
        sha256(test_source) == record["test_evidence"].get("test_source_sha256")
        and sha256(build_source) == record["test_evidence"].get("build_source_sha256"),
        "test or build source SHA-256 mismatch",
    )
    test = record.get("test_evidence", {})
    require(
        test.get("execution_kind")
        == "PINNED_ORIGINAL_VFILE_MEMORY_SOURCES_WITH_SYNTHETIC_LINKER_WRAPPERS"
        and test.get("linker_wrappers", {}).get("memcpy", "").startswith(
            "When an injected allocation has failed, suppresses"
        )
        and test.get("tested_sizes", {}).get("max_requested_bytes") == 8
        and test.get("tested_sizes", {}).get("max_observed_backing_allocation_bytes") == 8
        and test.get("tested_sizes", {}).get("global_size_or_overflow_safety_proven") is False,
        "failure-injection or tested-size boundary overclaim",
    )
    claims = test.get("execution_claims", {})
    require(
        claims.get("original_allocator_and_vfile_translation_units_compiled_unchanged") is True
        and claims.get("synthetic_linker_wrappers_used") is True
        and claims.get("gba_savedata_restore_executed") is False
        and claims.get("full_mgba_runtime_executed") is False
        and claims.get("gameplay_or_real_save_executed") is False
        and claims.get("physical_flash_or_durable_persistence_tested") is False
        and claims.get("actual_uninstrumented_null_memcpy_outcome_observed") is False,
        "native runtime/gameplay evidence overclaim",
    )
    require(
        sha256(native_log) == test.get("local_runtime_log_sha256"),
        "native log hash mismatch",
    )
    log = native_log.decode("utf-8")
    require(
        log.count("\nPASS ") == 8
        and "\nFAIL " not in log
        and log.startswith("SCOPE original pinned memory.c and vfs-mem.c compiled unchanged;")
        and log.endswith("SUMMARY assertions=8 failures=0 max_backing_allocation=8\n"),
        "native log assertions or scope mismatch",
    )

    disposition = record.get("disposition", {})
    obligations = {item.get("id"): item for item in disposition.get("unresolved_obligations", [])}
    require(
        disposition.get("verdict") == "NEEDS_EVIDENCE"
        and set(obligations) == REQUIRED_OBLIGATIONS
        and all(item.get("disposition") == "NEEDS_EVIDENCE" for item in obligations.values()),
        "review verdict or unresolved obligations were promoted/dropped",
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
        and phase.get("p0_approved_before") == phase.get("p0_approved_after") == 0
        and phase.get("approved_before") == phase.get("approved_after") == 0
        and phase.get("phase2_started") is False
        and phase.get("shared_gate_or_register_edited") is False
        and phase.get("semantic_approval") is False,
        "Phase 1 protected-state invariant mismatch",
    )
    require(
        record.get("negative_control_inventory") == EXPECTED_CONTROLS,
        "negative-control inventory mismatch",
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

    def control(
        name: str,
        mutate_record=None,
        mutate_sources=None,
        candidate_test: bytes | None = None,
        candidate_build: bytes | None = None,
        candidate_log: bytes | None = None,
    ) -> None:
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
                test_source if candidate_test is None else candidate_test,
                build_source if candidate_build is None else candidate_build,
                native_log if candidate_log is None else candidate_log,
                PIN,
            )
        except (Rejected, KeyError, TypeError):
            passed.append(name)
        else:
            raise Rejected(f"negative control accepted: {name}")

    control(
        EXPECTED_CONTROLS[0],
        lambda value: value["source_pin"].update(revision="0" * 40),
    )
    control(
        EXPECTED_CONTROLS[1],
        lambda value: value["source_files"][0].update(git_blob_sha1="0" * 40),
    )
    control(
        EXPECTED_CONTROLS[2],
        lambda value: value["source_files"][0].update(source_sha256="0" * 64),
    )
    control(
        EXPECTED_CONTROLS[3],
        lambda value: value["source_files"][0].update(dossier_row_sha256="0" * 64),
    )
    control(
        EXPECTED_CONTROLS[4],
        lambda value: value["source_files"].pop(),
    )
    control(
        EXPECTED_CONTROLS[5],
        lambda value: value["test_evidence"].update(test_source_sha256="0" * 64),
    )
    control(
        EXPECTED_CONTROLS[6],
        lambda value: value["test_evidence"].update(build_source_sha256="0" * 64),
    )
    control(
        EXPECTED_CONTROLS[7],
        candidate_log=native_log.replace(b"PASS positive allocation", b"SKIP positive allocation"),
    )
    control(
        EXPECTED_CONTROLS[8],
        lambda value: value["test_evidence"]["execution_claims"].update(
            gba_savedata_restore_executed=True
        ),
    )
    control(
        EXPECTED_CONTROLS[9],
        lambda value: value["test_evidence"]["execution_claims"].update(
            full_mgba_runtime_executed=True
        ),
    )
    control(
        EXPECTED_CONTROLS[10],
        lambda value: value["test_evidence"]["tested_sizes"].update(
            max_requested_bytes=64
        ),
    )
    control(
        EXPECTED_CONTROLS[11],
        lambda value: value["disposition"]["unresolved_obligations"].pop(0),
    )
    control(
        EXPECTED_CONTROLS[12],
        lambda value: value["license_boundary"].update(
            combined_distribution_legal_conclusion=True
        ),
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
            {"src/util/memory.c": value["src/util/memory.c"] + b"\n"}
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
            "allocation-failure record SHA-256 mismatch")
    record = json.loads(record_raw)
    rows = load_dossier(root)
    source_root = checkout or source_directory
    assert source_root is not None
    sources = {
        path: (source_root / path).read_bytes()
        for path in EXPECTED_PATHS
    }
    test_source = (root / TEST_SOURCE).read_bytes()
    build_source = (root / BUILD_SOURCE).read_bytes()
    native_log = args.native_log.read_bytes()
    validate(record, rows, sources, test_source, build_source, native_log, checkout_revision)
    rejected = (
        run_controls(record, rows, sources, test_source, build_source, native_log)
        if args.self_test
        else []
    )
    print(
        f"PASS bounded allocator-failure evidence: {len(sources)} pinned source files; "
        f"8 local native VFile assertions; GBA restore remains NEEDS_EVIDENCE; "
        f"{len(rejected)} negative controls rejected"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Rejected, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"REJECTED: {error}")
