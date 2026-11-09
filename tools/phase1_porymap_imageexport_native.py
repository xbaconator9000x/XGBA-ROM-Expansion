#!/usr/bin/env python3
"""Verify pinned Porymap's 4-bit indexed PNG encoder with native Qt."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shlex
import subprocess
import zipfile
from pathlib import Path

PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
REPOSITORY = "huderlem/porymap"
WORKPACK_SHA256 = "5de8d2880a520aa4a80bf0a5b968ba6d19bb0a6a388260a08bd3906b2b4a5cb4"
CANDIDATE_MEMBER = "evidence/candidate_review_dossiers.jsonl.gz"
CANDIDATE_MEMBER_SHA256 = "fe7785c38c7cbd80256ff591dabf1308f06f51f6324b44a743b8b087defd27ac"

FILES = {
    "src/core/imageexport.cpp": {
        "blob": "b57c6dd976fa016f00f7344f00e0cce86cd5f325",
        "sha256": "6766bd924ef9f71a8f432d0304c020cf4b1114ed7f35ad66b785820e69cd1791",
        "row": "7c973a6ad0c38a54a91dcde77dfbaf55dfcf231d8321333af016326129086ebb",
        "bytes": 7274,
        "role": "focal: custom 4-bit indexed PNG chunk and scanline encoder",
    },
    "include/core/imageexport.h": {
        "blob": "d195e47180b0317e22bc1b3ed72f8db7770e0dbf",
        "sha256": "175b3d98f491cfba99ad012b7e9b7c8485016c276d6e54ad138c6f84e78afbd5",
        "row": "cc84e91b7a7cda9df78cb7d6a8fb7399463b381ea639f26552eb6743da8febfd",
        "bytes": 180,
        "role": "focal: public encoder declaration",
    },
    "src/ui/tileseteditor.cpp": {
        "blob": "723a2afdeb89c1752e9811a07715462c2279c645",
        "sha256": "a85e7827754d3f08cec5ebe90aa7a737958524ac379d563adfd269d1b7557ced",
        "row": "940f1b1723b84449dbc3f20648e057643c96d9be19a08e9fa210746193a35ee7",
        "bytes": 62438,
        "role": "caller context only: sole indexed tile-image export callsite; not re-reviewed",
    },
    "porymap.pro": {
        "blob": "53d8055ecfe5d88afb6f183b82d4a3472727ad4f",
        "sha256": "cff608e64a2d610ea029d199c2be3b50b7941437b62c80fa3eaffdba70de2996",
        "row": "93059d533a8cc5a5cc0fbe774b64bd8bf83ff107344a870cace53d6d96cf35e2",
        "bytes": 10630,
        "role": "build context only: application source list and Qt modules",
    },
    "include/log.h": {
        "blob": "abe85d356045e657efc79fea2f03370879762549",
        "sha256": "d3f4f498bcf797394cebb69be2d3a7e125a08f8c101ea2c34c20fff12ca2403e",
        "row": "4cdf4dac638e7b5eff37254062c1e347da5b6700de212495668f411dd8df8d09",
        "bytes": 621,
        "role": "dependency context: logError declaration; test supplies a test-only implementation",
    },
    "LICENSE.md": {
        "blob": "65c5ca88a67c30becee01c5a8816d964b03862f9",
        "sha256": "da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768",
        "row": "a620cf8ec560f8bf6f54e9d96403ec1cb204f3ddad7fef812ce7893059396986",
        "bytes": 7651,
        "role": "license context only: LGPL-3.0 notice, not a distribution conclusion",
    },
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def verify_identity(path: str, data: bytes) -> dict[str, object]:
    expected = FILES[path]
    require(len(data) == expected["bytes"], f"{path}: byte length mismatch")
    require(git_blob_sha(data) == expected["blob"], f"{path}: Git blob mismatch")
    require(sha256(data) == expected["sha256"], f"{path}: full-byte SHA-256 mismatch")
    return {
        "path": path,
        "git_blob_sha1": expected["blob"],
        "full_source_sha256": expected["sha256"],
        "original_dossier_row_sha256": expected["row"],
        "bytes": expected["bytes"],
        "role": expected["role"],
    }


def verify_workpack(workpack: Path) -> dict[str, object]:
    require(sha256(workpack.read_bytes()) == WORKPACK_SHA256, "workpack SHA-256 mismatch")
    with zipfile.ZipFile(workpack) as archive:
        require(CANDIDATE_MEMBER in archive.namelist(), "candidate dossier member missing")
        candidate_bytes = archive.read(CANDIDATE_MEMBER)
    require(sha256(candidate_bytes) == CANDIDATE_MEMBER_SHA256, "candidate dossier member hash mismatch")

    rows_by_path: dict[str, list[tuple[str, dict[str, object]]]] = {}
    for line in gzip.decompress(candidate_bytes).splitlines():
        row = json.loads(line)
        provenance = row.get("provenance", {})
        if (
            provenance.get("repository") == REPOSITORY
            and provenance.get("pinned_revision") == PIN
            and provenance.get("path") in FILES
        ):
            path = provenance["path"]
            rows_by_path.setdefault(path, []).append((sha256(line), provenance))

    for path, expected in FILES.items():
        matches = rows_by_path.get(path, [])
        require(len(matches) == 1, f"{path}: expected exactly one original dossier row, got {len(matches)}")
        row_hash, provenance = matches[0]
        require(row_hash == expected["row"], f"{path}: original dossier row hash mismatch")
        require(provenance.get("git_blob_sha") == expected["blob"], f"{path}: dossier blob mismatch")
        require(provenance.get("tracked_bytes") == str(expected["bytes"]), f"{path}: dossier byte count mismatch")
        if provenance.get("source_content_sha256") is not None:
            require(provenance["source_content_sha256"] == expected["sha256"], f"{path}: dossier source hash mismatch")

    return {
        "workpack_sha256": WORKPACK_SHA256,
        "candidate_dossier_member": CANDIDATE_MEMBER,
        "candidate_dossier_member_sha256": CANDIDATE_MEMBER_SHA256,
        "original_rows_verified": len(FILES),
    }


def verify_source_tree(source_root: Path, workpack: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    head = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    require(head == PIN, f"unexpected Porymap revision: {head}")

    identities = []
    sources: dict[str, bytes] = {}
    for path in FILES:
        data = (source_root / path).read_bytes()
        identities.append(verify_identity(path, data))
        sources[path] = data

    project = sources["porymap.pro"].decode()
    require("src/core/imageexport.cpp" in project, "porymap.pro does not build the focal implementation")
    require("include/core/imageexport.h" in project, "porymap.pro does not list the focal API")
    callers = subprocess.run(
        ["git", "-C", str(source_root), "grep", "-n", "exportIndexed4BPPPng", PIN],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    caller_paths = [line.split(":", 2)[1] for line in callers]
    require(
        sorted(caller_paths)
        == [
            "include/core/imageexport.h",
            "src/core/imageexport.cpp",
            "src/ui/tileseteditor.cpp",
        ],
        "pinned encoder declaration/implementation/callsite closure changed",
    )
    require("void logError(const QString &message);" in sources["include/log.h"].decode(), "logError declaration missing")
    pack_record = verify_workpack(workpack)
    pack_record["source_pin"] = PIN
    pack_record["repository"] = REPOSITORY
    return identities, pack_record


def validate_native_result(result: dict[str, object]) -> None:
    require(result.get("even_width_roundtrip") is True, "positive even-width indexed PNG round-trip failed")
    require(result.get("png_bit_depth") == 4, "positive output is not 4-bit PNG")
    require(result.get("png_color_type") == 3, "positive output is not indexed-color PNG")
    require(result.get("odd_width_file_nonempty") is True, "odd-width output was not produced")
    require(result.get("odd_width_roundtrip") is False, "pinned odd-width scanline mismatch was not reproduced")
    require(result.get("null_image_logged") is True, "null-image negative control did not log an error")
    require(result.get("null_image_no_file") is True, "null-image negative control created an output file")
    require(result.get("phase1_gate") == "FAIL_INCOMPLETE", "native record changed the Phase 1 gate")
    require(result.get("independent_approvals") == 0, "native record claims an approval")


def self_test(source_root: Path) -> dict[str, int]:
    source_mutations_rejected = 0
    evidence_mutations_rejected = 0
    for path in ("src/core/imageexport.cpp", "include/core/imageexport.h"):
        source = (source_root / path).read_bytes()
        mutated = bytes([source[0] ^ 1]) + source[1:]
        try:
            verify_identity(path, mutated)
        except ValueError:
            source_mutations_rejected += 1
        else:
            raise ValueError(f"source identity mutation was accepted: {path}")

    good = {
        "even_width_roundtrip": True,
        "png_bit_depth": 4,
        "png_color_type": 3,
        "odd_width_file_nonempty": True,
        "odd_width_roundtrip": False,
        "null_image_logged": True,
        "null_image_no_file": True,
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_approvals": 0,
    }
    for key, value in (
        ("even_width_roundtrip", False),
        ("png_bit_depth", 8),
        ("odd_width_roundtrip", True),
        ("null_image_no_file", False),
        ("phase1_gate", "PASS"),
        ("independent_approvals", 1),
    ):
        mutated = dict(good)
        mutated[key] = value
        try:
            validate_native_result(mutated)
        except ValueError:
            evidence_mutations_rejected += 1
        else:
            raise ValueError(f"evidence mutation was accepted: {key}")
    return {
        "source_mutations_rejected": source_mutations_rejected,
        "evidence_mutations_rejected": evidence_mutations_rejected,
    }


def compile_harness(source_root: Path, harness: Path, build_dir: Path) -> Path:
    build_dir.mkdir(parents=True, exist_ok=True)
    binary = build_dir / "phase1-porymap-imageexport-native"
    flags = subprocess.run(
        ["pkg-config", "--cflags", "--libs", "Qt6Core", "Qt6Gui", "Qt6Widgets"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    command = [
        os.environ.get("CXX", "c++"),
        "-std=c++17",
        "-Wall",
        "-Wextra",
        "-fPIC",
        f"-I{source_root / 'include/core'}",
        f"-I{source_root / 'include'}",
        str(harness),
        str(source_root / "src/core/imageexport.cpp"),
        *shlex.split(flags),
        "-o",
        str(binary),
    ]
    subprocess.run(command, check=True)
    return binary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--workpack", type=Path, required=True)
    parser.add_argument("--harness", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    identities, inventory = verify_source_tree(args.source_root, args.workpack)
    controls = self_test(args.source_root) if args.self_test else {}
    binary = compile_harness(args.source_root, args.harness, args.build_dir)
    run = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
    prefix = "PHASE1_IMAGEEXPORT_RESULT="
    lines = [line[len(prefix):] for line in run.stdout.splitlines() if line.startswith(prefix)]
    require(len(lines) == 1, "expected exactly one native image-export record")
    native = json.loads(lines[0])
    validate_native_result(native)

    report = {
        "schema": "phase1-porymap-imageexport-native-v1",
        "repository": REPOSITORY,
        "source_pin": PIN,
        "source_identities": identities,
        "candidate_inventory": inventory,
        "build_edges": {
            "application_project": "porymap.pro compiles src/core/imageexport.cpp",
            "direct_caller": "src/ui/tileseteditor.cpp (caller context only; already inventoried elsewhere)",
            "logger": "include/log.h::logError, replaced only by the test executable's stub",
            "license": "Pinned root LGPL-3.0 text; no distribution-compliance conclusion",
        },
        "native": native,
        "controls": controls,
        "finding": (
            "The unchanged encoder carries its nibble-pair counter across scanlines; "
            "the pinned odd-width 3x2 indexed image does not round-trip."
        ),
        "limits": [
            "The native harness compiles the original encoder and header, not the full Porymap GUI.",
            "The only caller is provenance/build context, not a new semantic review of tileseteditor.cpp.",
            "No write-failure, image-provider, project, ROM, gameplay, or hardware behavior is tested.",
            "This is evidence input, not independent whole-file approval.",
        ],
        "disposition": "NEEDS_EVIDENCE",
        "independent_approvals": 0,
        "phase1_gate": "FAIL_INCOMPLETE",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("Pinned Porymap 4-bit indexed PNG native evidence recorded; no approval")


if __name__ == "__main__":
    main()
