"""Build-time R31 catalogue, entirely independent of pinned native game proof."""
from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from xgba_r31_map_catalog import (
    CatalogError, MAGIC, original_map_catalog, render_c_catalog)


def source_pack(grid: bytes, border: bytes) -> bytes:
    segments=(grid,border,bytes(64),bytes(512),bytes(64),bytes(64))
    data=bytearray()
    offsets=[]
    for segment in segments:
        offsets.append(32+len(data))
        data.extend(segment)
        while len(data)%4:
            data.append(0)
    return struct.pack("<8I",MAGIC,32+len(data),*offsets)+data


class OriginalIdentityGeneration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/"data/maps").mkdir(parents=True)
        (self.root/"data/layouts").mkdir(parents=True)
        self.maps=["Foo","Bar","Baz"]
        groups={"group_order":["gMapGroup_Original","gMapGroup_Modified"],
                "gMapGroup_Original":["Foo","Bar"],
                "gMapGroup_Modified":["Baz"]}
        (self.root/"data/maps/map_groups.json").write_text(json.dumps(groups))
        layouts=[]
        for name in self.maps:
            (self.root/"data/maps"/name).mkdir()
            (self.root/"data/layouts"/name).mkdir()
            con={"Foo":["MAP_BAR"],"Bar":["MAP_FOO"],"Baz":[]}[name]
            (self.root/"data/maps"/name/"map.json").write_text(json.dumps({
                "name":name,"id":"MAP_"+name.upper(),
                "layout":"LAYOUT_"+name.upper(),
                "connections":[{"map":target,"direction":"up"} for target in con]}))
            grid=bytes([len(name),0])*400
            border=bytes([len(name),0])*4
            (self.root/"data/layouts"/name/"map.bin").write_bytes(grid)
            (self.root/"data/layouts"/name/"border.bin").write_bytes(border)
            layouts.append({
                "id":"LAYOUT_"+name.upper(),
                "width":20,"height":20,
                "blockdata_filepath":f"data/layouts/{name}/map.bin",
                "border_filepath":f"data/layouts/{name}/border.bin"})
        (self.root/"data/layouts/layouts.json").write_text(
            json.dumps({"layouts":layouts}))
        self.selected={}
        for name in self.maps:
            layout=self.root/"data/layouts"/name
            self.selected[name]=("emerald."+name.lower(),
                source_pack((layout/"map.bin").read_bytes(),
                            (layout/"border.bin").read_bytes()))

    def test_keeps_original_group_and_map_numbers(self):
        rows=original_map_catalog(self.root,self.selected)
        self.assertEqual([(r["group"],r["map"]) for r in rows],
                         [(0,0),(0,1),(1,0)])
        self.assertEqual([(r["width"],r["height"]) for r in rows],[(20,20)]*3)

    def test_shuffled_selection_is_not_map_renumbering(self):
        sel={"Bar":self.selected["Bar"],"Foo":self.selected["Foo"]}
        rows=original_map_catalog(self.root,sel)
        self.assertEqual([(r["group"],r["map"]) for r in rows],[(0,1),(0,0)])
        code=render_c_catalog(rows)
        self.assertIn("{0x00000000u, 1u}",code)
        self.assertIn("{0x00000001u, 0u}",code)

    def test_prefetch_only_from_original_connections(self):
        rows=original_map_catalog(self.root,self.selected)
        self.assertEqual([r["prefetch_index"] for r in rows],[1,0,None])
        self.assertIn("XGBA_CATALOG_NO_NEIGHBOR",render_c_catalog(rows))

    def test_original_map_identity_changes_derive_from_source_not_literals(self):
        groups=json.loads((self.root/"data/maps/map_groups.json").read_text())
        groups["gMapGroup_Original"]=["Bar","Foo"]
        (self.root/"data/maps/map_groups.json").write_text(json.dumps(groups))
        rows=original_map_catalog(self.root,self.selected)
        self.assertEqual([(r["group"],r["map"]) for r in rows],[(0,1),(0,0),(1,0)])

    def test_fails_closed_on_invalid_resource_ids_and_duplicate_ids(self):
        bad=dict(self.selected)
        bad["Foo"]=("../escape",bad["Foo"][1])
        with self.assertRaises(CatalogError):
            original_map_catalog(self.root,bad)
        bad["Foo"]=self.selected["Bar"]
        with self.assertRaises(CatalogError):
            original_map_catalog(self.root,bad)

    def test_fails_closed_on_modified_or_oversized_original_pack(self):
        bad=dict(self.selected)
        name,data=bad["Foo"]
        corrupt=bytearray(data)
        corrupt[32]=255
        bad["Foo"]=(name,bytes(corrupt))
        with self.assertRaises(CatalogError):
            original_map_catalog(self.root,bad)
        bad["Foo"]=(name,data+bytes(8192))
        with self.assertRaises(CatalogError):
            original_map_catalog(self.root,bad)

    def test_unselected_vanilla_maps_require_no_catalogue_entries(self):
        rows=original_map_catalog(self.root,{"Foo":self.selected["Foo"]})
        self.assertEqual(len(rows),1)
        self.assertNotIn("Baz",render_c_catalog(rows))
        with self.assertRaises(CatalogError):
            original_map_catalog(self.root,{"Missing":self.selected["Foo"]})


if __name__=="__main__":
    unittest.main()
