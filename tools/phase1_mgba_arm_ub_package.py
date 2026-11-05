#!/usr/bin/env python3
"""Verify bounded, non-approving arithmetic/UB evidence for pinned mGBA ARM code."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import phase1_mgba_arm_decode_emit_review_verify as arm_verify
from phase1_bulk_triage import canonical, checked_dossiers, digest, read_queue

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
REPOSITORY = "mgba-emu/mgba"
ARCHIVE_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
SCHEMA = "xgba.phase1.mgba_arm_ub_objection_package.v1"

SOURCES = {
    "isa_inlines": {
        "path": "include/mgba/internal/arm/isa-inlines.h",
        "blob": "ebda28e411f627c6cd1570aff6f29a3b79a60840",
        "source_sha256": "17d976d898d9e412f863ea5a1ff41bde3232c16c13e08f9b0f9350a911e269a9",
        "dossier_sha256": "22099dfd7b67ee163af3dd04afe6aed7b70f059d9df2ebb14f713aeec91f58db",
    },
    "decoder_thumb": {
        "path": "src/arm/decoder-thumb.c",
        "blob": "e96ae839613f846fbb477a6ddefc284a745c8e0d",
        "source_sha256": "627e5919e13c5c909193839c0fbc8069f55fb1e173c03d4ed5956e4168c1f4e0",
        "dossier_sha256": "585228eef510e0acd6cf7df901a04d63bca7f71bcc82e320b28d463ff9b7016f",
    },
    "decoder": {
        "path": "src/arm/decoder.c",
        "blob": "21ea0e872c32689b46f7ab746d871a7a1070c97c",
        "source_sha256": "0676c6934b3f3fbce0204b5aff8afb4cd85286db724f6ca04e0a626ad1180fd1",
        "dossier_sha256": "c2fdc6d4229837ff35c4786c446ecf25eef97fa1f11bc57f037c31f284581961",
    },
}

ANCHOR_LINES = {
    "isa_inlines": [
        (30, "#define ARM_SXT_8(I) (((int8_t) (I) << 24) >> 24)"),
        (31, "#define ARM_SXT_16(I) (((int16_t) (I) << 16) >> 16)"),
    ],
    "decoder_thumb": [
        (221, "int8_t immediate = opcode;"),
        (222, "info->op1.immediate = immediate << 1; \\"),
        (273, "int16_t immediate = (opcode & 0x07FF) << 5;"),
        (276, "info->op3.immediate = (((int32_t) immediate) << 7);"),
    ],
    "decoder": [
        (582, "offset <<= shiftSize;"),
        (585, "offset = ((uint32_t) offset) >> shiftSize;"),
        (588, "offset >>= shiftSize;"),
        (600, "return address + (info->memory.format & ARM_MEMORY_OFFSET_SUBTRACT ? -offset : offset);"),
    ],
}

ANCHORS = {
    key: [text for _, text in anchors]
    for key, anchors in ANCHOR_LINES.items()
}

DEPENDENCY_PATHS = {
    "isa_inlines": [
        "include/mgba/internal/arm/macros.h",
        "include/mgba/internal/arm/arm.h",
        "include/mgba-util/common.h",
    ],
    "decoder_thumb": [
        "include/mgba/internal/arm/decoder.h",
        "include/mgba/internal/arm/decoder-inlines.h",
        "include/mgba/internal/arm/emitter-thumb.h",
        "include/mgba/internal/arm/emitter-inlines.h",
        "include/mgba/internal/arm/isa-inlines.h",
        "include/mgba/internal/arm/macros.h",
        "include/mgba/internal/arm/arm.h",
        "include/mgba-util/common.h",
    ],
    "decoder": [
        "include/mgba/internal/arm/decoder.h",
        "include/mgba/internal/arm/decoder-inlines.h",
        "include/mgba/internal/arm/arm.h",
        "include/mgba/internal/debugger/symbols.h",
        "include/mgba-util/string.h",
        "include/mgba-util/common.h",
    ],
}

OBJECTIONS = [
    {
        "id": "arm_signed_extension_left_shift",
        "source_key": "isa_inlines",
        "anchors": ANCHORS["isa_inlines"],
        "counterexample": (
            "ARM_SXT_8(0xff) and ARM_SXT_16(0xffff) convert to negative narrow signed "
            "values on the tested host ABI, then left-shift those negative values."
        ),
        "preconditions": (
            "The macro receives 0xff or 0xffff; conversion of those values to int8_t/int16_t "
            "is implementation-defined when unrepresentable, and a negative signed left shift is undefined."
        ),
        "controls": ["signed-byte-extension", "signed-halfword-extension"],
        "open_issues": [
            "Exact values reachable at each compiled mGBA load caller are not proven by this host fixture.",
            "Conversion behavior is ABI/compiler dependent.",
        ],
    },
    {
        "id": "thumb_branch_signed_arithmetic",
        "source_key": "decoder_thumb",
        "anchors": ANCHORS["decoder_thumb"],
        "counterexample": (
            "The original decoder controls exercise conditional opcode 0xD080 and BL1 opcode "
            "0xF400, which produce a negative intermediate on the tested host ABI before a signed left shift."
        ),
        "preconditions": (
            "The opcode follows the indicated Thumb decoder path; out-of-range conversion to int8_t/int16_t "
            "is implementation-defined, and left-shifting a resulting negative signed value is undefined."
        ),
        "controls": ["thumb-negative-conditional-branch", "thumb-negative-bl1-prefix"],
        "open_issues": [
            "No independent ARMv4T oracle or target-hardware execution is included.",
            "Reachability and optimized native emulator behavior are not established by the host sanitizer run.",
        ],
    },
    {
        "id": "arm_resolve_memory_signed_offset",
        "source_key": "decoder",
        "anchors": ANCHORS["decoder"],
        "counterexample": (
            "The original resolver controls exercise a negative signed LSL offset and subtracting "
            "INT32_MIN; both trigger signed-arithmetic UBSan diagnostics."
        ),
        "preconditions": (
            "ARMResolveMemoryAccess receives a shifted negative offset, or subtraction is requested "
            "with offset INT32_MIN. Conversion of an out-of-range uint32_t register value to int32_t "
            "and right-shifting a negative signed value are separately implementation-defined."
        ),
        "controls": ["debugger-negative-shifted-memory-offset", "resolver-int-min-subtract"],
        "open_issues": [
            "The focused controls are synthetic debugger-style inputs, not evidence that normal CPU execution supplies them.",
            "Implementation-defined conversion and negative right-shift results have not been compared across target compilers.",
        ],
    },
]

CONTROL_DIAGNOSTICS = {
    "signed-byte-extension": "left shift of negative value",
    "signed-halfword-extension": "left shift of negative value",
    "thumb-negative-conditional-branch": "left shift of negative value",
    "thumb-negative-bl1-prefix": "left shift of negative value",
    "debugger-negative-shifted-memory-offset": "left shift of negative value",
    "resolver-int-min-subtract": "negation of -2147483648",
}


def _expected_input_identities() -> dict[str, dict[str, str]]:
    result = {
        path: {"git_blob_sha1": blob, "source_sha256": source_sha}
        for path, (blob, source_sha) in arm_verify.SUPPORT.items()
    }
    result.update({
        item["path"]: {
            "git_blob_sha1": item["blob"],
            "source_sha256": item["source_sha256"],
        }
        for item in SOURCES.values()
    })
    for target in arm_verify.TARGETS.values():
        result[target["path"]] = {
            "git_blob_sha1": target["blob"],
            "source_sha256": target["sha256"],
        }
    return result


def _verify_dossier_rows(repository_root: Path) -> dict[str, dict[str, str]]:
    snapshot = repository_root / "semantic-snapshots/current"
    archive_path = snapshot / "candidate_review_dossiers.jsonl.gz"
    if hashlib.sha256(archive_path.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("Original compressed dossier archive SHA-256 mismatch")
    queue = read_queue(snapshot)
    dossiers = checked_dossiers(snapshot, queue)
    result = {}
    for item in SOURCES.values():
        path = item["path"]
        row = dossiers.get((REPOSITORY, path))
        if row is None or digest(canonical(row)) != item["dossier_sha256"]:
            raise ValueError(f"Original dossier row SHA-256 mismatch: {path}")
        provenance = row.get("provenance", {})
        if (
            provenance.get("repository") != REPOSITORY
            or provenance.get("pinned_revision") != PIN
            or provenance.get("path") != path
            or provenance.get("git_blob_sha") != item["blob"]
            or provenance.get("source_content_sha256") != item["source_sha256"]
        ):
            raise ValueError(f"Original dossier identity mismatch: {path}")
        result[path] = {
            "row_sha256": item["dossier_sha256"],
            "archive_sha256": ARCHIVE_SHA256,
        }
    return result


def _source_anchor_lines(source_root: Path) -> dict[str, list[dict[str, object]]]:
    result = {}
    for key, anchors in ANCHOR_LINES.items():
        raw = arm_verify.require_source(
            source_root,
            SOURCES[key]["path"],
            SOURCES[key]["blob"],
            SOURCES[key]["source_sha256"],
        )
        notice = " ".join(raw.decode("utf-8").replace("*", " ").split())
        if "Mozilla Public License, v. 2.0." not in notice:
            raise ValueError(f"Expected file-level MPL-2.0 notice missing: {SOURCES[key]['path']}")
        arm_verify.check_anchors(raw, SOURCES[key]["path"], anchors)
        result[key] = [{"line": number, "text": anchor} for number, anchor in anchors]
    return result


def _dependency_identities() -> dict[str, dict[str, str]]:
    return _expected_input_identities()


def compose_report(
    dossier_rows: dict[str, dict[str, str]],
    anchor_lines: dict[str, list[dict[str, object]]],
    compiler_version: str,
) -> dict:
    sources = {}
    for key, item in SOURCES.items():
        sources[item["path"]] = {
            "git_blob_sha1": item["blob"],
            "source_sha256": item["source_sha256"],
            "dossier_row_sha256": dossier_rows[item["path"]]["row_sha256"],
            "dossier_archive_sha256": dossier_rows[item["path"]]["archive_sha256"],
            "line_anchors": anchor_lines[key],
        }
    objections = []
    for objection in OBJECTIONS:
        item = copy.deepcopy(objection)
        item["source"] = sources[SOURCES[item.pop("source_key")]["path"]]
        item["disposition"] = "NEEDS_EVIDENCE"
        item["evidence_status"] = "HOST_UBSAN_COUNTEREXAMPLE_REPRODUCED"
        item["controls"] = [
            {
                "id": control,
                "expected_diagnostic": CONTROL_DIAGNOSTICS[control],
                "result": "EXPECTED_FAILURE_OBSERVED",
            }
            for control in item["controls"]
        ]
        objections.append(item)
    return {
        "schema": SCHEMA,
        "repository": REPOSITORY,
        "pinned_revision": PIN,
        "source_identities": sources,
        "dossier_archive_sha256": ARCHIVE_SHA256,
        "license_evidence": {
            "source_file_notices": "MPL-2.0 notices verified for the three source files",
            "root_license": "Pinned mGBA MPL license verified",
            "distribution_clearance": False,
        },
        "dependency_evidence": {
            "verified_input_identities": _dependency_identities(),
            "pinned_dependency_paths": DEPENDENCY_PATHS,
            "scope": (
                "The registered mGBA ARM review source/dependency identities are pinned; "
                "this does not claim complete build, toolchain, system-header, or distribution closure."
            ),
            "complete_project_closure": False,
        },
        "sanitizer_evidence": {
            "compiler": "gcc",
            "compiler_version": compiler_version,
            "flags": ["-std=c11", "-O1", "-fsanitize=undefined", "-fno-sanitize-recover=undefined"],
            "expected_ubsan_control_ids": sorted(CONTROL_DIAGNOSTICS),
            "native_mgba_execution": False,
            "armv4t_hardware_oracle": False,
            "whole_api_abi_established": False,
        },
        "objections": objections,
        "phase1_gate": "FAIL_INCOMPLETE",
        "gate_contribution": 0,
        "independent_approvals": 0,
        "external_human_approval": False,
    }


def validate_report(report: dict) -> None:
    if set(report) != {
        "schema", "repository", "pinned_revision", "source_identities",
        "dossier_archive_sha256", "license_evidence", "dependency_evidence",
        "sanitizer_evidence", "objections", "phase1_gate", "gate_contribution",
        "independent_approvals", "external_human_approval",
    }:
        raise ValueError("UB package contains unknown or missing claims")
    if report.get("schema") != SCHEMA or report.get("repository") != REPOSITORY:
        raise ValueError("UB package schema or repository mismatch")
    if report.get("pinned_revision") != PIN:
        raise ValueError("UB package source revision mismatch")
    if report.get("dossier_archive_sha256") != ARCHIVE_SHA256:
        raise ValueError("UB package dossier archive identity mismatch")
    if report.get("source_identities") != {
        item["path"]: {
            "git_blob_sha1": item["blob"],
            "source_sha256": item["source_sha256"],
            "dossier_row_sha256": item["dossier_sha256"],
            "dossier_archive_sha256": ARCHIVE_SHA256,
            "line_anchors": report.get("source_identities", {}).get(item["path"], {}).get("line_anchors"),
        }
        for item in SOURCES.values()
    }:
        raise ValueError("UB package source or dossier identity drift")
    for key, item in SOURCES.items():
        anchors = report["source_identities"][item["path"]].get("line_anchors")
        if (
            not isinstance(anchors, list)
            or [anchor.get("text") for anchor in anchors] != ANCHORS[key]
            or [(anchor.get("line"), anchor.get("text")) for anchor in anchors] != ANCHOR_LINES[key]
        ):
            raise ValueError(f"UB package source anchor drift: {item['path']}")
    license_evidence = report.get("license_evidence", {})
    if set(license_evidence) != {"source_file_notices", "root_license", "distribution_clearance"} or (
        license_evidence.get("source_file_notices") != "MPL-2.0 notices verified for the three source files"
        or license_evidence.get("root_license") != "Pinned mGBA MPL license verified"
        or license_evidence.get("distribution_clearance") is not False
    ):
        raise ValueError("Unsupported distribution-license clearance claim")
    dependency = report.get("dependency_evidence", {})
    if dependency.get("verified_input_identities") != _dependency_identities():
        raise ValueError("UB package dependency identity drift")
    if set(dependency) != {
        "verified_input_identities", "pinned_dependency_paths", "scope", "complete_project_closure"
    }:
        raise ValueError("UB package contains unknown dependency claims")
    if dependency.get("pinned_dependency_paths") != DEPENDENCY_PATHS:
        raise ValueError("UB package pinned dependency list drift")
    if any(
        path not in dependency.get("verified_input_identities", {})
        for paths in DEPENDENCY_PATHS.values()
        for path in paths
    ):
        raise ValueError("Unpinned dependency in UB package")
    if (
        dependency.get("complete_project_closure") is not False
        or dependency.get("scope") != (
            "The registered mGBA ARM review source/dependency identities are pinned; "
            "this does not claim complete build, toolchain, system-header, or distribution closure."
        )
    ):
        raise ValueError("Unsupported complete project dependency closure claim")
    sanitizer = report.get("sanitizer_evidence", {})
    if (
        set(sanitizer) != {
            "compiler", "compiler_version", "flags", "expected_ubsan_control_ids",
            "native_mgba_execution", "armv4t_hardware_oracle", "whole_api_abi_established",
        }
        or sanitizer.get("compiler") != "gcc"
        or not isinstance(sanitizer.get("compiler_version"), str)
        or sanitizer.get("flags") != [
            "-std=c11", "-O1", "-fsanitize=undefined", "-fno-sanitize-recover=undefined"
        ]
        or sanitizer.get("native_mgba_execution") is not False
        or sanitizer.get("armv4t_hardware_oracle") is not False
        or sanitizer.get("whole_api_abi_established") is not False
        or sanitizer.get("expected_ubsan_control_ids") != sorted(CONTROL_DIAGNOSTICS)
    ):
        raise ValueError("Unsupported compiler, runtime, ABI, or oracle claim")
    if (
        report.get("phase1_gate") != "FAIL_INCOMPLETE"
        or report.get("gate_contribution") != 0
        or report.get("independent_approvals") != 0
        or report.get("external_human_approval") is not False
    ):
        raise ValueError("UB package cannot change gate or approval state")
    objections = report.get("objections")
    if not isinstance(objections, list) or len(objections) != len(OBJECTIONS):
        raise ValueError("UB package objection set is incomplete")
    for actual, expected in zip(objections, OBJECTIONS):
        if (
            set(actual) != {
                "id", "anchors", "counterexample", "preconditions", "controls",
                "open_issues", "source", "disposition", "evidence_status",
            }
            or actual.get("id") != expected["id"]
            or actual.get("disposition") != "NEEDS_EVIDENCE"
            or actual.get("evidence_status") != "HOST_UBSAN_COUNTEREXAMPLE_REPRODUCED"
            or any(actual.get(field) != expected[field] for field in ("anchors", "counterexample", "preconditions", "open_issues"))
            or actual.get("source") != report["source_identities"][SOURCES[expected["source_key"]]["path"]]
            or [item.get("id") for item in actual.get("controls", [])] != expected["controls"]
            or any(
                item.get("result") != "EXPECTED_FAILURE_OBSERVED"
                or item.get("expected_diagnostic") != CONTROL_DIAGNOSTICS[item["id"]]
                for item in actual.get("controls", [])
            )
        ):
            raise ValueError(f"Invalid or unsupported disposition/evidence for {expected['id']}")


def build_report(source_root: Path, repository_root: Path = ROOT) -> dict:
    arm_verify.verify_packet()
    arm_verify.verify_sources(source_root)
    if arm_verify.run_host_controls(source_root) != len(CONTROL_DIAGNOSTICS):
        raise ValueError("Pinned ARM UBSan controls did not all reproduce")
    dossier_rows = _verify_dossier_rows(repository_root)
    anchors = _source_anchor_lines(source_root)
    compiler = shutil.which("gcc")
    if compiler is None:
        raise RuntimeError("gcc is required for the pinned-source UBSan controls")
    version = subprocess.run(
        [compiler, "--version"], check=True, text=True, capture_output=True
    ).stdout.splitlines()[0]
    report = compose_report(dossier_rows, anchors, version)
    validate_report(report)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = build_report(args.source_root, args.repository_root)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    print("P0_ARM_UB_PACKAGE_PASS objections=3 ubsan_controls=6 approvals=0 gate=FAIL_INCOMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
