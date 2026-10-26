#!/usr/bin/env python3
"""Pinned FireRed authored map-header → layout-table join (Phase 1 evidence only).

This is not a compiled-link, save-state reachability, runtime, or independent
semantic-review certification. The source tree MUST be at the pinned commit.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
PINNED_BLOBS = {
    "data/maps/map_groups.json": "8c382f504d208286161903244772c93138cd7662",
    "data/layouts/layouts.json": "41d0eb1b5e51fa75d535b5a098bae2bd650f710d",
    "tools/mapjson/mapjson.cpp": "8d8ec4e4e6e1c011b06f00819abe40bad10d19d5",
    "src/overworld.c": "339014da46ae8543143edc99ab72bf7496203a0d",
    "src/fieldmap.c": "41567772299000ba5855419e5c39ad9373a34c20",
}
REQUIRED_GENERATOR_EXPRESSIONS = (
    'string map_layout_id = json_to_string(map_data, "layout");',
    'if (map_layout_id == json_to_string(layout, "id", true))',
    'if (matched.size() != 1)',
    '<< "\\t.4byte " << json_to_string(layout, "name")',
    '<< "\\t.2byte " << json_to_string(layout, "id")',
)
REQUIRED_RUNTIME_EXPRESSIONS = (
    "u16 mapLayoutId = gSaveBlock1Ptr->mapLayoutId;",
    "return gMapLayouts[mapLayoutId - 1];",
)


def git(source: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(source), *args], text=True, stderr=subprocess.PIPE
    ).strip()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    source = args.source.resolve()
    require(git(source, "rev-parse", "HEAD") == PIN, "upstream commit drift")

    # Git tree pins each of the 425 map JSON blobs, not just the map-group list.
    tree = git(source, "ls-tree", "-r", "HEAD").splitlines()
    blobs = {}
    for line in tree:
        metadata, path = line.split("\t", 1)
        mode, kind, sha = metadata.split()
        if kind == "blob":
            blobs[path] = sha
    for path, sha in PINNED_BLOBS.items():
        require(blobs.get(path) == sha, "pinned Git blob drift: " + path)

    def load(path: str):
        return json.loads((source / path).read_text(encoding="utf-8"))

    generator = (source / "tools/mapjson/mapjson.cpp").read_text(encoding="utf-8")
    runtime = (source / "src/overworld.c").read_text(encoding="utf-8")
    for expression in REQUIRED_GENERATOR_EXPRESSIONS:
        require(expression in generator, "map-header producer expression drift: " + expression)
    for expression in REQUIRED_RUNTIME_EXPRESSIONS:
        require(expression in runtime, "runtime layout lookup drift: " + expression)

    groups = load("data/maps/map_groups.json")
    layouts = load("data/layouts/layouts.json")["layouts"]
    require(len(layouts) == 383, "layout-table positional census drift")
    slots = {}
    empty = []
    for index, entry in enumerate(layouts, 1):
        if not entry:
            empty.append(index)
            continue
        ident = entry["id"]
        require(ident not in slots, "duplicate authored layout ID: " + ident)
        require(isinstance(entry["border_width"], int) and isinstance(entry["border_height"], int),
                "non-integer border dimensions: " + ident)
        slots[ident] = {
            "table_slot_1_based": index,
            "border_width": entry["border_width"],
            "border_height": entry["border_height"],
        }
    require(len(empty) == 18 and len(slots) == 365, "authored layout census drift")
    zero_ids = {ident for ident, row in slots.items()
                if row["border_width"] == 0 or row["border_height"] == 0}
    require(len(zero_ids) == 28, "authored zero-border layout census drift")

    group_order = groups["group_order"]
    require(len(group_order) == len(set(group_order)) == 43, "map-group order drift")
    require(set(groups) == set(group_order) | {"group_order"}, "map-group keys drift")
    maps = []
    seen_names = set()
    seen_ids = set()
    for group_index, group in enumerate(group_order):
        for map_index, name in enumerate(groups[group]):
            require(name not in seen_names, "duplicate map name: " + name)
            seen_names.add(name)
            path = "data/maps/" + name + "/map.json"
            require(path in blobs, "missing map JSON in pinned Git tree: " + path)
            record = load(path)
            require(record["name"] == name, "map name/path mismatch: " + name)
            require(record["id"] not in seen_ids, "duplicate map constant: " + record["id"])
            seen_ids.add(record["id"])
            layout = record["layout"]
            require(layout in slots, "unresolved map-header layout: " + name + " -> " + layout)
            maps.append({
                "map_name": name,
                "map_constant": record["id"],
                "group": group,
                "group_index": group_index,
                "map_index": map_index,
                "map_json_blob": blobs[path],
                "layout_id": layout,
                "layout_table_slot_1_based": slots[layout]["table_slot_1_based"],
                "border_width": slots[layout]["border_width"],
                "border_height": slots[layout]["border_height"],
            })
    require(len(maps) == 425, "map-header census drift")
    referenced = {row["layout_id"] for row in maps}
    zero_references = [row for row in maps if row["layout_id"] in zero_ids]
    counts = Counter((row["border_width"], row["border_height"]) for row in maps)
    result = {
        "evidence_class": "PINNED_SOURCE_AUTHORING_JOIN_ONLY",
        "phase1_verdict": "FAIL_INCOMPLETE",
        "independent_whole_file_approvals": 0,
        "upstream": "pret/pokefirered",
        "upstream_commit": PIN,
        "pinned_blobs": PINNED_BLOBS,
        "map_group_count": len(group_order),
        "map_count": len(maps),
        "layout_table_slots": len(layouts),
        "empty_layout_slots": empty,
        "named_layout_count": len(slots),
        "zero_border_authored_layout_ids": sorted(zero_ids),
        "zero_border_map_header_references": zero_references,
        "map_header_border_dimension_counts": [
            {"width": w, "height": h, "count": count}
            for (w, h), count in sorted(counts.items())
        ],
        "referenced_layout_count": len(referenced),
        "unreferenced_authored_layout_ids": sorted(set(slots) - referenced),
        "maps": maps,
        "limits": [
            "Map headers are authored JSON, not compiled/linker inclusion.",
            "Saved mapLayoutId can be modified independently of map-header layout IDs.",
            "No runtime border fallback or script reachability was exercised.",
            "No whole-file independent semantic review was performed.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("PINNED_AUTHORING_JOIN_PASS maps=%d layouts=%d zero_border_map_refs=%d" %
          (len(maps), len(slots), len(zero_references)))
    print("PHASE1_GATE=FAIL_INCOMPLETE; independent approvals=0")


if __name__ == "__main__":
    main()
