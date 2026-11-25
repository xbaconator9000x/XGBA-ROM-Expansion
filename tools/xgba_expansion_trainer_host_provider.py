#!/usr/bin/env python3
"""Fail-closed private host-side reader for source-authentic RHH trainer pages.

This is a host provider input, not a guest-side MMIO implementation. Verify
both files before exposing any bytes to the existing 16-KiB page provider.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from xgba_expansion_trainer_host_pack import HEADER, MAGIC
from xgba_expansion_trainer_provider_catalogue import (
    PAGE_BYTES, PAGE_CAPACITY, PINNED_RHH, ProviderPackError,
)

RESOURCE = re.compile(r"rhh\.trainer\.[0-9a-f]{4}\Z")


class TrainerHostProvider:
    """Validated immutable pack snapshot; no pointers into guest DMA buffers."""

    def __init__(self, pack_path: Path, index_path: Path):
        if pack_path.is_symlink() or index_path.is_symlink():
            raise ProviderPackError("unsafe trainer host pack path")
        packed = pack_path.read_bytes()
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ProviderPackError("invalid trainer host index") from exc
        if not isinstance(index, dict) or index.get("format") != "xgba-private-trainer-pack-v1":
            raise ProviderPackError("invalid trainer host index format")
        if index.get("source_release_sha") != PINNED_RHH or index.get("header_bytes") != HEADER.size:
            raise ProviderPackError("trainer host provenance mismatch")
        if index.get("pack_sha256") != hashlib.sha256(packed).hexdigest():
            raise ProviderPackError("trainer host pack digest mismatch")
        if len(packed) < HEADER.size:
            raise ProviderPackError("truncated trainer host pack")
        magic, count, payload_bytes = HEADER.unpack_from(packed)
        entries = index.get("entries")
        if (magic != MAGIC or not isinstance(entries, list) or count != len(entries)
                or payload_bytes != len(packed) - HEADER.size
                or index.get("payload_bytes") != payload_bytes):
            raise ProviderPackError("trainer host header mismatch")
        pages = {}
        expected_offset = 0
        for entry in entries:
            if not isinstance(entry, dict):
                raise ProviderPackError("invalid trainer host entry")
            key = entry.get("resource_id")
            if (not isinstance(key, str) or RESOURCE.fullmatch(key) is None
                    or key in pages or entry.get("offset") != expected_offset
                    or entry.get("bytes") != PAGE_BYTES
                    or expected_offset + PAGE_BYTES > payload_bytes):
                raise ProviderPackError("trainer host resource layout mismatch")
            start = HEADER.size + expected_offset
            page = packed[start:start + PAGE_BYTES]
            if hashlib.sha256(page).hexdigest() != entry.get("sha256"):
                raise ProviderPackError("trainer host page digest mismatch")
            pages[key] = page
            expected_offset += PAGE_BYTES
        if expected_offset != payload_bytes or not pages:
            raise ProviderPackError("trainer host payload coverage mismatch")
        self._pages = pages

    def acquire(self, resource_id: str, requested_bytes: int) -> bytes | None:
        """Return a detached bounded page, or None for original-loader fallback."""
        if (not isinstance(resource_id, str) or RESOURCE.fullmatch(resource_id) is None
                or not isinstance(requested_bytes, int) or isinstance(requested_bytes, bool)
                or requested_bytes != PAGE_BYTES or requested_bytes > PAGE_CAPACITY):
            return None
        page = self._pages.get(resource_id)
        return bytes(page) if page is not None else None

    def copy_into(self, resource_id: str, destination: bytearray | memoryview) -> bool:
        """Synchronous host-provider transfer into a caller-owned staging buffer.

        The caller must publish the buffer to MMIO only after success. A miss,
        malformed destination, or length mismatch leaves destination unchanged.
        No borrowed view of the immutable private pack escapes this method.
        """
        page = self.acquire(resource_id, PAGE_BYTES)
        if page is None:
            return False
        try:
            view = memoryview(destination)
            if (view.readonly or view.ndim != 1 or view.itemsize != 1
                    or view.format != "B" or not view.c_contiguous
                    or len(view) != PAGE_BYTES):
                return False
            # Make the complete source snapshot before writing. The caller
            # owns the destination and must not DMA from the private pack.
            view[:] = page
            return True
        except (TypeError, ValueError, BufferError):
            return False

    def stage_mmio_page(self, resource_id: str, requested_bytes: int,
                        staging: bytearray | memoryview) -> bool:
        """Prepare a full 16-KiB MMIO provider window without borrowed pointers.

        The guest requests precisely the 2-KiB verified trainer resource.
        Copy to a private scratch window first, then publish synchronously
        into the caller-owned 16-KiB buffer. Missing/malformed requests
        leave the existing window untouched for the original GBA loader.
        Zero the unused tail to avoid exposing previous resident pages.
        This does not acquire or release the guest-side page lease.
        """
        if (not isinstance(requested_bytes, int) or isinstance(requested_bytes, bool)
                or requested_bytes != PAGE_BYTES):
            return False
        try:
            view = memoryview(staging)
            if (view.readonly or view.ndim != 1 or view.itemsize != 1
                    or view.format != "B" or not view.c_contiguous
                    or len(view) != PAGE_CAPACITY):
                return False
        except (TypeError, ValueError, BufferError):
            return False
        scratch = bytearray(PAGE_CAPACITY)
        if not self.copy_into(resource_id, memoryview(scratch)[:PAGE_BYTES]):
            return False
        try:
            view[:] = scratch
        except (TypeError, ValueError, BufferError):
            return False
        return True
