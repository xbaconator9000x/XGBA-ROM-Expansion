"""R36: all-ROM-byte paging, original map IDs, script-root references, corruption gates.

Synthetic non-copyrighted GBA binaries only. No custom scripts are executed.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import xgba_r34_binary_maps as r34
import xgba_r36_binary_pages as r36
import xgba_r36_mixed_world as mix36
import xgba_mixed_world_pool as r35
import xgba_whole_corpus as r32
from test_xgba_r34_binary_maps import FakeEmeraldBinary


class BinaryPaging(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory()
        cls.root=Path(cls.temporary.name)
        cls.fixture=FakeEmeraldBinary()
        cls.original=cls.fixture.image()
        cls.rom=cls.root/"fake.gba"
        cls.rom.write_bytes(cls.original)
        cls.scanner=r34.BinaryMapDiscovery(cls.rom)
        cls.found=cls.scanner.discover()
        cls.raw=cls.root/"raw-pages"
        cls.report=r36.export_binary_pages(cls.scanner,cls.found,cls.raw,"rocket",pages_per_shard=8)
        cls.index=cls.raw/"xgba-binary-rom-pages.json"
        cls.mappacks=cls.root/"maps"
        cls.scanner.export_maps(cls.found,cls.mappacks,"rocket",max_shard_entries=10,max_shard_bytes=4096)
        cls.map_index=cls.mappacks/"xgba-binary-maps.json"
        cls.worldroots=[]
        cls.content={}
        for world in ("emerald","heartsoul"):
            dest=cls.root/world
            cls.worldroots.append((world,dest))
            files={
              "data/maps/map_groups.json":json.dumps({"group_order":["g"],"g":["Home"]}).encode(),
              "data/maps/Home/map.json":json.dumps({"name":"Home","id":"MAP_HOME","connections":[]}).encode(),
              "data/scripts/events.inc":b"STORY "+world.encode(),
              "graphics/sprite.bin":world.encode()*120,
            }
            cls.content[world]=files
            for name,raw in files.items():
                p=dest/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        cls.source=cls.root/"sources"
        r32.export_corpus([r32.inspect_source(n,p) for n,p in cls.worldroots],
                          [p for n,p in cls.worldroots],cls.source,pack=True,
                          max_shard_entries=2,max_shard_bytes=4096)

    @classmethod
    def tearDownClass(cls):cls.temporary.cleanup()

    def pool(self):return r36.PagedBinaryPool(self.index,max_staged_bytes=32768,chunk_size=97)

    def world(self):
        w=mix36.R36MixedWorldPool(max_staged_bytes=32768)
        w.mount_corpus(self.source/"xgba-whole-corpus-index.json")
        w.mount_binary(self.map_index)
        w.mount_binary_pages(self.index)
        return w

    def changed_index(self,change):
        doc=json.loads(self.index.read_text())
        change(doc)
        p=self.raw/"tampered-test-index.json"
        p.write_text(json.dumps(doc))
        self.addCleanup(p.unlink,missing_ok=True)
        return p

    def test_entire_rom_byte_for_byte_and_unmodified(self):
        p=self.pool()
        self.assertEqual(p.rom_bytes,len(self.original))
        self.assertEqual(p.resource_count,len(self.original)//r36.PAGE_SIZE)
        self.assertEqual(p.verify_original_rom(self.rom),len(self.original))
        self.assertEqual(p.staged_bytes,0)
        self.assertEqual(hashlib.sha256(self.original).hexdigest(),p.source_sha256)

    def test_page_identity_preserves_source_offsets(self):
        p=self.pool()
        for i,e in enumerate(self.report["pages"]):
            rid=f"rom.page.{i:06d}"
            self.assertEqual(e["id"],rid)
            self.assertEqual(e["rom_offset"],i*r36.PAGE_SIZE)
            self.assertEqual(p.page_at(i*r36.PAGE_SIZE),(rid,0))
            self.assertEqual(e["sha256"],hashlib.sha256(self.original[i*r36.PAGE_SIZE:(i+1)*r36.PAGE_SIZE]).hexdigest())

    def test_boundary_crossings_and_offset_reads_verified(self):
        p=self.pool()
        for off in (0,1,1024,16382,16383,16384,32765,self.fixture.first_grid,self.fixture.first_event,len(self.original)-12):
            with self.subTest(off=off):
                size=min(16,len(self.original)-off)
                self.assertEqual(p.read_rom(off,size),self.original[off:off+size])
        self.assertEqual(p.read_rom(len(self.original),0),b"")

    def test_mixed_three_world_lookup_source_map_collision_safe(self):
        w=self.world()
        self.assertEqual(set(w.source_ids),{"emerald","rocket","heartsoul"})
        self.assertEqual(w.find_original_map("rocket",0,0)["width"],48)
        self.assertEqual(w.find_original_map("emerald",0,0)["name"],"Home")
        self.assertEqual(w.find_original_map("heartsoul",0,0)["name"],"Home")
        a,_=w.find_rom_page("rocket",16384)
        self.assertEqual(bytes(w.stage(a)),self.original[16384:32768])
        self.assertEqual(w.read_rom("rocket",16382,14),self.original[16382:16396])
        b=w.find_segment("rocket",0,0,"map_grid")
        self.assertEqual(w.read_window(b,0,16),self.original[self.fixture.first_grid:self.fixture.first_grid+16])
        c=w.find_source("heartsoul","data/scripts/events.inc")
        self.assertEqual(bytes(w.stage(c)),self.content["heartsoul"]["data/scripts/events.inc"])
        self.assertGreater(w.resource_count,128)

    def test_script_entrypoints_are_not_executable_claims(self):
        report=self.report
        self.assertFalse(report["scripts_executable"])
        self.assertFalse(report["battle_data_decoded"])
        self.assertEqual(report["coverage"]["unaddressable_source_bytes"],0)
        self.assertFalse(report["coverage"]["native_emulator_provider_bound"])
        self.assertEqual(report["script_roots"]["summary"]["script_commands_decoded"],0)

    def test_injected_known_map_table_and_npc_entrypoint_discovery(self):
        data=bytearray(self.original)
        root=0x1a0000;script=0x1a1000;cond=0x1a2000
        header=self.fixture.header_offsets[0]
        struct.pack_into("<I",data,header+8,r34.GBA_BASE+root)
        data[root:root+11]=bytes([3])+struct.pack("<I",r34.GBA_BASE+script)+bytes([2])+struct.pack("<I",r34.GBA_BASE+cond)+b"\x00"
        struct.pack_into("<HHI",data,cond,0x4001,2,r34.GBA_BASE+script+40)
        struct.pack_into("<H",data,cond+8,0)
        events=self.fixture.first_event
        object_off=struct.unpack_from("<I",data,events+4)[0]-r34.GBA_BASE
        bg_off=struct.unpack_from("<I",data,events+16)[0]-r34.GBA_BASE
        struct.pack_into("<I",data,object_off+16,r34.GBA_BASE+script+80)
        data[bg_off+5]=7
        struct.pack_into("<I",data,bg_off+8,0xffff)
        s=r34.BinaryMapDiscovery(data)
        roots=r36.script_roots(s,s.discover())
        here=[(x["kind"],x["source_rom_offset"]) for x in roots["original_script_entrypoints"] if x["group"]==0 and x["map"]==0]
        self.assertIn(("map_script",script),here)
        self.assertIn(("conditional_script",script+40),here)
        self.assertIn(("object_event_script",script+80),here)
        self.assertNotIn(("background_event_script",0xffff),here)
        self.assertGreater(roots["summary"]["counts_by_origin"]["hidden_item_records"],0)

    def test_sha_corrupted_page_never_replaces_verified_staging(self):
        p=self.pool()
        rid="rom.page.000000"
        original=bytes(p.stage(rid))
        m=p._pages[rid][2]
        b=m.data_path.read_bytes()
        self.addCleanup(m.data_path.write_bytes,b)
        with m.data_path.open("r+b") as f:
            f.seek(m.resources[rid].offset+24);f.write(b"TAMPER")
        with self.assertRaisesRegex(ValueError,"SHA-256"):
            p.stage(rid)
        with self.assertRaisesRegex(ValueError,"SHA-256"):
            p.read_window(rid,0,16)
        self.assertEqual(bytes(p.staged_resource(rid)),original)
        with self.assertRaisesRegex(r36.PageError,"checksum|SHA"):
            r36.PagedBinaryPool(self.index)

    def test_forged_root_rom_offset_rejected(self):
        def edit(d):
            refs=d["script_roots"]["original_script_entrypoints"]
            if refs:refs[0]["source_rom_offset"]=d["rom_bytes"]
            else:
                refs.append({"group":0,"map":0,"kind":"map_script","slot":0,"source_rom_offset":d["rom_bytes"]})
                d["script_roots"]["summary"]["entrypoints"]+=1
        with self.assertRaisesRegex(r36.PageError,"script entrypoint"):
            r36.PagedBinaryPool(self.changed_index(edit))

    def test_wrong_digest_cannot_open_or_mount(self):
        def edit(d):d["source_identity"]["sha256"]="a"*64
        with self.assertRaises(ValueError):
            r36.PagedBinaryPool(self.changed_index(edit))
        w=self.world()
        total=w.resource_count
        with self.assertRaisesRegex(r35.MixedPoolError,"already mounted"):
            w.mount_binary_pages(self.index)
        self.assertEqual(w.resource_count,total)

    def test_renumber_or_remove_page_denied(self):
        def change(d):d["pages"][1]["number"]+=2
        with self.assertRaisesRegex(r36.PageError,"renumbered"):
            r36.PagedBinaryPool(self.changed_index(change))
        def remove(d):d["pages"].pop()
        with self.assertRaisesRegex(r36.PageError,"page or shard"):
            r36.PagedBinaryPool(self.changed_index(remove))

    def test_wrong_shard_or_checksum_denied_before_access(self):
        def edit(d):d["shards"][0]["sha256"]="0"*64
        with self.assertRaisesRegex(r36.PageError,"checksum"):
            r36.PagedBinaryPool(self.changed_index(edit))
        def wrong(d):d["pages"][0]["manifest"]=d["pages"][-1]["manifest"]
        with self.assertRaisesRegex(r36.PageError,"provenance"):
            r36.PagedBinaryPool(self.changed_index(wrong))

    def test_host_and_guest_memory_budgets_enforced(self):
        p=self.pool()
        with self.assertRaisesRegex(r36.PageError,"bounds"):
            p.read_rom(len(self.original)-1,2)
        with self.assertRaisesRegex(r36.PageError,"bounds"):
            p.read_rom(0,r36.PAGE_SIZE+1)
        w=mix36.R36MixedWorldPool(max_staged_bytes=16384)
        w.mount_binary(self.map_index);w.mount_binary_pages(self.index)
        first,_=w.find_rom_page("rocket",0)
        second,_=w.find_rom_page("rocket",16384)
        w.stage(first)
        with self.assertRaisesRegex(r35.MixedPoolError,"budget"):
            w.stage(second)
        w.unstage(first)
        self.assertEqual(bytes(w.stage(second)),self.original[16384:32768])

    def test_unknown_source_and_bogus_resource_refused(self):
        w=self.world()
        self.assertIsNone(w.find_rom_page("nonexistent",0))
        with self.assertRaisesRegex(r35.MixedPoolError,"Unregistered"):
            w.read_rom("nonexistent",0,1)
        from xgba_mixed_world_pool import SourceHandle
        with self.assertRaisesRegex(r36.PageError,"Unknown"):
            w.stage(SourceHandle("rocket","rom.page.999999"))

    def test_original_rom_mismatch_does_not_write_or_stage(self):
        p=self.pool()
        a=bytes(p.stage("rom.page.000000"))
        bad=self.root/"wrong.gba"
        bad.write_bytes(self.original[:-1]+b"\x01")
        self.addCleanup(bad.unlink,missing_ok=True)
        with self.assertRaisesRegex(r36.PageError,"identity mismatch"):
            p.verify_original_rom(bad)
        self.assertEqual(bytes(p.staged_resource("rom.page.000000")),a)
        self.assertEqual(self.rom.read_bytes(),self.original)

    def test_unmount_clears_all_sources_and_buffers(self):
        w=self.world()
        h,_=w.find_rom_page("rocket",0)
        w.stage(h)
        w.close()
        self.assertEqual(w.resource_count,0)
        self.assertEqual(w.staged_bytes,0)
        self.assertEqual(w.source_ids,())

if __name__=="__main__":unittest.main()
