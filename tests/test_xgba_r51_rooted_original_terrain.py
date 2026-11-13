"""R51 actual original-group table scanner: three namespaces, no ROM bytes.

Authored 2-group fixture follows the source ROM layout exactly: adjacent
u32 map-header pointer arrays and a trailing GBA-pointer root table.
Tests the full original importer CLI path with SHA-pinned input identities,
not a forged R34 API or disconnected fixture pack method.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import xgba_r51_original_grid_pages as r51

def original_rom_map_group_fixture(salt=0):
    blob=bytearray(0x4000)
    def word(at,value):struct.pack_into("<I",blob,at,value)
    def ptr(at):return 0x08000000+at
    root=0x110
    word(root,ptr(0x100));word(root+4,ptr(0x108))
    word(0x100,ptr(0x200));word(0x104,ptr(0x220))
    word(0x108,0);word(0x10c,ptr(0x240))
    for i,header in enumerate((0x200,0x220,0x240)):
        layout=0x300+i*0x20
        word(header,ptr(layout))
        struct.pack_into("<6I",blob,layout,4,4,
             ptr(0xA00+i*0x20),ptr(0xB00+i*0x20),ptr(0x800),ptr(0x900))
        blob[0xA00+i*0x20:0xA08+i*0x20]=bytes([salt+i])*8
        blob[0xB00+i*0x20:0xB20+i*0x20]=bytes([salt+i+1])*32
    return bytes(blob)

class ExactOriginalThreeRomGroupRoots(unittest.TestCase):
    def test_original_scanner_preserves_all_source_map_slots(self):
        blob=original_rom_map_group_fixture()
        parsed=r51.discover_original_geometries(blob,0x110,2,3,1,0x100)
        self.assertEqual(parsed["null_slot_count"],1)
        self.assertEqual(parsed["original_map_slots"],4)
        self.assertEqual([(m["group"],m["map"]) for m in parsed["maps"]],
          [(0,0),(0,1),(1,1)])
        self.assertEqual([m["header_offset"] for m in parsed["maps"]],
          [0x200,0x220,0x240])
        self.assertTrue(all(m["map_grid_bytes"]==32 for m in parsed["maps"]))

    def test_source_ptr_and_expected_counts_fail_closed(self):
        blob=original_rom_map_group_fixture()
        with self.assertRaisesRegex(r51.OriginalGridError,"root drift"):
            r51.discover_original_geometries(blob,0x110,2,3,1,0x104)
        with self.assertRaisesRegex(r51.OriginalGridError,"count mismatch"):
            r51.discover_original_geometries(blob,0x110,2,3,0,0x100)
        corrupt=bytearray(blob)
        struct.pack_into("<I",corrupt,0x100,0xFF000000)
        with self.assertRaisesRegex(r51.OriginalGridError,"pointer"):
            r51.discover_original_geometries(bytes(corrupt),0x110,2,3,1,0x100)

    def test_full_real_importer_path_all_three_authored_roms(self):
        blobs=[original_rom_map_group_fixture(i*15) for i in range(3)]
        names=tuple(r51.SOURCES)
        fixtures={name:(hashlib.sha256(blob).hexdigest(),3,1)
                  for name,blob in zip(names,blobs)}
        roots={name:(0x110,2,0x100) for name in names}
        with tempfile.TemporaryDirectory() as tmp, \\
             patch.object(r51,"SOURCES",fixtures), \\
             patch.object(r51,"ORIGINAL_GROUP_ROOTS",roots):
            files={}
            for n,blob in zip(names,blobs):
                path=Path(tmp)/(n+".gba")
                path.write_bytes(blob)
                files[n]=path
            index,grids,report=r51.from_three_original_roms(files)
            self.assertEqual(report["maps"],9)
            self.assertEqual(report["original_null_map_slots"],3)
            self.assertEqual(report["native_guest_fit_maps"],9)
            self.assertEqual(len(index),1)
            keys=[struct.unpack_from("<I",index[0],i*32)[0] for i in range(9)]
            self.assertEqual(keys,[0,1,0x101,0x10000,0x10001,
                 0x10101,0x20000,0x20001,0x20101])
            manifest=r51.write_private_pages(index,grids,report,
                   Path(tmp)/"private")
            self.assertEqual(len(manifest["resources"]),2)
            self.assertEqual(manifest["resources"][0]["id"],"r51.index.000")
            broken=bytearray(blobs[1]);broken[-1]^=0x80
            files[names[1]].write_bytes(broken)
            with self.assertRaisesRegex(r51.OriginalGridError,"Unrecognized"):
                r51.from_three_original_roms(files)

if __name__=="__main__": unittest.main()
