#!/usr/bin/env python3
"""Assemble SHA-verified private trainer pages into a deterministic host pack.

This tool is deliberately separate from public CI artifacts. Run against a
private staging directory containing source-authentic RHH page manifests.
The host must validate the index and payload digest before exposing pages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile

from xgba_expansion_trainer_provider_catalogue import (
    PAGE_BYTES, PINNED_RHH, ProviderPackError, build_catalogue,
)

MAGIC = b"XGBATRN1"
HEADER = struct.Struct("<8sII")  # magic, entry count, payload bytes


def build_pack(directory: Path) -> tuple[bytes, dict]:
    catalogue = build_catalogue(directory)
    entries = []
    payload = bytearray()
    for item in catalogue["entries"]:
        resource = item["resource_id"]
        path = directory / item["filename"]
        if path.is_symlink() or not path.is_file():
            raise ProviderPackError(f"unsafe private trainer page: {resource}")
        page = path.read_bytes()
        if len(page) != PAGE_BYTES or hashlib.sha256(page).hexdigest() != item["sha256"]:
            raise ProviderPackError(f"trainer page changed during packaging: {resource}")
        offset = len(payload)
        payload.extend(page)
        entries.append({
            "resource_id": resource,
            "offset": offset,
            "bytes": len(page),
            "sha256": item["sha256"],
        })
    if len(entries) > 0xFFFFFFFF or len(payload) > 0xFFFFFFFF:
        raise ProviderPackError("private trainer pack exceeds 32-bit host format")
    header = HEADER.pack(MAGIC, len(entries), len(payload))
    packed = header + payload
    index = {
        "format": "xgba-private-trainer-pack-v1",
        "source_release_sha": PINNED_RHH,
        "header_bytes": HEADER.size,
        "payload_bytes": len(payload),
        "pack_sha256": hashlib.sha256(packed).hexdigest(),
        "entries": entries,
    }
    return packed, index


def write_private_pack(directory: Path, pack_path: Path, index_path: Path) -> dict:
    directory = directory.resolve(strict=True)
    if pack_path.parent.resolve() != directory or index_path.parent.resolve() != directory:
        raise ProviderPackError("pack and index must remain in private staging directory")
    if pack_path == index_path or pack_path.is_symlink() or index_path.is_symlink():
        raise ProviderPackError("unsafe private pack destination")
    packed, index = build_pack(directory)
    for destination, data in (
        (pack_path, packed),
        (index_path, (json.dumps(index, indent=2, sort_keys=True) + "\n").encode()),
    ):
        fd, name = tempfile.mkstemp(prefix=".xgba-trainer-", dir=directory)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
            os.replace(name, destination)
        finally:
            if os.path.exists(name):
                os.unlink(name)
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", required=True, type=Path)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--index", required=True, type=Path)
    args = parser.parse_args()
    index = write_private_pack(args.private_dir, args.pack, args.index)
    print(f"Packed {len(index['entries'])} private trainer pages")


if __name__ == "__main__":
    main()
