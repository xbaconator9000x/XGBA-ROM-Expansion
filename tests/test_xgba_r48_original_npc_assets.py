"""R48 original source NPC assets: validate exact original bytecodes/text.

Public tests use authored fake fixture bytes; actual private user ROMs must
independently pass complete SHA-256 and unchanged local NPC provenance.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import xgba_r48_original_npc_assets as r48


def fake_rom():
    rom=bytearray(2048)
    rom[0x200]=2
    struct.pack_into("<H",rom,0x201,17)
    struct.pack_into("<hh",rom,0x204,12,13)
    struct.pack_into("<I",rom,0x210,0x08000300)
    rom[0x300:0x309]=bytes([0x0f,0x00])+struct.pack("<I",0x08000500)+bytes([0x09,0x02,0x02])
    rom[0x500:0x505]=b"\xbb\xbc\xbd\xfe\xff"
    return bytes(rom)


class FakeDiscovery:
    def __init__(self,rom):
        self.rom=rom
    def discover(self,*,min_root_references,allow_null_slots):
        if not min_root_references==1 or not allow_null_slots:
            raise AssertionError("Do not discard zero-pointer map slots")
        return {"maps":[{
            "group":0,"map":9,"object_count":1,
            "event_array_offsets":[0x200,None,None,None],
        }]}


class RealOriginalNpcResourceTests(unittest.TestCase):
    def source(self,blob=None):
        rom=fake_rom() if blob is None else bytes(blob)
        witness=r48.Witness("authored-test",0,0,9,2,12,13,17,0x300,0x500,
                            hashlib.sha256(rom).hexdigest())
        return witness,rom

    @patch.object(r48.r34,"BinaryMapDiscovery",FakeDiscovery)
    def test_exact_opcode_and_raw_original_dialogue_retained(self):
        witness,rom=self.source()
        pack,proof=r48.extract_npc_bytes(witness,rom)
        self.assertEqual(len(pack),256)
        self.assertEqual(pack[:4],b"X48N")
        self.assertEqual(struct.calcsize(r48.HEADER_FORMAT),32)
        self.assertEqual(pack[32:41],rom[0x300:0x309])
        self.assertEqual(pack[41:46],rom[0x500:0x505])
        self.assertEqual(pack[32:34],bytes([0x0f,0]))
        self.assertEqual(pack[38:41],bytes([0x09,0x02,0x02]))
        self.assertEqual(proof["original_script_rom_offset"],0x300)
        self.assertEqual(proof["original_text_rom_offset"],0x500)
        self.assertFalse(proof["original_script_executed_in_emerald_engine"])
        self.assertTrue(proof["original_bytes_unmodified_in_pack"])

    @patch.object(r48.r34,"BinaryMapDiscovery",FakeDiscovery)
    def test_rejects_changed_original_script_or_rom_sha(self):
        witness,rom=self.source()
        corrupt=bytearray(rom)
        corrupt[0x300]=0x16
        with self.assertRaises(r48.NotOriginalNpcSource):
            r48.extract_npc_bytes(witness,corrupt)
        witness2,_=self.source(corrupt)
        with self.assertRaises(r48.NotOriginalNpcSource):
            r48.extract_npc_bytes(witness2,bytes(corrupt))

    @patch.object(r48.r34,"BinaryMapDiscovery",FakeDiscovery)
    def test_rejects_wrong_original_npc_identity_and_text_pointer(self):
        witness,rom=self.source()
        wrong=r48.Witness(**{**witness.__dict__,"npc_id":3})
        with self.assertRaises(r48.NotOriginalNpcSource):
            r48.extract_npc_bytes(wrong,rom)
        corrupt=bytearray(rom)
        struct.pack_into("<I",corrupt,0x302,0x08000600)
        witness2,_=self.source(corrupt)
        with self.assertRaises(r48.NotOriginalNpcSource):
            r48.extract_npc_bytes(witness2,bytes(corrupt))

    def test_target_provenance_is_full_original_game_not_synthetic_label(self):
        records=r48.WITNESSES
        self.assertEqual([w.name for w in records],["emerald","rocket","heart_soul"])
        self.assertEqual([(w.group,w.map,w.npc_id) for w in records],
                         [(0,9,2),(0,9,2),(0,4,7)])
        self.assertEqual([w.script_offset for w in records],
                         [0x1E8022,0x215543,0x390519])
        self.assertEqual([w.text_offset for w in records],
                         [0x1E8ACF,0x1DC3364,0x3908E6])
        self.assertEqual(len({w.rom_sha256 for w in records}),3)
        for witness in records:
            self.assertEqual(len(witness.rom_sha256),64)
            int(witness.rom_sha256,16)
        self.assertGreater(r48.START_OFFSET,32*1024*1024)

    def test_guest_bridge_is_hard_gated_by_real_npc_object_interaction(self):
        include=(Path(__file__).resolve().parents[1]/
                 "integration/emerald/xgba_r48_original_npc_scripts.inc").read_text()
        source_patch=(Path(__file__).resolve().parents[1]/
                      "tools/xgba_r17_emerald_patch.py").read_text()
        for required in (
                "XgbaR48ResolveActualOriginalNpcScript",
                "XgbaR48SetSourceMapLoaded",
                "if(!sXgbaR48SourceMapLoaded)",
                "XgbaGuestFetch(",
                "original_script_fetches",
                "real_npc_interactions",
                "actual_cross_world_fly_warps"):
            self.assertIn(required,include)
        self.assertIn("src/field_control_avatar.c",source_patch)
        self.assertIn("gObjectEvents[objectEventId].localId",source_patch)
        self.assertNotIn("FLY_TEST_PASSED",include)


if __name__=="__main__":
    unittest.main()
