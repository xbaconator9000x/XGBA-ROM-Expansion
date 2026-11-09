#!/usr/bin/env python3
"""Audit pinned FireRed maps.o connection records from archived ELF objects."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

FIRERED_PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
MAP_GROUPS_BLOB = "8c382f504d208286161903244772c93138cd7662"
MAP_GROUPS_SHA256 = "ce296c9b54c8bb85cc35870b30a533ab017e72107fd40cf471224a42127af79a"
EXPECTED_OBJECTS = {
    "modern": "1b52f4efdb9c7125e5860af211f8097882f2dadc6ee0d997a020945c1cd4ef98",
    "classic": "90a7e17a223dec05577d3faefc8af46c7fb1ed0ff3f3f3006e468d4154ee07dc",
}
EXPECTED_CONNECTION_INCLUDES_SHA256 = (
    "3c2ef81589d9bf09784350da0714a8a07d891c795c00024cdb1da5ea743e98cf"
)
ARM_ABS32 = 2
CONNECTION_RECORD_SIZE = 12


def fail(message: str) -> None:
    raise ValueError(message)


def blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def map_id_index(groups: dict) -> dict[tuple[int, int], str]:
    order = groups.get("group_order")
    if not isinstance(order, list) or not order or len(set(order)) != len(order):
        fail("invalid map group order")
    result = {}
    seen = set()
    for group_id, group in enumerate(order):
        maps = groups.get(group)
        if not isinstance(maps, list):
            fail(f"missing map group {group}")
        for map_num, name in enumerate(maps):
            if not isinstance(name, str) or name in seen or map_num > 0xFF:
                fail(f"invalid or duplicate map name in group {group}")
            seen.add(name)
            result[(group_id, map_num)] = name
    return result


def validate_record(record: bytes, map_ids: dict[tuple[int, int], str]) -> str:
    if len(record) != CONNECTION_RECORD_SIZE:
        fail("connection record is not 12 bytes")
    if record[0] not in (1, 2, 3, 4):
        fail("unexpected direction value")
    if record[1:4] != b"\0\0\0" or record[10:12] != b"\0\0":
        fail("connection record padding is nonzero")
    target = (record[8], record[9])
    if target not in map_ids:
        fail("connection map-group/map-number bytes do not resolve")
    return map_ids[target]


def validate_header_pointer(
    rodata: bytes,
    header_address: int,
    list_address: int,
    relocations: dict,
) -> None:
    if header_address < 0 or header_address + 8 > len(rodata):
        fail("MapConnections header is outside .rodata")
    count = struct.unpack_from("<i", rodata, header_address)[0]
    if count <= 0 or header_address - list_address != count * CONNECTION_RECORD_SIZE:
        fail("MapConnections count does not match the preceding record extent")
    relocation = relocations.get(header_address + 4)
    if (
        relocation is None
        or relocation["type"] != ARM_ABS32
        or not relocation["targets_rodata"]
        or struct.unpack_from("<I", rodata, header_address + 4)[0] != list_address
    ):
        fail("MapConnections list pointer relocation/addend mismatch")


def validate_pointer(
    rodata: bytes,
    offset: int,
    expected_target: int | None,
    relocations: dict,
) -> None:
    if offset < 0 or offset + 4 > len(rodata):
        fail("pointer field is outside .rodata")
    value = struct.unpack_from("<I", rodata, offset)[0]
    relocation = relocations.get(offset)
    if expected_target is None:
        if value != 0 or relocation is not None:
            fail("expected NULL pointer lacks a zero word or has a relocation")
        return
    if (
        relocation is None
        or relocation["type"] != ARM_ABS32
        or not relocation["targets_rodata"]
        or value != expected_target
    ):
        fail("pointer relocation/addend does not target expected .rodata object")


def validate_include_order(actual: list[str], expected: list[str]) -> None:
    if actual != expected:
        fail("compiled connection table order differs from authored active order")


def parse_elf32_arm(path: Path) -> dict:
    raw = path.read_bytes()
    if len(raw) < 52 or raw[:4] != b"\x7fELF" or raw[4:6] != b"\x01\x01":
        fail("object is not ELF32 little-endian")
    if struct.unpack_from("<H", raw, 18)[0] != 40:
        fail("object is not ARM")
    shoff = struct.unpack_from("<I", raw, 32)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", raw, 46)
    if shentsize != 40 or shnum == 0 or shstrndx >= shnum:
        fail("invalid ELF32 section table")
    sections = [
        struct.unpack_from("<IIIIIIIIII", raw, shoff + index * shentsize)
        for index in range(shnum)
    ]
    shstr = sections[shstrndx]
    section_names = raw[shstr[4]:shstr[4] + shstr[5]]

    def cstring(data: bytes, offset: int) -> str:
        if offset < 0 or offset >= len(data):
            fail("ELF string offset out of range")
        end = data.find(b"\0", offset)
        if end < 0:
            fail("unterminated ELF string")
        return data[offset:end].decode("utf-8")

    by_name = {cstring(section_names, section[0]): (index, section)
               for index, section in enumerate(sections)}
    for required in (".rodata", ".rel.rodata", ".symtab"):
        if required not in by_name:
            fail(f"missing ELF section {required}")
    rodata_index, rodata_section = by_name[".rodata"]
    rodata = raw[rodata_section[4]:rodata_section[4] + rodata_section[5]]

    symtab_index, symtab = by_name[".symtab"]
    if symtab[6] >= shnum or symtab[9] != 16:
        fail("invalid ELF32 symbol table")
    strtab_section = sections[symtab[6]]
    strtab = raw[strtab_section[4]:strtab_section[4] + strtab_section[5]]
    symbols = []
    symbol_count = symtab[5] // 16
    for index in range(symbol_count):
        entry = struct.unpack_from("<IIIBBH", raw, symtab[4] + index * 16)
        symbols.append({
            "name": cstring(strtab, entry[0]) if entry[0] else "",
            "value": entry[1],
            "info": entry[3],
            "section": entry[5],
        })

    rel_index, rel_section = by_name[".rel.rodata"]
    if rel_section[6] != symtab_index or rel_section[7] != rodata_index or rel_section[9] != 8:
        fail("invalid .rel.rodata linkage or entry size")
    relocations = {}
    for index in range(rel_section[5] // 8):
        offset, info = struct.unpack_from("<II", raw, rel_section[4] + index * 8)
        symbol_index, relocation_type = info >> 8, info & 0xFF
        if symbol_index >= len(symbols):
            fail("relocation symbol index out of range")
        symbol = symbols[symbol_index]
        relocations[offset] = {
            "type": relocation_type,
            "symbol": symbol["name"],
            "targets_rodata": symbol["section"] == rodata_index,
        }
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "rodata": rodata,
        "rodata_sha256": hashlib.sha256(rodata).hexdigest(),
        "rodata_index": rodata_index,
        "symbols": symbols,
        "relocations": relocations,
    }


def inspect_object(path: Path, groups: dict, expected_include_order: list[str]) -> dict:
    image = parse_elf32_arm(path)
    by_name = {
        symbol["name"]: symbol["value"]
        for symbol in image["symbols"]
        if symbol["section"] == image["rodata_index"] and symbol["name"]
    }
    map_ids = map_id_index(groups)
    tables = []
    for name, list_address in by_name.items():
        if not name.endswith("_MapConnectionsList"):
            continue
        header_name = name[:-4]
        if header_name not in by_name:
            fail(f"connection list has no count/pointer header: {name}")
        header_address = by_name[header_name]
        validate_header_pointer(
            image["rodata"], header_address, list_address, image["relocations"]
        )
        count = struct.unpack_from("<i", image["rodata"], header_address)[0]
        records = []
        targets = []
        for index in range(count):
            start = list_address + index * CONNECTION_RECORD_SIZE
            record = image["rodata"][start:start + CONNECTION_RECORD_SIZE]
            targets.append(validate_record(record, map_ids))
            records.append(record)
        tables.append({
            "map": header_name.removesuffix("_MapConnections"),
            "address": list_address,
            "count": count,
            "records": records,
            "targets": targets,
        })
    tables.sort(key=lambda table: table["address"])

    include_names = re.findall(
        r'(?m)^\s*\.include\s+"[^"]*/([^/"]+)/connections\.inc"\s*$',
        expected_include_order,
    ) if isinstance(expected_include_order, str) else None
    if include_names is None:
        fail("connection include text is not a string")
    explicit_order = groups.get("connections_include_order")
    if not isinstance(explicit_order, list) or len(explicit_order) != 63:
        fail("pinned explicit connection order drift")
    if len(include_names) != 425 or len(set(include_names)) != 425:
        fail("generated global connection include list is incomplete or duplicated")
    table_names = [table["map"] for table in tables]
    if set(table_names) != set(explicit_order) or len(table_names) != 63:
        fail("compiled connection-table map set differs from authored explicit order")
    saffron_table = next((table for table in tables if table["map"] == "SaffronCity"), None)
    if saffron_table is None or saffron_table["count"] != 4:
        fail("pinned SaffronCity suppressed-table control drift")
    actual_table_order = [
        name for name in include_names if name in set(table_names)
    ]
    validate_include_order(actual_table_order, explicit_order)
    if table_names != actual_table_order:
        fail("ELF connection table addresses do not follow generated include order")

    map_group_symbols = {
        symbol["name"]: symbol["value"]
        for symbol in image["symbols"]
        if symbol["section"] == image["rodata_index"] and symbol["name"]
    }
    map_to_table = {
        table["map"]: by_name[f'{table["map"]}_MapConnections']
        for table in tables
        if table["map"] != "SaffronCity"
    }
    null_headers = 0
    referenced_headers = 0
    for group_index, group_name in enumerate(groups["group_order"]):
        group_symbol = map_group_symbols.get(group_name)
        if group_symbol is None:
            fail(f"compiled map-group pointer array is absent: {group_name}")
        for map_number, map_name in enumerate(groups[group_name]):
            map_header_pointer = group_symbol + map_number * 4
            group_relocation = image["relocations"].get(map_header_pointer)
            if (
                group_relocation is None
                or group_relocation["type"] != ARM_ABS32
                or not group_relocation["targets_rodata"]
            ):
                fail(f"map-group entry is not a native header pointer: {map_name}")
            map_header_address = struct.unpack_from(
                "<I", image["rodata"], map_header_pointer
            )[0]
            expected_connection_header = map_to_table.get(map_name)
            validate_pointer(
                image["rodata"],
                map_header_address + 0x0C,
                expected_connection_header,
                image["relocations"],
            )
            if expected_connection_header is None:
                null_headers += 1
            else:
                referenced_headers += 1

    direction_counts = {}
    for table in tables:
        for record in table["records"]:
            direction_counts[str(record[0])] = direction_counts.get(str(record[0]), 0) + 1

    inbound_targets = {}
    for offset, relocation in image["relocations"].items():
        if (
            relocation["type"] == ARM_ABS32
            and relocation["targets_rodata"]
            and offset + 4 <= len(image["rodata"])
        ):
            target = struct.unpack_from("<I", image["rodata"], offset)[0]
            inbound_targets[target] = inbound_targets.get(target, 0) + 1
    saffron_header = by_name.get("SaffronCity_MapConnections")
    pallet_header = by_name.get("PalletTown_MapConnections")
    if saffron_header is None or pallet_header is None:
        fail("expected pinned positive/null-pointer map controls are absent")
    if inbound_targets.get(saffron_header, 0) != 0:
        fail("suppressed SaffronCity connection header unexpectedly has a reference")
    if inbound_targets.get(pallet_header, 0) == 0:
        fail("PalletTown positive connection-header reference is absent")

    result = {
        "object_sha256": image["sha256"],
        "rodata_sha256": image["rodata_sha256"],
        "connection_tables": len(tables),
        "connection_records": sum(table["count"] for table in tables),
        "map_headers_checked": len(map_ids),
        "map_headers_with_connections": referenced_headers,
        "map_headers_with_null_connections": null_headers,
        "saffron_city_suppressed_table_records": saffron_table["count"],
        "record_size_bytes": CONNECTION_RECORD_SIZE,
        "connection_count_distribution": {
            str(count): sum(table["count"] == count for table in tables)
            for count in sorted({table["count"] for table in tables})
        },
        "direction_counts": direction_counts,
        "ordered_map_names": table_names,
        "decoded_targets": [target for table in tables for target in table["targets"]],
        "pallet_town_header_references": inbound_targets.get(pallet_header, 0),
        "saffron_city_suppressed_header_references": inbound_targets.get(saffron_header, 0),
        "_tables": tables,
    }
    return result


def run_negative_controls(groups: dict, expected_order: list[str]) -> int:
    map_ids = map_id_index(groups)
    valid = bytes.fromhex("020000000000000003130000")
    validate_record(valid, map_ids)
    controls = [
        lambda: validate_record(valid[:-1], map_ids),
        lambda: validate_record(b"\xff" + valid[1:], map_ids),
        lambda: validate_record(valid[:1] + b"\x01" + valid[2:], map_ids),
        lambda: validate_record(valid[:8] + b"\xff" + valid[9:], map_ids),
        lambda: validate_include_order(expected_order[::-1], expected_order),
    ]
    accepted = 0
    for control in controls:
        try:
            control()
        except ValueError:
            accepted += 1
    if accepted != len(controls):
        fail("a malformed table/order mutation was not rejected")
    bad_pointer_data = bytearray(b"\0" * 20)
    struct.pack_into("<i", bad_pointer_data, 12, 1)
    good_relocation = {16: {"type": ARM_ABS32, "targets_rodata": True}}
    bad_relocation = {16: {"type": 3, "targets_rodata": True}}
    for data, relocations in (
        (bytes(bad_pointer_data), {}),
        (bytes(bad_pointer_data), bad_relocation),
    ):
        try:
            validate_header_pointer(data, 12, 0, relocations)
        except ValueError:
            accepted += 1
    null_pointer_data = bytes(8)
    try:
        validate_pointer(null_pointer_data, 0, 4, {})
    except ValueError:
        accepted += 1
    try:
        validate_pointer(b"\x04\0\0\0", 0, None, {})
    except ValueError:
        accepted += 1
    if accepted != 9:
        fail("connection-header pointer/count mutations were not rejected")
    return accepted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=EXPECTED_OBJECTS, required=True)
    parser.add_argument("--object", type=Path, required=True)
    parser.add_argument("--connections-include", type=Path, required=True)
    parser.add_argument("--map-groups", type=Path, required=True)
    parser.add_argument("--compare-object", type=Path)
    args = parser.parse_args()

    groups_bytes = args.map_groups.read_bytes()
    if (
        blob_sha1(groups_bytes) != MAP_GROUPS_BLOB
        or hashlib.sha256(groups_bytes).hexdigest() != MAP_GROUPS_SHA256
    ):
        fail("pinned map_groups.json identity mismatch")
    groups = json.loads(groups_bytes)
    if len(groups["group_order"]) != 43 or sum(
        len(groups[group]) for group in groups["group_order"]
    ) != 425:
        fail("pinned map group or map count drift")
    connections_bytes = args.connections_include.read_bytes()
    if hashlib.sha256(connections_bytes).hexdigest() != EXPECTED_CONNECTION_INCLUDES_SHA256:
        fail("archived authored connections.inc identity mismatch")
    include_text = connections_bytes.decode("utf-8")
    summary = inspect_object(args.object, groups, include_text)
    if summary["object_sha256"] != EXPECTED_OBJECTS[args.variant]:
        fail(f"{args.variant} object SHA-256 mismatch")
    expected_order = groups["connections_include_order"]
    controls = run_negative_controls(groups, expected_order)
    output = {
        "schema": "phase1-firered-connection-object-audit-v1",
        "source_pin": FIRERED_PIN,
        "map_groups_blob_sha1": MAP_GROUPS_BLOB,
        "map_groups_sha256": MAP_GROUPS_SHA256,
        "variant": args.variant,
        "object_sha256": summary["object_sha256"],
        "rodata_sha256": summary["rodata_sha256"],
        "connection_tables": summary["connection_tables"],
        "connection_records": summary["connection_records"],
        "map_headers_checked": summary["map_headers_checked"],
        "map_headers_with_connections": summary["map_headers_with_connections"],
        "map_headers_with_null_connections": summary[
            "map_headers_with_null_connections"
        ],
        "saffron_city_suppressed_table_records": summary[
            "saffron_city_suppressed_table_records"
        ],
        "record_size_bytes": summary["record_size_bytes"],
        "connection_count_distribution": summary["connection_count_distribution"],
        "direction_counts": summary["direction_counts"],
        "authored_table_order_matches_elf_addresses": True,
        "all_target_map_ids_decode": len(summary["decoded_targets"]) == summary["connection_records"],
        "pallet_town_header_references": summary["pallet_town_header_references"],
        "saffron_city_suppressed_header_references": summary[
            "saffron_city_suppressed_header_references"
        ],
        "negative_controls_rejected": controls,
        "runtime_reader_executed": False,
        "independent_approvals": 0,
        "phase1_complete": False,
    }
    if args.compare_object:
        other = parse_elf32_arm(args.compare_object)
        other_variant = "classic" if args.variant == "modern" else "modern"
        if other["sha256"] != EXPECTED_OBJECTS[other_variant]:
            fail(f"{other_variant} comparison object SHA-256 mismatch")
        other_summary = inspect_object(
            args.compare_object, groups, include_text
        )
        first_tables = summary.pop("_tables")
        second_tables = other_summary.pop("_tables")
        if [
            (table["map"], table["count"], table["records"])
            for table in first_tables
        ] != [
            (table["map"], table["count"], table["records"])
            for table in second_tables
        ]:
            fail("modern/classic connection table bytes differ")
        output["cross_variant_table_bytes_equal"] = True
        output["comparison_object_sha256"] = other["sha256"]
        output["comparison_rodata_sha256"] = other_summary["rodata_sha256"]
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
