#!/usr/bin/env python3
"""Export a verified private trainer pack as an existing XGBA MMIO manifest.

The binary pack and manifest remain private. The existing patched-mGBA
resource provider reads this standard manifest directly, with no new ABI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from xgba_expansion_trainer_host_pack import HEADER
from xgba_expansion_trainer_host_provider import TrainerHostProvider
from xgba_expansion_trainer_provider_catalogue import PAGE_BYTES, PINNED_RHH, ProviderPackError

_SHA = re.compile(r"[0-9a-f]{64}\Z")


def export_manifest(pack_path: Path, index_path: Path, source_rom_sha256: str, target: str) -> dict:
    """Validate every pack byte before advertising its exact MMIO offsets."""
    if target not in ("emerald", "firered", "leafgreen"):\n        raise ProviderPackError("unsupported original RHH game target")\n    if not isinstance(source_rom_sha256, str) or _SHA.fullmatch(source_rom_sha256) is None:
        raise ProviderPackError("expected authentic source ROM SHA-256")
    if pack_path.is_symlink() or index_path.is_symlink() or not pack_path.is_file():
        raise ProviderPackError("unsafe private pack")
    if pack_path.parent.resolve() != index_path.parent.resolve():
        raise ProviderPackError("pack and index must share private directory")
    # Constructor verifies pack digest, entry ordering, per-page hashes and
    # the pinned RHH source. Never trust offsets from an unverified index.
    provider = TrainerHostProvider(pack_path, index_path)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    resources = []
    for entry in index["entries"]:
        resource_id = entry["resource_id"]
        page = provider.acquire(resource_id, PAGE_BYTES)
        if page is None:
            raise ProviderPackError("private trainer page unavailable")
        resources.append({
            "id": resource_id,
            "offset": HEADER.size + entry["offset"],
            "length": PAGE_BYTES,
            "sha256": hashlib.sha256(page).hexdigest(),
        })
    return {
        "format": "xgba-resource-manifest",
        "version": 1,
        "source_identity": {
            "id": f"rhh-{target}-expansion-1.17.2",
            "sha256": source_rom_sha256,
        },
        "data_file": pack_path.name,
        "resources": resources,
    }


def write_manifest(pack_path: Path, index_path: Path, output: Path,
                   source_rom_sha256: str) -> dict:
    directory = pack_path.parent.resolve(strict=True)
    if output.parent.resolve() != directory or output.is_symlink():
        raise ProviderPackError("manifest must stay in private pack directory")
    if output.resolve() in (pack_path.resolve(), index_path.resolve()):
        raise ProviderPackError("manifest would overwrite a private pack input")
    manifest = export_manifest(pack_path, index_path, source_rom_sha256, target)
    fd, temporary = tempfile.mkstemp(prefix=".xgba-trainer-mmio-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(manifest, stream, sort_keys=True, indent=2)
            stream.write("\n")
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-rom-sha256", required=True)
    parser.add_argument("--target", choices=("emerald", "firered", "leafgreen"), required=True)\n    args = parser.parse_args()
    result = write_manifest(args.pack, args.index, args.output, args.source_rom_sha256, args.target)
    print(f"Exported {len(result['resources'])} verified private MMIO resources")


if __name__ == "__main__":
    main()
