"""R41 three real-ROM compatibility harness: synthetic source-only acceptance."""
from __future__ import annotations
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest

import xgba_r41_three_rom_trial as r41
import xgba_r34_binary_maps as r34
from test_xgba_r34_binary_maps import FakeEmeraldBinary


class TripleSourceTrial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="xgba-r41-triple-")
        cls.root=Path(cls.temp.name)
        cls.inputs=[]
        for sid,padding in (("emerald",0),("rocket",0x800),("heart_soul",0x1400)):
            synthetic=FakeEmeraldBinary(padding=padding)
            b=bytearray(synthetic.image())
            if sid=="heart_soul":
                # Preserve inactive source slots and original active IDs.
                for group,number in ((3,0),(4,0),(5,0),(6,1),(7,0)):
                    table=struct.unpack_from("<I",b,synthetic.table_offset+group*4)[0]-r34.GBA_BASE
                    struct.pack_into("<I",b,table+number*4,0)
                # Source-local different geometry with same numeric identity.
                first_layout=synthetic.layout_offsets[0]
                struct.pack_into("<I",b,first_layout,47)
            dest=cls.root/(sid+".gba")
            dest.write_bytes(b)
            cls.inputs.append((sid,dest))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_three_worlds_map_and_original_source_isolation(self):
        report=r41.run_trial(self.inputs,windows=2400)
        self.assertEqual(len(report["source_worlds"]),3)
        self.assertTrue(report["test_results"]["accepted_3_real_sources_with_sparse_hns_compatible_map_ids"])
        self.assertEqual(report["test_results"]["random_byte_mismatches"],0)
        self.assertEqual(report["test_results"]["total_original_bytes"],3*2*1024*1024)
        self.assertGreater(report["cross_source_collisions"]["ids_present_in_all_three"],32)
        self.assertGreater(report["cross_source_collisions"]["duplicate_numeric_ids_with_different_map_geometry"],0)
        self.assertEqual(report["source_worlds"]["heart_soul"]["original_zero_pointer_map_holes"],5)
        self.assertEqual(report["source_worlds"]["emerald"]["original_zero_pointer_map_holes"],0)

    def test_original_numeric_ids_never_renumbered_by_sparse_import(self):
        result=r41.run_trial(self.inputs,windows=0)
        for sid in ("emerald","rocket","heart_soul"):
            src=result["source_worlds"][sid]
            self.assertEqual(src["original_numeric_map_slots"],
                             src["structurally_valid_nonnull_maps"]+src["original_zero_pointer_map_holes"])
            self.assertTrue(src["active_original_numeric_map_ids_preserved"])
        self.assertEqual(result["source_worlds"]["heart_soul"]["original_zero_pointer_map_holes"],5)

    def test_all_file_pages_sha_are_unchanged_after_trial(self):
        before={sid:hashlib.sha256(p.read_bytes()).hexdigest() for sid,p in self.inputs}
        report=r41.run_trial(self.inputs,windows=200)
        after={sid:hashlib.sha256(p.read_bytes()).hexdigest() for sid,p in self.inputs}
        self.assertEqual(before,after)
        self.assertEqual({sid:p["original_rom_sha256"] for sid,p in report["source_worlds"].items()},before)

    def test_paged_lru_only_keeps_two_small_pages(self):
        with r41.SourceReader(self.inputs) as src:
            for sid,p in self.inputs:
                for i in range(0,128,13):
                    src.page(sid,i)
                self.assertEqual(src.read(sid,16380,16),p.read_bytes()[16380:16396])
            self.assertLessEqual(sum(map(len,src.cache.values())),r41.CACHE_BYTES)
            self.assertGreater(src.evictions,0)

    def test_cross_page_contiguous_host_read_preserves_source(self):
        with r41.SourceReader(self.inputs) as src:
            a=src.read("rocket",r41.PAGE-3,14)
            b=self.inputs[1][1].read_bytes()[r41.PAGE-3:r41.PAGE+11]
            self.assertEqual(a,b)
            self.assertEqual(len(a),14)

    def test_reject_unknown_source_and_out_of_bounds_reads(self):
        with r41.SourceReader(self.inputs) as src:
            for sid,off,size in (("invalid",0,1),("emerald",-1,2),
                                 ("emerald",0,r41.PAGE+1),
                                 ("rocket",2*1024*1024,1)):
                with self.assertRaises(r41.TrialError):
                    src.read(sid,off,size)

    def test_reject_invalid_names_duplicates_and_too_many_sources(self):
        with self.assertRaises(r41.TrialError):
            r41._source_arg("../bad=/tmp/a.gba")
        with self.assertRaises(r41.TrialError):
            r41.SourceReader([("emerald",self.inputs[0][1]),("emerald",self.inputs[1][1])])
        with self.assertRaises(r41.TrialError):
            r41.SourceReader(self.inputs+[("fourth",self.inputs[0][1])])

    def test_bounded_random_window_argument(self):
        for amount in (-1,100001,2.5,True):
            with self.subTest(amount=amount),self.assertRaises(r41.TrialError):
                r41.run_trial(self.inputs,windows=amount)

    def test_nonzero_corrupt_source_header_is_fail_closed(self):
        temp=self.root/"damaged.gba"
        bad=bytearray(self.inputs[1][1].read_bytes())
        bad[0xBD]^=1
        temp.write_bytes(bad)
        with self.assertRaises(r34.DiscoveryError):
            r41.run_trial([("emerald",self.inputs[0][1]),("rocket",temp)],windows=0)

    def test_unexpected_game_code_fail_closed_before_merging(self):
        temp=self.root/"wrong-code.gba"
        bad=bytearray(self.inputs[0][1].read_bytes())
        bad[0xAC:0xB0]=b"BPRE"
        bad[0xBD]=(-sum(bad[0xA0:0xBD])-0x19)&255
        temp.write_bytes(bad)
        with self.assertRaises(r41.TrialError):
            r41.run_trial([("emerald",self.inputs[1][1]),("other",temp)],windows=0)

    def test_result_omits_source_bytes_and_any_playability_claim(self):
        report=r41.run_trial(self.inputs,windows=0)
        self.assertFalse(report["three_game_playable_build_proven"])
        self.assertFalse(report["native_guest_multi_rom_scripts_executed"])
        self.assertFalse(report["shared_native_flash_save_proven"])
        self.assertTrue(report["read_only_all_original_bytes_preserved"])
        self.assertNotIn("rom_data",str(report))
        self.assertNotIn(str(self.root),str(report))

    def test_source_hashes_and_counts_are_deterministic(self):
        a=r41.run_trial(self.inputs,windows=12,seed=12345)
        b=r41.run_trial(self.inputs,windows=12,seed=12345)
        self.assertEqual(a,b)


if __name__=="__main__":
    unittest.main()
