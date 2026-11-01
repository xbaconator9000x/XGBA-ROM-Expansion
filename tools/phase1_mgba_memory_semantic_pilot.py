#!/usr/bin/env python3
"""Build a source-index pilot; never create semantic dispositions or approvals."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from phase1_bulk_triage import PINS, TOTAL, canonical, checked_dossiers, digest, git_blob, read_queue

ROOT = Path(__file__).resolve().parents[1]
MGBA = "mgba-emu/mgba"
FIRERED = "pret/pokefirered"
SNAPSHOT_BLOBS = {
    "candidate_review_dossiers.jsonl.gz": "3b982876c7d810a827af8c80c7e5d9231fdaa327",
    "semantic_review_queue.csv.gz": "52fe1a9b8498dd4fa3ea0e6e0236ae1cdeda7268",
    "phase1_mapping_gate.json": "dab5789433dc55cf325a917a220d060088bf1d29",
}

SOURCES = (
    {
        "path": "include/mgba/internal/gba/memory.h",
        "blob": "0aad912613e726560d06bbdbf6061986e69e5842",
        "role": "GBA ROM window constants",
        "anchors": {
            "rom_window_bases": r"GBA_BASE_ROM[012]\s*=\s*0x0[8AC]000000",
            "rom_window_size": r"GBA_SIZE_ROM0\s*=\s*0x02000000",
        },
    },
    {
        "path": "src/gba/gba.c",
        "blob": "c30bd943909dc00df0b5b9932e6d9ddb6e1c404e",
        "role": "GBA ROM load and patch implementation",
        "anchors": {
            "large_rom_path": r"if\s*\(gba->pristineRomSize\s*>\s*GBA_SIZE_ROM0\)",
            "large_rom_size_cap": r"gba->pristineRomSize\s*=\s*GBA_SIZE_ROM0",
            "patch_size_cap": r"patchedSize\s*>\s*GBA_SIZE_ROM0",
        },
    },
    {
        "path": "src/gba/memory.c",
        "blob": "aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc",
        "role": "GBA memory region dispatch and ROM reads",
        "anchors": {
            "shared_rom_region": r"cpu->memory\.activeRegion\s*=\s*memory->rom",
            "shared_rom_mask": r"cpu->memory\.activeMask\s*=\s*memory->romMask",
            "rom_address_mask": r"address\s*&\s*\(GBA_SIZE_ROM0\s*-\s*1\)",
        },
    },
    {
        "path": "src/gba/core.c",
        "blob": "6bfc518bb8899205c07d1d0fc091a287cb42f874",
        "role": "GBA core memory-block descriptors",
        "anchors": {
            "waitstate_window_descriptors": r'"cart[012]"',
            "rom_block_size": r'"Game Pak \(32MiB\)"',
        },
    },
    {
        "path": "src/gba/CMakeLists.txt",
        "blob": "71ab7bbb199ad95422e35ded5774c06a1b2e7c5c",
        "role": "GBA source and test manifest",
        "anchors": {
            "test_source_list": r"set\(TEST_FILES",
            "test_export": r"export_directory\(GBA_TEST TEST_FILES\)",
        },
    },
    {
        "path": "src/gba/test/core.c",
        "blob": "25b8f3ce30b59c3ecde8ecb377ea80964888b0ae",
        "role": "Existing GBA core test source",
        "anchors": {
            "null_rom_test": r"M_TEST_DEFINE\(loadNullROM\)",
            "null_rom_assertion": r"assert_false\(core->loadROM\(core,\s*NULL\)\)",
            "registered_null_rom_test": r"cmocka_unit_test\(loadNullROM\)",
        },
    },
    {
        "path": "LICENSE",
        "blob": "14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e",
        "role": "Pinned upstream license text",
        "anchors": {"mpl2_title": r"Mozilla Public License Version 2\.0"},
    },
    {
        "repository": FIRERED,
        "path": "Makefile",
        "blob": "8b454dbd18eb0069fa5851d788697190890a5b37",
        "role": "FireRed ROM build and linker-script selection",
        "anchors": {
            "rom_output": r"ROM\s*:=\s*poke\$\(BUILD_NAME\)\.gba",
            "original_linker_selection": r"LD_SCRIPT\s*:=\s*ld_script\.ld",
            "pad_to_address": r"--pad-to\s+0x9000000",
        },
    },
    {
        "repository": FIRERED,
        "path": "ld_script.ld",
        "blob": "9a4b45031e93c1e1da8186d8c697332710526048",
        "role": "FireRed original ROM linker region",
        "anchors": {
            "rom_origin": r"ROM\s+\(rx\)\s*:\s*ORIGIN\s*=\s*0x8000000",
            "rom_length": r"ROM\s+\(rx\)\s*:\s*ORIGIN\s*=\s*0x8000000,\s*LENGTH\s*=\s*32M",
        },
    },
)

REFERENCES = (
    {
        "id": "GBATEK",
        "url": "https://mgba-emu.github.io/gbatek/",
        "scope": "GBA hardware memory map and cartridge context",
        "retrieval": "UNVERIFIED_EXTERNAL_REFERENCE_ONLY",
        "content_sha256": None,
        "used_to_support_pilot_claim": False,
    },
    {
        "id": "NBA_HW_DOCS",
        "url": "https://nba-emu.github.io/hw-docs/",
        "scope": "GBA hardware documentation and known discrepancies",
        "retrieval": "UNVERIFIED_EXTERNAL_REFERENCE_ONLY",
        "content_sha256": None,
        "used_to_support_pilot_claim": False,
    },
)

REQUIRED_DOC_IDS = {item["id"] for item in REFERENCES}
REQUIRED_TEST_PATH = "src/gba/test/core.c"
REQUIRED_LICENSE_PATH = "LICENSE"


def _read_source(source_root: Path, spec: dict) -> bytes:
    path = source_root / spec["path"]
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"Missing pinned source file: {spec['path']}") from exc
    actual = git_blob(content)
    if actual != spec["blob"]:
        raise ValueError(f"Pinned source drift: {spec['path']} ({actual})")
    return content


def _anchors(content: bytes, patterns: dict[str, str], path: str) -> dict:
    lines = content.decode("utf-8", "strict").splitlines()
    result = {}
    for name, pattern in patterns.items():
        hits = [number for number, line in enumerate(lines, 1) if re.search(pattern, line)]
        if not hits:
            raise ValueError(f"Missing source anchor {name}: {path}")
        result[name] = hits
    return result


def validate_references(references: list[dict], claimed_document_ids: set[str]) -> None:
    by_id = {reference.get("id"): reference for reference in references}
    if set(by_id) != REQUIRED_DOC_IDS or len(by_id) != len(references):
        raise ValueError("Unknown, missing, or duplicate external documentation reference")
    if claimed_document_ids - set(by_id):
        raise ValueError("Claim cites ungrounded external documentation")
    for reference in references:
        if reference.get("used_to_support_pilot_claim"):
            checksum = reference.get("content_sha256")
            if not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum):
                raise ValueError("External documentation claim lacks retrieved content hash")
            if reference.get("retrieval") != "RETRIEVED_AND_HASHED":
                raise ValueError("External documentation claim is not verified")


def validate_coverage(source_by_path: dict[str, bytes]) -> None:
    if REQUIRED_TEST_PATH not in source_by_path:
        raise ValueError("Missing upstream test evidence")
    test_text = source_by_path[REQUIRED_TEST_PATH].decode("utf-8")
    if not all(
        re.search(pattern, test_text)
        for pattern in SOURCES[5]["anchors"].values()
    ):
        raise ValueError("Required upstream test case is absent or unregistered")
    manifest = source_by_path["src/gba/CMakeLists.txt"].decode("utf-8")
    if not re.search(r"test/core\.c", manifest):
        raise ValueError("GBA core tests are not present in the pinned test manifest")


def validate_license(source_by_path: dict[str, bytes]) -> None:
    license_text = source_by_path.get(REQUIRED_LICENSE_PATH)
    if not license_text:
        raise ValueError("Missing pinned license evidence")
    if b"Mozilla Public License Version 2.0" not in license_text:
        raise ValueError("Pinned license evidence is not MPL-2.0")
    for spec in SOURCES:
        if spec["path"].endswith(".c"):
            content = source_by_path[spec["path"]]
            if b"Mozilla Public" not in content or b"License, v. 2.0." not in content:
                raise ValueError(f"Missing per-file MPL notice: {spec['path']}")


def _source_records(snapshot: Path, source_roots: dict[str, Path]) -> tuple[list[dict], dict[str, bytes]]:
    for name, expected_blob in SNAPSHOT_BLOBS.items():
        path = snapshot / name
        if git_blob(path.read_bytes()) != expected_blob:
            raise ValueError(f"Original machine snapshot drift: {name}")

    gate = json.loads((snapshot / "phase1_mapping_gate.json").read_text(encoding="utf-8"))
    if (
        gate.get("decision") != "FAIL_INCOMPLETE"
        or gate.get("approved_semantic_dispositions") != 0
        or gate.get("p0_review_candidates") != 338
        or gate.get("machine_generated_dossiers") != TOTAL
    ):
        raise ValueError("Authoritative Phase 1 gate changed; stop and reconcile")

    queue = read_queue(snapshot)
    dossiers = checked_dossiers(snapshot, queue)
    queue_by_identity = {
        (record["repo"], record["path"]): record for record in queue
    }

    records = []
    contents_by_path = {}
    for spec in SOURCES:
        repository = spec.get("repository", MGBA)
        pin = PINS[repository]
        source_root = source_roots.get(repository)
        if source_root is None:
            raise ValueError(f"Missing pinned source root: {repository}")
        content = _read_source(source_root, spec)
        contents_by_path[f"{repository}:{spec['path']}"] = content
        machine = queue_by_identity.get((repository, spec["path"]))
        dossier = dossiers.get((repository, spec["path"]))
        if not machine or not dossier:
            raise ValueError(f"Missing original machine dossier: {spec['path']}")
        if (
            machine["blob_sha"] != spec["blob"]
            or digest(canonical(dossier)) != machine["evidence_sha256"]
        ):
            raise ValueError(f"Source/dossier binding mismatch: {spec['path']}")
        source_sha256 = hashlib.sha256(content).hexdigest()
        dossier_source_sha256 = dossier["provenance"].get("source_content_sha256")
        if str(dossier["provenance"].get("tracked_bytes")) != str(len(content)):
            raise ValueError(f"Source bytes disagree with original dossier: {spec['path']}")
        if dossier_source_sha256 is None and spec["path"] != REQUIRED_LICENSE_PATH:
            raise ValueError(f"Original dossier omitted source hash: {spec['path']}")
        if dossier_source_sha256 is not None and dossier_source_sha256 != source_sha256:
            raise ValueError(f"Source bytes disagree with original dossier: {spec['path']}")
        if dossier.get("review", {}).get("semantic_signoff") is not False:
            raise ValueError(f"Machine dossier unexpectedly claims approval: {spec['path']}")
        records.append({
            "identity": {
                "repository": repository,
                "pinned_commit": pin,
                "path": spec["path"],
                "git_blob_sha1": spec["blob"],
                "source_sha256": source_sha256,
                "source_bytes": len(content),
                "source_lines": len(content.splitlines()),
            },
            "machine_dossier": {
                "sha256": machine["evidence_sha256"],
                "source_content_sha256": dossier_source_sha256,
                "original_compressed_archive_git_blob_sha1":
                    SNAPSHOT_BLOBS["candidate_review_dossiers.jsonl.gz"],
                "signoff": False,
            },
            "role": spec["role"],
            "source_line_anchors": _anchors(content, spec["anchors"], spec["path"]),
        })
    gba_sources = {
        spec["path"]: contents_by_path[f"{MGBA}:{spec['path']}"]
        for spec in SOURCES if spec.get("repository", MGBA) == MGBA
    }
    validate_coverage(gba_sources)
    validate_license(gba_sources)
    return records, contents_by_path


def _dependency_edges(source_by_path: dict[str, bytes]) -> list[dict]:
    indexed = {
        (spec.get("repository", MGBA), spec["path"]) for spec in SOURCES
    }
    edges = []
    for source_identity, content in source_by_path.items():
        repository, path = source_identity.split(":", 1)
        if not path.endswith((".c", ".h")):
            continue
        for line_number, raw in enumerate(content.decode("utf-8").splitlines(), 1):
            match = re.match(r'\s*#\s*include\s*[<"]([^>"]+)[>"]', raw)
            if not match:
                continue
            included = match.group(1)
            for target_repository, target in indexed:
                include_target = target.removeprefix("include/")
                if (
                    repository == target_repository
                    and (included == target or included == include_target)
                ):
                    edges.append({
                        "from": source_identity,
                        "to": f"{target_repository}:{target}",
                        "kind": "pinned_direct_include",
                        "line": line_number,
                    })

    cmake = source_by_path[f"{MGBA}:src/gba/CMakeLists.txt"].decode("utf-8")
    for variable, kind in (("SOURCE_FILES", "build_source_member"), ("TEST_FILES", "build_test_member")):
        match = re.search(rf"set\({variable}\s+(.*?)\)", cmake, re.DOTALL)
        if not match:
            raise ValueError(f"Missing pinned CMake {variable} declaration")
        for member in re.findall(r"[A-Za-z0-9_./-]+", match.group(1)):
            path = "src/gba/" + member
            if (MGBA, path) in indexed:
                edges.append({
                    "from": f"{MGBA}:src/gba/CMakeLists.txt",
                    "to": f"{MGBA}:{path}",
                    "kind": kind,
                })
    firered_makefile = source_by_path[f"{FIRERED}:Makefile"].decode("utf-8")
    if not re.search(r"LD_SCRIPT\s*:=\s*ld_script\.ld", firered_makefile):
        raise ValueError("Pinned FireRed Makefile does not select indexed linker script")
    edges.append({
        "from": f"{FIRERED}:Makefile",
        "to": f"{FIRERED}:ld_script.ld",
        "kind": "linker_script_selection",
    })
    unique = {(edge["from"], edge["to"], edge["kind"], edge.get("line")): edge for edge in edges}
    if not any(edge["kind"] == "build_test_member" for edge in unique.values()):
        raise ValueError("Pinned build manifest has no indexed test dependency edge")
    return sorted(unique.values(), key=lambda edge: (
        edge["from"], edge["to"], edge["kind"], edge.get("line", 0)
    ))


def build(snapshot: Path, source_roots: dict[str, Path], output: Path | None = None) -> dict:
    records, source_by_path = _source_records(snapshot, source_roots)
    validate_references(list(REFERENCES), set())
    paths = {record["identity"]["path"]: record for record in records}

    invariants = [
        {
            "id": "rom-window-and-size-constants",
            "evidence_level": "PINNED_SOURCE",
            "members": ["include/mgba/internal/gba/memory.h", "src/gba/core.c"],
            "observation": "The source names three 32 MiB ROM waitstate windows.",
        },
        {
            "id": "shared-rom-backing-for-waitstate-regions",
            "evidence_level": "PINNED_SOURCE",
            "members": ["src/gba/memory.c"],
            "observation": "The six ROM region selectors install the same ROM pointer and mask.",
        },
        {
            "id": "loader-and-patch-size-boundary",
            "evidence_level": "PINNED_SOURCE",
            "members": ["src/gba/gba.c"],
            "observation": (
                "The >32 MiB loader path clamps the ordinary mapping boundary; "
                "patch outputs above 32 MiB are rejected. Special header handling remains."
            ),
        },
        {
            "id": "firered-producer-linker-boundary",
            "evidence_level": "PINNED_SOURCE",
            "members": ["Makefile", "ld_script.ld"],
            "observation": (
                "The pinned FireRed original build selects ld_script.ld, whose ROM region "
                "starts at 0x08000000 with LENGTH=32M; Makefile uses objcopy --pad-to "
                "0x9000000. This does not prove an XGBA expanded-ROM build."
            ),
        },
        {
            "id": "existing-test-coverage-and-gap",
            "evidence_level": "UPSTREAM_TEST_SOURCE_ONLY",
            "members": ["src/gba/CMakeLists.txt", REQUIRED_TEST_PATH],
            "observation": (
                "A registered loadNullROM test checks null-input rejection; it does not "
                "test ROM-window aliasing or the 32 MiB/32 MiB+1 loader and patch boundary."
            ),
        },
    ]
    for invariant in invariants:
        if any(member not in paths for member in invariant["members"]):
            raise ValueError(f"Unindexed invariant dependency: {invariant['id']}")

    result = {
        "schema": "xgba.phase1.upstream_semantic_index_pilot.v1",
        "status": "SOURCE_INDEX_ONLY_NO_SEMANTIC_DISPOSITIONS",
        "scope": {
            "subsystem": "pinned mGBA GBA cartridge ROM window, load and patch boundary",
            "safe_indexed_file_records": len(records),
            "inventory_file_total": TOTAL,
            "inventory_file_records_not_indexed": TOTAL - len(records),
            "records_by_role": {
                "implementation_or_interface": 4,
                "build_or_test_manifest": 2,
                "linker_script": 1,
                "test_source": 1,
                "license": 1,
            },
            "source_invariants_indexed": len(invariants),
            "extrapolation_claimed": False,
        },
        "phase1_gate": {
            "decision": "FAIL_INCOMPLETE",
            "p0_candidates": 338,
            "inventory_total": TOTAL,
            "legacy_approvals_added": 0,
            "whole_file_dispositions_added": 0,
        },
        "snapshot_identity": {
            "original_dossier_archive_git_blob_sha1":
                SNAPSHOT_BLOBS["candidate_review_dossiers.jsonl.gz"],
            "original_queue_archive_git_blob_sha1":
                SNAPSHOT_BLOBS["semantic_review_queue.csv.gz"],
            "gate_git_blob_sha1": SNAPSHOT_BLOBS["phase1_mapping_gate.json"],
        },
        "source_records": records,
        "dependency_edges": _dependency_edges(source_by_path),
        "invariants": invariants,
        "upstream_test_coverage": {
            "test_source_record": REQUIRED_TEST_PATH,
            "available": ["loadNullROM: rejects a null ROM input"],
            "not_covered": [
                "ROM waitstate-window backing alias",
                "ROM loader at 32 MiB and 32 MiB + 1",
                "patch output at 32 MiB and 32 MiB + 1",
            ],
            "execution": "NOT_RUN_BY_THIS_INDEXER",
        },
        "external_references": list(REFERENCES),
        "license": {
            "source_record": REQUIRED_LICENSE_PATH,
            "license_id": "MPL-2.0",
            "source_notice_check": "PINNED_TEXT_PRESENT",
            "combined_distribution_clearance": "NOT_ASSESSED",
            "pret_pokefirered_distribution_clearance": "NOT_ASSESSED",
        },
        "evidence_boundaries": [
            "Source and machine-dossier identities were checked independently.",
            "Source-derived observations are not native emulator or hardware execution.",
            "Upstream test source presence is not a test execution result.",
            "External documentation links are context only and are unverified in this run.",
            "This pilot adds no semantic approval and proves no expanded-ROM behavior.",
        ],
    }
    if len(records) != 9 or len({
        (record["identity"]["repository"], record["identity"]["path"])
        for record in records
    }) != 9:
        raise ValueError("Pilot file-record cardinality or uniqueness failed")
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(canonical(result) + b"\n")
        if json.loads(output.read_text(encoding="utf-8")) != result:
            raise ValueError("Output round-trip failed")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=ROOT / "semantic-snapshots/current")
    parser.add_argument("--mgba-source-root", type=Path, required=True,
                        help="Directory containing the pinned mGBA source tree")
    parser.add_argument("--firered-source-root", type=Path, required=True,
                        help="Directory containing the pinned FireRed source tree")
    parser.add_argument("--output", type=Path, default=ROOT /
                        "docs/phase1-review-readiness/mgba-rom-memory-semantic-index-pilot-20261101.json")
    args = parser.parse_args()
    result = build(args.snapshot, {
        MGBA: args.mgba_source_root,
        FIRERED: args.firered_source_root,
    }, args.output)
    print(json.dumps({
        "indexed_files": result["scope"]["safe_indexed_file_records"],
        "source_invariants": result["scope"]["source_invariants_indexed"],
        "legacy_approvals_added": 0,
        "gate": result["phase1_gate"]["decision"],
        "output_sha256": digest(args.output.read_bytes()),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
