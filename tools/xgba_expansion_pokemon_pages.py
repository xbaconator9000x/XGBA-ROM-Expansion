#!/usr/bin/env python3
"""Build a private source-authentic Pokemon battle graphics provider for RHH 1.17.2.

Emits the original Bulbasaur (player back) and Geodude (opponent front) tile
streams as `rhh.mon.b.XXXX` / `rhh.mon.f.XXXX`. Palettes, animation tables and
every other species stay with the original engine.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from xgba_expansion_map_pages import (
    ROOT_TAG_SHA, START, LAYOUT_VERSION, SourceAssetError,
    safe_source_path, indexed_gba_tiles,
)
from xgba_expansion_trainer_pages import pinned_asset, private_create

SPECIES = (
    # id, constant, directory, symbol, front tiles (2 frames), back tiles
    (1, "BULBASAUR", "bulbasaur", "Bulbasaur"),
    (74, "GEODUDE", "geodude", "Geodude"),
)
FRONT_SIZE = (64, 128)
BACK_SIZE = (64, 64)
RESOURCE_PREFIX = "rhh.mon."


def species_block(info, constant):
    start = re.search(r"\[SPECIES_" + constant + r"\]\s*=\s*\{", info)
    if not start:
        raise SourceAssetError("Pokemon species info ABI changed")
    nxt = re.search(r"\n    \[SPECIES_[A-Z0-9_]+\]\s*=", info[start.end():])
    return info[start.start():start.end() + (nxt.start() if nxt else len(info))]


def pokemon_pages(source):
    """Return [(id, raw)] after proving the source bindings and image geometry."""
    from PIL import Image
    config = pinned_asset(source, "include/config/pokemon.h").read_text()
    if not re.search(r"^#define P_GBA_STYLE_SPECIES_GFX\s+FALSE\b", config, re.M):
        raise SourceAssetError("GBA-style species graphics are not the verified layout")
    constants = pinned_asset(source, "include/constants/species.h").read_text()
    graphics = pinned_asset(source, "src/data/graphics/pokemon.h").read_text()
    info = pinned_asset(source, "src/data/pokemon/species_info/gen_1_families.h").read_text()
    pages = []
    for number, constant, directory, symbol in SPECIES:
        if not re.search(rf"\bSPECIES_{constant} = {number},", constants):
            raise SourceAssetError("species numbering changed")
        block = species_block(info, constant)
        if re.search(r"\.(front|back)PicFemale\b", block):
            raise SourceAssetError("gender-specific species graphics are unsupported")
        for kind, field, label, filename, size, expected in (
            ("f", "frontPic", "Front", "anim_front.png", FRONT_SIZE, 4096),
            ("b", "backPic", "Back", "back.png", BACK_SIZE, 2048),
        ):
            path = f"graphics/pokemon/{directory}/{filename}"
            declaration = (f'gMon{label}Pic_{symbol}[] = '
                           f'INCGFX_U32("{path}", ".4bpp.smol");')
            binding = rf"\.{field}\s*=\s*gMon{label}Pic_{symbol}\s*,"
            if declaration not in graphics or len(re.findall(binding, block)) != 1:
                raise SourceAssetError("Pokemon source graphics binding changed")
            with Image.open(pinned_asset(source, path)) as image:
                if image.size != size:
                    raise SourceAssetError("unexpected Pokemon sprite dimensions")
            raw = indexed_gba_tiles(source, path, expected // 32)
            if len(raw) != expected:
                raise SourceAssetError("unexpected Pokemon tile byte count")
            pages.append((f"{RESOURCE_PREFIX}{kind}.{number:04x}", raw))
    return pages


def build(source, target, output, base_manifest=None):
    source = Path(source).resolve()
    raw_output = Path(output).absolute()
    if any(parent.is_symlink() for parent in (raw_output, *raw_output.parents)):
        raise SourceAssetError("symlinked private Pokemon output directory")
    output = raw_output.resolve()
    if target not in LAYOUT_VERSION:
        raise SourceAssetError("unsupported target")
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if head != ROOT_TAG_SHA:
        raise SourceAssetError("wrong upstream source revision")
    pages = pokemon_pages(source)
    rom = safe_source_path(source, f"poke{target}.gba")
    if output == source or source in output.parents:
        raise SourceAssetError("private Pokemon output must be outside upstream source")
    data = output / f"xgba-{target}-pokemon-private.bin"
    manifest = output / f"xgba-{target}-pokemon-private.json"
    if data.exists() or data.is_symlink() or manifest.exists() or manifest.is_symlink():
        raise SourceAssetError("private Pokemon outputs already exist; choose a fresh directory")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    identity = {"id": f"rhh-{target}-expansion-1.17.2",
                "sha256": hashlib.sha256(rom.read_bytes()).hexdigest()}
    resources = []
    inherited = []
    if base_manifest is not None:
        base_manifest = Path(base_manifest).resolve()
        base = json.loads(base_manifest.read_text())
        if (base.get("format") != "xgba-resource-manifest" or base.get("version") != 1
                or base.get("source_identity") != identity):
            raise SourceAssetError("base provider source identity mismatch")
        base_data = safe_source_path(base_manifest.parent, base["data_file"])
        if base_data == data or base_manifest == manifest:
            raise SourceAssetError("base provider must not be overwritten")
        seen = {identifier for identifier, _ in pages}
        intervals = []
        file_size = base_data.stat().st_size
        if not isinstance(base.get("resources"), list):
            raise SourceAssetError("invalid base resource table")
        with base_data.open("rb") as handle:
            for entry in base["resources"]:
                if not isinstance(entry, dict):
                    raise SourceAssetError("invalid base resource entry")
                try:
                    identifier, offset, length = entry["id"], entry["offset"], entry["length"]
                    digest = entry["sha256"]
                except KeyError as exc:
                    raise SourceAssetError("incomplete base resource entry") from exc
                # Only this pinned source generator may publish Pokemon IDs.
                if (not isinstance(identifier, str) or not identifier
                        or identifier.startswith(RESOURCE_PREFIX)
                        or identifier in seen or type(offset) is not int
                        or type(length) is not int or offset < START
                        or not 0 < length <= 16384 or offset + length > file_size
                        or not isinstance(digest, str)
                        or any(offset < end and start < offset + length for start, end in intervals)):
                    raise SourceAssetError("invalid, overlapping or duplicate base resource")
                seen.add(identifier)
                intervals.append((offset, offset + length))
                handle.seek(offset)
                raw = handle.read(length)
                if len(raw) != length or hashlib.sha256(raw).hexdigest() != digest:
                    raise SourceAssetError("base resource integrity mismatch")
                inherited.append((identifier, raw))
    # The manifest is published last, so a partial pack is never advertised.
    created_data = False
    created_manifest = False
    try:
        with private_create(data) as handle:
            created_data = True
            handle.seek(START)
            for identifier, raw in inherited + pages:
                offset = handle.tell()
                handle.write(raw)
                resources.append({"id": identifier, "offset": offset,
                                  "length": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
            handle.flush()
            os.fsync(handle.fileno())
        with data.open("rb") as verify:
            for entry in resources:
                verify.seek(entry["offset"])
                actual = verify.read(entry["length"])
                if (len(actual) != entry["length"]
                        or hashlib.sha256(actual).hexdigest() != entry["sha256"]):
                    raise SourceAssetError("private Pokemon provider write verification failed")
        record = {
            "format": "xgba-resource-manifest", "version": 1,
            "source_identity": identity,
            "data_file": data.name,
            "resources": resources,
        }
        with private_create(manifest, text=True) as handle:
            created_manifest = True
            handle.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        with manifest.open("r", encoding="utf-8") as verify_manifest:
            if json.load(verify_manifest) != record:
                raise SourceAssetError("private Pokemon manifest verification failed")
        directory_fd = os.open(output, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        if created_manifest and manifest.exists():
            manifest.unlink()
        if created_data and data.exists():
            data.unlink()
        raise
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, choices=LAYOUT_VERSION)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--base-manifest", type=Path,
                        help="Preserve verified map/trainer pages in the battle provider")
    args = parser.parse_args()
    print(build(args.source, args.target, args.output, args.base_manifest))
