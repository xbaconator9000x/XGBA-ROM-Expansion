#!/usr/bin/env python3
"""Package genuine pinned RHH source map/tiles pages for local XGBA testing.

Only derived files in --output are produced; do NOT commit sidecars, game ROMs
or source tile artwork. Entry names correspond exactly to the original
1-based gMapLayouts index and the native fieldmap binding. Missing assets
and unexpected source sizes fail closed; no synthetic map content is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

WINDOW = 32 * 1024 * 1024
START = WINDOW + 8192
PAGE = 16384
LAYOUT_VERSION = {"emerald": "emerald", "firered": "frlg", "leafgreen": "frlg"}
ROOT_TAG_SHA = "79dd436920845ebc145577649de624f65298c209"


class SourceAssetError(ValueError):
    pass


def safe_source_path(source: Path, relative: str) -> Path:
    p = Path(relative)
    if p.is_absolute() or ".." in p.parts:
        raise SourceAssetError("source asset path escapes checkout")
    resolved = (source / p).resolve()
    if not resolved.is_relative_to(source.resolve()) or not resolved.is_file():
        raise SourceAssetError(f"source asset not found in checkout: {relative}")
    return resolved


def source_layout(source: Path, target: str, name: str):
    if target not in LAYOUT_VERSION:
        raise SourceAssetError("unsupported RHH game variant")
    layouts = json.loads(safe_source_path(source, "data/layouts/layouts.json").read_text())["layouts"]
    chosen = [(i, row) for i, row in enumerate(layouts, 1) if row["id"] == name]
    if len(chosen) != 1:
        raise SourceAssetError(f"expected exactly one original layout: {name}")
    number, row = chosen[0]
    if row["layout_version"] != LAYOUT_VERSION[target]:
        raise SourceAssetError(f"layout {name} does not belong to {target}")
    width, height = row["width"], row["height"]
    if not isinstance(width, int) or not isinstance(height, int) or not (0 < width <= 10240 and 0 < height <= 10240):
        raise SourceAssetError("invalid original map dimensions")
    raw = safe_source_path(source, row["blockdata_filepath"]).read_bytes()
    if len(raw) != width * height * 2:
        raise SourceAssetError("source map dimensions differ from original map.bin")
    return number, row, raw


def indexed_gba_tiles(source: Path, relative: str, expected_tiles: int) -> bytes:
    from PIL import Image
    image_path = safe_source_path(source, relative)
    with Image.open(image_path) as image:
        if image.mode != "P" or image.width % 8 or image.height % 8:
            raise SourceAssetError("source tiles must be indexed 8x8 4bpp PNG")
        pixels = image.load()
        result = bytearray()
        for ty in range(0, image.height, 8):
            for tx in range(0, image.width, 8):
                for y in range(8):
                    for x in range(0, 8, 2):
                        lo, hi = pixels[tx + x, ty + y], pixels[tx + x + 1, ty + y]
                        if lo > 15 or hi > 15:
                            raise SourceAssetError("tileset palette index exceeds 4bpp")
                        result.append(lo | (hi << 4))
        if len(result) != expected_tiles * 32:
            raise SourceAssetError(
                f"full tileset must contain exactly {expected_tiles} tiles, "
                f"source has {len(result) // 32}; partial graphics would corrupt VRAM")
        return bytes(result)


def build(source: Path, target: str, layout: str, output: Path,
          primary_png: str | None = None, secondary_png: str | None = None) -> dict:
    source = source.resolve()
    number, row, map_data = source_layout(source, target, layout)
    rom = safe_source_path(source, f"poke{target}.gba")
    source_rom_sha = hashlib.sha256(rom.read_bytes()).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    sidecar = output / f"xgba-{target}-{number:04x}-private.bin"
    manifest = output / f"xgba-{target}-{number:04x}-private.json"
    pages: list[tuple[str, bytes]] = [("m", map_data)]
    primary_size = 640 if row["layout_version"] == "frlg" else 512
    secondary_size = 1024 - primary_size
    if primary_png:
        pages.append(("p", indexed_gba_tiles(source, primary_png, primary_size)))
    # The native fieldmap binds secondary pages for these source layouts.
    # Resolve their exact pinned RHH tileset symbols, not a guessed layout name.
    # Retain explicit --secondary-png for other source-authenticated layouts.
    pinned_secondary = {
        "gTileset_Petalburg": "data/tilesets/secondary/petalburg/tiles.png",
        "gTileset_PalletTown": "data/tilesets/secondary/pallet_town_frlg/tiles.png",
    }
    if secondary_png is None and primary_png and layout in (
        "LAYOUT_LITTLEROOT_TOWN", "LAYOUT_ROUTE101",
        "LAYOUT_PALLET_TOWN", "LAYOUT_ROUTE1",
    ):
        candidate = pinned_secondary.get(row.get("secondary_tileset"))
        if candidate and (source / candidate).is_file():
            secondary_png = candidate
    if secondary_png:
        pages.append(("s", indexed_gba_tiles(source, secondary_png, secondary_size)))
    resources = []
    written = START
    with sidecar.open("wb") as handle:
        handle.truncate(START)
        handle.seek(START)
        for kind, raw in pages:
            for i in range(0, len(raw), PAGE):
                chunk = raw[i:i + PAGE]
                suffix = i // PAGE
                if suffix > 255:
                    raise SourceAssetError("resource needs more than 256 pages")
                identifier = f"rhh.{kind}.{number:04x}.{suffix:02x}"
                handle.write(chunk)
                resources.append({
                    "id": identifier, "offset": written,
                    "length": len(chunk),
                    "sha256": hashlib.sha256(chunk).hexdigest(),
                })
                written += len(chunk)
    manifest.write_text(json.dumps({
        "format": "xgba-resource-manifest",
        "version": 1,
        "source_identity": {"id": f"rhh-{target}-expansion-1.17.2", "sha256": source_rom_sha},
        "data_file": sidecar.name,
        "resources": resources,
    }, sort_keys=True, indent=2) + "\n")
    return {
        "target": target, "layout_id": number,
        "original_layout": layout, "width": row["width"], "height": row["height"],
        "original_map_sha256": hashlib.sha256(map_data).hexdigest(),
        "source_rom_sha256": source_rom_sha,
        "primary_pages": sum(r["id"].startswith("rhh.p.") for r in resources),
        "secondary_pages": sum(r["id"].startswith("rhh.s.") for r in resources),
        "map_pages": sum(r["id"].startswith("rhh.m.") for r in resources),
        "resource_ids": [r["id"] for r in resources],
        "private_sidecar": str(sidecar),
        "private_manifest": str(manifest),
        "runtime_gameplay_verified": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--target", choices=LAYOUT_VERSION, required=True)
    p.add_argument("--layout", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--primary-png")
    p.add_argument("--secondary-png")
    a = p.parse_args()
    print(json.dumps(build(a.source, a.target, a.layout, a.output,
                           a.primary_png, a.secondary_png), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
