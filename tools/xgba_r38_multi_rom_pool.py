#!/usr/bin/env python3
"""R38 multi-ROM lossless *storage* mounting and hostile-workload testing.

Host-only, read-only source ROM catalogue. ROMs are NEVER merged into an
executable guest, scripts are not run, engine tables are not translated and
saves are not modified. Every byte comes from SHA-256 verified R36 pages.
Guest transfers remain bounded to <= 16 KiB; no GBA RAM capacity is extended.
"""
from __future__ import annotations

from collections import OrderedDict
import hashlib
from pathlib import Path

import xgba_r36_binary_pages as r36

DEFAULT_MAX_SOURCES = 16
DEFAULT_HOST_CACHE = 4 * r36.PAGE_SIZE


class MultiROMError(ValueError):
    pass


def _integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise MultiROMError("Invalid " + name)
    return value


class MultiROMPool:
    """Source-isolated whole-ROM addressing over verified R36 sidecar indexes.

    The host may hold any number of complete independent ROM sources in their
    backing files. Only requested immutable page bytes enter the bounded LRU.
    Eviction is host-only: this does NOT establish safe asynchronous guest DMA.
    """

    def __init__(self, *, max_sources=DEFAULT_MAX_SOURCES,
                 max_cache_bytes=DEFAULT_HOST_CACHE,
                 max_transfer_bytes=r36.PAGE_SIZE):
        self.max_sources = _integer(max_sources, 1, 64, "source count")
        self.max_cache_bytes = _integer(max_cache_bytes, 1, 64 * 1024 * 1024,
                                         "cache budget")
        self.max_transfer_bytes = _integer(max_transfer_bytes, 1, r36.PAGE_SIZE,
                                            "guest transfer limit")
        self._sources = {}
        self._cache = OrderedDict()
        self._cache_bytes = 0
        self.evictions = 0
        self.page_misses = 0
        self.page_hits = 0

    @property
    def source_ids(self):
        return tuple(self._sources)

    @property
    def source_count(self):
        return len(self._sources)

    @property
    def total_source_bytes(self):
        return sum(p.rom_bytes for p in self._sources.values())

    @property
    def total_pages(self):
        return sum(p.resource_count for p in self._sources.values())

    @property
    def staged_bytes(self):
        return self._cache_bytes

    def _source(self, source_id):
        if not isinstance(source_id, str):
            raise MultiROMError("Source namespace must be a string")
        try:
            return self._sources[source_id]
        except KeyError as exc:
            raise MultiROMError("Unknown original ROM namespace") from exc

    def mount(self, page_index):
        """Check the entire new source before publishing it; no partial mount."""
        if self.source_count >= self.max_sources:
            raise MultiROMError("Source count budget exceeded")
        try:
            candidate = r36.PagedBinaryPool(page_index,
                                            max_staged_bytes=self.max_cache_bytes,
                                            max_window_bytes=r36.PAGE_SIZE)
        except (OSError, ValueError) as exc:
            raise MultiROMError("Source page validation failed: " + str(exc)) from exc
        if candidate.source_id in self._sources:
            raise MultiROMError("Original ROM namespace already mounted")
        self._sources[candidate.source_id] = candidate
        return candidate.source_id

    def mount_many(self, page_indexes):
        """Atomic N-way mount: failed or duplicate input leaves prior state intact."""
        if not isinstance(page_indexes, (list, tuple)) or not page_indexes:
            raise MultiROMError("Expected at least one page-index path")
        if len(page_indexes) + self.source_count > self.max_sources:
            raise MultiROMError("Source count budget exceeded")
        pending = {}
        for index in page_indexes:
            try:
                candidate = r36.PagedBinaryPool(index,
                                                max_staged_bytes=self.max_cache_bytes,
                                                max_window_bytes=r36.PAGE_SIZE)
            except (OSError, ValueError) as exc:
                raise MultiROMError("Source page validation failed: " + str(exc)) from exc
            sid = candidate.source_id
            if sid in self._sources or sid in pending:
                raise MultiROMError("Duplicate original ROM namespace")
            pending[sid] = candidate
        self._sources.update(pending)
        return tuple(pending)

    def original_map(self, source_id, group, number):
        pool = self._source(source_id)
        _integer(group, 0, len(pool.original_group_map_counts) - 1, "source map group")
        _integer(number, 0, pool.original_group_map_counts[group] - 1,
                 "original source map number")
        return (source_id, group, number)

    def script_roots(self, source_id):
        pool = self._source(source_id)
        # R36 independently validates every root against original map identity.
        # Return copies so a caller cannot mutate the source's metadata.
        return tuple(dict(x) for x in pool.script_roots["original_script_entrypoints"])

    def read_rom(self, source_id, offset, length):
        """Read a bounded window, including a window crossing two 16-KiB pages."""
        pool = self._source(source_id)
        _integer(offset, 0, pool.rom_bytes, "original source ROM offset")
        _integer(length, 0, self.max_transfer_bytes, "transfer size")
        if length > pool.rom_bytes - offset:
            raise MultiROMError("Source transfer outside original ROM")
        try:
            return pool.read_rom(offset, length)
        except (OSError, ValueError) as exc:
            raise MultiROMError("Source page read failed integrity/bounds") from exc

    def read_pointer(self, source_id, pointer, length):
        """Resolve *only* a source-local GBA ROM pointer, never a merged address."""
        _integer(pointer, 0, 0xffffffff, "source pointer")
        if not 0x08000000 <= pointer < 0x0a000000:
            raise MultiROMError("Pointer is not in source ROM address space")
        return self.read_rom(source_id, pointer - 0x08000000, length)

    def stage_page(self, source_id, page_number):
        """Return immutable bytes; caller cannot retain a mutable/aliased cache view."""
        pool = self._source(source_id)
        _integer(page_number, 0, pool.resource_count - 1, "source-local page")
        key = (source_id, page_number)
        if key in self._cache:
            self._cache.move_to_end(key)
            self.page_hits += 1
            return self._cache[key]
        rid = f"rom.page.{page_number:06d}"
        length = min(r36.PAGE_SIZE, pool.rom_bytes - page_number*r36.PAGE_SIZE)
        if length > self.max_cache_bytes:
            raise MultiROMError("One complete page exceeds host cache budget")
        # Verify before ANY cache change: corruption must never evict good data.
        try:
            block = pool.read_window(rid, 0, length)
        except (OSError, ValueError) as exc:
            raise MultiROMError("Staged source page failed verification") from exc
        while self._cache and self._cache_bytes + len(block) > self.max_cache_bytes:
            _, old = self._cache.popitem(last=False)
            self._cache_bytes -= len(old)
            self.evictions += 1
        self._cache[key] = block
        self._cache_bytes += len(block)
        self.page_misses += 1
        return block

    def unstage_all(self):
        self._cache.clear()
        self._cache_bytes = 0

    def audit_complete_sources(self):
        """Actually hash all mounted original bytes, not just a sampled subset."""
        verified = []
        for sid, pool in self._sources.items():
            digest = hashlib.sha256()
            seen = 0
            for offset in range(0, pool.rom_bytes, r36.PAGE_SIZE):
                length = min(r36.PAGE_SIZE, pool.rom_bytes - offset)
                block = self.read_rom(sid, offset, length)
                digest.update(block)
                seen += len(block)
            if seen != pool.rom_bytes or digest.hexdigest() != pool.source_sha256:
                raise MultiROMError("Whole source byte audit failed")
            verified.append({
                "source_id": sid, "source_sha256": pool.source_sha256,
                "rom_bytes": seen, "pages": pool.resource_count,
                "original_map_count": sum(pool.original_group_map_counts),
                "script_entrypoint_references": len(pool.script_roots["original_script_entrypoints"]),
            })
        return {
            "sources": verified, "total_original_bytes_verified": sum(x["rom_bytes"] for x in verified),
            "total_pages_verified": sum(x["pages"] for x in verified),
            "rom_bytes_preserved": True, "source_ids_preserved": True,
            "engine_interoperability_proven": False,
            "gameplay_scripts_executed": False, "cross_world_saves_implemented": False,
            "native_guest_dma_lifetime_proven": False,
        }

    def close(self):
        self.unstage_all()
        self._sources.clear()
