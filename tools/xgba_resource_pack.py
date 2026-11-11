#!/usr/bin/env python3
"""Build deterministic, integrity-checked XGBA resource sidecars."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

import xgba_resource_sidecar as sidecar


def _validate_source_identity(value):
    if not isinstance(value, dict) or set(value) != {"id", "sha256"}:
        raise ValueError("source_identity must contain exactly id and sha256")
    identity_id, digest = value["id"], value["sha256"]
    if not isinstance(identity_id, str) or not sidecar.IDENTIFIER.fullmatch(identity_id):
        raise ValueError("Invalid source identity ID")
    if not isinstance(digest, str) or not sidecar.SHA256.fullmatch(digest):
        raise ValueError("Invalid source identity SHA-256")
    return {"id": identity_id, "sha256": digest}


def _write_all(handle, data):
    view = memoryview(data)
    written = 0
    while written < len(view):
        count = handle.write(view[written:])
        if type(count) is not int or count <= 0:
            raise OSError("Short write while creating resource pack")
        written += count


def _matches_blob(path: Path, expected_size: int, expected_digest: str) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"Existing resource pack blob is not a regular file: {path}")
    if info.st_size != expected_size:
        raise ValueError(f"Existing resource pack blob has unexpected size: {path}")
    digest = hashlib.sha256()
    with path.open("rb", buffering=0) as handle:
        while True:
            block = handle.read(sidecar.MAX_CHUNK_SIZE)
            if not block:
                break
            digest.update(block)
    if digest.hexdigest() != expected_digest:
        raise ValueError(f"Existing resource pack blob is corrupted: {path}")
    return True


def build_pack(source_manifests, output_manifest, source_identity, *, chunk_size=64 * 1024):
    """Stream source resources into a stable, atomically published sidecar.

    Resource IDs are retained and sorted; duplicate IDs across source manifests
    are rejected. The output manifest is the single atomic publication point
    and refers to a content-addressed data file in the same directory.
    """
    if type(chunk_size) is not int or not 1 <= chunk_size <= sidecar.MAX_CHUNK_SIZE:
        raise ValueError(
            f"chunk_size must be between 1 and {sidecar.MAX_CHUNK_SIZE}"
        )
    identity = _validate_source_identity(source_identity)
    manifests = [sidecar.load_manifest(path) for path in source_manifests]
    target = Path(output_manifest)
    if not target.name:
        raise ValueError("output_manifest must name a file")
    parent = target.parent.resolve(strict=True)
    target = parent / target.name
    target_alias = target.resolve(strict=False)

    sources_by_id = {}
    source_paths = set()
    for manifest in manifests:
        source_paths.update((manifest.manifest_path, manifest.data_path))
        for resource_id, resource in manifest.resources.items():
            if resource_id in sources_by_id:
                raise ValueError(f"Duplicate resource ID: {resource_id}")
            sources_by_id[resource_id] = (manifest, resource)
    if target in source_paths or target_alias in source_paths:
        raise ValueError("output_manifest must not overwrite an input file")

    data_fd, data_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".data.tmp", dir=parent
    )
    data_temp = Path(data_name)
    data_fd_open = True
    manifest_temp = None
    blob_path = None
    blob_created = False
    try:
        pack_digest = hashlib.sha256()
        packed_resources = []
        total_size = 0
        with os.fdopen(data_fd, "wb", buffering=0) as output:
            data_fd_open = False
            for resource_id in sorted(sources_by_id):
                manifest, resource = sources_by_id[resource_id]
                if total_size > sidecar.MAX_U64 - resource.length:
                    raise ValueError("Packed resource data exceeds uint64 range")
                offset = total_size
                resource_digest = hashlib.sha256()
                copied = 0
                for block in sidecar.iter_resource_chunks(
                    manifest, resource_id, chunk_size
                ):
                    _write_all(output, block)
                    resource_digest.update(block)
                    pack_digest.update(block)
                    copied += len(block)
                if copied != resource.length:
                    raise ValueError(f"Resource length changed while packing: {resource_id}")
                digest = resource_digest.hexdigest()
                if digest != resource.sha256:
                    raise ValueError(f"Resource SHA-256 mismatch: {resource_id}")
                packed_resources.append({
                    "id": resource_id,
                    "offset": offset,
                    "length": copied,
                    "sha256": digest,
                })
                total_size += copied
            output.flush()
            os.fsync(output.fileno())

        payload_digest = pack_digest.hexdigest()
        blob_name = f"xgba-{payload_digest}.bin"
        blob_path = parent / blob_name
        blob_alias = blob_path.resolve(strict=False)
        if blob_path in source_paths or blob_alias in source_paths or blob_path == target:
            raise ValueError("Output resource data must not overwrite an input file")

        if not _matches_blob(blob_path, total_size, payload_digest):
            try:
                os.link(data_temp, blob_path)
                blob_created = True
            except FileExistsError:
                if not _matches_blob(blob_path, total_size, payload_digest):
                    raise
        data_temp.unlink()

        document = {
            "format": sidecar.FORMAT,
            "version": sidecar.VERSION,
            "source_identity": identity,
            "data_file": blob_name,
            "resources": packed_resources,
        }
        encoded_manifest = (
            json.dumps(
                document,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            )
            + "\n"
        ).encode("utf-8")
        manifest_fd, manifest_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".manifest.tmp", dir=parent
        )
        manifest_temp = Path(manifest_name)
        with os.fdopen(manifest_fd, "wb", buffering=0) as output:
            _write_all(output, encoded_manifest)
            output.flush()
            os.fsync(output.fileno())
        sidecar.load_manifest(manifest_temp)
        os.replace(manifest_temp, target)
        manifest_temp = None
        return target
    except BaseException:
        if blob_created and blob_path is not None:
            blob_path.unlink(missing_ok=True)
        raise
    finally:
        if data_fd_open:
            os.close(data_fd)
        data_temp.unlink(missing_ok=True)
        if manifest_temp is not None:
            manifest_temp.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", action="append", required=True)
    parser.add_argument("--output-manifest", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--chunk-size", type=int, default=64 * 1024)
    args = parser.parse_args(argv)
    try:
        build_pack(
            args.source_manifest,
            args.output_manifest,
            {"id": args.source_id, "sha256": args.source_sha256},
            chunk_size=args.chunk_size,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
