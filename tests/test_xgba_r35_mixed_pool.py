"""R35 public synthetic original binary + source-built cross-world acceptance.

This test does not contain or exercise copyrighted game binaries.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS=Path(__file__).resolve().parents[1]/'tools'
sys.path.insert(0,str(TOOLS))
import xgba_mixed_world_pool as r35
import xgba_r34_binary_maps as r34
import xgba_whole_corpus as r32
from test_xgba_r34_binary_maps import FakeEmeraldBinary


class MixedWorldAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.original=FakeEmeraldBinary()
        self.image=self.original.image()
        self.rom=self.root/'synthetic.gba'
        self.rom.write_bytes(self.image)
        self.binary=self.root/'binary'
        engine=r34.BinaryMapDiscovery(self.rom)
        engine.export_maps(engine.discover(),self.binary,'rocket',
                           max_shard_entries=10,max_shard_bytes=4096)
        self.binary_index=self.binary/'xgba-binary-maps.json'
        self.source_data={}
        roots=[]
        for world in ('emerald','heartsoul'):
            root=self.root/world
            roots.append(root)
            files={
                'data/maps/map_groups.json':json.dumps(
                    {'group_order':['g'], 'g':['Home','Path']}).encode(),
                'data/maps/Home/map.json':json.dumps(
                    {'name':'Home','id':'MAP_HOME','connections':[]}).encode(),
                'data/maps/Path/map.json':json.dumps(
                    {'name':'Path','id':'MAP_PATH',
                     'connections':[{'map':'MAP_HOME','direction':'up'}]}).encode(),
                'graphics/map.bin':bytes([len(world)])*3500,
                'src/data/battle_moves.h':world.encode(),
                'data/scripts/story.inc':b'script fixture',
            }
            self.source_data[world]=files
            for name,content in files.items():
                dest=root/name
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(content)
        sources=[r32.inspect_source(w,root) for w,root in
                 zip(('emerald','heartsoul'),roots)]
        self.source=self.root/'source'
        r32.export_corpus(sources,roots,self.source,pack=True,
                          max_shard_entries=3,max_shard_bytes=4000)
        self.source_index=self.source/'xgba-whole-corpus-index.json'

    def altered(self,mutation):
        doc=json.loads(self.binary_index.read_text())
        mutation(doc)
        output=self.binary/'altered.json'
        output.write_text(json.dumps(doc))
        return output

    def test_all_exported_original_binary_segments_have_exact_rom_bytes(self):
        p=r35.BinaryMapPool(self.binary_index)
        d=json.loads(self.binary_index.read_text())
        self.assertEqual(p.resource_count,len(d['segments']))
        self.assertEqual(p.map_count,sum(self.original.groups))
        self.assertEqual(p.shard_count,len(d['shards']))
        self.assertEqual(p.verify_original_rom(self.rom),p.resource_count)
        for e in d['segments']:
            self.assertEqual(bytes(p.stage(e['id'])),
                self.image[e['source_rom_offset']:e['source_rom_offset']+e['length']])
            p.unstage(e['id'])
        self.assertEqual(p.staged_bytes,0)

    def test_three_source_worlds_mounted_together_without_map_id_rewrites(self):
        p=r35.MixedWorldPool()
        p.mount_corpus(self.source_index)
        p.mount_binary(self.binary_index)
        self.assertEqual(set(p.source_ids),{'emerald','heartsoul','rocket'})
        self.assertEqual(p.find_original_map('emerald',0,0)['name'],'Home')
        self.assertEqual(p.find_original_map('heartsoul',0,0)['name'],'Home')
        self.assertEqual(p.find_original_map('rocket',0,0)['width'],48)
        self.assertIsNone(p.find_original_map('rocket',254,254))
        r=p.find_segment('rocket',0,0,'map_grid')
        e=p.find_source('emerald','graphics/map.bin')
        h=p.find_source('heartsoul','graphics/map.bin')
        self.assertEqual(len({r,e,h}),3)
        self.assertNotEqual(bytes(p.stage(e)),bytes(p.stage(h)))
        self.assertEqual(p.read_window(r,4,8),
                         self.image[self.original.first_grid+4:self.original.first_grid+12])

    def test_every_source_tree_file_accessible_via_same_registry(self):
        p=r35.MixedWorldPool()
        p.mount_corpus(self.source_index)
        p.mount_binary(self.binary_index)
        for world,files in self.source_data.items():
            for path,expected in files.items():
                handle=p.find_source(world,path)
                self.assertIsNotNone(handle)
                self.assertEqual(bytes(p.stage(handle)),expected)
                p.unstage(handle)
        self.assertEqual(p.staged_bytes,0)

    def test_digest_failure_never_replaces_previously_verified_buffer(self):
        p=r35.BinaryMapPool(self.binary_index)
        rid=p.find_segment(0,0,'map_grid')
        good=bytes(p.stage(rid))
        m=p._segments[rid][-1]
        with m.data_path.open('r+b') as f:
            f.seek(m.resources[rid].offset+80)
            f.write(b'X')
        with self.assertRaisesRegex(ValueError,'SHA-256'):
            p.read_window(rid,0,1)
        with self.assertRaisesRegex(ValueError,'SHA-256'):
            p.stage(rid)
        self.assertEqual(bytes(p.staged_resource(rid)),good)

    def test_corrupted_entire_shard_refused_at_mount(self):
        d=json.loads(self.binary_index.read_text())
        path=self.binary/d['shards'][0]['data_file']
        with path.open('r+b') as f:f.write(b'bad!')
        with self.assertRaisesRegex(r35.MixedPoolError,'SHA-256'):
            r35.BinaryMapPool(self.binary_index)

    def test_original_binary_map_identity_forgery_refused(self):
        def change(doc):
            doc['original_map_headers'][0]['map']=200
        with self.assertRaisesRegex(r35.MixedPoolError,'identity'):
            r35.BinaryMapPool(self.altered(change))

    def test_exported_layout_pointer_forgery_refused(self):
        def change(doc):
            next(e for e in doc['segments'] if
                e['id']=='binary.0.0.layout')['source_rom_offset']+=4
        with self.assertRaisesRegex(r35.MixedPoolError,'pointer mismatch'):
            r35.BinaryMapPool(self.altered(change))

    def test_cross_world_source_identity_drift_refused(self):
        def change(doc):
            doc['source_identity']['sha256']='f'*64
        with self.assertRaisesRegex(r35.MixedPoolError,'source identity'):
            r35.BinaryMapPool(self.altered(change))

    def test_unindexed_binary_segment_refused(self):
        def change(doc):
            deleted=doc['segments'].pop()
            doc['summary']['exported_fixed_segments']-=1
            doc['summary']['exported_raw_bytes']-=deleted['length']
        with self.assertRaisesRegex(r35.MixedPoolError,'Orphaned'):
            r35.BinaryMapPool(self.altered(change))

    def test_bounded_guest_window_and_global_multisource_staging(self):
        p=r35.MixedWorldPool(max_staged_bytes=4000)
        p.mount_binary(self.binary_index)
        p.mount_corpus(self.source_index)
        first=p.find_segment('rocket',0,0,'map_grid')
        second=p.find_source('emerald','graphics/map.bin')
        with self.assertRaisesRegex(r35.MixedPoolError,'transfer'):
            p.read_window(first,0,16385)
        p.stage(first)
        previous=p.staged_bytes
        with self.assertRaisesRegex(r35.MixedPoolError,'multi-world RAM'):
            p.stage(second)
        self.assertEqual(p.staged_bytes,previous)
        p.unstage(first)
        self.assertEqual(bytes(p.stage(second)),self.source_data['emerald']['graphics/map.bin'])

    def test_duplicate_mounted_source_refused_without_state_loss(self):
        p=r35.MixedWorldPool()
        p.mount_corpus(self.source_index)
        p.mount_binary(self.binary_index)
        current=p.source_ids
        with self.assertRaisesRegex(r35.MixedPoolError,'already mounted'):
            p.mount_corpus(self.source_index)
        with self.assertRaisesRegex(r35.MixedPoolError,'already mounted'):
            p.mount_binary(self.binary_index)
        self.assertEqual(p.source_ids,current)

    def test_bad_original_rom_hash_and_foreign_handle_refused(self):
        p=r35.BinaryMapPool(self.binary_index)
        bad=self.root/'other.gba'
        bad.write_bytes(self.image[:-1]+b'X')
        with self.assertRaisesRegex(r35.MixedPoolError,'digest'):
            p.verify_original_rom(bad)
        world=r35.MixedWorldPool()
        world.mount_binary(self.binary_index)
        with self.assertRaisesRegex(r35.MixedPoolError,'Unknown source'):
            world.stage(r35.SourceHandle('unknown','binary.0.0.header'))
        with self.assertRaisesRegex(r35.MixedPoolError,'source-aware'):
            world.stage('binary.0.0.header')
        world.close()
        self.assertEqual(world.staged_bytes,0)
        self.assertTrue(self.rom.is_file())


if __name__=='__main__':
    unittest.main()
