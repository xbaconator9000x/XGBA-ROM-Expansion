#!/usr/bin/env python3
"""Private manifest-backed trainer resource bridge for the 16-KiB host window.

This bridge consumes the same manifest emitted for patched mGBA, validates
the source identity and exact offsets against the immutable private pack,
and only publishes complete detached windows. No ROM data belongs in git.
"""
from __future__ import annotations

import json
from pathlib import Path

from xgba_expansion_trainer_host_pack import HEADER
from xgba_expansion_trainer_host_provider import TrainerHostProvider
from xgba_expansion_trainer_provider_catalogue import PAGE_BYTES, PAGE_CAPACITY, ProviderPackError
from xgba_expansion_trainer_mmio_manifest import export_manifest


class TrainerManifestBridge:
    def __init__(self, manifest_path: Path, index_path: Path):
        manifest_path = Path(manifest_path)
        index_path = Path(index_path)
        # Reject symlinked ancestors as well as leaf files. A private pack
        # must never escape its intended provider directory via an alias.
        for path in (manifest_path, index_path):
            if any(part.is_symlink() for part in (path, *path.parents)):
                raise ProviderPackError("unsafe private trainer manifest path")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ProviderPackError("invalid trainer MMIO manifest") from exc
        if not isinstance(manifest, dict) or manifest.get("format") != "xgba-resource-manifest" or manifest.get("version") != 1:
            raise ProviderPackError("unsupported trainer MMIO manifest")
        source = manifest.get("source_identity")
        if not isinstance(source, dict):
            raise ProviderPackError("missing source identity")
        name = source.get("id")
        targets = {f"rhh-{target}-expansion-1.17.2": target for target in ("emerald", "firered", "leafgreen")}
        if name not in targets:
            raise ProviderPackError("unsupported source identity")
        data_file = manifest.get("data_file")
        if not isinstance(data_file, str) or not data_file or Path(data_file).name != data_file:
            raise ProviderPackError("unsafe private pack filename")
        pack = manifest_path.parent / data_file
        if (any(part.is_symlink() for part in (pack, *pack.parents))
                or pack.parent.resolve() != index_path.parent.resolve()):
            raise ProviderPackError("private pack path mismatch")
        expected = export_manifest(pack, index_path, source.get("sha256"), targets[name])
        if manifest != expected:
            raise ProviderPackError("manifest does not match authenticated private pack")
        self._provider = TrainerHostProvider(pack, index_path)

    def stage(self, resource_id: str, requested_bytes: int, window: bytearray | memoryview) -> bool:
        """Synchronous atomic host window transfer; False preserves fallback state."""
        return self._provider.stage_mmio_page(resource_id, requested_bytes, window)
