"""R33: actual R32 sharded source data, three-world lookups and no ID rewrites.

All fixtures are synthetic; they are not three playable ROM hacks.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import xgba_corpus_pool as pool
import xgba_whole_corpus as importer


class MultiSourceShardedPool(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="xgba-r33-")
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.worlds={}
        self.content={}
        for i,world in enumerate(("emerald","rocket","heartsoul")):
            p=self.root/world
            self.worlds[world]=p
            data={
                "data/maps/map_groups.json":json.dumps({
                    "group_order":["gTowns"],"gTowns":["Town","Route"]}).encode(),
                "data/maps/Town/map.json":json.dumps({
                    "id":"MAP_TOWN","name":"Town",
                    "connections":[{"map":"MAP_ROUTE","direction":"up"}]}).encode(),
                "data/maps/Route/map.json":json.dumps({
                    "id":"MAP_ROUTE","name":"Route","connections":[]}).encode(),
                "data/layouts/Town/map.bin":bytes([i+1])*800,
                "data/scripts/entry.inc":b"ORIGINAL_SCRIPT_"+bytes([i+49]),
                "src/data/pokemon/species_info.h":b"SPECIES_"+bytes([i+49]),
                "src/data/battle_moves.h":b"MOVE_"+bytes([i+49]),
                "graphics/front.bin":bytes([i+1])*2017,
                "sound/song.bin":bytes(range(256))*15,
                "extra/unknown.zzz":b"UNKNOWN_PRESERVED",
                "data/scripts/empty.inc":b"",
            }
            self.content[world]=data
            for name,blob in data.items():
                q=p/name
                q.parent.mkdir(parents=True,exist_ok=True)
                q.write_bytes(blob)
        snapshots=[importer.inspect_source(name,p) for name,p in self.worlds.items()]
        self.out=self.root/"external"
        importer.export_corpus(snapshots,list(self.worlds.values()),self.out,
                               pack=True,max_shard_entries=3,max_shard_bytes=4100)
        self.index=self.out/"xgba-whole-corpus-index.json"
        self.p=pool.CorpusPool(self.index,max_resource_bytes=4096,
                               max_staged_bytes=5000,max_window_bytes=16,chunk_size=7)

    def rid(self,world,name):
        result=self.p.find(world,name)
        self.assertIsNotNone(result)
        return result

    def altered(self,mutate):
        data=json.loads(self.index.read_text())
        mutate(data)
        path=self.out/"modified-index.json"
        path.write_text(json.dumps(data))
        return path

    def test_every_input_byte_retrievable_across_multiple_sidecars(self):
        self.assertEqual(self.p.source_ids,("emerald","rocket","heartsoul"))
        self.assertGreater(self.p.shard_count,3)
        self.assertEqual(self.p.resource_count,sum(len(v) for v in self.content.values()))
        for world,items in self.content.items():
            for path,payload in items.items():
                rid=self.rid(world,path)
                self.assertEqual(self.p.source_of(rid),(world,path,len(payload)))
                self.assertEqual(bytes(self.p.stage(rid)),payload)
                self.p.unstage(rid)
        self.assertEqual(self.p.staged_bytes,0)

    def test_same_original_map_ids_belong_to_separate_source_worlds(self):
        for name in self.worlds:
            self.assertEqual(self.p.find_original_map(name,0,0)["name"],"Town")
            self.assertEqual(self.p.find_original_map(name,0,1)["name"],"Route")
            self.assertIsNone(self.p.find_original_map(name,1,0))
        a=bytes(self.p.stage(self.rid("emerald","graphics/front.bin")))
        b=bytes(self.p.stage(self.rid("rocket","graphics/front.bin")))
        self.assertNotEqual(a,b)

    def test_window_rehashes_entire_original_resource_before_delivery(self):
        rid=self.rid("rocket","sound/song.bin")
        payload=self.content["rocket"]["sound/song.bin"]
        self.assertEqual(self.p.read_window(rid,128,16),payload[128:144])
        self.assertEqual(self.p.read_window(rid,0,1),payload[:1])
        self.assertEqual(self.p.read_window(rid,len(payload),0),b"")
        self.assertEqual(self.p.staged_bytes,0)

    def test_window_bounds_reject_bad_requests(self):
        rid=self.rid("rocket","sound/song.bin")
        with self.assertRaisesRegex(pool.PoolError,"Window outside"):
            self.p.read_window(rid,3839,2)
        with self.assertRaisesRegex(pool.PoolError,"configured host"):
            self.p.read_window(rid,0,17)

    def test_corrupt_pack_denied_without_overwriting_prior_stage(self):
        rid=self.rid("emerald","graphics/front.bin")
        valid=bytes(self.p.stage(rid))
        _,_,rec,manifest=self.p._resources[rid]
        with manifest.data_path.open("r+b") as f:
            f.seek(rec.offset)
            f.write(b"X")
        with self.assertRaisesRegex(ValueError,"SHA-256 mismatch"):
            self.p.stage(rid)
        with self.assertRaisesRegex(ValueError,"SHA-256 mismatch"):
            self.p.read_window(rid,0,1)
        self.assertEqual(bytes(self.p.staged_resource(rid)),valid)

    def test_bad_reload_is_atomic(self):
        rid=self.rid("rocket","src/data/battle_moves.h")
        previous=bytes(self.p.stage(rid))
        def change(d):
            d["source_reports"][0]["source_snapshot_sha256"]="f"*64
        with self.assertRaisesRegex(pool.PoolError,"different source snapshot"):
            self.p.open(self.altered(change))
        self.assertEqual(bytes(self.p.staged_resource(rid)),previous)
        self.assertEqual(self.p.resource_count,sum(len(v) for v in self.content.values()))

    def test_unindexed_sidecar_bytes_refused(self):
        def change(d):
            entry=next(e for e in d["source_reports"][0]["resources"] if e["bytes"]>0)
            d["source_reports"][0]["resources"].remove(entry)
            d["source_reports"][0]["file_count"]-=1
            d["source_reports"][0]["byte_count"]-=entry["bytes"]
            d["summary"]["catalogued_files"]-=1
            d["summary"]["catalogued_bytes"]-=entry["bytes"]
        with self.assertRaisesRegex(pool.PoolError,"Unindexed"):
            pool.CorpusPool(self.altered(change))

    def test_unknown_or_swapped_source_identity_rejected(self):
        def change(d):
            a=d["source_reports"]
            a[0]["resources"][0]["resource_id"]=a[1]["resources"][0]["resource_id"]
        with self.assertRaisesRegex(pool.PoolError,"non-original"):
            pool.CorpusPool(self.altered(change))
        self.assertIsNone(self.p.find("rocket","not/in/corpus.bin"))

    def test_source_original_map_ids_checked_against_verified_groups(self):
        def change(d):
            d["source_reports"][0]["original_maps"][0]["map"]=500
        with self.assertRaisesRegex(pool.PoolError,"original map IDs differ"):
            pool.CorpusPool(self.altered(change))

    def test_inventory_only_rejected_as_unavailable_storage(self):
        with self.assertRaisesRegex(pool.PoolError,"inventory-only"):
            pool.CorpusPool(self.altered(lambda d:d.update(storage_mode="inventory_only")))

    def test_empty_source_file_roundtrip_and_staging_limits(self):
        rid=self.rid("heartsoul","data/scripts/empty.inc")
        self.assertEqual(bytes(self.p.stage(rid)),b"")
        self.assertEqual(self.p.read_window(rid,0,0),b"")
        a=self.rid("emerald","sound/song.bin")
        b=self.rid("rocket","sound/song.bin")
        self.p.stage(a)
        with self.assertRaisesRegex(pool.PoolError,"host memory budget"):
            self.p.stage(b)
        self.p.unstage(a)
        self.assertEqual(bytes(self.p.stage(b)),self.content["rocket"]["sound/song.bin"])

    def test_missing_shard_or_path_escape_is_refused(self):
        with self.assertRaisesRegex(pool.PoolError,"Unsafe shard"):
            pool.CorpusPool(self.altered(lambda d:d["shards"][0].update(manifest="../bad.json")))
        self.out.joinpath(next(self.out.glob("emerald-*.json")).name).unlink()
        with self.assertRaises((ValueError,FileNotFoundError)):
            pool.CorpusPool(self.index)

    def test_release_clears_host_buffers_and_identity_catalogue(self):
        rid=self.rid("rocket","graphics/front.bin")
        self.p.stage(rid)
        self.p.close()
        self.assertEqual(self.p.resource_count,0)
        self.assertEqual(self.p.staged_bytes,0)
        self.assertEqual(self.p.source_ids,())

if __name__=="__main__":
    unittest.main()
