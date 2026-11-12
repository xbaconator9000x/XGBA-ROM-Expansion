#!/usr/bin/env python3
"""R36: index every fixed-format warp/event trigger in R34 binary map packs.

This is a read-only original-world topology and SCRIPT ENTRY POINT inventory.
It never decodes/executed variable-length scripts or changes map IDs/save data.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import struct
import sys

from xgba_mixed_world_pool import BinaryMapPool, MixedPoolError, ROM_BASE, MAX_ROM_BYTES

MAX_EVENT_RECORDS = 250000
MAX_MAPS = 8192
MAX_GUEST_WINDOW = 16384

class GraphError(ValueError):
    pass


def _script_address(value):
    """Report opaque ROM addresses without assuming any opcode boundaries."""
    if value == 0:
        return 'null'
    if ROM_BASE <= value < ROM_BASE + MAX_ROM_BYTES:
        return 'rom_candidate'
    return 'non_rom_opaque'


def _source_map(source, group, number):
    return {'source_id': source, 'original_group': group, 'original_map': number}


def _warp_destination(pool, group, number):
    # Native original Emerald map constants: MAP_DYNAMIC is 0x7F/0x7F,
    # MAP_UNDEFINED is 0xFF/0xFF. Never silently map these to another world.
    if group == number == 127:
        return 'dynamic_original_engine'
    if group == number == 255:
        return 'undefined_original_engine'
    if (group, number) in pool._maps:
        return 'original_source_map'
    return 'unresolved_original_reference'


def extract_event_graph(pool: BinaryMapPool):
    """Produce a source-namespaced, complete *structural* event index.

    Every read goes through the production SHA-256-checking v1 resource
    provider. The script field is only a candidate address; no bytecode
    length, custom instruction set, script meaning or executable runtime
    compatibility is inferred.
    """
    if not isinstance(pool, BinaryMapPool) or not pool.source_id:
        raise GraphError('An open binary-map pool is required')
    if len(pool._maps) > MAX_MAPS:
        raise GraphError('Too many original maps')
    result = {
        'format': 'xgba-binary-event-graph',
        'version': 1,
        'source_identity': {'id': pool.source_id, 'sha256': pool.source_sha256},
        'original_map_ids_remapped': False,
        'scripts_executable': False,
        'cross_world_travel_implemented': False,
        'warps': [], 'connections': [], 'objects': [],
        'coordinate_events': [], 'background_events': [],
        'map_script_roots': []}
    totals = Counter()
    pointer_classes = Counter()
    classification = Counter()

    def fetch(group, number, kind):
        rid = pool.find_segment(group, number, kind)
        if rid is None:
            return b''
        size = pool.source_of(rid)[2]
        if size > MAX_GUEST_WINDOW:
            raise GraphError('Unexpected event record exceeds guest transfer cap')
        return pool.read_window(rid, 0, size)

    def root(entry, ptr, kind, index):
        classification[_script_address(ptr)] += 1
        if ptr:
            entry['script_pointer'] = ptr
            entry['script_pointer_status'] = _script_address(ptr)
        else:
            entry['script_pointer'] = None
            entry['script_pointer_status'] = 'null'
        if _script_address(ptr) == 'non_rom_opaque':
            totals['unresolved_script_pointer_candidates'] += 1

    for (group, number), header in pool._maps.items():
        location = _source_map(pool.source_id, group, number)
        header_ptr = header['script_root_offset']
        if header_ptr is not None:
            item = dict(location, original_rom_offset=header_ptr)
            result['map_script_roots'].append(item)
            totals['map_script_roots'] += 1
        warps = fetch(group, number, 'warps')
        if len(warps) != header['warps'] * 8:
            raise GraphError('Warp table size does not match original map header')
        for i in range(header['warps']):
            x, y, elevation, warp_id, target_number, target_group = (
                struct.unpack_from('<hhBBBB', warps, i * 8))
            destination_class = _warp_destination(pool, target_group, target_number)
            item = dict(location, index=i, x=x, y=y,
                        original_elevation=elevation, destination_warp_id=warp_id,
                        target_original_group=target_group,
                        target_original_map=target_number,
                        target_status=destination_class)
            result['warps'].append(item)
            totals['warps'] += 1
            totals['warp_' + destination_class] += 1

        connections = fetch(group, number, 'connection_entries')
        if len(connections) != header['connections'] * 12:
            raise GraphError('Map connection count does not match original map header')
        for i in range(header['connections']):
            direction, offset, target_group, target_number = (
                struct.unpack_from('<B3xiBBxx', connections, 12 * i))
            status = _warp_destination(pool, target_group, target_number)
            result['connections'].append(dict(
                location, index=i, original_direction=direction, offset=offset,
                target_original_group=target_group, target_original_map=target_number,
                target_status=status))
            totals['connections'] += 1
            totals['connection_' + status] += 1

        objects = fetch(group, number, 'objects')
        if len(objects) != header['object_events'] * 24:
            raise GraphError('Object event count differs from map metadata')
        for i in range(header['object_events']):
            off = 24 * i
            x, y = struct.unpack_from('<hh', objects, off+4)
            script = struct.unpack_from('<I', objects, off+16)[0]
            flag_id = struct.unpack_from('<H', objects, off+20)[0]
            item = dict(location, index=i, original_local_id=objects[off],
                        original_graphics_id=objects[off+1], x=x, y=y,
                        original_flag_id=flag_id)
            root(item, script, 'object', i)
            result['objects'].append(item)
            totals['objects'] += 1

        coords = fetch(group, number, 'coordinate_events')
        if len(coords) != header['coord_events'] * 16:
            raise GraphError('Coordinate event table differs from original header')
        for i in range(header['coord_events']):
            off = i*16
            x, y, elevation, trigger, event_index = struct.unpack_from(
                '<hhBxHH', coords, off)
            script = struct.unpack_from('<I', coords, off+12)[0]
            item = dict(location, index=i, x=x, y=y, original_elevation=elevation,
                        original_trigger=trigger, original_index=event_index)
            root(item, script, 'coordinate', i)
            result['coordinate_events'].append(item)
            totals['coordinate_events'] += 1

        background = fetch(group, number, 'background_events')
        if len(background) != header['bg_events'] * 12:
            raise GraphError('Background event table differs from original header')
        for i in range(header['bg_events']):
            off = i*12
            x, y, elevation, kind, payload = struct.unpack_from(
                '<HHBB2xI', background, off)
            item = dict(location, index=i, x=x, y=y,
                        original_elevation=elevation, original_kind=kind)
            if kind in (0,1,2,3,4):
                root(item, payload, 'background', i)
            elif kind == 7:
                item['original_hidden_item_id'] = payload >> 16
                item['original_item_id'] = payload & 0xffff
            elif kind == 8:
                item['original_secret_base_id'] = payload
            else:
                item['opaque_union_payload'] = payload
                totals['unknown_bg_event_kinds'] += 1
            result['background_events'].append(item)
            totals['background_events'] += 1

        if sum(totals[k] for k in ('warps','connections','objects',
                                  'coordinate_events','background_events')) > MAX_EVENT_RECORDS:
            raise GraphError('Binary event graph exceeds resource cap')

    # Enforce complete coverage against the structurally validated R34 map
    # index. This must not turn missing entries into a partial success.
    count_by_field = {
        'warps':'warps', 'connections':'connections',
        'objects':'object_events', 'coordinate_events':'coord_events',
        'background_events':'bg_events'}
    for category,field in count_by_field.items():
        expected = sum(m[field] for m in pool._maps.values())
        if totals[category] != expected:
            raise GraphError('Truncated binary event index for ' + category)
    summary = {
        'original_maps': len(pool._maps),
        'original_warps': totals['warps'],
        'warps_to_source_maps': totals['warp_original_source_map'],
        'dynamic_original_engine_warps': totals['warp_dynamic_original_engine'],
        'undefined_original_engine_warps': totals['warp_undefined_original_engine'],
        'unresolved_warp_references': totals['warp_unresolved_original_reference'],
        'original_map_connections': totals['connections'],
        'connections_to_source_maps': totals['connection_original_source_map'],
        'unresolved_connection_references': totals['connection_unresolved_original_reference'],
        'object_events': totals['objects'],
        'coordinate_events': totals['coordinate_events'],
        'background_events': totals['background_events'],
        'map_script_roots': totals['map_script_roots'],
        'script_address_candidates': classification['rom_candidate'],
        'null_script_addresses': classification['null'],
        'unresolved_script_pointer_candidates': totals['unresolved_script_pointer_candidates'],
        'unknown_background_event_kinds': totals['unknown_bg_event_kinds'],
        'decoded_script_instructions': 0,
        'runtime_compatible_abilities_moves_species': 0,
    }
    result['summary'] = summary
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('index', help='private R34 xgba-binary-maps.json')
    parser.add_argument('--out-summary', help='aggregate-only JSON diagnostics')
    parser.add_argument('--out-private-index', help='full event index, includes source event data; keep private')
    parser.add_argument('--verify-source-rom', help='optional exact original .gba SHA and segment audit, read only')
    args = parser.parse_args(argv)
    try:
        pool = BinaryMapPool(args.index)
        if args.verify_source_rom:
            pool.verify_original_rom(args.verify_source_rom)
        graph = extract_event_graph(pool)
        if args.out_summary:
            Path(args.out_summary).write_text(json.dumps(
                graph['summary'], sort_keys=True, indent=2) + '\n', encoding='utf8')
        if args.out_private_index:
            Path(args.out_private_index).write_text(
                json.dumps(graph, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf8')
        print(json.dumps(graph['summary'], sort_keys=True))
        return 0
    except (OSError, ValueError) as exc:
        print('XGBA_R36_EVENT_GRAPH_FAIL_CLOSED: '+str(exc),file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
