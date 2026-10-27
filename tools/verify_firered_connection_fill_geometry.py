#!/usr/bin/env python3
"""Fail-closed pinned editor-to-native connection geometry source witness."""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess

PINS = {
    "firered": "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
    "porymap": "26b919d7ff4b54152de010abd5bf344af2ebe116",
}
BLOBS = {
    "firered": {
        "src/fieldmap.c": "41567772299000ba5855419e5c39ad9373a34c20",
        "include/global.fieldmap.h": "e2828ec0cb1439718e830fbef4366770b3b77b1c",
        "tools/mapjson/mapjson.cpp": "8d8ec4e4e6e1c011b06f00819abe40bad10d19d5",
        "asm/macros/map.inc": "83ef472c926ce767c9133ab9bd6922280b38bb2d",
    },
    "porymap": {
        "include/core/mapconnection.h": "40713d3a26157fce7a36465858e8273c78dc12f6",
        "src/project.cpp": "d43b0949303433111d4478ad76117c2b3445dd13",
    },
}


def south(offset: int, connected_width: int = 20, current_width: int = 20) -> tuple[int, int, int]:
    """Synthetic transcription of the source's south X clipping branch."""
    virtual_width = current_width + 15
    x = offset + 7
    if x < 0:
        x2 = -x
        x += connected_width
        width = x if x < virtual_width else virtual_width
        x = 0
    else:
        x2 = 0
        width = connected_width if x + connected_width < virtual_width else virtual_width - x
    return x, x2, width


def west(offset: int, connected_height: int = 20, current_height: int = 20) -> tuple[int, int, int]:
    """Synthetic transcription of the source's west Y clipping branch."""
    virtual_height = current_height + 14
    y = offset + 7
    if y < 0:
        y2 = -y
        height = y + connected_height if y + connected_height < virtual_height else virtual_height
        y = 0
    else:
        y2 = 0
        height = connected_height if y + connected_height < virtual_height else virtual_height - y
    return y, y2, height


def require(text: str, anchor: str, label: str) -> None:
    if anchor not in text:
        raise AssertionError("Pinned source anchor changed: " + label)


def self_test() -> None:
    assert south(0) == (7, 0, 20)
    assert south(40) == (47, 0, -12)
    assert south(-40) == (0, 33, -13)
    assert west(0) == (7, 0, 20)
    assert west(40) == (47, 0, -13)
    try:
        require("not an anchor", "CpuCopy16(src, dest, width * 2);", "negative control")
    except AssertionError:
        pass
    else:
        raise AssertionError("Source-anchor mutation was not rejected")


def git(root: pathlib.Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def inspect(firered: pathlib.Path, porymap: pathlib.Path) -> dict:
    sources: dict[str, dict[str, str]] = {}
    for key, root in (("firered", firered), ("porymap", porymap)):
        assert git(root, "rev-parse", "HEAD") == PINS[key], key + " pin mismatch"
        sources[key] = {}
        for path, blob in BLOBS[key].items():
            assert git(root, "hash-object", path) == blob, key + "/" + path + " blob mismatch"
            sources[key][path] = (root / path).read_text()
    f = sources["firered"]
    p = sources["porymap"]
    for text, anchor, label in [
        (p["include/core/mapconnection.h"], "int m_offset;", "editor signed offset"),
        (p["src/project.cpp"], 'connectionObj["offset"] = connection->offset();', "editor JSON writer"),
        (f["tools/mapjson/mapjson.cpp"], '<< json_to_string(connection, "offset")', "native generator offset"),
        (f["asm/macros/map.inc"], r".4byte \offset", "assembler four-byte offset"),
        (f["include/global.fieldmap.h"], "/*0x04*/ u32 offset;", "native unsigned storage"),
        (f["src/fieldmap.c"], "u32 offset = connection->offset;", "fieldmap unsigned intermediate"),
        (f["src/fieldmap.c"], "static void FillSouthConnection(struct MapHeader const *mapHeader, struct MapHeader const *connectedMapHeader, s32 offset)", "signed consumer"),
        (f["src/fieldmap.c"], "width = VMap.Xsize - x;", "unclamped south width"),
        (f["src/fieldmap.c"], "height = VMap.Ysize - y;", "unclamped west/east height"),
        (f["src/fieldmap.c"], "CpuCopy16(src, dest, width * 2);", "native copy consumer"),
        (f["src/fieldmap.c"], "y2 = cHeight - MAP_OFFSET;", "short north source"),
        (f["src/fieldmap.c"], "x2 = cWidth - MAP_OFFSET;", "short west source"),
    ]:
        require(text, anchor, label)
    return {
        "pins": PINS, "blobs": BLOBS,
        "synthetic_south": {
            "normal": south(0), "disjoint_positive": south(40), "disjoint_negative": south(-40),
        },
        "synthetic_west": {
            "normal": west(0), "disjoint_positive": west(40),
        },
        "finding": "disjoint synthetic offsets reach negative width/height or source column outside connected map",
        "stock_authored_reachability": "not established",
        "compiled_or_runtime_test": False,
        "independent_approval": False,
        "phase1": "FAIL_INCOMPLETE",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--firered", type=pathlib.Path, default=pathlib.Path("upstream/pokefirered"))
    parser.add_argument("--porymap", type=pathlib.Path, default=pathlib.Path("upstream/porymap"))
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("audit-output/connection_fill_geometry.json"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    self_test()
    if args.self_test:
        print("Synthetic geometry and fail-closed mutation control passed")
        return
    report = inspect(args.firered, args.porymap)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
