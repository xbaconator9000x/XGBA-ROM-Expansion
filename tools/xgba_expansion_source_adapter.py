#!/usr/bin/env python3
"""Fail-closed, reversible source adapter for RHH pokeemerald-expansion.

A single upstream repository builds Emerald AND FireRed/LeafGreen as separate
targets. This adapter reuses XGBA's existing guest MMIO ABI instead of
pretending a vanilla Emerald binary patch is compatible with an expansion.

Initial gate: source boot bridge, not full external maps/graphics/gameplay.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ("emerald", "firered", "leafgreen")
UPSTREAM = "https://github.com/rh-hideout/pokeemerald-expansion"
VALIDATED_RELEASE = "expansion/1.17.2"
VALIDATED_RELEASE_SHA = "79dd436920845ebc145577649de624f65298c209"
MGBA_PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"

class ExpansionDrift(RuntimeError):
    """Refuse unsupported or already-patched source instead of guessing."""


def _one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ExpansionDrift(f"{label}: expected 1 source anchor, found {count}")
    return text.replace(old, new, 1)


def validate_source(source: Path, target: str) -> dict:
    if target not in TARGETS:
        raise ExpansionDrift(f"unsupported game target: {target!r}")
    makefile_path = source / "Makefile"
    main_path = source / "src/main.c"
    global_path = source / "include/global.h"
    if not all(p.is_file() for p in (makefile_path, main_path, global_path)):
        raise ExpansionDrift("not an intact pokeemerald-expansion source checkout")
    makefile = makefile_path.read_text(encoding="utf-8")
    normalized_makefile = " ".join(makefile.split())
    main = main_path.read_text(encoding="utf-8")
    required_make = (
        "GAME_VERSION ?= EMERALD",
        "GAME_VERSION := FIRERED",
        "GAME_VERSION := LEAFGREEN",
        "emerald: all",
        "firered: all",
        "leafgreen: all",
    )
    missing = [s for s in required_make if s not in normalized_makefile]
    if missing:
        raise ExpansionDrift(f"unsupported expansion build matrix: {missing}")
    if "XgbaExpansionProbeBoot" in main or "gXgbaExpansionProof" in main:
        raise ExpansionDrift("upstream main.c is already patched")
    for anchor in ("void AgbMain(void)\n{",
                   "    InitHeap(gHeap, HEAP_SIZE);",
                   "    ReadKeys();"):
        if main.count(anchor) != 1:
            raise ExpansionDrift(f"expansion main ABI drift at {anchor!r}")
    fieldmap_path = source / "src/fieldmap.c"
    if not fieldmap_path.is_file():
        raise ExpansionDrift("missing original fieldmap.c")
    fieldmap = fieldmap_path.read_text(encoding="utf-8")
    for anchor in (
        "static inline u16 GetBorderBlockAt(int x, int y)",
        "    InitBackupMapLayoutData(mapLayout->map, mapLayout->width, mapLayout->height);",
        "static void CopyTilesetToVram(struct Tileset const *tileset, u16 numTiles, u16 offset)",
        "static void CopyTilesetToVramUsingHeap(struct Tileset const *tileset, u16 numTiles, u16 offset)",
    ):
        if fieldmap.count(anchor) != 1:
            raise ExpansionDrift(f"expansion fieldmap ABI drift at {anchor!r}")
    if "XgbaExpansionTryMapCopy" in fieldmap:
        raise ExpansionDrift("upstream fieldmap.c already patched")
    if "EWRAM_DATA" not in main:
        raise ExpansionDrift("missing expected expansion EWRAM declaration usage")
    return {
        "framework": "rh-hideout/pokeemerald-expansion",
        "target": target,
        "source_main_sha256": hashlib.sha256(main.encode()).hexdigest(),
        "guest_mmio_abi": 1,
        "source_anchors": 3,
        "runtime_gameplay_verified": False,
    }


def patched_fieldmap(original: str) -> str:
    """Integrate original RHH fieldmap and both tileset load entrypoints."""
    bridge_path = ROOT / "integration/expansion/xgba_expansion_fieldmap.inc"
    page_api = ROOT / "integration/expansion/xgba_expansion_page.h"
    bridge = bridge_path.read_text(encoding="utf-8").replace(
        "XGBA_EXPANSION_MAP_API_PLACEHOLDER", page_api.resolve().as_posix())
    text = _one(original,
                "static inline u16 GetBorderBlockAt(int x, int y)",
                bridge + "\nstatic inline u16 GetBorderBlockAt(int x, int y)",
                "fieldmap declaration ABI")
    text = _one(text,
                "    InitBackupMapLayoutData(mapLayout->map, mapLayout->width, mapLayout->height);",
                "    XgbaExpansionBindOriginalMap(mapHeader);\n"
                "    InitBackupMapLayoutData(mapLayout->map, mapLayout->width, mapLayout->height);\n"
                "    XgbaExpansionTryMapCopy(mapLayout);",
                "original map layout copy")
    for signature in (
        "static void CopyTilesetToVram(struct Tileset const *tileset, u16 numTiles, u16 offset)",
        "static void CopyTilesetToVramUsingHeap(struct Tileset const *tileset, u16 numTiles, u16 offset)",
    ):
        text = _one(text, signature + "\n{\n    if (tileset)",
                    signature + "\n{\n    if (XgbaExpansionTryTilesetCopy(tileset, numTiles, offset))\n"
                    "        return;\n    if (tileset)",
                    signature)
    return text


def patched_main(original: str, header: Path, probe: str) -> str:
    header_name = header.resolve().as_posix()
    if '"' in header_name or "\n" in header_name:
        raise ExpansionDrift("unsafe header path")
    if probe.count("__XGBA_SHARED_GUEST__") != 1 or probe.count("__XGBA_PAGE_API__") != 1:
        raise ExpansionDrift("XGBA source ABI include drift")
    page_api = ROOT / "integration/expansion/xgba_expansion_page.h"
    if not page_api.is_file():
        raise ExpansionDrift("XGBA expansion page ABI header missing")
    page_api_name = page_api.resolve().as_posix()
    if '"' in page_api_name or "\n" in page_api_name:
        raise ExpansionDrift("unsafe page API header path")
    probe = (probe.replace("__XGBA_SHARED_GUEST__", header_name)
                  .replace("__XGBA_PAGE_API__", page_api_name))
    text = _one(original,
                "void AgbMain(void)\n{",
                probe + "\nvoid AgbMain(void)\n{",
                "game boot function")
    text = _one(text,
                "    InitHeap(gHeap, HEAP_SIZE);",
                "    InitHeap(gHeap, XGBA_EXPANSION_HEAP_BYTES);\n"
                "    XgbaExpansionProbeBoot();",
                "post-heap initialization")
    text = _one(text,
                "    ReadKeys();",
                "    XgbaExpansionProbeTick();\n    ReadKeys();",
                "normal game loop")
    return text


@contextmanager
def patched_source(source: Path, target: str):
    """Apply only during build; reliably restore upstream source afterwards."""
    report = validate_source(source, target)
    path = source / "src/main.c"
    fieldmap_path = source / "src/fieldmap.c"
    before = path.read_text(encoding="utf-8")
    fieldmap_before = fieldmap_path.read_text(encoding="utf-8")
    header = ROOT / "integration/fire_red/xgba_guest.h"
    probe_path = ROOT / "integration/expansion/xgba_expansion_probe.inc"
    if not header.is_file() or not probe_path.is_file():
        raise ExpansionDrift("XGBA shared ABI/probe source unavailable")
    after = patched_main(before, header, probe_path.read_text(encoding="utf-8"))
    fieldmap_after = patched_fieldmap(fieldmap_before)
    try:
        path.write_text(after, encoding="utf-8")
        fieldmap_path.write_text(fieldmap_after, encoding="utf-8")
        yield report
    finally:
        path.write_text(before, encoding="utf-8")
        fieldmap_path.write_text(fieldmap_before, encoding="utf-8")


def require_release_tag(source: Path, tag: str) -> str:
    sha = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    tags = subprocess.check_output(
        ["git", "-C", str(source), "tag", "--points-at", "HEAD"], text=True)
    if tag not in tags.splitlines():
        raise ExpansionDrift(f"source HEAD {sha} is not tagged {tag}")
    if tag == VALIDATED_RELEASE and sha != VALIDATED_RELEASE_SHA:
        raise ExpansionDrift(f"release tag {tag} moved to unexpected commit {sha}")
    return sha


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--target", choices=TARGETS, required=True)
    p.add_argument("--build", action="store_true",
                   help="build the temporary patched upstream source")
    p.add_argument("--require-tag", default=None,
                   help="fail closed unless HEAD carries this exact tag")
    args = p.parse_args()
    source = args.source.resolve()
    report = validate_source(source, args.target)
    if args.require_tag:
        report["upstream_head"] = require_release_tag(source, args.require_tag)
        report["release_tag"] = args.require_tag
    if args.build:
        with patched_source(source, args.target):
            subprocess.run(["make", args.target, "-j2"], cwd=source, check=True)
        report["source_build_passed"] = True
    else:
        report["source_build_passed"] = False
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
