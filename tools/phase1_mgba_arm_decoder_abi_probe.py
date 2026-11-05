#!/usr/bin/env python3
"""Probe the pinned ARM instruction record layout with host and ARM-target Clang."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from phase1_bulk_triage import canonical, digest
from phase1_mgba_arm_decode_emit_review_verify import git_blob, require_source

ROOT = Path(__file__).resolve().parents[1]
PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
REPO = "mgba-emu/mgba"
SOURCE = "include/mgba/internal/arm/decoder.h"
SOURCE_BLOB = "f6e19769884054b42b5fb77988b156d48b1c6489"
SOURCE_SHA256 = "d67f8d528e3d7090878df4c9d44cb4b1cdf1f5af0a68ae89a631c35b4ae39729"
DOSSIER_SHA256 = "69bf00c7af7ef592cc5d115ebd892095fc4b55150a6690e299fcafec047f9f3e"
ARCHIVE_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
DEPENDENCIES = {
    "include/mgba-util/common.h": (
        "923e93086adfa09c9a55fcc2f0f6fa4d560e5888",
        "ec13354a050e4a7432232214b9991dd74000980ab2b8949389af0871cc1b799f",
    ),
    "include/mgba/internal/arm/arm.h": (
        "5ef2da96519ac3f429b65fd6d323be0775f3b3cf",
        "47822ffc4592230f6045dd2d8677dec5d72f518bff0b42e15ff26b5c77330bef",
    ),
    "LICENSE": (
        "14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e",
        "fab3dd6bdab226f1c08630b1dd917e11fcb4ec5e1e020e2c16f83a0a13863e85",
    ),
}
EXPECTED_LAYOUT = {
    "size": 40,
    "alignment": 4,
    "bitfields": {
        "execMode": "32:0-0",
        "traps": "32:1-1",
        "affectsCPSR": "32:2-2",
        "branchType": "32:3-5",
        "condition": "32:6-9",
        "mnemonic": "33:2-7",
        "iCycles": "34:0-2",
        "cCycles": "34:3-6",
        "sInstructionCycles": "34:7-10",
        "nInstructionCycles": "35:3-6",
        "sDataCycles": "36:0-9",
        "nDataCycles": "37:2-11",
    },
}
SCHEMA = "xgba.phase1.mgba_arm_decoder_abi_probe.v1"


def _verify_dossier_row(repository_root: Path) -> None:
    snapshot = repository_root / "semantic-snapshots/current"
    archive = snapshot / "candidate_review_dossiers.jsonl.gz"
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("Original compressed dossier archive SHA-256 mismatch")
    queue_path = snapshot / "semantic_review_queue.csv.gz"
    with gzip.open(queue_path, "rt", encoding="utf-8", newline="") as stream:
        queue = list(csv.DictReader(stream))
    matches = [
        (index, row) for index, row in enumerate(queue)
        if (row.get("repo"), row.get("path")) == (REPO, SOURCE)
    ]
    if len(matches) != 1:
        raise ValueError("Pinned decoder dossier queue row is missing or duplicated")
    row_index, queue_row = matches[0]
    with gzip.open(archive, "rt", encoding="utf-8") as stream:
        for index, line in enumerate(stream):
            if index == row_index:
                dossier = json.loads(line)
                break
        else:
            raise ValueError("Pinned decoder dossier row is missing from original archive")
    _check_dossier_row(queue_row, dossier)


def _check_dossier_row(queue_row: dict, dossier: dict) -> None:
    provenance = dossier.get("provenance", {})
    if (
        queue_row.get("category") != "source"
        or queue_row.get("priority") != "P0"
        or queue_row.get("machine_review_status") != "CANDIDATE_ONLY_SOURCE_HASH_VERIFIED"
        or dossier.get("review", {}).get("semantic_signoff") is not False
    ):
        raise ValueError("Decoder record is not an unapproved source-only candidate")
    if digest(canonical(dossier)) != DOSSIER_SHA256 or queue_row.get("evidence_sha256") != DOSSIER_SHA256:
        raise ValueError("Original decoder dossier row SHA-256 mismatch")
    if (
        queue_row.get("blob_sha") != SOURCE_BLOB
        or (provenance.get("repository"), provenance.get("pinned_revision"),
            provenance.get("path"), provenance.get("git_blob_sha"))
        != (REPO, PIN, SOURCE, SOURCE_BLOB)
        or provenance.get("source_content_sha256") != SOURCE_SHA256
    ):
        raise ValueError("Original decoder dossier identity mismatch")


def verify_pinned_inputs(source_root: Path, repository_root: Path = ROOT) -> dict:
    try:
        commit = subprocess.check_output(
            ["git", "-C", str(source_root), "rev-parse", "HEAD"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("Pinned mGBA Git checkout HEAD is unavailable") from exc
    if commit != PIN:
        raise ValueError("mGBA source checkout is not the exact pinned revision")
    source = require_source(source_root, SOURCE, SOURCE_BLOB, SOURCE_SHA256)
    notice = " ".join(source.decode("utf-8").replace("*", " ").split())
    if "Mozilla Public License, v. 2.0." not in notice:
        raise ValueError("Pinned decoder header MPL-2.0 notice is missing")
    dependency_hashes = {}
    for path, (blob, source_sha) in DEPENDENCIES.items():
        raw = require_source(source_root, path, blob, source_sha)
        if path != "LICENSE":
            notice = " ".join(raw.decode("utf-8").replace("*", " ").split())
            if "Mozilla Public License, v. 2.0." not in notice:
                raise ValueError(f"Pinned dependency MPL-2.0 notice is missing: {path}")
        dependency_hashes[path] = {"git_blob_sha1": git_blob(raw), "sha256": source_sha}
    if b"Mozilla Public License" not in require_source(
        source_root, "LICENSE", *DEPENDENCIES["LICENSE"]
    ):
        raise ValueError("Pinned mGBA root license is not MPL")
    _verify_dossier_row(repository_root)
    return {
        "revision": commit,
        "source": {
            "path": SOURCE,
            "git_blob_sha1": SOURCE_BLOB,
            "sha256": hashlib.sha256(source).hexdigest(),
            "line_count": len(source.splitlines()),
        },
        "dossier": {
            "archive_sha256": ARCHIVE_SHA256,
            "row_sha256": DOSSIER_SHA256,
        },
        "license": "MPL-2.0 file notice and pinned root license verified; distribution clearance not assessed",
        "dependencies": dependency_hashes,
    }


def parse_record_layout(output: str) -> dict:
    lines = output.splitlines()
    starts = [i for i, line in enumerate(lines) if line.rstrip().endswith("| struct ARMInstructionInfo")]
    if len(starts) != 1:
        raise ValueError("Expected exactly one ARMInstructionInfo record layout")
    section = []
    for line in lines[starts[0]:]:
        if section and line.strip().startswith("0 | struct "):
            break
        section.append(line)
        if "[sizeof=" in line:
            break
    size_match = re.search(r"\[sizeof=(\d+), align=(\d+)\]", "\n".join(section))
    if not size_match:
        raise ValueError("ARMInstructionInfo size/alignment is absent")
    bitfields = {}
    for line in section:
        match = re.match(r"\s*(\d+:\d+-\d+)\s*\|\s*[^|]*?\b([A-Za-z_]\w*)\s*$", line)
        if match:
            bitfields[match.group(2)] = match.group(1)
    observed = {
        "size": int(size_match.group(1)),
        "alignment": int(size_match.group(2)),
        "bitfields": {name: bitfields.get(name) for name in EXPECTED_LAYOUT["bitfields"]},
    }
    if observed != EXPECTED_LAYOUT:
        raise ValueError("ARMInstructionInfo layout differs from the pinned expected ABI facts")
    return observed


def _compiler_layout(clang: str, target: str, source_root: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="xgba-arm-abi-") as directory:
        root = Path(directory)
        stubs = root / "stubs"
        common = stubs / "mgba-util/common.h"
        arm = stubs / "mgba/internal/arm/arm.h"
        common.parent.mkdir(parents=True)
        arm.parent.mkdir(parents=True)
        common.write_text(
            "#include <stdbool.h>\n#include <stdint.h>\n"
            "#define CXX_GUARD_START\n#define CXX_GUARD_END\n",
            encoding="utf-8",
        )
        arm.write_text("struct ARMRegisterFile;\n", encoding="utf-8")
        probe = root / "layout.c"
        probe.write_text(
            "#include <mgba/internal/arm/decoder.h>\n"
            "struct ARMInstructionInfo layout_probe;\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                clang, "-target", target, "-ffreestanding", "-std=c11",
                f"-I{stubs}", f"-I{source_root / 'include'}",
                "-Xclang", "-fdump-record-layouts-complete", "-fsyntax-only", str(probe),
            ],
            check=False, capture_output=True, text=True,
        )
        if result.returncode:
            raise RuntimeError(f"Clang layout probe failed for {target}: {result.stderr.strip()}")
        return parse_record_layout(result.stdout + result.stderr)


def build_report(source_root: Path, repository_root: Path = ROOT) -> dict:
    provenance = verify_pinned_inputs(source_root, repository_root)
    clang = shutil.which("clang")
    if clang is None:
        raise RuntimeError("clang is required for the pinned C11 target-layout probe")
    host = _compiler_layout(clang, "x86_64-unknown-linux-gnu", source_root)
    target = _compiler_layout(clang, "armv4t-none-eabi", source_root)
    if host != target:
        raise ValueError("Host and ARM-target Clang record layouts differ")
    return {
        "schema": SCHEMA,
        "objection_id": "arm_decoder_instruction_info_target_abi_layout",
        "scope": "ARMInstructionInfo record layout and bitfield placement only",
        "provenance": provenance,
        "compiler": {"name": Path(clang).name, "host_target": "x86_64-unknown-linux-gnu",
                     "arm_target": "armv4t-none-eabi"},
        "before": {
            "disposition": "NEEDS_EVIDENCE",
            "evidence": "ARMInstructionInfo C bitfield layout had host-only compile evidence",
        },
        "after": {
            "disposition": "NEEDS_EVIDENCE",
            "evidence": "Exact pinned header layout matches under this Clang host and ARMv4T-target frontend",
            "host_layout": host,
            "arm_target_layout": target,
        },
        "objections_remaining": [
            "The complete ARM API ABI and runtime behavior are not established by this isolated structure layout.",
            "Independent ARMv4T hardware or architectural-oracle comparison is still absent.",
            "Signed shifts, signed conversion/right-shift portability, INT32_MIN negation, and typed video backing remain outside this probe.",
        ],
        "gate_contribution": 0,
        "gate_mutated": False,
        "approval_counts_mutated": False,
        "independent_approval": False,
        "external_human_approval": False,
        "limitations": [
            "This is a compiler record-layout probe, not execution on ARMv4T hardware.",
            "It uses minimal shims for common.h and arm.h because the measured record depends only on fixed-width integer and boolean types; it does not clear the complete ARM API ABI or dependency closure.",
            "Agreement from one Clang version does not establish GCC or all AAPCS toolchain behavior.",
            "The other five listed ARM objections remain NEEDS_EVIDENCE.",
            "The root MPL license and header notice are source evidence, not combined-distribution clearance.",
        ],
    }


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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
