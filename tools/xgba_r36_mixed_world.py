#!/usr/bin/env python3
"""R36 opt-in full original-ROM pages layered onto existing R35 mixed world pool.

All source map IDs remain original. Page bytes are NEVER executed directly.
"""
from __future__ import annotations

import json
from pathlib import Path
import xgba_mixed_world_pool as mixed
from xgba_r36_binary_pages import PagedBinaryPool


class R36MixedWorldPool(mixed.MixedWorldPool):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._pages = {}

    def mount_binary_pages(self, index_path):
        """Mount additional raw pages for an already verified binary map world.

        Must share precisely the same original ROM digest and map-group table.
        Refuse before publication on mismatch, leaving all live worlds intact.
        """
        candidate=PagedBinaryPool(index_path,max_window_bytes=self.max_window_bytes,
                                  max_staged_bytes=self.max_staged_bytes)
        source=candidate.source_id
        existing=self._sources.get(source)
        if not isinstance(existing,mixed.BinaryMapPool):
            raise mixed.MixedPoolError("Binary map world must be mounted before raw pages")
        if source in self._pages:
            raise mixed.MixedPoolError("Raw page provider already mounted")
        if candidate.source_sha256!=existing.source_sha256:
            raise mixed.MixedPoolError("Raw pages and map segment source ROM identities disagree")
        source_index=json.loads(Path(existing._index).read_text(encoding="utf8"))
        if tuple(source_index["group_map_counts"])!=candidate.original_group_map_counts or source_index["source_map_group_table_offset"]!=candidate.original_map_group_table_offset:
            raise mixed.MixedPoolError("Page metadata disagrees with original binary map group table")
        self._pages[source]=candidate
        self._backends.append(candidate)
        return candidate

    def _resolve(self,handle):
        if isinstance(handle,mixed.SourceHandle) and isinstance(handle.resource_id,str) and handle.resource_id.startswith("rom.page."):
            p=self._pages.get(handle.source_id)
            if p is None:
                raise mixed.MixedPoolError("Whole-ROM pages not mounted for source")
            if p.source_of(handle.resource_id)[0]!=handle.source_id:
                raise mixed.MixedPoolError("Raw page source namespace mismatch")
            return p
        return super()._resolve(handle)

    def find_rom_page(self,source_id,rom_offset):
        p=self._pages.get(source_id)
        if p is None:return None
        rid,within=p.page_at(rom_offset)
        return mixed.SourceHandle(source_id,rid),within

    def read_rom(self,source_id,original_offset,length):
        p=self._pages.get(source_id)
        if p is None:raise mixed.MixedPoolError("Unregistered whole-ROM source")
        if type(length) is not int or not 0<=length<=self.max_window_bytes:
            raise mixed.MixedPoolError("Read exceeds common guest window limit")
        return p.read_rom(original_offset,length)

    def script_root_census(self,source_id):
        p=self._pages.get(source_id)
        if p is None:raise mixed.MixedPoolError("Script entrypoint census not mounted")
        return p.script_roots["summary"]

    def close(self):
        super().close()
        self._pages={}
