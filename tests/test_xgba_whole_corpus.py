"""R32 source-corps and synthetic three-world stress; NOT genuine triple-ROM play."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import xgba_whole_corpus as c
import xgba_resource_sidecar as sidecar

class WholeCorpus(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name)
        self.worlds={}
        self.inputs={}
        for i,name in enumerate(("emerald","rocket","heartsoul")):
            root=self.root/name
            self.worlds[name]=root
            files={
                "data/maps/map_groups.json":json.dumps({"group_order":["gTowns"],"gTowns":["Town","Route"]}).encode(),
                "data/maps/Town/map.json":json.dumps({"name":"Town","id":"MAP_TOWN","connections":[{"map":"MAP_ROUTE","direction":"up"}]}).encode(),
                "data/maps/Route/map.json":json.dumps({"name":"Route","id":"MAP_ROUTE","connections":[{"map":"MAP_TOWN","direction":"down"}]}).encode(),
                "data/layouts/Town/map.bin":bytes([i+1])*800,
                "data/scripts/events.inc":b"flag 12; warp 0,0",
                "src/data/pokemon/species_info.h":b"SPECIES_FOO 12",
                "src/data/battle_moves.h":b"MOVE_FOO 12",
                "src/data/items.h":b"ITEM_FOO 12",
                "include/constants/abilities.h":b"ABILITY_FOO 12",
                "src/custom_engine.c":b"void custom(void){}",
                "graphics/front.png":b"FAKE_PNG",
                "sound/track.mid":b"FAKE_MIDI",
                "custom/unknown.zzz":b"UNKNOWN_PRESERVED",
                "empty.inc":b"",
            }
            for j in range(101):files[f"graphics/other/{j:04d}.bin"]=(name+str(j)).encode()
            for path,blob in files.items():
                dest=root/path
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(blob)
            self.inputs[name]=files

    def scan(self):
        return [c.inspect_source(name,root) for name,root in self.worlds.items()]

    def test_all_files_including_unknown_and_empty_preserved(self):
        for s in self.scan():
            self.assertEqual({x["path"] for x in s["resources"]},set(self.inputs[s["source_id"]]))
            self.assertGreater(s["category_counts"]["unclassified_preserved"],0)
            self.assertEqual(s["runtime_compatible_resources"],0)

    def test_original_map_ids_are_unchanged_despite_collisions(self):
        ss=self.scan()
        summary=c.summarize(ss)
        self.assertEqual(summary["original_map_identity_collision_count"],4)
        self.assertEqual(summary["original_map_count"],6)
        self.assertEqual(summary["unresolved_original_map_connections"],0)
        self.assertEqual(summary["overlapping_source_paths"],2*len(self.inputs["emerald"]))
        for s in ss:self.assertEqual([(m["group"],m["map"]) for m in s["original_maps"]],[(0,0),(0,1)])

    def test_namespaced_resources_never_collide(self):
        ids=[e["resource_id"] for s in self.scan() for e in s["resources"]]
        self.assertEqual(len(ids),len(set(ids)))

    def test_sharded_sidecars_restore_every_byte(self):
        ss=self.scan()
        out=self.root/"sidecars"
        result=c.export_corpus(ss,list(self.worlds.values()),out,pack=True,max_shard_entries=10,max_shard_bytes=1024)
        self.assertGreater(len(result["shards"]),10)
        for s in ss:
            for e in s["resources"]:
                expected=self.inputs[s["source_id"]][e["path"]]
                if not expected:
                    self.assertEqual(e["storage_status"],"verified_empty_source")
                    continue
                m=sidecar.load_manifest(out/e["shard"])
                blob=b"".join(sidecar.iter_resource_chunks(m,e["resource_id"],chunk_size=5))
                self.assertEqual(expected,blob)
        self.assertFalse(result["guarantees"]["runtime_compatibility_implied"])

    def test_inventory_only_does_not_export_binaries(self):
        out=self.root/"inventory"
        result=c.export_corpus(self.scan(),list(self.worlds.values()),out)
        self.assertEqual(result["storage_mode"],"inventory_only")
        self.assertEqual([f.name for f in out.iterdir()],["xgba-whole-corpus-index.json"])

    def test_input_mutation_changes_snapshot_not_logical_id(self):
        root=self.worlds["emerald"]
        a=c.inspect_source("emerald",root)
        (root/"data/scripts/events.inc").write_bytes(b"NEW CONTENT")
        b=c.inspect_source("emerald",root)
        self.assertNotEqual(a["source_snapshot_sha256"],b["source_snapshot_sha256"])
        self.assertEqual([x["resource_id"] for x in a["resources"]],
                         [x["resource_id"] for x in b["resources"]])

    def test_tampered_input_causes_atomic_failure(self):
        root=self.worlds["emerald"]
        snapshot=c.inspect_source("emerald",root)
        (root/"data/scripts/events.inc").write_bytes(b"CORRUPTED SOURCE")
        out=self.root/"out"
        with self.assertRaises(c.CorpusError):
            c.export_corpus([snapshot],[root],out,pack=True,max_shard_entries=5)
        self.assertEqual(list(out.iterdir()),[])

    def test_symlink_exfiltration_refused(self):
        target=self.root/"secret"
        target.write_text("not an input")
        os.symlink(target,self.worlds["emerald"]/"escaped.txt")
        with self.assertRaises(c.CorpusError):
            c.inspect_source("emerald",self.worlds["emerald"])

    def test_bounds_fail_closed_not_drop_files(self):
        with self.assertRaises(c.CorpusError):
            c.inspect_source("emerald",self.worlds["emerald"],max_files=2)
        with self.assertRaises(c.CorpusError):
            c.inspect_source("emerald",self.worlds["emerald"],max_total_bytes=10)
        with self.assertRaises(c.CorpusError):
            c.inspect_source("../bad",self.worlds["emerald"])

    def test_git_tracked_source_not_untracked_secrets(self):
        root=self.worlds["emerald"]
        subprocess.run(["git","-C",str(root),"init","-q"],check=True)
        subprocess.run(["git","-C",str(root),"add","data","graphics"],check=True)
        (root/"local.secret").write_text("PRIVATE")
        report=c.inspect_source("emerald",root)
        self.assertTrue(report["git_tracked_only"])
        self.assertNotIn("local.secret",{e["path"] for e in report["resources"]})

    def test_bad_map_references_fail_closed(self):
        root=self.worlds["emerald"]
        p=root/"data/maps/Town/map.json"
        doc=json.loads(p.read_text())
        doc["connections"]=[{"nonsense":1}]
        p.write_text(json.dumps(doc))
        with self.assertRaises(c.CorpusError):
            c.inspect_source("emerald",root)

    def test_missing_metadata_is_reported_not_invented(self):
        root=self.worlds["emerald"]
        (root/"data/maps/Route/map.json").unlink()
        report=c.inspect_source("emerald",root)
        self.assertEqual(report["original_maps"][1]["parse_status"],"metadata_unavailable")
        self.assertEqual(len(report["unresolved_connections"]),1)

    def test_stress_12000_individual_assets_across_three_source_worlds(self):
        for name,root in self.worlds.items():
            folder=root/"assets/more"
            folder.mkdir(parents=True)
            for j in range(4000):
                (folder/f"{j:05d}.bin").write_bytes(hashlib.sha256(f"{name}:{j}".encode()).digest())
        ss=self.scan()
        result=c.export_corpus(ss,list(self.worlds.values()),self.root/"stress")
        n=result["summary"]["catalogued_files"]
        self.assertGreaterEqual(n,12000)
        self.assertEqual(len({x["resource_id"] for s in ss for x in s["resources"]}),n)
        self.assertEqual(result["summary"]["runtime_compatible_resources"],0)

if __name__=="__main__":unittest.main()
