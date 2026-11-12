#!/usr/bin/env python3
"""R31: automatically resolve original Emerald map identities, never renumber them.

The input is the game's existing map_groups.json, map.json and layouts.json
plus the *chosen* external packs. This is a build-time adapter, not a demand
to recatalogue the maps in a ROM hack. Unsupported binary layouts are not
silently guessed: compatibility with arbitrary binary ROM hacks is future work.
"""
from __future__ import annotations

import json
import re
import struct
from pathlib import Path
from typing import Mapping

MAGIC=0x52313450
RESOURCE_ID=re.compile(r"[A-Za-z0-9._-]{1,31}\Z",re.ASCII)
MAX_PACK=8192


class CatalogError(ValueError):
    pass


def original_map_catalog(emerald: Path,
                         selected: Mapping[str, tuple[str, bytes]]) -> list[dict]:
    """Return one resource entry per selected existing original map (ordered).

    The input selection specifies ONLY maps chosen for external storage.
    Unselected maps do not acquire new IDs and keep the stock lookup path.
    """
    emerald=Path(emerald)
    groups=json.loads((emerald/"data/maps/map_groups.json").read_text())
    layouts=json.loads((emerald/"data/layouts/layouts.json").read_text())
    by_layout={layout["id"]:layout for layout in layouts["layouts"]}
    by_map={}
    for group_num,group_name in enumerate(groups["group_order"]):
        for map_num,name in enumerate(groups[group_name]):
            if name in by_map:
                raise CatalogError(f"Ambiguous original map name: {name}")
            if group_num>65535 or map_num>65535:
                raise CatalogError("Original map identity exceeds 16-bit fields")
            by_map[name]=(group_num,map_num)
    if not selected or len(selected)>=65535:
        raise CatalogError("Empty or oversized external resource selection")
    result=[]
    map_ids=set()
    used_resources=set()
    for name,(resource_id,pack) in selected.items():
        if name not in by_map or name in (".","..") or "/" in name or "\\" in name:
            raise CatalogError(f"Unknown or unsafe original map: {name}")
        if not isinstance(resource_id,str) or not RESOURCE_ID.fullmatch(resource_id):
            raise CatalogError(f"Unsafe or too-long provider resource id: {resource_id!r}")
        if resource_id in used_resources:
            raise CatalogError("Duplicate external provider resource id")
        used_resources.add(resource_id)
        if not isinstance(pack,bytes) or not 40<=len(pack)<=MAX_PACK:
            raise CatalogError("Packed source must fit exactly one physical 8 KiB slot")
        group,map_num=by_map[name]
        map_meta=json.loads((emerald/"data/maps"/name/"map.json").read_text())
        if map_meta["name"]!=name or map_meta["layout"] not in by_layout:
            raise CatalogError(f"Original map metadata/layout drift for {name}")
        layout=by_layout[map_meta["layout"]]
        width,height=layout["width"],layout["height"]
        if not isinstance(width,int) or not isinstance(height,int) or not 0<width<=65535 or not 0<height<=65535:
            raise CatalogError("Original map dimensions invalid")
        if (width+15)*(height+14)>0x2800:
            raise CatalogError("Original backup grid exceeds Emerald's existing EWRAM limit")
        grid=(emerald/layout["blockdata_filepath"]).read_bytes()
        border=(emerald/layout["border_filepath"]).read_bytes()
        if len(grid)!=2*width*height or len(border)!=8:
            raise CatalogError(f"Original map grid/border size mismatch: {name}")
        offsets=struct.unpack_from("<8I",pack)
        if (offsets[0]!=MAGIC or offsets[1]!=len(pack) or
            offsets[2]<32 or offsets[2]+len(grid)>offsets[3] or
            offsets[3]+8>offsets[4] or offsets[4]>=offsets[5] or
            offsets[5]+512>offsets[6] or offsets[6]>=offsets[7] or
            offsets[7]>=len(pack) or
            any(x&3 for x in offsets[2:]) or
            pack[offsets[2]:offsets[2]+len(grid)]!=grid or
            pack[offsets[3]:offsets[3]+8]!=border):
            raise CatalogError(f"Source pack cannot be validated against original map: {name}")
        if (group,map_num) in map_ids:
            raise CatalogError("Duplicate original group/map identity")
        map_ids.add((group,map_num))
        result.append(dict(name=name,group=group,map=map_num,
                           width=width,height=height,bytes=len(pack),
                           resource_id=resource_id,
                           source_map_constant=map_meta["id"],
                           source_connections=map_meta.get("connections",[])))
    id_to_index={item["source_map_constant"]:i for i,item in enumerate(result)}
    for i,item in enumerate(result):
        neighbors=[id_to_index[link["map"]]
                   for link in item["source_connections"]
                   if link["map"] in id_to_index and id_to_index[link["map"]]!=i]
        item["prefetch_index"]=min(neighbors) if neighbors else None
        del item["source_connections"]
    return result


def render_c_catalog(entries: list[dict]) -> str:
    """C table is ROM-resident; sorted secondary index gives O(log N) lookup."""
    if not entries or len(entries)>=65535:
        raise CatalogError("No valid catalogue entries")
    ordered=sorted(((entry["group"]<<16)|entry["map"],i)
                   for i,entry in enumerate(entries))
    if any(a[0]==b[0] for a,b in zip(ordered,ordered[1:])):
        raise CatalogError("Duplicate original map identity")
    lines=[
        "/* GENERATED from original Emerald map data, never edit map IDs. */",
        f"#define XGBA_R31_CATALOG_COUNT {len(entries)}u",
        "static const struct XgbaOriginalMapResource sXgbaR31Catalog[XGBA_R31_CATALOG_COUNT] = {",
    ]
    for item in entries:
        ident=json.dumps(item["resource_id"])
        neighbor=(f'{item["prefetch_index"]}u'
                  if item["prefetch_index"] is not None
                  else "XGBA_CATALOG_NO_NEIGHBOR")
        lines.append(
            f'    {{{item["group"]}u, {item["map"]}u, '
            f'{item["width"]}u, {item["height"]}u, {item["bytes"]}u, '
            f'{ident}, {neighbor}}}, /* {item["name"]} */')
    lines += [
        "};",
        "static const struct XgbaOriginalMapLocator sXgbaR31Lookup[XGBA_R31_CATALOG_COUNT] = {",
    ]
    for key,index in ordered:
        lines.append(f"    {{0x{key:08x}u, {index}u}},")
    lines += ["};",""]
    return "\n".join(lines)
