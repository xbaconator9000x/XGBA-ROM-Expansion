#!/usr/bin/env python3
"""Build a private source-authentic Hiker trainer graphics provider for RHH 1.17.2."""
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

def pinned_asset(source, relative):
    """Reject modified worktree artwork or declarations even at the pinned HEAD."""
    path = safe_source_path(source, relative)
    original = subprocess.check_output(
        ["git", "-C", str(source), "cat-file", "blob", f"{ROOT_TAG_SHA}:{relative}"])
    if path.read_bytes() != original:
        raise SourceAssetError(f"modified pinned trainer source: {relative}")
    return path

def build(source, target, output, base_manifest=None):
    source = Path(source).resolve()
    raw_output = Path(output).absolute()
    if any(parent.is_symlink() for parent in (raw_output, *raw_output.parents)):
        raise SourceAssetError("symlinked private trainer output directory")
    output = raw_output.resolve()
    if target not in LAYOUT_VERSION:
        raise SourceAssetError("unsupported target")
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if head != ROOT_TAG_SHA:
        raise SourceAssetError("wrong upstream source revision")
    constants = pinned_asset(source, "include/constants/trainers.h").read_text()
    enum = re.search(r"enum __attribute__\(\(packed\)\) TrainerPicID\s*\{([^}]+)\}", constants)
    if not enum:
        raise SourceAssetError("trainer enum ABI changed")
    prefix = re.sub(r"//[^\n]*|/\*[\s\S]*?\*/", "", enum.group(1)).split(",")
    names = [name.strip() for name in prefix]
    if names[:12] != ["TRAINER_PIC_" + n for n in
        ("NONE", "BRENDAN", "MAY", "RED", "LEAF", "RS_BRENDAN", "RS_MAY",
         "WALLY", "STEVEN", "POKEDUDE", "OLD_MAN", "HIKER")]:
        raise SourceAssetError("trainer picture numbering changed")
    graphics = pinned_asset(source, "src/data/graphics/trainers.h").read_text()
    # Both variants use distinct original picture IDs and artwork.
    pages = []
    # Preserve original trainer IDs and source-bound palette pairings.
    # Each 64x64 indexed image becomes a bounded 2-KiB graphics page;
    # the engine retains ownership of the destination and palette loader.
    for number, name, symbol, filename, palette in (
        (3, "RED", "Red", "red.png", "Red"),
        (4, "LEAF", "Leaf", "leaf.png", "Leaf"),
        (11, "HIKER", "Hiker", "hiker.png", "Hiker"),
        (105, "HIKER_FRLG", "HikerFrlg", "hiker_frlg.png", "HikerFrlg"),
    ):
        if len(names) <= number or names[number] != "TRAINER_PIC_" + name:
            raise SourceAssetError("trainer picture numbering changed")
        if any(not re.fullmatch(r"TRAINER_PIC_[A-Z0-9_]+", n)
               for n in names[:number + 1]):
            raise SourceAssetError("trainer enum contains explicit or conditional IDs")
        path = "graphics/trainers/front_pics/" + filename
        declaration = f'gTrainerFrontPic_{symbol}[] = INCGFX_U32("{path}", ".4bpp.smol");'
        binding = (r"\[TRAINER_PIC_" + name + r"\]\s*=\s*\{\s*"
                   + r"\.frontPic\s*=\s*TRAINER_FRONT_PIC\(gTrainerFrontPic_"
                   + symbol + r",\s*gTrainerPalette_" + palette + r"\)")
        if declaration not in graphics or not re.search(binding, graphics):
            raise SourceAssetError("trainer source graphics binding changed")
        from PIL import Image
        with Image.open(pinned_asset(source, path)) as image:
            if image.size != (64, 64):
                raise SourceAssetError("unexpected trainer sprite dimensions")
        raw = indexed_gba_tiles(source, path, 64)
        if len(raw) != 2048:
            raise SourceAssetError("unexpected trainer tile byte count")
        pages.append((f"rhh.trainer.{number:04x}", raw))
    rom = safe_source_path(source, f"poke{target}.gba")
    # Never overwrite the pinned source tree or a preexisting private pack.
    # Reject symlinked parents before opening either destination for writing.
    if output == source or source in output.parents:
        raise SourceAssetError("private trainer output must be outside upstream source")
    for parent in (output, *output.parents):
        if parent.is_symlink():
            raise SourceAssetError("symlinked private trainer output directory")
    data = output / f"xgba-{target}-trainer-private.bin"
    manifest = output / f"xgba-{target}-trainer-private.json"
    if data.exists() or data.is_symlink() or manifest.exists() or manifest.is_symlink():
        raise SourceAssetError("private trainer outputs already exist; choose a fresh directory")
    output.mkdir(parents=True, exist_ok=True)
    identity = {"id": f"rhh-{target}-expansion-1.17.2",
                "sha256": hashlib.sha256(rom.read_bytes()).hexdigest()}
    resources = []
    inherited = []
    if base_manifest is not None:
        base_manifest = Path(base_manifest).resolve()
        base = json.loads(base_manifest.read_text())
        if base.get("format") != "xgba-resource-manifest" or base.get("version") != 1 or base.get("source_identity") != identity:
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
                # Inherited pages must never impersonate trainer graphics.
                # Only this pinned source generator may publish trainer IDs.
                if (not isinstance(identifier, str) or not identifier
                    or identifier.startswith("rhh.trainer.")
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
    # A provider is usable only when BOTH its data and manifest are complete.
    # Exclusive creation prevents clobbering an output introduced between
    # preflight and write. A failed write leaves no half-published provider.
    created_data = False
    created_manifest = False
    try:
        with data.open("xb") as handle:
            created_data = True
            handle.seek(START)
            for identifier, raw in inherited + pages:
                offset = handle.tell()
                handle.write(raw)
                resources.append({"id": identifier, "offset": offset,
                                  "length": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
            handle.flush()
            os.fsync(handle.fileno())
        # Re-open the completed private pack before publishing its manifest.
        # A short or corrupted write must never become an advertised MMIO
        # resource; the original game graphics loader remains the fallback.
        with data.open("rb") as verify:
            for entry in resources:
                verify.seek(entry["offset"])
                actual = verify.read(entry["length"])
                if (len(actual) != entry["length"]
                    or hashlib.sha256(actual).hexdigest() != entry["sha256"]):
                    raise SourceAssetError("private trainer provider write verification failed")
        record = {
            "format": "xgba-resource-manifest", "version": 1,
            "source_identity": identity,
            "data_file": data.name,
            "resources": resources,
        }
        with manifest.open("x", encoding="utf-8") as handle:
            created_manifest = True
            handle.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        # Verify metadata after publication, not just the data pages.
        with manifest.open("r", encoding="utf-8") as verify_manifest:
            if json.load(verify_manifest) != record:
                raise SourceAssetError("private trainer manifest verification failed")
        # File fsync alone does not persist newly created directory entries.
        # Commit both private files' names before advertising the provider.
        directory_fd = os.open(output, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        # Never delete a pre-existing file when exclusive creation failed.
        # The manifest is published last, after the entire private data pack.
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
    parser.add_argument("--base-manifest", type=Path, help="Preserve verified map/tileset pages in the battle provider")
    args = parser.parse_args()
    print(build(args.source, args.target, args.output, args.base_manifest))
