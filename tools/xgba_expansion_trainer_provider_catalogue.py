#!/usr/bin/env python3
"""Validate private RHH trainer pages and build a deterministic provider catalogue.

Run only against a private staging directory. This tool writes no original
graphics to the public source tree. Each catalogue entry references a private
page by relative filename; the provider must verify SHA-256 before serving it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

PAGE_BYTES = 2048
PAGE_CAPACITY = 16 * 1024
PINNED_RHH = "79dd436920845ebc145577649de624f65298c209"


class ProviderPackError(ValueError):
    pass


def build_catalogue(directory: Path) -> dict:
    entries = []
    for manifest_path in sorted(directory.glob("rhh.trainer.*.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise ProviderPackError(f"invalid manifest {manifest_path.name}") from exc
        resource = manifest_path.stem
        if not isinstance(manifest, dict) or manifest.get("resource_id") != resource:
            raise ProviderPackError(f"resource identity mismatch: {resource}")
        suffix = resource.removeprefix("rhh.trainer.")
        if (len(suffix) != 4 or any(c not in "0123456789abcdef" for c in suffix)
                or resource != "rhh.trainer." + suffix):
            raise ProviderPackError(f"invalid trainer resource key: {resource}")
        if (manifest.get("source_release_sha") != PINNED_RHH
                or manifest.get("bytes") != PAGE_BYTES
                or manifest.get("page_capacity") != PAGE_CAPACITY
                or manifest.get("requires_private_provider") is not True):
            raise ProviderPackError(f"invalid page contract: {resource}")
        page_path = directory / (resource + ".bin")
        if not page_path.is_file() or page_path.is_symlink():
            raise ProviderPackError(f"missing or unsafe private page: {resource}")
        page = page_path.read_bytes()
        if len(page) != PAGE_BYTES:
            raise ProviderPackError(f"page size mismatch: {resource}")
        digest = hashlib.sha256(page).hexdigest()
        if digest != manifest.get("page_sha256"):
            raise ProviderPackError(f"page digest mismatch: {resource}")
        entries.append({"resource_id": resource, "filename": page_path.name,
                        "bytes": PAGE_BYTES, "sha256": digest})
    if not entries:
        raise ProviderPackError("no private trainer pages found")
    return {"format": "xgba-private-trainer-pages-v1",
            "source_release_sha": PINNED_RHH,
            "lease_capacity": PAGE_CAPACITY, "entries": entries}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--catalogue", type=Path, required=True)
    args = parser.parse_args()
    directory = args.private_dir.resolve(strict=True)
    target = args.catalogue.resolve()
    if target.parent != directory:
        parser.error("catalogue must be written inside the private staging directory")
    catalogue = build_catalogue(directory)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(catalogue, sort_keys=True, indent=2) + "\n",
                         encoding="utf-8")
    temporary.replace(target)
    print(f"Validated {len(catalogue['entries'])} private trainer pages")


if __name__ == "__main__":
    main()
