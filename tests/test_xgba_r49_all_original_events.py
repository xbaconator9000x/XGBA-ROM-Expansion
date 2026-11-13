"""R49 full original 3-ROM event preservation, 16KiB page packing."""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import xgba_r49_all_original_map_events as r49


def authored_source(n):
    raw=bytearray(512)
    raw[0]=n
    # Every original event class must round-trip without a single byte lost.
    raw[64:88]=bytes([2+n,17,0,0,12+n,0,13,0,0,0,0,0,0,0,0,0]) + struct.pack("<I",0x08210000+n)+bytes(4)
    raw[88:96]=struct.pack("<hhBBBB",3,5,0,0,9,0)
    raw[96:112]=bytes(range(16))
    raw[112:124]=bytes([0x88+i for i in range(12)])
    return bytes(raw)


class FakeMapDiscovery:
    def __init__(self,rom):
        self.source=rom[0]
    def discover(self,*,min_root_references,allow_null_slots):
        if min_root_references!=1 or not allow_null_slots:
            raise AssertionError("R49 must preserve null original map slots")
        return {
            "maps":[{
                "group":0,"map":4 if self.source==2 else 9,
                "object_count":1,"warp_count":1,
                "coordinate_event_count":1,"background_event_count":1,
                "event_array_offsets":[64,88,96,112],
                "header_offset":160+self.source*4,
                "events_offset":192+self.source*4,
                "script_root_offset":256+self.source*4,
            }],
            "slot_count":1495 if self.source==2 else 1,
            "null_slot_count":935 if self.source==2 else 0,
        }


class R49EntireOriginalEventScope(unittest.TestCase):
    def test_all_four_original_emerald_event_arrays_preserved(self):
        rom=authored_source(1)
        discovered=FakeMapDiscovery(rom).discover(
            min_root_references=1,allow_null_slots=True)
        key,blob=r49.pack_event_record(1,rom,discovered["maps"][0])
        self.assertEqual(key,0x10009)
        self.assertEqual(blob[:4],b"X49E")
        self.assertEqual(len(blob),32+24+8+16+12)
        self.assertEqual(blob[32:56],rom[64:88])
        self.assertEqual(blob[56:64],rom[88:96])
        self.assertEqual(blob[64:80],rom[96:112])
        self.assertEqual(blob[80:92],rom[112:124])
        self.assertEqual(struct.unpack_from("<I",blob,20)[0],
                         zlib.crc32(blob[32:])&0xffffffff)
        self.assertEqual(struct.unpack_from("<I",blob,28)[0],260)
    def test_three_source_original_map_keys_hns_holes_and_paged_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            paths={}
            expected={}
            for index,name in enumerate(("emerald","rocket","heart_soul")):
                data=authored_source(index)
                path=root/(name+".gba")
                path.write_bytes(data)
                paths[name]=path
                expected[name]=(hashlib.sha256(data).hexdigest(),1)
            with patch.object(r49,"SOURCES",expected):
                with patch.object(r49.r34,"BinaryMapDiscovery",FakeMapDiscovery):
                    idx_pages,pages,proof,entries=r49.compile_all_original_map_events(
                        paths,require_complete=False)
            self.assertEqual(proof["all_original_maps_indexed"],3)
            self.assertEqual(proof["object_event_records_retained"],3)
            self.assertEqual(proof["original_warp_records_retained"],3)
            self.assertEqual(proof["background_interactions_retained"],3)
            self.assertEqual(proof["source_reports"]["heart_soul"]["null_map_slots"],935)
            self.assertEqual([x[0] for x in entries],[0x000009,0x010009,0x020004])
            self.assertEqual(len(idx_pages),1)
            self.assertEqual(len(pages),1)
            for i,(key,page,offset,length,head) in enumerate(entries):
                self.assertEqual(page,0)
                p=pages[page][offset:offset+length]
                self.assertEqual(struct.unpack_from("<I",p,4)[0],key)
                self.assertEqual(struct.unpack_from("<I",p,12)[0],head)
                self.assertEqual(p[32:56],authored_source(i)[64:88])
            private=root/"private-pack"
            r49.save_private_pack(private,idx_pages,pages,proof)
            self.assertEqual(len(list(private.glob("r49.*.bin"))),2)
            self.assertFalse(proof["original_engine_foreign_npc_interaction_verified"])
            self.assertFalse(proof["cross_world_fly_verified"])
            self.assertEqual((private/"r49.index.000.bin").read_bytes(),idx_pages[0])
            with patch.object(r49,"SOURCES",expected):
                with patch.object(r49.r34,"BinaryMapDiscovery",FakeMapDiscovery):
                    with self.assertRaises(r49.OriginalEventImportError):
                        r49.compile_all_original_map_events(paths)
    def test_broken_pointer_and_missing_nonzero_original_events_rejected(self):
        rom=authored_source(0)
        m=FakeMapDiscovery(rom).discover(min_root_references=1,allow_null_slots=True)["maps"][0]
        for corrupt in ([64,88,96,None],[64,88,96,511]):
            changed=dict(m,event_array_offsets=corrupt)
            with self.assertRaises(r49.OriginalEventImportError):
                r49.pack_event_record(0,rom,changed)
    def test_complete_world_requirement_sha_and_private_output_gate(self):
        with self.assertRaises(r49.OriginalEventImportError):
            r49.compile_all_original_map_events({})
        self.assertEqual(sum(x[1] for x in r49.SOURCES.values()),2856)
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)
            p.joinpath("not-empty").write_text("stop")
            with self.assertRaises(r49.OriginalEventImportError):
                r49.save_private_pack(p,[bytes(r49.PAGE)],[bytes(r49.PAGE)],{})
    def test_no_synthetic_npcs_or_script_execution_claims(self):
        import inspect
        source=inspect.getsource(r49)
        self.assertIn("original_script_pointers_preserved_not_executed",source)
        self.assertIn("original_engine_foreign_npc_interaction_verified",source)
        self.assertIn("cross_world_fly_verified",source)
        self.assertNotIn("R49_FLY_COMPLETED",source)


if __name__=="__main__":
    unittest.main()
