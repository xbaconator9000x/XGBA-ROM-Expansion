#!/usr/bin/env python3
"""Pinned FireRed 425-map cardinal connection fill-geometry census.

Static geometry analysis of authored JSON and the source-clipping algorithm.
Does not execute the GBA native copy routine or certify runtime safety.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
GROUP_BLOB = "8c382f504d208286161903244772c93138cd7662"
LAYOUT_BLOB = "41d0eb1b5e51fa75d535b5a098bae2bd650f710d"
DIRECTIONS = {"up", "down", "left", "right"}
VIRTUAL_LIMIT = 0x2800


def geometry(direction: str, offset: int, width: int, height: int, cwidth: int, cheight: int) -> dict:
    """Direct arithmetic transcription of pinned fieldmap.c:192-345."""
    vw, vh = width + 15, height + 14
    if direction in ("up", "down"):
        x = offset + 7
        if x < 0:
            x2 = -x
            x += cwidth
            count = x if x < vw else vw
            x = 0
        else:
            x2 = 0
            count = cwidth if x + cwidth < vw else vw - x
        y, y2 = (0, cheight - 7) if direction == "up" else (height + 7, 0)
        rect = {"x": x, "y": y, "src_x": x2, "src_y": y2, "width": count, "height": 7}
    else:
        y = offset + 7
        if y < 0:
            y2 = -y
            count = y + cheight if y + cheight < vh else vh
            y = 0
        else:
            y2 = 0
            count = cheight if y + cheight < vh else vh - y
        x, x2, nwidth = (0, cwidth - 7, 7) if direction == "left" else (width + 7, 0, 8)
        rect = {"x": x, "y": y, "src_x": x2, "src_y": y2, "width": nwidth, "height": count}
    problems = []
    if rect["width"] <= 0 or rect["height"] <= 0:
        problems.append("empty_or_negative_copy_extent")
    if rect["x"] < 0 or rect["y"] < 0 or rect["x"] > vw or rect["y"] > vh or rect["x"] + rect["width"] > vw or rect["y"] + rect["height"] > vh:
        problems.append("destination_rectangle_outside_virtual_map")
    if rect["src_x"] < 0 or rect["src_y"] < 0 or rect["src_x"] > cwidth or rect["src_y"] > cheight or rect["src_x"] + rect["width"] > cwidth or rect["src_y"] + rect["height"] > cheight:
        problems.append("source_rectangle_outside_connected_layout")
    if vw * vh > VIRTUAL_LIMIT:
        problems.append("virtual_map_exceeds_static_buffer")
    return {"rect": rect, "virtual": [vw, vh], "source": [cwidth, cheight], "issues": problems}


def self_test() -> None:
    assert not geometry("down", 0, 20, 20, 20, 20)["issues"]
    assert "empty_or_negative_copy_extent" in geometry("down", 40, 20, 20, 20, 20)["issues"]
    assert "source_rectangle_outside_connected_layout" in geometry("down", -40, 20, 20, 20, 20)["issues"]
    assert "empty_or_negative_copy_extent" in geometry("left", 40, 20, 20, 20, 20)["issues"]
    assert "source_rectangle_outside_connected_layout" in geometry("up", 0, 20, 20, 20, 5)["issues"]
    assert "source_rectangle_outside_connected_layout" in geometry("left", 0, 20, 20, 5, 20)["issues"]


def git(root: pathlib.Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def inspect(root: pathlib.Path) -> dict:
    assert git(root, "rev-parse", "HEAD") == PIN, "Not pinned FireRed"
    assert git(root, "hash-object", "data/maps/map_groups.json") == GROUP_BLOB
    assert git(root, "hash-object", "data/layouts/layouts.json") == LAYOUT_BLOB
    data = root / "data"
    groups = json.loads((data / "maps/map_groups.json").read_text())
    layouts = json.loads((data / "layouts/layouts.json").read_text())["layouts"]
    layout_by_id = {layout["id"]: layout for layout in layouts if "id" in layout}
    assert len(layouts) == 383 and len(layout_by_id) == 365, "Layout slot census changed"
    map_names = [name for group in groups["group_order"] for name in groups[group]]
    assert len(map_names) == len(set(map_names)) == 425, "Map identity census changed"
    maps = {}
    for name in map_names:
        path = data / "maps" / name / "map.json"
        obj = json.loads(path.read_text())
        assert obj["name"] == name, "Map name/path mismatch: " + name
        assert obj["id"] not in maps, "Duplicate map constant: " + obj["id"]
        assert obj["layout"] in layout_by_id, "Unknown layout: " + obj["layout"]
        maps[obj["id"]] = obj
    assert sum(bool(m.get("connections")) for m in maps.values()) == 63, "Authored nonempty connection census changed"
    records = []
    suppressed = []
    active_cardinal = 0
    for obj in maps.values():
        conns = obj.get("connections") or []
        if not conns:
            continue
        if obj.get("connections_no_include", False):
            suppressed.append({"map": obj["name"], "count": len(conns)})
            continue
        src = layout_by_id[obj["layout"]]
        for conn in conns:
            assert conn["map"] in maps, "Unknown connected map " + conn["map"]
            target = maps[conn["map"]]
            dest = layout_by_id[target["layout"]]
            direction = conn["direction"]
            if direction not in DIRECTIONS:
                records.append({"map": obj["name"], "direction": direction, "kind": "non_cardinal_skipped"})
                continue
            assert type(conn["offset"]) is int, "Noninteger authored offset"
            result = geometry(direction, conn["offset"], src["width"], src["height"], dest["width"], dest["height"])
            records.append({
                "map": obj["name"], "target": target["name"], "direction": direction,
                "offset": conn["offset"], "source_layout": src["id"], "target_layout": dest["id"],
                **result,
            })
            active_cardinal += 1
    problems = [r for r in records if r.get("issues")]
    return {
        "pin": PIN, "group_blob": GROUP_BLOB, "layout_blob": LAYOUT_BLOB,
        "map_count": len(maps), "layout_slots": len(layouts), "populated_layouts": len(layout_by_id),
        "maps_with_authored_connections": 63, "suppressed_maps": suppressed,
        "active_cardinal_connections": active_cardinal, "records": records,
        "geometry_issue_count": len(problems), "geometry_issues": problems,
        "scope": "authored cardinal rectangle bounds only; no compiled native copy or runtime proof",
        "independent_approval": False, "phase1": "FAIL_INCOMPLETE",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path("upstream/pokefirered"))
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("audit-output/authored_connection_fill_geometry.json"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    self_test()
    if args.self_test:
        print("Synthetic cardinal geometry controls passed")
        return
    report = inspect(args.root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "maps": report["map_count"],
        "suppressed": report["suppressed_maps"],
        "cardinal_connections": report["active_cardinal_connections"],
        "geometry_issues": report["geometry_issue_count"],
    }, indent=2))
    if report["geometry_issue_count"]:
        raise SystemExit("Authored geometry has unresolved invalid rectangles: see JSON artifact")


if __name__ == "__main__":
    main()
