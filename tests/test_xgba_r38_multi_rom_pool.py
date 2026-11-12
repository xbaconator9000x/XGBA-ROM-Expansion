"""R38 independent three-ROM, all-original-byte synthetic integration/stress.

No real copyrighted ROM is checked into GitHub. Each 32 MiB fixture is built
from the original R34 noncopyrighted structural test generator and distinct
deterministic padding; the separate private TRE 3.06 remains outside CI.
This is a host storage test, NOT native GBA cross-game execution.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import random
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import xgba_r34_binary_maps as r34
import xgba_r36_binary_pages as r36
import xgba_r38_multi_rom_pool as r38
from test_xgba_r34_binary_maps import FakeEmeraldBinary

SOURCE_IDS = ("emerald", "rocket", "third")
ROM_SIZE = 32 * 1024 * 1024
ROUNDS = 90000
STRESS_SEED = 0x58474241


class ThreeROMStress(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.images = {}
        cls.indexes = {}
        cls.metadata = {}
        for sequence, source_id in enumerate(SOURCE_IDS):
            synth = FakeEmeraldBinary()
            image = bytearray(synth.image())
            marker = 0x1A0000
            # Each source has a different original script dependency at the
            # SAME address, map group and number; none is executable here.
            image[marker:marker+4] = bytes((41, sequence+1, 0, 2))
            obj = struct.unpack_from("<I", image, synth.first_event+4)[0]-r34.GBA_BASE
            struct.pack_into("<I", image, obj+16, r34.GBA_BASE+marker)
            # Force original 32 MiB ROM sizes and distinct high-offset data:
            # 6,144 SHA-verified pages across three independently owned ROMs.
            fill = bytes((i*29+sequence*43) & 255 for i in range(256))
            image.extend(fill * ((ROM_SIZE-len(image))//len(fill)))
            assert len(image) == ROM_SIZE
            cls.images[source_id] = bytes(image)
            scanner = r34.BinaryMapDiscovery(image)
            discovered = scanner.discover()
            out = cls.root/source_id
            cls.metadata[source_id] = r36.export_binary_pages(
                scanner, discovered, out, source_id, pages_per_shard=128)
            cls.indexes[source_id] = out/"xgba-binary-rom-pages.json"
        cls.pool = r38.MultiROMPool(max_sources=3,
                                    max_cache_bytes=2*r36.PAGE_SIZE,
                                    max_transfer_bytes=r36.PAGE_SIZE)
        cls.pool.mount_many(list(cls.indexes.values()))

    @classmethod
    def tearDownClass(cls):
        cls.pool.close()
        cls.tmp.cleanup()

    def test_triple_full_32mib_rom_mount_and_original_namespace(self):
        p=self.pool
        self.assertEqual(p.source_ids,SOURCE_IDS)
        self.assertEqual(p.source_count,3)
        self.assertEqual(p.total_source_bytes,3*ROM_SIZE)
        self.assertEqual(p.total_pages,6144)
        for source_id in SOURCE_IDS:
            self.assertEqual(p.original_map(source_id,0,0),(source_id,0,0))
            self.assertEqual(p._source(source_id).source_sha256,
                             hashlib.sha256(self.images[source_id]).hexdigest())
            self.assertEqual(p._source(source_id).resource_count,2048)
            self.assertGreater(len(p.script_roots(source_id)),0)

    def test_whole_96mib_original_byte_sha256_audit_not_merely_samples(self):
        report=self.pool.audit_complete_sources()
        self.assertEqual(report["total_original_bytes_verified"],100663296)
        self.assertEqual(report["total_pages_verified"],6144)
        self.assertEqual(set(x["source_id"] for x in report["sources"]),set(SOURCE_IDS))
        self.assertTrue(report["rom_bytes_preserved"])
        for unsafe in ("engine_interoperability_proven",
                       "gameplay_scripts_executed",
                       "cross_world_saves_implemented",
                       "native_guest_dma_lifetime_proven"):
            self.assertFalse(report[unsafe])

    def test_identical_original_pointer_has_separate_source_bytes(self):
        for n,source_id in enumerate(SOURCE_IDS):
            self.assertEqual(self.pool.read_pointer(source_id,0x081a0000,4),
                             bytes((41,n+1,0,2)))
            refs=[x for x in self.pool.script_roots(source_id)
                  if x["source_rom_offset"]==0x1a0000]
            self.assertGreater(len(refs),0)
        self.assertEqual(len({self.pool.read_rom(src,0x1a0000,4)
                              for src in SOURCE_IDS}),3)

    def test_all_page_identity_and_exact_last_byte_per_original_source(self):
        for source_id in SOURCE_IDS:
            original=self.images[source_id]
            for k in (0,1,127,128,256,1024,2047):
                off=k*r36.PAGE_SIZE
                self.assertEqual(self.pool.read_rom(source_id,off,128),original[off:off+128])
            self.assertEqual(self.pool.read_rom(source_id,ROM_SIZE-1,1),original[-1:])
            self.assertEqual(self.pool.read_rom(source_id,ROM_SIZE,0),b"")

    def test_90000_deterministic_cross_source_random_windows(self):
        rng=random.Random(STRESS_SEED)
        totals={source_id:0 for source_id in SOURCE_IDS}
        crossed=0
        for i in range(ROUNDS):
            source_id=SOURCE_IDS[rng.randrange(3)]
            # Include 1 KiB, partial and full 16 KiB transfer windows.
            length=rng.choice((1,2,31,63,256,1024,2048,4096,8192,16384))
            off=rng.randrange(ROM_SIZE-length+1)
            got=self.pool.read_rom(source_id,off,length)
            self.assertEqual(got,self.images[source_id][off:off+length])
            totals[source_id]+=1
            if off//r36.PAGE_SIZE!=(off+length-1)//r36.PAGE_SIZE:
                crossed+=1
            if i%20000==0:
                self.assertLessEqual(self.pool.staged_bytes,2*r36.PAGE_SIZE)
        self.assertTrue(all(x>29000 for x in totals.values()))
        self.assertGreater(crossed,10000)

    def test_every_page_under_host_lru_churn_and_no_mutable_alias(self):
        p=self.pool
        p.unstage_all()
        before=p.evictions
        for page in range(2048):
            for source_id in SOURCE_IDS:
                data=p.stage_page(source_id,page)
                off=page*r36.PAGE_SIZE
                self.assertEqual(data,self.images[source_id][off:off+r36.PAGE_SIZE])
                self.assertIsInstance(data,bytes)
                self.assertLessEqual(p.staged_bytes,2*r36.PAGE_SIZE)
        self.assertGreaterEqual(p.evictions-before,6140)
        self.assertLessEqual(p.staged_bytes,32768)
        # Caller-retained source bytes remain immutable even after eviction.
        preserved=p.stage_page("emerald",0)
        for page in range(10):
            p.stage_page("third",page+50)
        self.assertEqual(preserved,self.images["emerald"][:r36.PAGE_SIZE])

    def test_cross_page_exact_boundaries_for_every_source(self):
        for source_id in SOURCE_IDS:
            for page in (0,1,127,128,1023,1024,2046):
                off=(page+1)*r36.PAGE_SIZE-7
                self.assertEqual(self.pool.read_rom(source_id,off,14),
                                 self.images[source_id][off:off+14])

    def test_incorrect_namespace_or_pointer_never_falls_back(self):
        for invalid in ("ROCKET","other","",None):
            with self.subTest(invalid=invalid), self.assertRaises(r38.MultiROMError):
                self.pool.read_rom(invalid,0,1)
        for ptr in (0,0x07000000,0x0a000000,0xffffffff,True,-1):
            with self.subTest(ptr=ptr),self.assertRaises(r38.MultiROMError):
                self.pool.read_pointer("rocket",ptr,1)

    def test_invalid_offsets_sizes_and_boolean_arguments_refused(self):
        for off,n in ((-1,1),(ROM_SIZE+1,0),(ROM_SIZE,1),(0,16385),
                      (True,1),(0,True),(0,-1)):
            with self.subTest(off=off,n=n),self.assertRaises(r38.MultiROMError):
                self.pool.read_rom("emerald",off,n)
        for group,num in ((-1,0),(0,999),(True,0),(0,True)):
            with self.subTest(group=group,num=num),self.assertRaises(r38.MultiROMError):
                self.pool.original_map("rocket",group,num)

    def test_duplicate_original_source_and_maximum_source_limit(self):
        with self.assertRaises(r38.MultiROMError):
            self.pool.mount(self.indexes["rocket"])
        with self.assertRaises(r38.MultiROMError):
            self.pool.mount_many([self.indexes["emerald"]])
        self.assertEqual(self.pool.source_count,3)

    def test_atomic_mount_rejects_corrupt_index_without_partial_publish(self):
        candidate=r38.MultiROMPool(max_sources=3)
        index=self.indexes["rocket"]
        doc=json.loads(index.read_text())
        doc["source_identity"]["sha256"]="0"*64
        bad=index.parent/"bad-r38.json"
        bad.write_text(json.dumps(doc))
        self.addCleanup(bad.unlink,missing_ok=True)
        with self.assertRaises(r38.MultiROMError):
            candidate.mount_many([self.indexes["emerald"],bad])
        self.assertEqual(candidate.source_count,0)
        candidate.mount_many([self.indexes["emerald"],self.indexes["rocket"]])
        self.assertEqual(candidate.source_count,2)

    def test_bad_source_map_numbers_do_not_remap_original_ids(self):
        for source_id in SOURCE_IDS:
            p=self.pool
            self.assertEqual(p.original_map(source_id,0,6),(source_id,0,6))
            self.assertEqual(p.original_map(source_id,1,4),(source_id,1,4))
            with self.assertRaises(r38.MultiROMError):
                p.original_map(source_id,1,5)

    def test_reader_never_mutates_original_backing_bytes(self):
        previous={s:hashlib.sha256(v).hexdigest() for s,v in self.images.items()}
        for s in SOURCE_IDS:
            self.pool.stage_page(s,512)
            self.pool.read_rom(s,ROM_SIZE-16384,16384)
            self.pool.script_roots(s)
        for s in SOURCE_IDS:
            self.assertEqual(hashlib.sha256(self.images[s]).hexdigest(),previous[s])
            self.assertEqual(self.pool._source(s).source_sha256,previous[s])


if __name__=="__main__":
    unittest.main()
