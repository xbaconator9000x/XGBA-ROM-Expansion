#!/usr/bin/env python3
"""Validate and stream opt-in XGBA sidecar resources in bounded chunks."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from types import MappingProxyType
from typing import Mapping

FORMAT = "xgba-resource-manifest"
VERSION = 1
MAX_U64 = (1 << 64) - 1
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_RESOURCES = 100_000
MAX_CHUNK_SIZE = 1024 * 1024
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class SourceIdentity:
    id: str
    sha256: str


@dataclass(frozen=True)
class Resource:
    id: str
    offset: int
    length: int
    sha256: str


@dataclass(frozen=True)
class ResourceManifest:
    manifest_path: Path
    data_path: Path
    source_identity: SourceIdentity
    resources: Mapping[str, Resource]

    def get_resource(self, resource_id: str) -> Resource:
        try:
            return self.resources[resource_id]
        except KeyError as exc:
            raise ValueError(f"Unknown resource ID: {resource_id!r}") from exc


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate manifest key: {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value):
    raise ValueError(f"Invalid JSON constant: {value}")


def _read_manifest(path: Path):
    with path.open("rb") as handle:
        raw = handle.read(MAX_MANIFEST_BYTES + 1)
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("Manifest exceeds size limit")
    try:
        text = raw.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Manifest is not valid UTF-8 JSON") from exc


def _validate_identity(value, label):
    if not isinstance(value, dict) or set(value) != {"id", "sha256"}:
        raise ValueError(f"{label} must contain exactly id and sha256")
    identity_id, digest = value["id"], value["sha256"]
    if not isinstance(identity_id, str) or not IDENTIFIER.fullmatch(identity_id):
        raise ValueError(f"Invalid {label} ID")
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise ValueError(f"Invalid {label} SHA-256")
    return SourceIdentity(identity_id, digest)


def _resolve_data_file(manifest_path: Path, value: str) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise ValueError("Invalid data_file path")
    relative = Path(value)
    if (
        relative.is_absolute()
        or re.match(r"^[A-Za-z]:", value)
        or any(part in (".", "..") for part in value.split("/"))
    ):
        raise ValueError("data_file must stay within the manifest directory")
    root = manifest_path.parent.resolve()
    candidate = (root / relative).resolve(strict=True)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("data_file escapes the manifest directory") from exc
    if not stat.S_ISREG(candidate.stat().st_mode):
        raise ValueError("data_file must be a regular file")
    return candidate


def _bounded_integer(value, label, *, allow_zero):
    if type(value) is not int:
        raise ValueError(f"{label} must be an integer")
    minimum = 0 if allow_zero else 1
    if not minimum <= value <= MAX_U64:
        raise ValueError(f"{label} is outside the unsigned 64-bit range")
    return value


def load_manifest(
    manifest_path,
    expected_source_identity=None,
):
    """Load and validate a v1 manifest and all resource bounds.

    The manifest schema has exactly ``format``, ``version``,
    ``source_identity``, ``data_file``, and ``resources`` fields. Resource
    entries have exactly ``id``, ``offset``, ``length``, and ``sha256``.
    """
    path = Path(manifest_path).resolve(strict=True)
    if not path.is_file():
        raise ValueError("Manifest must be a regular file")
    payload = _read_manifest(path)
    if not isinstance(payload, dict) or set(payload) != {
        "format", "version", "source_identity", "data_file", "resources"
    }:
        raise ValueError("Malformed manifest fields")
    if payload["format"] != FORMAT or type(payload["version"]) is not int:
        raise ValueError("Unsupported manifest format or version")
    if payload["version"] != VERSION:
        raise ValueError("Unsupported manifest version")

    source_identity = _validate_identity(payload["source_identity"], "source identity")
    if expected_source_identity is not None:
        expected = _validate_identity(expected_source_identity, "expected source identity")
        if expected != source_identity:
            raise ValueError("Manifest source identity does not match expected identity")

    data_path = _resolve_data_file(path, payload["data_file"])
    data_size = data_path.stat().st_size
    raw_resources = payload["resources"]
    if not isinstance(raw_resources, list) or len(raw_resources) > MAX_RESOURCES:
        raise ValueError("Resources must be a bounded list")

    resources = {}
    for entry in raw_resources:
        if not isinstance(entry, dict) or set(entry) != {
            "id", "offset", "length", "sha256"
        }:
            raise ValueError("Malformed resource fields")
        resource_id = entry["id"]
        if not isinstance(resource_id, str) or not IDENTIFIER.fullmatch(resource_id):
            raise ValueError("Invalid resource ID")
        if resource_id in resources:
            raise ValueError(f"Duplicate resource ID: {resource_id}")
        offset = _bounded_integer(entry["offset"], "Resource offset", allow_zero=True)
        length = _bounded_integer(entry["length"], "Resource length", allow_zero=False)
        if offset > MAX_U64 - length:
            raise ValueError(f"Resource range overflows uint64: {resource_id}")
        if not isinstance(entry["sha256"], str) or not SHA256.fullmatch(entry["sha256"]):
            raise ValueError(f"Invalid resource SHA-256: {resource_id}")
        if offset + length > data_size:
            raise ValueError(f"Resource range is out of bounds: {resource_id}")
        resources[resource_id] = Resource(
            resource_id, offset, length, entry["sha256"]
        )

    return ResourceManifest(
        path, data_path, source_identity, MappingProxyType(resources)
    )


def iter_resource_chunks(manifest: ResourceManifest, resource_id, chunk_size=64 * 1024):
    """Yield a resource in bounded chunks and verify its SHA-256 on exhaustion.

    Callers must consume the iterator to completion to receive integrity
    verification; an early-stopped iterator has not established the digest.
    """
    if type(chunk_size) is not int or not 1 <= chunk_size <= MAX_CHUNK_SIZE:
        raise ValueError(f"chunk_size must be between 1 and {MAX_CHUNK_SIZE}")
    resource = manifest.get_resource(resource_id)
    root = manifest.manifest_path.parent.resolve()
    current_path = manifest.data_path.resolve(strict=True)
    try:
        current_path.relative_to(root)
    except ValueError as exc:
        raise ValueError("data_file escapes the manifest directory") from exc

    digest = hashlib.sha256()
    with current_path.open("rb", buffering=0) as handle:
        file_stat = os.fstat(handle.fileno())
        if not stat.S_ISREG(file_stat.st_mode):
            raise ValueError("data_file must be a regular file")
        if resource.offset + resource.length > file_stat.st_size:
            raise ValueError(f"Resource range is out of bounds: {resource_id}")
        handle.seek(resource.offset)
        remaining = resource.length
        while remaining:
            block = handle.read(min(chunk_size, remaining))
            if not block:
                raise ValueError(f"Truncated resource content: {resource_id}")
            digest.update(block)
            remaining -= len(block)
            yield block
    if digest.hexdigest() != resource.sha256:
        raise ValueError(f"Resource SHA-256 mismatch: {resource_id}")
