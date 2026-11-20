#!/usr/bin/env python3
"""Build a private source-authentic Hiker trainer graphics provider for RHH 1.17.2."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from xgba_expansion_map_pages import (
    ROOT_TAG_SHA, START, LAYOUT_VERSION, SourceAssetError,
    safe_source_path, indexed_gba_tiles,
)

def build(source, target, output):
    source = Path(source).resolve()
    output = Path(output).resolve()
    if target not in LAYOUT_VERSION:
        raise SourceAssetError("unsupported target")
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if head != ROOT_TAG_SHA:
        raise SourceAssetError("wrong upstream source revision")
    constants = safe_source_path(source, "include/constants/trainers.h").read_text()
    enum = re.search(r"enum __attribute__\(\(packed\)\) TrainerPicID\s*\{([^}]+)\}", constants)
    if not enum:
        raise SourceAssetError("trainer enum ABI changed")
    prefix = re.sub(r"//[^\n]*|/\*[\s\S]*?\*/", "", enum.group(1)).split(",")
    names = [name.strip() for name in prefix]
    if names[:12] != ["TRAINER_PIC_" + n for n in
        ("NONE", "BRENDAN", "MAY", "RED", "LEAF", "RS_BRENDAN", "RS_MAY",
         "WALLY", "STEVEN", "POKEDUDE", "OLD_MAN", "HIKER")]:
        raise SourceAssetError("trainer picture numbering changed")
    graphics = safe_source_path(source, "src/data/graphics/trainers.h").read_text()
    # Both variants use distinct original picture IDs and artwork.
    pages = []
    for number, name, symbol, filename, palette in (
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
        with Image.open(safe_source_path(source, path)) as image:
            if image.size != (64, 64):
                raise SourceAssetError("unexpected trainer sprite dimensions")
        raw = indexed_gba_tiles(source, path, 64)
        pages.append((f"rhh.trainer.{number:04x}", raw))
    rom = safe_source_path(source, f"poke{target}.gba")
    output.mkdir(parents=True, exist_ok=True)
    data = output / f"xgba-{target}-trainer-private.bin"
    manifest = output / f"xgba-{target}-trainer-private.json"
    resources = []
    with data.open("wb") as handle:
        handle.seek(START)
        for identifier, raw in pages:
            offset = handle.tell()
            handle.write(raw)
            resources.append({"id": identifier, "offset": offset,
                              "length": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    record = {
        "format": "xgba-resource-manifest", "version": 1,
        "source_identity": {"id": f"rhh-{target}-expansion-1.17.2",
                            "sha256": hashlib.sha256(rom.read_bytes()).hexdigest()},
        "data_file": data.name,
        "resources": resources,
    }
    manifest.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return manifest

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, choices=LAYOUT_VERSION)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(build(args.source, args.target, args.output))
