#!/usr/bin/env python3
"""R46 tests: source-aware binary router, original alias safety and bounded shards."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import xgba_r46_source_warp_index as mod


class _FakeDiscovery:
    def __init__(self,data):
        self.idx=data[0]
    def discover(self,**kwargs):
        assert kwargs=={"min_root_references":1,"allow_null_slots":True}
        common={"event_array_offsets":[None,64,None,None],
                "header_offset":32,"group":0}
        if self.idx==0:
            maps=[dict(common,map=9,width=20,height=20,warp_count=1)]
            holes=0
        elif self.idx==1:
            maps=[dict(common,map=9,width=24,height=25,warp_count=1),
                  dict(common,map=10,width=22,height=20,warp_count=1,
                       event_array_offsets=[None,72,None,None])]
            holes=0
        else:
            maps=[dict(common,map=0,width=30,height=39,warp_count=1)]
            holes=935
        return {"maps":maps,"table_offset":128,
                "slot_count":len(maps)+holes,"null_slot_count":holes}


class SourceWarpRouterTests(unittest.TestCase):
    def test_source_aware_keys_prevent_original_collision(self):
        self.assertEqual(mod.map_key("emerald",0,9),9)
        self.assertEqual(mod.map_key("rocket",0,9),0x10009)
        self.assertEqual(mod.map_key("heart_soul",0,0),0x20000)
        with self.assertRaises(mod.WarpIndexError):
            mod.map_key("unknown",0,9)
        with self.assertRaises(mod.WarpIndexError):
            mod.map_key("rocket",256,9)
    def test_three_genuine_source_id_slots_and_warp_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            paths=[]
            for i,source in enumerate(("emerald","rocket","heart_soul")):
                data=bytearray(1024)
                data[0]=i
                if i==0:
                    struct.pack_into(mod.WARP_FORMAT,data,64,4,5,0,0,10,0)
                elif i==1:
                    struct.pack_into(mod.WARP_FORMAT,data,64,6,9,0,0,10,0)
                    struct.pack_into(mod.WARP_FORMAT,data,72,8,12,0,0,9,0)
                else:
                    struct.pack_into(mod.WARP_FORMAT,data,64,11,7,1,0,0,0)
                path=Path(folder)/f"{source}.gba"
                path.write_bytes(data)
                paths.append((source,path))
            before={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in paths}
            with patch.object(mod.r34,"BinaryMapDiscovery",_FakeDiscovery):
                bm,bw,proof=mod.build_indexes(paths)
            self.assertEqual(proof["map_records"],4)
            self.assertEqual(proof["warp_records"],4)
            self.assertEqual(proof["sources"]["heart_soul"]["original_zero_pointer_slots"],935)
            self.assertEqual(proof["original_warp_destination_classification"]["source_local_warp_resolves"],3)
            self.assertEqual(proof["original_warp_destination_classification"]["missing_or_null_original_destination"],1)
            self.assertEqual(proof["explicit_cross_world_portal_definitions"],0)
            self.assertEqual(len(bm),4*16)
            self.assertEqual(len(bw),4*8)
            rows=[struct.unpack_from(mod.MAP_FORMAT,bm,i*16) for i in range(4)]
            self.assertEqual([row[0] for row in rows],[9,0x10009,0x1000a,0x20000])
            self.assertEqual([row[3] for row in rows],[0,1,2,3])
            self.assertEqual([row[4] for row in rows],[1,1,1,1])
            self.assertEqual(struct.unpack_from(mod.WARP_FORMAT,bw,8)[4:],(10,0))
            out=Path(folder)/"private-results"
            mod.write_private_output(out,bm,bw,proof)
            self.assertEqual((out/"r46.map.000.bin").read_bytes(),bm)
            self.assertEqual((out/"r46.warp.000.bin").read_bytes(),bw)
            self.assertEqual(json.loads((out/"r46_source_scoped_warp_summary.json").read_text())["world_count"],3)
            self.assertEqual(before,{n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in paths})
            self.assertFalse(proof["native_original_emerald_overworld_warps_executed"])
    def test_invalid_or_duplicate_source_input_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"e.gba"
            p.write_bytes(bytes(1024))
            with self.assertRaises(mod.WarpIndexError):
                mod.build_indexes([("emerald",p),("emerald",p)])
            with self.assertRaises(mod.WarpIndexError):
                mod.parse_source("bad=/private/path")
            with self.assertRaises(mod.WarpIndexError):
                mod.parse_source("emerald")
            with self.assertRaises(mod.WarpIndexError):
                mod.build_indexes([("emerald",Path(folder)/"missing.gba")])


if __name__=="__main__":
    unittest.main()
