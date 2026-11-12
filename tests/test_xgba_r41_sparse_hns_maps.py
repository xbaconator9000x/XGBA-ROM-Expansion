"""R41 sparse map-group import acceptance: preserve actual original slot IDs.

Only zero map pointers are allowed as holes. Any malformed nonzero pointer
remains fatal. FakeEmeraldBinary consists exclusively of generated fixtures.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest

import xgba_r34_binary_maps as r34
from test_xgba_r34_binary_maps import FakeEmeraldBinary


class SparseHnSMapSlots(unittest.TestCase):
    def setUp(self):
        self.fake=FakeEmeraldBinary()
        self.data=bytearray(self.fake.image())
        self.slots=((3,0),(3,1),(4,2),(5,0),(6,1),(7,0))
        for group,number in self.slots:
            off=self._slot(group,number)
            struct.pack_into("<I",self.data,off,0)

    def _slot(self,group,number):
        start=struct.unpack_from("<I",self.data,self.fake.table_offset+group*4)[0]-r34.GBA_BASE
        return start+number*4

    def discover(self,image=None):
        engine=r34.BinaryMapDiscovery(bytes(self.data if image is None else image))
        return engine,engine.discover(min_root_references=1,allow_null_slots=True)

    def test_six_zero_pointer_holes_preserved_at_original_indices(self):
        _,d=self.discover()
        self.assertEqual(d["table_offset"],self.fake.table_offset)
        self.assertEqual(d["slot_count"],sum(self.fake.groups))
        self.assertEqual(d["map_count"],sum(self.fake.groups)-len(self.slots))
        self.assertEqual(d["null_slot_count"],len(self.slots))
        self.assertEqual({(x["group"],x["map"]) for x in d["null_slots"]},set(self.slots))
        self.assertEqual(d["group_map_counts"],list(self.fake.groups))

    def test_holes_do_not_reindex_neighboring_maps(self):
        _,d=self.discover()
        active={(m["group"],m["map"]) for m in d["maps"]}
        all_slots={(g,n) for g,limit in enumerate(self.fake.groups) for n in range(limit)}
        self.assertEqual(active,all_slots-set(self.slots))
        self.assertIn((7,4),active)
        self.assertIn((3,2),active)

    def test_default_r34_strict_mode_still_refuses_any_hole(self):
        s=r34.BinaryMapDiscovery(bytes(self.data))
        with self.assertRaisesRegex(r34.DiscoveryError,"No validated"):
            s.discover()
        with self.assertRaisesRegex(r34.DiscoveryError,"No validated"):
            s.discover(min_root_references=4)

    def test_single_source_reference_requires_explicit_sparse_mode(self):
        d=bytearray(self.data)
        d[0x204:0x214]=bytes(16)
        s=r34.BinaryMapDiscovery(bytes(d))
        with self.assertRaisesRegex(r34.DiscoveryError,"threshold"):
            s.discover(min_root_references=1)
        self.assertEqual(s.discover(min_root_references=1,allow_null_slots=True)["reference_count"],1)

    def test_malformed_nonzero_header_pointer_rejected(self):
        d=bytearray(self.data)
        struct.pack_into("<I",d,self._slot(4,2),r34.GBA_BASE+len(d)-4)
        s=r34.BinaryMapDiscovery(bytes(d))
        with self.assertRaisesRegex(r34.DiscoveryError,"No validated"):
            s.discover(min_root_references=1,allow_null_slots=True)

    def test_nonzero_corrupted_layout_rejected_even_with_sparse_mode(self):
        d=bytearray(self.data)
        header=self.fake.header_offsets[19]
        layout=struct.unpack_from("<I",d,header)[0]-r34.GBA_BASE
        struct.pack_into("<I",d,layout,0)
        s=r34.BinaryMapDiscovery(bytes(d))
        with self.assertRaisesRegex(r34.DiscoveryError,"No validated"):
            s.discover(min_root_references=1,allow_null_slots=True)

    def test_can_export_sparse_fixed_structures_without_hole_segments(self):
        engine,d=self.discover()
        with tempfile.TemporaryDirectory() as temp:
            report=engine.export_maps(d,Path(temp)/"out","heart_soul")
            self.assertEqual(report["original_null_map_slots"],d["null_slots"])
            self.assertEqual(len(report["original_map_headers"]),d["map_count"])
            self.assertEqual(report["summary"]["zero_pointer_map_slots_preserved"],len(self.slots))
            present={(m["group"],m["map"]) for m in report["original_map_headers"]}
            self.assertFalse(present.intersection(self.slots))
            self.assertEqual({(x["group"],x["map"]) for x in report["original_null_map_slots"]},set(self.slots))

    def test_export_preserves_complete_original_byte_identity(self):
        engine,d=self.discover()
        before=hashlib.sha256(engine.data).hexdigest()
        with tempfile.TemporaryDirectory() as temp:
            engine.export_maps(d,Path(temp)/"out","hns",max_shard_entries=32,max_shard_bytes=32768)
        self.assertEqual(hashlib.sha256(engine.data).hexdigest(),before)

    def test_refuse_empty_or_all_null_group_table(self):
        d=bytearray(self.data)
        for g in range(len(self.fake.groups)):
            for n in range(self.fake.groups[g]):
                struct.pack_into("<I",d,self._slot(g,n),0)
        with self.assertRaisesRegex(r34.DiscoveryError,"No validated"):
            r34.BinaryMapDiscovery(bytes(d)).discover(min_root_references=1,allow_null_slots=True)

    def test_strict_bool_mode_and_header_digest_fail_closed(self):
        s=r34.BinaryMapDiscovery(bytes(self.data))
        with self.assertRaisesRegex(r34.DiscoveryError,"threshold"):
            s.discover(allow_null_slots=1)
        damaged=bytearray(self.data)
        damaged[0xBD]^=1
        with self.assertRaisesRegex(r34.DiscoveryError,"header"):
            r34.BinaryMapDiscovery(bytes(damaged))


if __name__=="__main__":
    unittest.main()
