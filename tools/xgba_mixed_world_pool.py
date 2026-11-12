#!/usr/bin/env python3
"""R35: verified binary-ROM map resources in the R33 multi-source host pool.

Read-only resource resolution. No custom script execution, save rewrites,
emulator hook installation, or claims of cross-ROM gameplay compatibility.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import struct

import xgba_resource_sidecar as sidecar
import xgba_corpus_pool as source_pool

ROM_BASE = 0x08000000
MAX_ROM_BYTES = 64 * 1024 * 1024
MAX_INDEX_BYTES = 64 * 1024 * 1024
MAX_MAPS = 8192
MAX_SEGMENTS = 250000
MAX_SHARDS = 20000
MAX_WINDOW = 16384
MAX_STAGING = 16 * 1024 * 1024
MAX_ITEM = 16 * 1024 * 1024
MAX_CHUNK = 65536
SOURCE_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z')
SHA_RE = re.compile(r'[0-9a-f]{64}\Z')
FILE_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,159}\Z')
KINDS = frozenset((
    'header', 'layout', 'border', 'map_grid', 'events',
    'objects', 'warps', 'coordinate_events', 'background_events',
    'connections', 'connection_entries', 'primary_tileset_descriptor',
    'secondary_tileset_descriptor'))
MANDATORY = frozenset((
    'header', 'layout', 'border', 'map_grid', 'events',
    'primary_tileset_descriptor', 'secondary_tileset_descriptor'))
EVENT_SIZES = {'objects': 24, 'warps': 8, 'coordinate_events': 16,
               'background_events': 12}


class MixedPoolError(ValueError):
    pass


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise MixedPoolError('Duplicate index key')
        result[key] = value
    return result


def _invalid_constant(value):
    raise MixedPoolError('Non-finite index number')


def _integer(value, label, *, low=0, high=MAX_ROM_BYTES):
    if type(value) is not int or not low <= value <= high:
        raise MixedPoolError('Invalid ' + label)
    return value


def _filename(value):
    if not isinstance(value, str) or FILE_RE.fullmatch(value) is None:
        raise MixedPoolError('Unsafe shard filename')
    return value


def _read_index(original):
    path = Path(original)
    if path.is_symlink():
        raise MixedPoolError('Symlinked binary map index refused')
    path = path.resolve(strict=True)
    if not path.is_file() or path.stat().st_size > MAX_INDEX_BYTES:
        raise MixedPoolError('Missing or oversized binary map index')
    try:
        with path.open('rb') as f:
            return path, json.loads(f.read(MAX_INDEX_BYTES + 1).decode('utf8'),
                                    object_pairs_hook=_pairs,
                                    parse_constant=_invalid_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise MixedPoolError('Invalid binary map catalogue JSON') from exc


class BinaryMapPool:
    """Eagerly validate index and pointers; lazily deliver individual assets.

    This adapter consumes only the deterministic, source-bound R34 layout.
    A file claiming to be another Pokémon engine does not bypass validation.
    """

    def __init__(self, index_path, *, max_window_bytes=MAX_WINDOW,
                 max_staged_bytes=MAX_STAGING,
                 max_resource_bytes=MAX_ITEM, chunk_size=MAX_CHUNK):
        self.max_window_bytes = _integer(max_window_bytes, 'window limit',
                                         low=1, high=MAX_ITEM)
        self.max_staged_bytes = _integer(max_staged_bytes, 'memory limit',
                                         low=1)
        self.max_resource_bytes = _integer(max_resource_bytes, 'resource limit',
                                           low=1)
        self.chunk_size = _integer(chunk_size, 'chunk size', low=1,
                                   high=sidecar.MAX_CHUNK_SIZE)
        self._segments = {}
        self._maps = {}
        self._shards = {}
        self._staged = {}
        self.source_id = None
        self.source_sha256 = None
        self.open(index_path)

    @property
    def source_ids(self):
        return (self.source_id,) if self.source_id else ()

    @property
    def resource_count(self):
        return len(self._segments)

    @property
    def map_count(self):
        return len(self._maps)

    @property
    def shard_count(self):
        return len(self._shards)

    @property
    def staged_bytes(self):
        return sum(len(b) for b in self._staged.values())

    def close(self):
        self._segments = {}
        self._maps = {}
        self._shards = {}
        self._staged = {}
        self.source_id = self.source_sha256 = None

    def open(self, index_path):
        """Transactional install: malformed replacements cannot displace live data."""
        path, doc = _read_index(index_path)
        if not isinstance(doc, dict) or doc.get('format') != 'xgba-binary-map-source' or \
           type(doc.get('version')) is not int or doc['version'] != 1 or \
           doc.get('original_map_id_remapping') is not False or \
           doc.get('engine_runtime_compatibility_certified') is not False or \
           doc.get('binary_only_map_structures_verified') is not True:
            raise MixedPoolError('Unsupported binary catalogue or unsupported claim')
        identity = doc.get('source_identity')
        if not isinstance(identity, dict) or set(identity) != {'id', 'sha256'} or \
           not isinstance(identity['id'], str) or SOURCE_RE.fullmatch(identity['id']) is None or \
           not isinstance(identity['sha256'], str) or SHA_RE.fullmatch(identity['sha256']) is None:
            raise MixedPoolError('Invalid binary source identity')
        source_id, digest = identity['id'], identity['sha256']
        counts, headers, segments, shards, summary = (
            doc.get('group_map_counts'), doc.get('original_map_headers'),
            doc.get('segments'), doc.get('shards'), doc.get('summary'))
        if not isinstance(counts, list) or not 1 <= len(counts) <= 256 or \
           not all(type(x) is int and 1 <= x <= 256 for x in counts) or \
           not isinstance(headers, list) or len(headers) != sum(counts) or len(headers) > MAX_MAPS or \
           not isinstance(segments, list) or len(segments) > MAX_SEGMENTS or \
           not isinstance(shards, list) or len(shards) > MAX_SHARDS or \
           not isinstance(summary, dict):
            raise MixedPoolError('Invalid map counts, catalogue or budgets')
        if summary.get('maps') != len(headers) or summary.get('map_groups') != len(counts) or \
           summary.get('exported_fixed_segments') != len(segments) or \
           summary.get('shard_count') != len(shards) or \
           doc.get('script_bytecode') != 'roots_only_unknown_lengths_not_copied' or \
           doc.get('battle_data') != 'not_yet_decoded_or_exported':
            raise MixedPoolError('Binary source overstates import coverage')
        maps = {}
        for group, count in enumerate(counts):
            for number in range(count):
                info = headers[len(maps)]
                if not isinstance(info, dict) or \
                   (info.get('group'), info.get('map')) != (group, number):
                    raise MixedPoolError('Original binary map identity changed')
                _integer(info.get('width'), 'map width', low=1, high=2048)
                _integer(info.get('height'), 'map height', low=1, high=2048)
                for field in ('object_events', 'warps', 'coord_events',
                              'bg_events', 'connections'):
                    _integer(info.get(field), 'event count', low=0, high=255)
                if info.get('script_root_offset') is not None:
                    _integer(info['script_root_offset'], 'script root')
                maps[group, number] = info

        # Verify the source-identity of EVERY shard, including aggregate SHA.
        # This reads in fixed-size chunks and does not populate guest buffers.
        by_shard = {}
        for shard in shards:
            if not isinstance(shard, dict):
                raise MixedPoolError('Malformed source shard')
            filename = _filename(shard.get('manifest'))
            data_name = _filename(shard.get('data_file'))
            if filename in by_shard:
                raise MixedPoolError('Duplicate sidecar name')
            manifest_path = path.parent / filename
            data_path = path.parent / data_name
            if manifest_path.is_symlink() or data_path.is_symlink():
                raise MixedPoolError('Linked sidecar file refused')
            manifest = sidecar.load_manifest(manifest_path)
            if manifest.data_path.parent != path.parent or \
               manifest.data_path.name != data_name or \
               manifest.source_identity.id != source_id or \
               manifest.source_identity.sha256 != digest or \
               shard.get('resources') != len(manifest.resources) or \
               shard.get('payload_bytes') != sum(r.length for r in manifest.resources.values()):
                raise MixedPoolError('Sidecar source identity / bounds mismatch')
            expected = shard.get('sha256')
            if not isinstance(expected, str) or SHA_RE.fullmatch(expected) is None:
                raise MixedPoolError('Invalid shard checksum')
            size = 0
            sha = hashlib.sha256()
            with manifest.data_path.open('rb') as f:
                for block in iter(lambda: f.read(MAX_CHUNK), b''):
                    size += len(block)
                    if size > shard['payload_bytes']:
                        raise MixedPoolError('Unexpected shard content')
                    sha.update(block)
            if size != shard['payload_bytes'] or sha.hexdigest() != expected:
                raise MixedPoolError('Shard SHA-256 mismatch')
            by_shard[filename] = manifest

        resources = {}
        by_map = {key: {} for key in maps}
        coverage = {name: set() for name in by_shard}
        raw_bytes = 0
        for entry in segments:
            if not isinstance(entry, dict):
                raise MixedPoolError('Malformed map segment')
            group = _integer(entry.get('original_group'), 'original group',
                             high=255)
            number = _integer(entry.get('original_map'), 'original map', high=255)
            kind = entry.get('kind')
            if not isinstance(kind, str) or kind not in KINDS or \
               (group, number) not in by_map:
                raise MixedPoolError('Segment has unknown source map/kind')
            rid = 'binary.%d.%d.%s' % (group, number, kind)
            if entry.get('id') != rid or rid in resources:
                raise MixedPoolError('Non-original or duplicate map segment ID')
            offset = _integer(entry.get('source_rom_offset'), 'original ROM offset')
            length = _integer(entry.get('length'), 'map resource length', low=1)
            if offset + length > MAX_ROM_BYTES:
                raise MixedPoolError('Segment crosses ROM address limit')
            filename = _filename(entry.get('manifest'))
            m = by_shard.get(filename)
            record = m.resources.get(rid) if m else None
            if record is None or record.length != length:
                raise MixedPoolError('Segment not present in declared sidecar')
            resources[rid] = group, number, kind, offset, length, m
            by_map[group, number][kind] = rid
            coverage[filename].add(rid)
            raw_bytes += length
        if raw_bytes != summary.get('exported_raw_bytes'):
            raise MixedPoolError('Binary imported byte counts disagree')
        for filename, manifest in by_shard.items():
            if coverage[filename] != set(manifest.resources):
                raise MixedPoolError('Orphaned/unlisted binary map data')

        for (group, number), kinds in by_map.items():
            header_info = maps[group, number]
            if not MANDATORY.issubset(kinds):
                raise MixedPoolError('Incomplete map structures')
            lengths = {
                'header': 28, 'layout': 24, 'border': 8,
                'map_grid': 2 * header_info['width'] * header_info['height'],
                'events': 20, 'primary_tileset_descriptor': 24,
                'secondary_tileset_descriptor': 24}
            for kind, field in zip(EVENT_SIZES,
                    ('object_events', 'warps', 'coord_events', 'bg_events')):
                if header_info[field]:
                    lengths[kind] = header_info[field] * EVENT_SIZES[kind]
                elif kind in kinds:
                    raise MixedPoolError('Unexpected empty event array')
            if header_info['connections']:
                lengths['connections'] = 8
                lengths['connection_entries'] = 12 * header_info['connections']
            elif 'connection_entries' in kinds:
                raise MixedPoolError('Unexpected empty connection entries')
            for kind, length in lengths.items():
                if kind not in kinds or resources[kinds[kind]][4] != length:
                    raise MixedPoolError('Original map structure length mismatch')

            def resource(kind):
                rid = kinds[kind]
                return b''.join(sidecar.iter_resource_chunks(
                    resources[rid][5], rid, self.chunk_size))

            def pointer(kind):
                return ROM_BASE + resources[kinds[kind]][3]

            header = resource('header')
            layout, events, script, connections = struct.unpack_from('<4I', header)
            script_offset = header_info['script_root_offset']
            expected_script = ROM_BASE + script_offset if script_offset is not None else 0
            if layout != pointer('layout') or events != pointer('events') or \
               script != expected_script or \
               connections != (pointer('connections') if 'connections' in kinds else 0):
                raise MixedPoolError('Original header pointer mismatch')
            width, height, border, grid, primary, secondary = struct.unpack_from(
                '<6I', resource('layout'))
            if (width, height, border, grid, primary, secondary) != (
                    header_info['width'], header_info['height'],
                    pointer('border'), pointer('map_grid'),
                    pointer('primary_tileset_descriptor'),
                    pointer('secondary_tileset_descriptor')):
                raise MixedPoolError('Original layout pointer mismatch')
            event_fields = struct.unpack_from('<4B4I', resource('events'))
            if event_fields[:4] != tuple(header_info[k] for k in (
                    'object_events', 'warps', 'coord_events', 'bg_events')):
                raise MixedPoolError('Original event counts mismatch')
            for i, kind in enumerate(EVENT_SIZES):
                if event_fields[i] and event_fields[4+i] != pointer(kind):
                    raise MixedPoolError('Original event array pointer mismatch')
            if header_info['connections']:
                count, entry_ptr = struct.unpack_from(
                    '<iI', resource('connections'))
                if count != header_info['connections'] or \
                   entry_ptr != pointer('connection_entries'):
                    raise MixedPoolError('Original connection pointer mismatch')

        # Transactional publication: all checks have passed.
        self._segments = resources
        self._maps = maps
        self._shards = by_shard
        self.source_id, self.source_sha256 = source_id, digest
        self._staged = {}
        return self

    def find_segment(self, group, number, kind):
        if type(group) is not int or type(number) is not int or kind not in KINDS:
            return None
        rid = 'binary.%d.%d.%s' % (group, number, kind)
        return rid if rid in self._segments else None

    def find_original_map(self, source_id, group, number):
        return self._maps.get((group, number)) if source_id == self.source_id else None

    def source_of(self, rid):
        try:
            group, number, kind, _, length, _ = self._segments[rid]
        except KeyError as exc:
            raise MixedPoolError('Unknown binary resource') from exc
        return self.source_id, 'maps/%d/%d/%s' % (group, number, kind), length

    def read_window(self, rid, start, length):
        if type(start) is not int or start < 0 or type(length) is not int or \
           not 0 <= length <= self.max_window_bytes:
            raise MixedPoolError('Window exceeds guest transfer cap')
        try:
            _, _, _, _, size, manifest = self._segments[rid]
        except KeyError as exc:
            raise MixedPoolError('Unknown binary resource') from exc
        if start > size or length > size - start:
            raise MixedPoolError('Window exceeds source span')
        result = bytearray()
        pos = 0
        # Sidecar v1 lacks authenticated per-chunk digests. Hash the COMPLETE
        # source resource before returning even a single-byte window.
        for block in sidecar.iter_resource_chunks(manifest, rid, self.chunk_size):
            low = max(0, start - pos)
            high = min(len(block), start + length - pos)
            if high > low:
                result.extend(block[low:high])
            pos += len(block)
        if pos != size or len(result) != length:
            raise MixedPoolError('Resource mutated during window read')
        return bytes(result)

    def stage(self, rid):
        try:
            _, _, _, _, size, manifest = self._segments[rid]
        except KeyError as exc:
            raise MixedPoolError('Unknown binary resource') from exc
        previous = self._staged.get(rid)
        used = self.staged_bytes - (len(previous) if previous is not None else 0)
        if size > self.max_resource_bytes or size > self.max_staged_bytes - used:
            raise MixedPoolError('Resource exceeds host staging budget')
        candidate = b''.join(sidecar.iter_resource_chunks(
            manifest, rid, self.chunk_size))
        if len(candidate) != size:
            raise MixedPoolError('Resource changed during staging')
        self._staged[rid] = candidate
        return memoryview(candidate)

    def staged_resource(self, rid):
        try:
            return memoryview(self._staged[rid])
        except KeyError as exc:
            raise MixedPoolError('Binary resource not staged') from exc

    def unstage(self, rid):
        self._staged.pop(rid, None)

    def verify_original_rom(self, rom_path):
        """Optional private proof: every packed byte matches user's source ROM."""
        digest = hashlib.sha256()
        path = Path(rom_path)
        with path.open('rb') as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                digest.update(block)
        if digest.hexdigest() != self.source_sha256:
            raise MixedPoolError('Original ROM digest mismatch')
        with path.open('rb') as rom:
            for rid, (_, _, _, offset, size, manifest) in self._segments.items():
                rom.seek(offset)
                remaining = size
                for block in sidecar.iter_resource_chunks(
                        manifest, rid, self.chunk_size):
                    if rom.read(len(block)) != block:
                        raise MixedPoolError('Original ROM segment mismatch')
                    remaining -= len(block)
                if remaining:
                    raise MixedPoolError('Truncated original ROM source segment')
        return len(self._segments)


@dataclass(frozen=True)
class SourceHandle:
    source_id: str
    resource_id: str


class MixedWorldPool:
    """Federate R32 source-based and R34 binary-based imports without ID edits."""

    def __init__(self, *, max_staged_bytes=MAX_STAGING,
                 max_window_bytes=MAX_WINDOW):
        self.max_staged_bytes = _integer(
            max_staged_bytes, 'global staging cap', low=1)
        self.max_window_bytes = _integer(
            max_window_bytes, 'global window cap', low=1, high=MAX_ITEM)
        self._sources = {}
        self._backends = []

    @property
    def source_ids(self):
        return tuple(self._sources)

    @property
    def resource_count(self):
        return sum(p.resource_count for p in self._backends)

    @property
    def staged_bytes(self):
        return sum(p.staged_bytes for p in self._backends)

    def _mount(self, pool):
        if any(s in self._sources for s in pool.source_ids):
            raise MixedPoolError('Source namespace already mounted')
        for source_id in pool.source_ids:
            self._sources[source_id] = pool
        self._backends.append(pool)
        return pool

    def mount_binary(self, catalog_path):
        return self._mount(BinaryMapPool(
            catalog_path, max_staged_bytes=self.max_staged_bytes,
            max_window_bytes=self.max_window_bytes))

    def mount_corpus(self, index_path):
        return self._mount(source_pool.CorpusPool(
            index_path, max_staged_bytes=self.max_staged_bytes,
            max_window_bytes=self.max_window_bytes))

    def find_source(self, source_id, original_path):
        backend = self._sources.get(source_id)
        if not isinstance(backend, source_pool.CorpusPool):
            return None
        rid = backend.find(source_id, original_path)
        return SourceHandle(source_id, rid) if rid else None

    def find_segment(self, source_id, group, number, kind):
        backend = self._sources.get(source_id)
        if not isinstance(backend, BinaryMapPool):
            return None
        rid = backend.find_segment(group, number, kind)
        return SourceHandle(source_id, rid) if rid else None

    def find_original_map(self, source_id, group, number):
        backend = self._sources.get(source_id)
        return backend.find_original_map(source_id, group, number) if backend else None

    def _resolve(self, handle):
        if not isinstance(handle, SourceHandle):
            raise MixedPoolError('Expected source-aware resource handle')
        backend = self._sources.get(handle.source_id)
        if backend is None:
            raise MixedPoolError('Unknown source world')
        if backend.source_of(handle.resource_id)[0] != handle.source_id:
            raise MixedPoolError('Source handle identity mismatch')
        return backend

    def source_of(self, handle):
        return self._resolve(handle).source_of(handle.resource_id)

    def read_window(self, handle, start, length):
        if type(length) is not int or not 0 <= length <= self.max_window_bytes:
            raise MixedPoolError('Window exceeds combined guest transfer cap')
        return self._resolve(handle).read_window(
            handle.resource_id, start, length)

    def stage(self, handle):
        backend = self._resolve(handle)
        size = backend.source_of(handle.resource_id)[2]
        try:
            old_size = len(backend.staged_resource(handle.resource_id))
        except (ValueError, KeyError, source_pool.PoolError, MixedPoolError):
            old_size = 0
        if size > self.max_staged_bytes - (self.staged_bytes - old_size):
            raise MixedPoolError('Resource exceeds combined multi-world RAM budget')
        return backend.stage(handle.resource_id)

    def unstage(self, handle):
        self._resolve(handle).unstage(handle.resource_id)

    def close(self):
        for backend in self._backends:
            backend.close()
        self._sources = {}
        self._backends = []
