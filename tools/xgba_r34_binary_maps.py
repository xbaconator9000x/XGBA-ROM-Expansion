#!/usr/bin/env python3
"""R34 read-only discovery and opt-in local export of Emerald-family ROM maps.

Untrusted ROM data is validated before any map/header or array is counted.
Never rewrites source map group/number, game scripts, ROM bytes or saves.
An Emerald-compatible binary layout is a STRUCTURAL finding, not proof that
custom bytecode, trainer data, move engines or scripts can run in any other game.
"""
from __future__ import annotations

from array import array
from collections import Counter
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys

import xgba_resource_sidecar as sidecar

GBA_BASE = 0x08000000
MAX_ROM_BYTES = 64 * 1024 * 1024
MAX_GROUPS = 256
MAX_GROUP_MAPS = 256
MAX_LAYOUT_DIM = 2048
MAX_CONNECTIONS = 64
MAX_STRUCTURED_MAPS = 8192
MAX_SHARD_ENTRIES = 256
MAX_SHARD_BYTES = 256 * 1024 * 1024
SOURCE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
EVENT_RECORD_SIZES = (24, 8, 16, 12)
RESOURCE_KINDS = ("header", "layout", "border", "map_grid", "events", "objects", "warps", "coordinate_events", "background_events", "connections", "connection_entries", "primary_tileset_descriptor", "secondary_tileset_descriptor")


class DiscoveryError(ValueError):
    pass


class BinaryMapDiscovery:
    """Local, no-network introspection of a user's binary .gba ROM."""

    def __init__(self, rom):
        if isinstance(rom, (bytes, bytearray)):
            data = bytes(rom)
        else:
            path = Path(rom)
            if path.stat().st_size > MAX_ROM_BYTES:
                raise DiscoveryError("GBA input exceeds read-only scan byte cap")
            data = path.read_bytes()
        if not 0xC0 <= len(data) <= MAX_ROM_BYTES or len(data) % 4:
            raise DiscoveryError("Invalid GBA file length")
        self.data = data
        self.size = len(data)
        self.digest = hashlib.sha256(data).hexdigest()
        header = data[:0xC0]
        if header[0xB2] != 0x96 or ((-sum(header[0xA0:0xBD]) - 0x19) & 255) != header[0xBD]:
            raise DiscoveryError("GBA header failed fixed-marker or complement check")
        self.game_code = header[0xAC:0xB0].decode("ascii", "replace")
        self.title = header[0xA0:0xAC].rstrip(b"\x00 ").decode("ascii", "replace")
        self.words = array("I")
        self.words.frombytes(data)
        if sys.byteorder != "little":
            self.words.byteswap()

    def pointer(self, word, size=1):
        if type(word) is not int or not GBA_BASE <= word < GBA_BASE + self.size:
            return None
        off = word - GBA_BASE
        return off if size <= self.size - off else None

    def span(self, offset, length):
        return type(offset) is int and type(length) is int and offset >= 0 and length >= 0 and offset <= self.size - length

    def u32(self, offset):
        return struct.unpack_from("<I", self.data, offset)[0]

    def _valid_tileset(self, address):
        off = self.pointer(address, 24)
        if off is None or self.data[off] > 1 or self.data[off + 1] > 1:
            return False
        tiles, palettes, metatiles, attributes = struct.unpack_from("<4I", self.data, off + 4)
        return all(self.pointer(x, 1) is not None for x in (tiles, palettes, metatiles, attributes))

    def _parse_header(self, address, group, number):
        off = self.pointer(address, 28)
        if off is None or (off & 3):
            return None
        layout_ptr, events_ptr, script_ptr, connections_ptr = struct.unpack_from("<4I", self.data, off)
        layout_off = self.pointer(layout_ptr, 24)
        events_off = self.pointer(events_ptr, 20)
        if layout_off is None or events_off is None or (layout_off & 3) or (events_off & 3):
            return None
        if script_ptr and self.pointer(script_ptr) is None:
            return None
        if connections_ptr and self.pointer(connections_ptr, 8) is None:
            return None
        width, height, border, grid, tiles1, tiles2 = struct.unpack_from("<6I", self.data, layout_off)
        if not (1 <= width <= MAX_LAYOUT_DIM and 1 <= height <= MAX_LAYOUT_DIM):
            return None
        grid_len = width * height * 2
        if self.pointer(grid, grid_len) is None or self.pointer(border, 8) is None:
            return None
        if not self._valid_tileset(tiles1) or not self._valid_tileset(tiles2):
            return None
        counts = struct.unpack_from("<4B", self.data, events_off)
        arrays = struct.unpack_from("<4I", self.data, events_off + 4)
        for i, n in enumerate(counts):
            if n and self.pointer(arrays[i], n * EVENT_RECORD_SIZES[i]) is None:
                return None
        connection_count = 0
        connection_entries = 0
        if connections_ptr:
            connection_count, connection_entries = struct.unpack_from("<iI", self.data, connections_ptr - GBA_BASE)
            if not 0 <= connection_count <= MAX_CONNECTIONS:
                return None
            if connection_count and self.pointer(connection_entries, 12 * connection_count) is None:
                return None
        return {
            "group": group, "map": number, "header_offset": off,
            "layout_offset": layout_off, "width": width, "height": height,
            "border_offset": border - GBA_BASE, "map_grid_offset": grid - GBA_BASE,
            "map_grid_bytes": grid_len,
            "events_offset": events_off,
            "object_count": counts[0], "warp_count": counts[1],
            "coordinate_event_count": counts[2], "background_event_count": counts[3],
            "event_array_offsets": [v - GBA_BASE if counts[i] else None for i, v in enumerate(arrays)],
            "script_root_offset": script_ptr - GBA_BASE if script_ptr else None,
            "connections_offset": connections_ptr - GBA_BASE if connections_ptr else None,
            "connection_count": connection_count,
            "connection_array_offset": connection_entries - GBA_BASE if connection_count else None,
            "primary_tileset_offset": tiles1 - GBA_BASE,
            "secondary_tileset_offset": tiles2 - GBA_BASE,
            "music_id": struct.unpack_from("<H", self.data, off + 16)[0],
            "original_layout_id": struct.unpack_from("<H", self.data, off + 18)[0],
        }

    def _candidate(self, table_off, refs, *, allow_null_slots=False):
        if table_off % 4 or table_off >= self.size - 24:
            return None
        targets = []
        previous = None
        for i in range(MAX_GROUPS):
            if not self.span(table_off + 4 * i, 4):
                break
            offset = self.pointer(self.u32(table_off + 4 * i))
            if offset is None or offset % 4 or offset >= table_off or (previous is not None and offset <= previous):
                break
            if previous is not None and offset - previous > MAX_GROUP_MAPS * 4:
                break
            targets.append(offset)
            previous = offset
        if not 8 <= len(targets) <= MAX_GROUPS:
            return None
        # The original Emerald data/maps/groups.inc lays the group-table
        # pointer array immediately after contiguous group map-pointer arrays.
        if targets[0] >= table_off or (table_off - targets[-1]) % 4:
            return None
        counts = [(right - left) // 4 for left, right in zip(targets, targets[1:])]
        counts.append((table_off - targets[-1]) // 4)
        if any(not 1 <= c <= MAX_GROUP_MAPS for c in counts):
            return None
        total = sum(counts)
        if not 32 <= total <= MAX_STRUCTURED_MAPS:
            return None
        # Cheap fail-closed gate before touching every candidate header.
        probes = [(0, 0), (0, min(2, counts[0] - 1)),
                  (len(targets) // 2, 0), (len(targets) - 1, counts[-1] - 1)]
        verified_probes = 0
        for g, n in probes:
            address = self.u32(targets[g] + n * 4)
            if allow_null_slots and address == 0:
                continue
            if self._parse_header(address, g, n) is None:
                return None
            verified_probes += 1
        if not verified_probes:
            return None
        maps = []
        null_slots = []
        for group, start in enumerate(targets):
            for number in range(counts[group]):
                address = self.u32(start + number * 4)
                if address == 0 and allow_null_slots:
                    # HnS decomp-derived map tables preserve deliberately
                    # empty numeric slots; DO NOT compact/renumber other maps.
                    null_slots.append({"group": group, "map": number})
                    continue
                record = self._parse_header(address, group, number)
                if record is None:
                    # An invalid *nonzero* pointer remains fatal even when
                    # known-null holes are permitted; never skip corruption.
                    return None
                maps.append(record)
        if len(maps) < 32:
            return None
        return {"table_offset": table_off, "reference_count": refs,
                "group_count": len(targets), "map_count": len(maps),
                "slot_count": total, "null_slot_count": len(null_slots),
                "null_slots": null_slots,
                "group_map_counts": counts, "maps": maps}

    def discover(self, min_root_references=4, *, allow_null_slots=False):
        if type(allow_null_slots) is not bool or type(min_root_references) is not int or \
           min_root_references < (1 if allow_null_slots else 2):
            raise DiscoveryError("Invalid table reference threshold or null-slot policy")
        # A ROM code/data pointer must refer to the table. Do not trust
        # only the header title, BPEE game code, or a pinned absolute offset.
        references = Counter()
        for word in self.words:
            if word % 4 == 0 and GBA_BASE + 0xC0 <= word < GBA_BASE + self.size:
                references[word] += 1
        candidates = []
        for absolute, count in references.items():
            if count < min_root_references:
                continue
            probe = self._candidate(absolute - GBA_BASE, count,
                                    allow_null_slots=allow_null_slots)
            if probe:
                candidates.append(probe)
        if not candidates:
            raise DiscoveryError("No validated referenced Emerald-family map-group table")
        candidates.sort(key=lambda e: (e["reference_count"], e["map_count"], e["group_count"]), reverse=True)
        if len(candidates) > 1 and (candidates[0]["reference_count"], candidates[0]["map_count"]) == (candidates[1]["reference_count"], candidates[1]["map_count"]):
            raise DiscoveryError("Ambiguous equally supported map-group tables")
        result = candidates[0]
        layouts = set()
        sizes = Counter()
        for m in result["maps"]:
            layouts.add(m["layout_offset"])
            for key in ("object_count", "warp_count", "coordinate_event_count", "background_event_count"):
                sizes[key] += m[key]
            sizes["connections"] += m["connection_count"]
            sizes["maps_with_scripts"] += bool(m["script_root_offset"] is not None)
        result["summary"] = {
            "map_groups": result["group_count"], "maps": result["map_count"],
            "original_numeric_map_slots": result["slot_count"],
            "zero_pointer_map_slots_preserved": result["null_slot_count"],
            "unique_layouts": len(layouts),
            "object_events": sizes["object_count"], "warp_events": sizes["warp_count"],
            "coordinate_events": sizes["coordinate_event_count"],
            "background_events": sizes["background_event_count"],
            "connections": sizes["connections"],
            "maps_with_script_roots": sizes["maps_with_scripts"],
            "map_group_table_references": result["reference_count"],
            "headers_fully_structurally_validated": result["map_count"],
            "script_bytecode_decoded": 0,
            "battle_species_moves_abilities_decoded": False,
        }
        return result

    def segments(self, m):
        """Each fixed-length source ROM structure; unknown-length script and
        tileset graphic data are NOT copied by guessing pointer boundaries."""
        items = [("header", m["header_offset"], 28),
                 ("layout", m["layout_offset"], 24),
                 ("border", m["border_offset"], 8),
                 ("map_grid", m["map_grid_offset"], m["map_grid_bytes"]),
                 ("events", m["events_offset"], 20),
                 ("primary_tileset_descriptor", m["primary_tileset_offset"], 24),
                 ("secondary_tileset_descriptor", m["secondary_tileset_offset"], 24)]
        for key, count, size, offset in zip(
            ("objects", "warps", "coordinate_events", "background_events"),
            (m["object_count"], m["warp_count"], m["coordinate_event_count"], m["background_event_count"]),
            EVENT_RECORD_SIZES, m["event_array_offsets"]):
            if count:
                items.append((key, offset, count * size))
        if m["connections_offset"] is not None:
            items.append(("connections", m["connections_offset"], 8))
            if m["connection_count"]:
                items.append(("connection_entries", m["connection_array_offset"], 12 * m["connection_count"]))
        for kind, offset, size in items:
            if kind not in RESOURCE_KINDS or not self.span(offset, size):
                raise DiscoveryError("Non-contained map source segment")
        return items

    def _write_shard(self, directory, source, identity, index, records):
        name = f"{source}-{index:05d}"
        manifest_path = directory / (name + ".json")
        bin_path = directory / (name + ".bin")
        if manifest_path.exists() or bin_path.exists():
            raise DiscoveryError("Refusing to overwrite an existing original segment shard")
        entries = []
        digest = hashlib.sha256()
        off = 0
        with bin_path.open("xb") as handle:
            for resource_id, buffer in records:
                if not buffer:
                    raise DiscoveryError("Zero-length binary segment")
                handle.write(buffer)
                digest.update(buffer)
                entries.append({"id": resource_id, "offset": off, "length": len(buffer),
                                "sha256": hashlib.sha256(buffer).hexdigest()})
                off += len(buffer)
            handle.flush()
            os.fsync(handle.fileno())
        payload = {"format": sidecar.FORMAT, "version": sidecar.VERSION,
                   "source_identity": identity, "data_file": bin_path.name,
                   "resources": entries}
        encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf8")
        if len(encoded) > sidecar.MAX_MANIFEST_BYTES:
            raise DiscoveryError("Map metadata shard exceeds v1 sidecar manifest size")
        manifest_path.write_bytes(encoded)
        manifest = sidecar.load_manifest(manifest_path, expected_source_identity=identity)
        for entry in entries:
            # SHA-256 verify actual output bytes through production reader.
            read_count = sum(map(len, sidecar.iter_resource_chunks(manifest, entry["id"])))
            if read_count != entry["length"]:
                raise DiscoveryError("Segment shard failed output readback")
        return {"manifest": manifest_path.name, "data_file": bin_path.name,
                "resources": len(entries), "payload_bytes": off,
                "sha256": digest.hexdigest()}

    def export_maps(self, discovered, destination, source_id, *, max_shard_entries=MAX_SHARD_ENTRIES,
                    max_shard_bytes=MAX_SHARD_BYTES):
        if not isinstance(source_id, str) or not SOURCE_ID.fullmatch(source_id):
            raise DiscoveryError("Invalid binary source namespace")
        if type(max_shard_entries) is not int or not 1 <= max_shard_entries <= MAX_SHARD_ENTRIES:
            raise DiscoveryError("Invalid shard entry limit")
        if type(max_shard_bytes) is not int or not 1024 <= max_shard_bytes <= MAX_SHARD_BYTES:
            raise DiscoveryError("Invalid shard byte limit")
        directory = Path(destination)
        directory.mkdir(parents=True, exist_ok=True)
        if any(directory.iterdir()):
            raise DiscoveryError("Output folder must be empty")
        identity = {"id": source_id, "sha256": self.digest}
        shards = []
        locations = {}
        segments = []
        queued = []
        size = 0
        total = 0
        try:
            for m in discovered["maps"]:
                for kind, off, length in self.segments(m):
                    rid = f"binary.{m['group']}.{m['map']}.{kind}"
                    if rid in locations:
                        raise DiscoveryError("Duplicate original group/map segment")
                    if length > max_shard_bytes:
                        raise DiscoveryError("Source segment exceeds requested shard byte cap")
                    if queued and (len(queued) >= max_shard_entries or size + length > max_shard_bytes):
                        shards.append(self._write_shard(directory, source_id, identity, len(shards), queued))
                        queued = []
                        size = 0
                    locations[rid] = {"id": rid, "original_group": m["group"], "original_map": m["map"],
                                      "source_rom_offset": off, "length": length, "kind": kind,
                                      "shard_number": len(shards)}
                    segments.append(locations[rid])
                    queued.append((rid, self.data[off:off + length]))
                    size += length
                    total += length
            if queued:
                shards.append(self._write_shard(directory, source_id, identity, len(shards), queued))
            for segment in segments:
                segment["manifest"] = shards[segment.pop("shard_number")]["manifest"]
            report = {"format": "xgba-binary-map-source", "version": 1,
                      "source_identity": identity, "original_map_id_remapping": False,
                      "engine_runtime_compatibility_certified": False,
                      "binary_only_map_structures_verified": True,
                      "source_map_group_table_offset": discovered["table_offset"],
                      "group_map_counts": discovered["group_map_counts"],
                      "original_null_map_slots": discovered["null_slots"],
                      "summary": dict(discovered["summary"], exported_fixed_segments=len(segments),
                                      exported_raw_bytes=total, shard_count=len(shards)),
                      "shards": shards, "segments": segments,
                      "script_bytecode": "roots_only_unknown_lengths_not_copied",
                      "battle_data": "not_yet_decoded_or_exported",
                      "original_map_headers": [
                          {"group": m["group"], "map": m["map"], "width": m["width"],
                           "height": m["height"], "original_layout_id": m["original_layout_id"],
                           "script_root_offset": m["script_root_offset"],
                           "connections": m["connection_count"],
                           "object_events": m["object_count"], "warps": m["warp_count"],
                           "coord_events": m["coordinate_event_count"],
                           "bg_events": m["background_event_count"]}
                          for m in discovered["maps"]]}
            (directory / "xgba-binary-maps.json").write_text(
                json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf8")
            return report
        except BaseException:
            for path in directory.iterdir():
                if path.is_file():
                    path.unlink()
            raise


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("rom", help="private user-supplied Emerald-family GBA image")
    p.add_argument("--out", help="write local aggregate JSON evidence (no source bytes)")
    p.add_argument("--export", help="write all known fixed-length map structures to private sidecar shards")
    p.add_argument("--source-id", help="private source namespace required for --export")
    p.add_argument("--allow-null-maps", action="store_true",
                   help="permit actual zero-pointer map slots without changing original IDs (HnS compatibility)")
    args = p.parse_args(argv)
    try:
        scan = BinaryMapDiscovery(args.rom)
        result = scan.discover(
            min_root_references=(1 if args.allow_null_maps else 4),
            allow_null_slots=args.allow_null_maps)
        summary = {"bytes": scan.size, "game_code": scan.game_code,
                   "source_sha256": scan.digest, "header_valid": True,
                   "binary_map_structure_profile": "pret-emerald-structural-candidate-not-execution-certified",
                   "source_rom_untouched": True, "summary": result["summary"],
                   "original_group_map_counts": result["group_map_counts"]}
        if args.export:
            if not args.source_id:
                raise DiscoveryError("--source-id is required for --export")
            exported = scan.export_maps(result, args.export, args.source_id)
            summary["export"] = {"fixed_segments": exported["summary"]["exported_fixed_segments"],
                                 "raw_bytes": exported["summary"]["exported_raw_bytes"],
                                 "shards": exported["summary"]["shard_count"],
                                 "scripts_executable": False,
                                 "battle_data_executable": False}
        if args.out:
            Path(args.out).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf8")
        print(json.dumps(summary, sort_keys=True))
        return 0
    except (DiscoveryError, OSError, ValueError) as exc:
        print("XGBA_BINARY_MAP_DISCOVERY_FAIL_CLOSED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
