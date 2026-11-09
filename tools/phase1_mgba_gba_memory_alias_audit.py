#!/usr/bin/env python3
"""Verify pinned GBA memory callers and run bounded host alignment controls."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
PACKET_PATH = ROOT / "docs/phase1-review-readiness/packet-0000-0099.json"
PACKET_BLOB = "a48c12900acc7e0211a8071119763e2b5de4b1a4"
DOSSIER_PATH = ROOT / "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
PACKET_FIVE_SHA256 = "6508e54c65f1b871f5998bb17dbf6204a73e9428e4ff57734e50e0d1e4dbf558"
LICENSE_BLOB = "14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e"
GATE_BLOB = "dab5789433dc55cf325a917a220d060088bf1d29"


def _git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# Every source identity and dossier digest is rechecked against the original
# compressed machine dossier, rather than accepted from the analyst workpaper.
SOURCES = {
    "include/mgba/internal/arm/macros.h": (
        "4832f054611044e63f1e2393fe4072f48004545a",
        "196d6bf1210d223dd58930908dcf5d538a7111fe93e0a0b36b45721cd93dbad9",
        "6508e54c65f1b871f5998bb17dbf6204a73e9428e4ff57734e50e0d1e4dbf558",
    ),
    "include/mgba-util/common.h": (
        "923e93086adfa09c9a55fcc2f0f6fa4d560e5888",
        "ec13354a050e4a7432232214b9991dd74000980ab2b8949389af0871cc1b799f",
        "b0a970a0105d3d1b109325bda5fedc99cff7a182cb010f24f826944faa0616ec",
    ),
    "include/mgba-util/memory.h": (
        "325f748f6fddc33a5539739ebc6eff6f3bb42bad",
        "509b56f31b2a279d954a16799501a1585cf7aa55f917a180432283b0205c198c",
        "cf858e1e109d1346cab0d7b30bcd119c207cfb84e9b45a3e73321c1e3576315e",
    ),
    "include/mgba-util/vfs.h": (
        "6c9bd299153af4c3c9cd5487f2425a2481331ee5",
        "4c829529f21c424196b4d1efe25ce11227312437cf1aa5028cae94a741bf6656",
        "5d4c30179d703f5b013badf083d6c99c736186091873d65edcb3f0943c2763dd",
    ),
    "include/mgba/internal/arm/arm.h": (
        "5ef2da96519ac3f429b65fd6d323be0775f3b3cf",
        "47822ffc4592230f6045dd2d8677dec5d72f518bff0b42e15ff26b5c77330bef",
        "aca7d604d669aced639ef33deb3a23ca309747d961c83972ec9baf8805ebd1b1",
    ),
    "include/mgba/internal/gba/memory.h": (
        "0aad912613e726560d06bbdbf6061986e69e5842",
        "fca671fc3bc5ab06641f6259ebf092688e1ba1ddd8eb80e4fba9a43cda44fb41",
        "6d4aad1e87edf5e5e07bc6af2af6f36c396f1a5530518ca575a765e3640dea8e",
    ),
    "include/mgba/internal/gba/video.h": (
        "289689446a6cf2334f8f478e35b376c9e87aa736",
        "5121b0486b889ff134deafbfeac42afa9dc0e1e134affb106c6b6bcf78824500",
        "0723c5fade118b9999f0203af025b2761e867341653af8cbbc3cf0fae5811c32",
    ),
    "src/arm/arm.c": (
        "0b92d7f55f1fb853d4b1b9c9163ee086126066e2",
        "c241587e974ac29aa09ed4992c9244c7ac65fad938e61d45836dc457f57129d2",
        "37c2acf57fc04d0327426d88d01b3353f46868be77fa73f3fa633fcc0a267934",
    ),
    "src/gba/CMakeLists.txt": (
        "71ab7bbb199ad95422e35ded5774c06a1b2e7c5c",
        "6ec3687f3dd8f23e2d40ed0fdf382b562e9bfa7af07659f985c0b9577773d9f4",
        "eb80fd02bccebe69d7964f08d0e7976adc94c1b980152e4877e98674f41a3e71",
    ),
    "src/gba/gba.c": (
        "c30bd943909dc00df0b5b9932e6d9ddb6e1c404e",
        "e84eaba17f6c96ac7b78431afaee79d7633dd50118f92e31e4432793f80c4c7b",
        "d1870b438fe6dd9bfa628a99d90189778e112588c14ae08f28fa379903595056",
    ),
    "src/gba/hle-bios.c": (
        "5b1acd3ba3da2232c86b2fdf54ae6af0944f08f4",
        "dfcf0b107efa70b96ddeec079b0fe189f40d282ae69e5fbfee38a0cacd8f2abc",
        "01aaf2bb76f374c6e9eddf4d6c216ac50751ed1ce5b612e07db3ac7095ae413d",
    ),
    "src/gba/hle-bios.h": (
        "cc15e2f5c3a442e3fefbef95c91547f8ff954eeb",
        "09b0e668be2085f795e16524dc17500b797edd3196c948ebb8c94d9e91bfbe2d",
        "25071f14752babc10dde0a62c757e830aafe2f88a8debab43bbe4ccdc53a7687",
    ),
    "src/gba/memory.c": (
        "aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc",
        "501dbbca7d5d7cbaa86240de2d6a4e2e1186b50f74dde11bcf2f323c4af8c437",
        "4b18ab8b7b5f947457093503c6c085e0ba6677f321255d140720cb2965b07f54",
    ),
    "src/gba/renderers/gl.c": (
        "5b4ef700fbc5314e4f89e5ec6efb61f288133bc4",
        "f50cbecdb115d92bacd8eec52105aac9ac641d74a12cf261e5dfdb99d40ebab2",
        "58884df765e9a05cd0f3abab0dba7f789aef90f4e7609a1f27592fcbecaad122",
    ),
    "src/gba/renderers/video-software.c": (
        "c5bc37b181ea4026e0660cbe67e745f725b7c650",
        "39a03b64a3fe9ab384a17de7d92d215298e9f5b64415f7c550d33779c2bbaf70",
        "10858746c81a0b67edd69a286a21d4a87b51a5beebb7561d4ac7c72097137fdd",
    ),
    "src/gba/video.c": (
        "28f072ec0b880d272f4f9564cc5ca8f5af389caf",
        "77f6bd32b19a5e78f06b0826cf3b5135abfcc3be24e08bd278829cdc564eda4d",
        "20c76a3c969ef4b98f090290b1183872d6c87cb4f68521375e5f5369d16479c0",
    ),
    "src/platform/posix/memory.c": (
        "67cdd96d7d0c6009ec113b293a60d82f9d2194a8",
        "3864d8aa21e852b64080d4c8365cf2399f755c6b7f95fbbcc78e21b24b030f06",
        "b7065b9e09a0896f8b4b4642980e1850dd3f2dab8aea78a52d1594916aa627e9",
    ),
    "src/platform/windows/memory.c": (
        "3c05b02d7aed5821e3ef87469a4728bb987736af",
        "f895be3276bdd50ab04f37613cc85c37f5538b3b4a7fb01cd45c4b28b73148d6",
        "e7362b45462ad50539ccc4870324a37c9dd3fb97860c8034b76e101c7dd21f65",
    ),
    "src/util/memory.c": (
        "89646d3bcb5a23e6c75ee5ea8ee8dfd7b940027b",
        "920e7bc5d3ddf4bc69c864d526c9bd141ece547894e9430f5bde3c7fe0acc1e5",
        "f022333144a428531384d50b32cff338bb88f52c8912efb2f1cf5b07eed4875c",
    ),
    "src/util/vfs/vfs-fd.c": (
        "2535bd0fb76740745ae038d5523ead28658f1035",
        "0073a68b6688f1baa26acaf609af52e9f29308605e449e7c3182c9f4d768da44",
        "bb351807533d3de29f1f87c2c3a644a70c67430f556e83e219b1e25292589942",
    ),
    "src/util/vfs/vfs-file.c": (
        "4a63e53f842b31b24d6188e6525ddcf121a0c7da",
        "77737a3fa897db96e31f1f5e56faa0c06afa0cc86c7697642b28026308ba0921",
        "263f5e29518c63b6c0cfb36819debd8c57dfc630a6490376255e2f1fd1fe3849",
    ),
    "src/util/vfs/vfs-mem.c": (
        "048194e2dd2d0b3b395a852d2092c694663c88a2",
        "6b5951a0cd634d398a69ce57766298bd32d5e6410ee0aa4e8b8894c6aaa5829b",
        "3c95e0a322b5aff0655ec59a1c1f5d34a740a21676da0bf5cce444d2434248ce",
    ),
    "CMakeLists.txt": (
        "834e9fd9ceb94a972941fb7b12494270702601e8",
        "6dd68feaebc479a02606b14be889e7c966949aa6aa5a4c52f601861c5d369a31",
        "bdd06250969b306e24337370ffd6ad4d955a944987575a107ffdb41829a732d1",
    ),
}

ANCHORS = {
    "include/mgba-util/common.h": {
        236: "#define LOAD_32LE(DEST, ADDR, ARR)",
        239: "#define STORE_32LE(SRC, ADDR, ARR)",
    },
    "include/mgba/internal/arm/macros.h": {
        12: "#define LOAD_32 LOAD_32LE",
        15: "#define STORE_32 STORE_32LE",
    },
    "include/mgba/internal/arm/arm.h": {
        127: "const uint32_t* activeRegion;",
    },
    "include/mgba/internal/gba/memory.h": {
        103: "uint32_t* bios;",
        104: "uint32_t* wram;",
        105: "uint32_t* iwram;",
        106: "uint32_t* rom;",
    },
    "include/mgba/internal/gba/video.h": {
        105: "uint16_t raw[512];",
        201: "uint16_t* palette;",
        202: "uint16_t* vram;",
        225: "uint16_t palette[512];",
        226: "uint16_t* vram;",
        227: "union GBAOAM oam;",
    },
    "src/arm/arm.c": {
        205: "LOAD_32(cpu->prefetch[1]",
        224: "LOAD_16(cpu->prefetch[1]",
    },
    "src/gba/gba.c": {
        447: "gba->memory.rom = vf->map(vf, GBA_SIZE_ROM0, MAP_READ);",
        465: "gba->memory.rom = vf->map(vf, gba->pristineRomSize, MAP_READ);",
        518: "uint32_t* bios = vf->map(vf, GBA_SIZE_BIOS, MAP_READ);",
    },
    "src/gba/hle-bios.c": {
        5: "const uint8_t hleBios[GBA_SIZE_BIOS] = {",
    },
    "src/gba/hle-bios.h": {
        13: "extern const uint8_t hleBios[];",
    },
    "src/gba/memory.c": {
        54: "gba->memory.bios = (uint32_t*) hleBios;",
        93: "gba->memory.wram = anonymousMemoryMap",
        94: "gba->memory.iwram = &gba->memory.wram[GBA_SIZE_EWRAM >> 2];",
        320: "cpu->memory.activeRegion = (uint32_t*) gba->video.palette;",
        326: "cpu->memory.activeRegion = (uint32_t*) &gba->video.vram[0x8000];",
        329: "cpu->memory.activeRegion = (uint32_t*) gba->video.vram;",
        335: "cpu->memory.activeRegion = (uint32_t*) gba->video.oam.raw;",
        386: "LOAD_32(value, address & -4, memory->bios);",
        397: "LOAD_32(value, address & (GBA_SIZE_EWRAM - 4), memory->wram);",
        400: "#define LOAD_IWRAM LOAD_32(value, address & (GBA_SIZE_IWRAM - 4), memory->iwram);",
        404: "LOAD_32(value, address & (GBA_SIZE_PALETTE_RAM - 4), gba->video.palette);",
        413: "LOAD_32(value, address & 0x00017FFC, gba->video.vram);",
        416: "LOAD_32(value, address & 0x0001FFFC, gba->video.vram);",
        423: "#define LOAD_OAM LOAD_32(value, address & (GBA_SIZE_OAM - 4), gba->video.oam.raw);",
        428: "LOAD_32(value, address & (GBA_SIZE_ROM0 - 4), memory->rom);",
        772: "STORE_32(value, address & (GBA_SIZE_PALETTE_RAM - 4), gba->video.palette);",
        785: "STORE_32(value, address & 0x00017FFC, gba->video.vram);",
        793: "STORE_32(value, address & 0x0001FFFC, gba->video.vram);",
        806: "STORE_32(value, address & (GBA_SIZE_OAM - 4), gba->video.oam.raw);",
        1111: "address &= ~3;",
        1228: "STORE_32(value, address & (GBA_SIZE_EWRAM - 4), memory->wram);",
        1232: "STORE_32(value, address & (GBA_SIZE_IWRAM - 4), memory->iwram);",
        1239: "STORE_32(value, address & (GBA_SIZE_PALETTE_RAM - 4), gba->video.palette);",
        1246: "STORE_32(value, address & 0x0001FFFC, gba->video.vram);",
        1251: "STORE_32(value, address & 0x00017FFC, gba->video.vram);",
        1258: "STORE_32(value, address & (GBA_SIZE_OAM - 4), gba->video.oam.raw);",
    },
    "src/gba/renderers/video-software.c": {
        121: "LOAD_16(entry, i, softwareRenderer->d.palette);",
    },
    "src/gba/renderers/gl.c": {
        1809: "LOAD_16(mat.a, 0, &renderer->d.oam->mat",
    },
    "src/gba/video.c": {
        61: "video->vram = anonymousMemoryMap(GBA_SIZE_VRAM);",
        132: "renderer->palette = video->palette;",
        133: "renderer->vram = video->vram;",
        134: "renderer->oam = &video->oam;",
    },
    "src/platform/posix/memory.c": {
        22: "return mmap(0, size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANON, -1, 0);",
        30: "return calloc(1, size);",
    },
    "src/platform/windows/memory.c": {
        11: "return VirtualAlloc(NULL, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);",
    },
    "src/util/memory.c": {
        9: "return calloc(1, size);",
    },
    "src/util/vfs/vfs-fd.c": {
        144: "void* mapped = mmap(0, size, PROT_READ | PROT_WRITE, mmapFlags, vfd->fd, 0);",
        148: "return mapped;",
    },
    "src/util/vfs/vfs-file.c": {
        96: "void* mem = anonymousMemoryMap(size);",
        104: "return mem;",
    },
    "src/util/vfs/vfs-mem.c": {
        72: "vfm->mem = (void*) mem;",
        99: "vfm->mem = anonymousMemoryMap(vfm->bufferSize);",
        281: "return vfm->mem;",
    },
    "CMakeLists.txt": {
        25: "set(CMAKE_C_STANDARD 11)",
        28: "set(CMAKE_C_EXTENSIONS OFF)",
        37: "-Werror=implicit-function-declaration -Werror=implicit-int -fwrapv\")",
        241: "file(GLOB OS_SRC ${CMAKE_CURRENT_SOURCE_DIR}/src/platform/posix/*.c)",
    },
    "src/gba/CMakeLists.txt": {
        21: "memory.c",
        29: "renderers/video-software.c",
        36: "video.c)",
    },
}


def verify_source_identity(data: bytes, expected_blob: str, expected_sha256: str) -> None:
    if _git_blob(data) != expected_blob or _digest(data) != expected_sha256:
        raise ValueError("Pinned source identity mismatch")


def verify_anchor(data: bytes, line_number: int, expected: str) -> None:
    lines = data.decode("utf-8", "strict").splitlines()
    if line_number < 1 or line_number > len(lines) or expected not in lines[line_number - 1]:
        raise ValueError(f"Missing pinned source anchor at line {line_number}")


def verify_gate(data: bytes) -> None:
    if _git_blob(data) != GATE_BLOB:
        raise ValueError("Authoritative gate snapshot changed")
    gate = json.loads(data)
    if gate.get("decision") != "FAIL_INCOMPLETE" or gate.get("approved_semantic_dispositions") != 0:
        raise ValueError("Authoritative gate is no longer the expected incomplete state")


def _verify_packet() -> None:
    packet_bytes = PACKET_PATH.read_bytes()
    if _git_blob(packet_bytes) != PACKET_BLOB:
        raise ValueError("Original packet blob changed")
    packet = json.loads(packet_bytes)
    entry = packet["packets"][5]
    identity = entry["identity"]
    if (
        identity.get("repository") != "mgba-emu/mgba"
        or identity.get("path") != "include/mgba/internal/arm/macros.h"
        or identity.get("pinned_commit") != PIN
        or identity.get("git_blob_sha1") != SOURCES["include/mgba/internal/arm/macros.h"][0]
        or entry.get("dossier_sha256") != PACKET_FIVE_SHA256
        or entry.get("independently_approved") is not False
        or entry.get("state") != "MACHINE_REVIEW_PACKET_NOT_WHOLE_FILE_SEMANTIC_DISPOSITION"
    ):
        raise ValueError("Original packet #5 identity or non-approval state changed")


def _verify_dossiers(snapshot: Path, source_root: Path) -> None:
    archive = snapshot / DOSSIER_PATH.name
    data = archive.read_bytes()
    if _git_blob(data) != DOSSIER_BLOB or _digest(data) != DOSSIER_SHA256:
        raise ValueError("Original compressed machine dossier archive changed")

    expected = {
        ("mgba-emu/mgba", path): (blob, source_sha, dossier_sha)
        for path, (blob, source_sha, dossier_sha) in SOURCES.items()
    }
    found = {}
    with gzip.open(archive, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            identity = (provenance.get("repository"), provenance.get("path"))
            if identity not in expected:
                continue
            if identity in found:
                raise ValueError(f"Duplicate original dossier row: {identity[1]}")
            payload = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
            blob, source_sha, dossier_sha = expected[identity]
            source_data = (source_root / identity[1]).read_bytes()
            if (
                provenance.get("git_blob_sha") != blob
                or provenance.get("source_content_sha256") != source_sha
                or str(provenance.get("tracked_bytes")) != str(len(source_data))
                or _digest(source_data) != source_sha
            ):
                raise ValueError(f"Original dossier source identity mismatch: {identity[1]}")
            if _digest(payload) != dossier_sha:
                raise ValueError(f"Original dossier row hash mismatch: {identity[1]}")
            found[identity] = provenance

    if set(found) != set(expected):
        raise ValueError("Original machine dossier is missing an audited source row")


def _verify_sources(source_root: Path) -> dict[str, bytes]:
    try:
        actual_pin = subprocess.check_output(
            ["git", "-C", str(source_root), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("Pinned source root is not a Git checkout") from exc
    if actual_pin != PIN:
        raise ValueError(f"Wrong pinned source revision: {actual_pin}")

    contents = {}
    for path, (blob, source_sha, _) in SOURCES.items():
        try:
            data = (source_root / path).read_bytes()
        except OSError as exc:
            raise ValueError(f"Missing pinned source: {path}") from exc
        verify_source_identity(data, blob, source_sha)
        contents[path] = data
    for path, anchors in ANCHORS.items():
        if path not in contents:
            contents[path] = (source_root / path).read_bytes()
        for line_number, expected in anchors.items():
            verify_anchor(contents[path], line_number, expected)

    cmake = contents["CMakeLists.txt"].decode("utf-8")
    if "-fno-strict-aliasing" in cmake:
        raise ValueError("Unexpected strict-aliasing opt-out in pinned CMake configuration")

    return contents


def _run_host_probes(source_root: Path, generated_include: Path) -> int:
    probe = ROOT / "tests/phase1_mgba_memory_object_probe.c"
    allocator = source_root / "src/platform/posix/memory.c"
    hle_bios = source_root / "src/gba/hle-bios.c"
    if not generated_include.is_dir():
        raise ValueError(f"Missing configured mGBA include directory: {generated_include}")
    completed = 0
    with tempfile.TemporaryDirectory(prefix="xgba-mgba-memory-") as directory:
        output_dir = Path(directory)
        for compiler in ("gcc", "clang"):
            executable = shutil.which(compiler)
            if not executable:
                raise ValueError(f"Required host compiler is unavailable: {compiler}")
            for alias_flag, alias_label in (
                ("-fstrict-aliasing", "strict"),
                ("-fno-strict-aliasing", "no-strict"),
            ):
                for allocator_flag, allocator_label in (([], "mmap"), (["-DDISABLE_ANON_MMAP"], "calloc")):
                    binary = output_dir / f"probe-{compiler}-{alias_label}-{allocator_label}"
                    command = [
                        executable,
                        "-std=c11",
                        "-O2",
                        "-g",
                        "-Wall",
                        "-Wextra",
                        "-D_GNU_SOURCE",
                        alias_flag,
                        "-fsanitize=alignment",
                        "-fno-sanitize-recover=alignment",
                        *allocator_flag,
                        "-I",
                        str(generated_include),
                        "-I",
                        str(source_root / "include"),
                        "-I",
                        str(source_root / "src"),
                        str(probe),
                        str(allocator),
                        str(hle_bios),
                        "-o",
                        str(binary),
                    ]
                    subprocess.run(command, check=True, capture_output=True, text=True)
                    result = subprocess.run(
                        [str(binary)],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    if "ARM_MEMORY_CALLER_ALIGNMENT_PASS" not in result.stdout:
                        raise ValueError(f"Host probe did not report success: {compiler}/{alias_label}/{allocator_label}")
                    print(
                        f"ARM_MEMORY_CALLER_HOST_PASS compiler={compiler} alias={alias_label} "
                        f"allocator={allocator_label}"
                    )
                    completed += 1
    return completed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--generated-include", type=Path, required=True)
    parser.add_argument(
        "--snapshot-root",
        type=Path,
        default=ROOT / "semantic-snapshots/current",
    )
    args = parser.parse_args()

    if _git_blob(DOSSIER_PATH.read_bytes()) != DOSSIER_BLOB:
        raise ValueError("Repository's current dossier snapshot is not the original compressed archive")
    verify_gate((args.snapshot_root / "phase1_mapping_gate.json").read_bytes())
    _verify_packet()
    source_root = args.source_root.resolve()
    _verify_dossiers(args.snapshot_root, source_root)
    sources = _verify_sources(source_root)

    license_data = (source_root / "LICENSE").read_bytes()
    if _git_blob(license_data) != LICENSE_BLOB:
        raise ValueError("Pinned mGBA root license blob changed")
    if b"Mozilla Public License Version 2.0" not in license_data:
        raise ValueError("Pinned mGBA root license is not MPL-2.0")
    for path in (
        "include/mgba/internal/arm/macros.h",
        "include/mgba-util/common.h",
        "src/gba/memory.c",
        "src/gba/video.c",
        "src/platform/posix/memory.c",
        "src/platform/windows/memory.c",
    ):
        if b"Mozilla Public" not in sources[path]:
            raise ValueError(f"Missing source-file MPL-2.0 notice: {path}")

    count = _run_host_probes(args.source_root.resolve(), args.generated_include.resolve())
    print(
        f"P0_ARM_MEMORY_CALLER_AUDIT_PASS source_files={len(SOURCES)} "
        f"dossier_rows={len(SOURCES)} host_variants={count} approvals=0 gate=FAIL_INCOMPLETE"
    )


if __name__ == "__main__":
    main()
