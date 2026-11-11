#!/usr/bin/env python3
"""Opt-in host staging for named XGBA resources; not a cartridge mapper."""
from __future__ import annotations

import hashlib

import xgba_resource_sidecar as sidecar


ROM_WINDOW_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_RESOURCE_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_STAGED_BYTES = 32 * 1024 * 1024


def _identity_dict(value):
    if isinstance(value, sidecar.SourceIdentity):
        value = {"id": value.id, "sha256": value.sha256}
    if not isinstance(value, dict) or set(value) != {"id", "sha256"}:
        raise ValueError("source identity must contain exactly id and sha256")
    identity_id, digest = value["id"], value["sha256"]
    if not isinstance(identity_id, str) or not sidecar.IDENTIFIER.fullmatch(identity_id):
        raise ValueError("Invalid source identity ID")
    if not isinstance(digest, str) or not sidecar.SHA256.fullmatch(digest):
        raise ValueError("Invalid source identity SHA-256")
    return {"id": identity_id, "sha256": digest}


class ResourceBridge:
    """Stage selected resources into bounded host buffers without ROM remapping.

    The caller opts in by opening a pack and naming each resource to stage.
    ``original_rom`` is retained without replacement or modification. Its
    supplied identity is checked against its bytes and must match the pack.
    """

    def __init__(
        self,
        original_rom,
        source_identity,
        *,
        max_resource_bytes=DEFAULT_MAX_RESOURCE_BYTES,
        max_staged_bytes=DEFAULT_MAX_STAGED_BYTES,
        chunk_size=64 * 1024,
    ):
        for value, label in (
            (max_resource_bytes, "max_resource_bytes"),
            (max_staged_bytes, "max_staged_bytes"),
        ):
            if type(value) is not int or value < 1:
                raise ValueError(f"{label} must be a positive integer")
        if type(chunk_size) is not int or not 1 <= chunk_size <= sidecar.MAX_CHUNK_SIZE:
            raise ValueError(
                f"chunk_size must be between 1 and {sidecar.MAX_CHUNK_SIZE}"
            )
        identity = _identity_dict(source_identity)
        try:
            rom_view = memoryview(original_rom)
        except TypeError as exc:
            raise ValueError("original_rom must expose the 32 MiB ROM buffer") from exc
        if rom_view.nbytes != ROM_WINDOW_BYTES or not rom_view.c_contiguous:
            raise ValueError("original_rom must be a contiguous 32 MiB ROM buffer")
        rom_digest = hashlib.sha256(rom_view.cast("B")).hexdigest()
        if rom_digest != identity["sha256"]:
            raise ValueError("source identity does not match original ROM bytes")
        self.original_rom = original_rom
        self.source_identity = identity
        self.max_resource_bytes = max_resource_bytes
        self.max_staged_bytes = max_staged_bytes
        self.chunk_size = chunk_size
        self._manifest = None
        self._staged = {}

    @property
    def is_open(self):
        return self._manifest is not None

    @property
    def staged_resource_ids(self):
        return tuple(self._staged)

    @property
    def staged_bytes(self):
        return sum(len(buffer) for buffer in self._staged.values())

    def open(self, manifest_path):
        """Validate a sidecar against the fixed ROM identity, then replace it."""
        candidate = sidecar.load_manifest(
            manifest_path, expected_source_identity=self.source_identity
        )
        self._manifest = candidate
        self._staged = {}
        return candidate

    def close(self):
        self._manifest = None
        self._staged = {}

    def staged_resource(self, resource_id):
        try:
            return memoryview(self._staged[resource_id]).toreadonly()
        except KeyError as exc:
            raise ValueError(f"Resource is not staged: {resource_id!r}") from exc

    def stage(self, resource_id):
        """Read and verify one named resource before atomically replacing its buffer."""
        if self._manifest is None:
            raise RuntimeError("Resource bridge is not open")
        resource = self._manifest.get_resource(resource_id)
        if resource.length > self.max_resource_bytes:
            raise ValueError(f"Resource exceeds per-resource staging limit: {resource_id}")

        previous = self._staged.get(resource_id)
        current_size = self.staged_bytes - (len(previous) if previous is not None else 0)
        if resource.length > self.max_staged_bytes - current_size:
            raise ValueError(f"Resource exceeds aggregate staging limit: {resource_id}")

        candidate = bytearray()
        for block in sidecar.iter_resource_chunks(
            self._manifest, resource_id, self.chunk_size
        ):
            candidate.extend(block)
        if len(candidate) != resource.length:
            raise ValueError(f"Resource length changed while staging: {resource_id}")

        self._staged[resource_id] = candidate
        return memoryview(candidate).toreadonly()

    def validate_savestate_identity(self, identity):
        """Reject state created for a different source ROM identity."""
        if _identity_dict(identity) != self.source_identity:
            raise ValueError("Savestate source identity does not match the ROM")
