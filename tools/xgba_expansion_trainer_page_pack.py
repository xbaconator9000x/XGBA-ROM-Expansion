#!/usr/bin/env python3
"""Build a private, source-authentic XGBA trainer page from an original RHH LZ77 blob.

Input is an extracted original GetTrainerFrontPicData(trainerPicId) compressed
resource, not an invented drawing. Never commit generated output or input.
The output .bin is the exact raw 2048-byte page requested by the battle loader;
the manifest records provenance for a private host provider importer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

TILE_BYTES = 64 * 64 // 2
PAGE_LIMIT = 16 * 1024


class TrainerPageError(ValueError):
    pass


def decompress_gba_lz77(blob: bytes) -> bytes:
    """Strict BIOS LZ77 0x10 decode, rejecting truncation and trailing bytes."""
    if len(blob) < 4 or blob[0] != 0x10:
        raise TrainerPageError("expected GBA LZ77 0x10 header")
    length = int.from_bytes(blob[1:4], "little")
    if length != TILE_BYTES or length > PAGE_LIMIT:
        raise TrainerPageError("trainer must decompress to exactly 2048 bytes")
    out = bytearray()
    cursor = 4
    while len(out) < length:
        if cursor >= len(blob):
            raise TrainerPageError("truncated flag byte")
        flags = blob[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if len(out) == length:
                break
            if flags & (1 << bit):
                if cursor + 2 > len(blob):
                    raise TrainerPageError("truncated backreference")
                a, b = blob[cursor:cursor + 2]
                cursor += 2
                count = (a >> 4) + 3
                distance = (((a & 15) << 8) | b) + 1
                if distance > len(out) or len(out) + count > length:
                    raise TrainerPageError("invalid LZ77 backreference")
                for _ in range(count):
                    out.append(out[-distance])
            else:
                if cursor >= len(blob):
                    raise TrainerPageError("truncated literal")
                out.append(blob[cursor])
                cursor += 1
    # Original GBA compressed resources may be padded to four-byte alignment.
    if len(blob) - cursor > 3 or any(blob[cursor:]):
        raise TrainerPageError("unexpected trailing compressed data")
    return bytes(out)


def build_page(blob: bytes, trainer_id: int, expected_source_sha256: str) -> tuple[bytes, dict]:
    if not 0 <= trainer_id <= 0xFFFF:
        raise TrainerPageError("trainer ID must fit the RHH four-hex-digit resource key")
    digest = hashlib.sha256(blob).hexdigest()
    if len(expected_source_sha256) != 64 or digest != expected_source_sha256.lower():
        raise TrainerPageError("original compressed source SHA256 mismatch")
    page = decompress_gba_lz77(blob)
    resource_id = f"rhh.trainer.{trainer_id:04x}"
    return page, {
        "resource_id": resource_id,
        "source_format": "original RHH GetTrainerFrontPicData LZ77 0x10",
        "source_sha256": digest,
        "page_sha256": hashlib.sha256(page).hexdigest(),
        "bytes": len(page),
        "page_capacity": PAGE_LIMIT,
        "source_release_sha": "79dd436920845ebc145577649de624f65298c209",
        "requires_private_provider": True,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-lz77", type=Path, required=True)
    p.add_argument("--trainer-id", type=lambda s: int(s, 0), required=True)
    p.add_argument("--source-sha256", required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    blob = args.original_lz77.read_bytes()
    page, manifest = build_page(blob, args.trainer_id, args.source_sha256)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # Private staging only; never copy these generated assets to public CI.
    (args.output_dir / (manifest["resource_id"] + ".bin")).write_bytes(page)
    (args.output_dir / (manifest["resource_id"] + ".json")).write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
