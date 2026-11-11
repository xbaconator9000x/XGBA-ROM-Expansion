"""Memory budget regressions, including simultaneous asset requirements."""
import tempfile
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from xgba_memory_plan import (Resource, Phase, MemoryBudgetError,
                              plan_residency, align_up, patch_firered_heap_tail,
                              FIRERED_HEAP_BYTES, EWRAM_START, EWRAM_END)

class MemoryBudgetTests(unittest.TestCase):
    def test_two_exclusive_maps_share_one_reservation(self):
        plan=plan_residency([Resource("outdoor",8000),Resource("indoor",11000)],
            [Phase("outdoor",("outdoor",)),Phase("house",("indoor",))])
        self.assertEqual(plan.reserve_bytes,11000)
        self.assertEqual(plan.phase_slots["outdoor"]["outdoor"],0)
        self.assertEqual(plan.phase_slots["house"]["indoor"],0)
    def test_simultaneously_resident_resources_do_not_alias(self):
        plan=plan_residency([Resource("map",2000),Resource("audio",5000,alignment=256)],
            [Phase("field",("map","audio"))])
        self.assertEqual(plan.phase_slots["field"]["audio"],2048)
        self.assertEqual(plan.reserve_bytes,7048)
    def test_alignment_and_resource_order(self):
        plan=plan_residency([Resource("sprite",27,alignment=32),
                             Resource("tile",1,alignment=16)],
                            [Phase("render",("sprite","tile"))])
        self.assertEqual(plan.phase_slots["render"]["tile"],32)
        self.assertEqual(plan.reserve_bytes,36)
    def test_guest_single_request_limit(self):
        with self.assertRaises(MemoryBudgetError):
            Resource("too_big",16385)
    def test_simultaneous_overflow_fails_before_link(self):
        with self.assertRaisesRegex(MemoryBudgetError,"insufficient GBA"):
            plan_residency([Resource(f"r{i}",16000) for i in range(5)],
                [Phase("all",tuple(f"r{i}" for i in range(5)))],
                base_heap_floor=70000)
    def test_engine_transient_heap_is_charged(self):
        p=plan_residency([Resource("map",12000)],[Phase("field",("map",),12000)])
        self.assertEqual(p.minimum_heap_bytes,0x10000+12000)
    def test_save_copy_scratch_floor_is_charged(self):
        with self.assertRaisesRegex(MemoryBudgetError,"insufficient GBA"):
            plan_residency([Resource("pack",16000)],[Phase("save",("pack",))],
                save_copy_scratch_bytes=110000)
    def test_unregistered_resource_is_blocked(self):
        with self.assertRaisesRegex(MemoryBudgetError,"Unregistered"):
            plan_residency([Resource("map",100)],[Phase("field",("npc",))])
    def test_duplicate_or_invalid_phase_is_blocked(self):
        with self.assertRaises(MemoryBudgetError):
            plan_residency([Resource("map",100)],[Phase("field",("map","map"))])
        with self.assertRaises(MemoryBudgetError):
            plan_residency([Resource("map",100)],[Phase("field",("map",)),Phase("field",("map",))])
    def test_invalid_alignment_is_blocked(self):
        with self.assertRaises(MemoryBudgetError):
            Resource("map",120,alignment=3)
    def test_actual_linker_bounds_checked(self):
        p=plan_residency([Resource("map",1024)],[Phase("field",("map",))],
                         symbol_prefix="gTest")
        heap=0x02010000
        end=heap+FIRERED_HEAP_BYTES
        self.assertEqual(p.verify_linker({"gHeap":heap,"gTestHeapEnd":end,
                                          "gTestArenaStart":end-p.reserve_bytes})[0],end-1024)
        with self.assertRaises(MemoryBudgetError):
            p.verify_linker({"gHeap":heap,"gTestHeapEnd":end,
                             "gTestArenaStart":end-1023})
        with self.assertRaises(MemoryBudgetError):
            p.verify_linker({"gHeap":EWRAM_END-0x1000,"gTestHeapEnd":EWRAM_END+0x1000,
                             "gTestArenaStart":EWRAM_END})
    def test_shared_heap_patcher_updates_all_reset_paths(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for path,data in (
                ("src/malloc.c",'#include "global.h"\nvoid InitHeap(void *heapStart, u32 heapSize)\n{\nfoo;\n}\n'),
                ("src/load_save.c",'void MoveSaveBlocks_ResetHeap(void)\n{\nfoo;\n}\n'),
                ("ld_script_modern.ld",'        . = 0x1C000;\n')):
                file=root/path
                file.parent.mkdir(parents=True,exist_ok=True)
                file.write_text(data)
            def replace_once(s,a,b,name):
                if s.count(a)!=1: raise RuntimeError(name)
                return s.replace(a,b,1)
            old=patch_firered_heap_tail(root,reserve_bytes=1024,
                symbol_prefix="gTest",source_config_header=root/"config.h",
                replace_once=replace_once)
            self.assertIn("heapSize > HEAP_SIZE - 1024u",(root/"src/malloc.c").read_text())
            self.assertIn("_Static_assert",(root/"src/load_save.c").read_text())
            self.assertIn("gTestArenaStart",(root/"ld_script_modern.ld").read_text())
            for path,source in old.items():
                path.write_text(source)
            self.assertEqual((root/"ld_script_modern.ld").read_text(),old[root/"ld_script_modern.ld"])


class MixedSourceSceneTests(unittest.TestCase):
    def rom(self,offset=120,bytes=500):
        from xgba_memory_plan import StorageRef
        return StorageRef("rom",offset,bytes)
    def external(self,offset=74,bytes=200,pack="p1",id="a",physical=0):
        from xgba_memory_plan import StorageRef
        return StorageRef("external",offset,bytes,id,pack,physical)

    def test_gym_leader_mixes_local_and_huge_offsets(self):
        from xgba_memory_plan import SceneAsset,ScenePhase,plan_scene_assets
        mon_local=SceneAsset("local_mon",self.rom(), "obj_vram",1024)
        mon_near=SceneAsset("near_mon",self.external(74,256,"p1","mon2",4096),
                            "obj_vram",2048,staging_bytes=256)
        mon_far=SceneAsset("far_mon",self.external(67987873254192,1024,"p2","mon3",8192),
                           "obj_vram",3072,staging_bytes=512)
        move_far=SceneAsset("move",self.external(8888888888888,256,"p3","move",16384),
                            "obj_vram",4096,staging_bytes=1024)
        palette=SceneAsset("palette",self.rom(5000,256),"obj_palette",64)
        plan=plan_scene_assets([mon_local,mon_near,mon_far,move_far,palette],
            [ScenePhase("gym",("local_mon","near_mon","far_mon","move","palette"),
                        concurrent_fetches=2)],
            pool_reserved={"obj_vram":12*1024,"obj_palette":128})
        self.assertEqual(plan.physical_pool_usage["gym"]["obj_vram"],10240)
        self.assertEqual(plan.phase_staging_bytes["gym"],1536)
        self.assertEqual(plan.arena_bytes,1536)
        self.assertEqual(plan.resource_sources["far_mon"].virtual_offset,67987873254192)
        self.assertEqual(plan.resource_sources["far_mon"].host_file_range(),("p2",8192,1024))
        self.assertLess(plan.arena_bytes,4096)

    def test_indoor_shared_local_and_remote_tilesets(self):
        from xgba_memory_plan import SceneAsset,ScenePhase,plan_scene_assets
        assets=[
            SceneAsset("local_collision",self.rom(), "rom",500),
            SceneAsset("room_map",self.external(74,300,"map","room",1024),"ewram",750),
            SceneAsset("remote_bg",self.external(67987873254192,2048,"farpak","bg",4096),
                       "bg_vram",8192,staging_bytes=2048),
            SceneAsset("local_bg",self.rom(10000,500),"bg_vram",2048),
        ]
        plan=plan_scene_assets(assets,
            [ScenePhase("inside",tuple(a.name for a in assets))],
            pool_reserved={"bg_vram":16384})
        self.assertEqual(plan.physical_pool_usage["inside"]["bg_vram"],10240)
        self.assertEqual(plan.arena_bytes,2800)
        self.assertEqual(plan.phase_slots["inside"]["local_collision"][0],"rom")
        self.assertEqual(plan.phase_slots["inside"]["remote_bg"][0],"bg_vram")

    def test_64bit_source_must_not_be_interpreted_as_guest_pointer(self):
        from xgba_memory_plan import StorageRef,MAX_U64
        source=self.external(67987873254192,4096,"packA","tiles",32768)
        self.assertEqual(source.host_file_range(),("packA",32768,4096))
        with self.assertRaises(MemoryBudgetError):
            StorageRef("external",MAX_U64,2,"tiles","packA",0)
        with self.assertRaises(MemoryBudgetError):
            StorageRef("rom",32*1024*1024,1)

    def test_host_file_offsets_have_independent_signed_limit(self):
        from xgba_memory_plan import StorageRef,MAX_POSIX_FILE_OFFSET
        with self.assertRaises(MemoryBudgetError):
            StorageRef("external",74,16,"tile","p",MAX_POSIX_FILE_OFFSET-3)
        with self.assertRaises(MemoryBudgetError):
            StorageRef("external",74,16,"tile","p",-1)
        with self.assertRaises(MemoryBudgetError):
            self.external(74,16,"pack","asset",None).host_file_range()

    def test_external_assets_are_not_rom_pointers(self):
        from xgba_memory_plan import SceneAsset
        with self.assertRaisesRegex(MemoryBudgetError,"not CPU-addressable ROM"):
            SceneAsset("external_rom",self.external(),"rom",128)

    def test_gpu_scene_requires_audited_existing_engine_reservation(self):
        from xgba_memory_plan import SceneAsset,ScenePhase,plan_scene_assets
        a=SceneAsset("local_obj",self.rom(),"obj_vram",1024)
        with self.assertRaisesRegex(MemoryBudgetError,"requires audited"):
            plan_scene_assets([a],[ScenePhase("battle",("local_obj",))])

    def test_graphics_pool_limits_remain_physical(self):
        from xgba_memory_plan import SceneAsset,ScenePhase,plan_scene_assets
        a=SceneAsset("huge_sprite",self.external(70,1000),
                    "obj_vram",32769,staging_bytes=500)
        with self.assertRaisesRegex(MemoryBudgetError,"real obj_vram"):
            plan_scene_assets([a],[ScenePhase("battle",("huge_sprite",))],
                              pool_reserved={"obj_vram":0})

    def test_palette_budget_does_not_expand_with_asset_offset(self):
        from xgba_memory_plan import SceneAsset,ScenePhase,plan_scene_assets
        a=SceneAsset("palette",self.external(67987873254192,500),
                     "obj_palette",400,staging_bytes=128)
        with self.assertRaisesRegex(MemoryBudgetError,"real obj_palette"):
            plan_scene_assets([a],[ScenePhase("battle",("palette",))],
                              pool_reserved={"obj_palette":200})

    def test_simultaneous_large_staging_violates_heap(self):
        from xgba_memory_plan import SceneAsset,ScenePhase,plan_scene_assets
        assets=[SceneAsset(f"remote{i}",self.external(74+i*100,100,f"p{i}",f"x{i}"),
                           "bg_vram",128,staging_bytes=16384) for i in range(3)]
        with self.assertRaisesRegex(MemoryBudgetError,"real EWRAM"):
            plan_scene_assets(assets,[ScenePhase("all",tuple(a.name for a in assets),
                                                  concurrent_fetches=3)],
                              engine_heap_floor=90000,pool_reserved={"bg_vram":0})

    def test_reset_requires_gpu_and_ewram_reload_not_rom(self):
        from xgba_memory_plan import SceneAsset,ScenePhase,plan_scene_assets
        assets=[
            SceneAsset("code",self.rom(),"rom",500),
            SceneAsset("map",self.external(),"ewram",1000),
            SceneAsset("sprite",self.external(100,500,"pack","sprite"),
                       "obj_vram",2048,staging_bytes=256),
        ]
        p=plan_scene_assets(assets,[ScenePhase("before",("code","map","sprite")),
                                    ScenePhase("after",("code","map","sprite"))],
                            pool_reserved={"obj_vram":10000})
        same=p.transition("before","after")
        self.assertEqual(same["retain"],("code","map","sprite"))
        reset=p.transition("before","after",hardware_reset=True)
        self.assertEqual(reset["retain"],("code",))
        self.assertEqual(reset["rebuild_after_reset"],("map","sprite"))

    def test_multiple_phases_reuse_staging_memory(self):
        from xgba_memory_plan import SceneAsset,ScenePhase,plan_scene_assets
        a=SceneAsset("outside",self.external(),"ewram",2500)
        b=SceneAsset("inside",self.external(67987873254192,300,"new","inside"),
                     "ewram",3900)
        plan=plan_scene_assets([a,b],
                    [ScenePhase("outside",("outside",)),ScenePhase("inside",("inside",))])
        self.assertEqual(plan.arena_bytes,3900)
        t=plan.transition("outside","inside")
        self.assertEqual(t["evict"],("outside",))
        self.assertEqual(t["load"],("inside",))

    def test_transition_detects_changed_slot(self):
        from xgba_memory_plan import SceneAsset,ScenePhase,plan_scene_assets
        a=SceneAsset("new",self.rom(),"ewram",400)
        b=SceneAsset("shared",self.external(),"ewram",600)
        p=plan_scene_assets([a,b],[ScenePhase("a",("shared",)),
                                   ScenePhase("b",("new","shared"))])
        self.assertEqual(p.transition("a","b")["relocate"],("shared",))

    def test_external_gpu_asset_must_declare_staging(self):
        from xgba_memory_plan import SceneAsset
        with self.assertRaisesRegex(MemoryBudgetError,"explicit EWRAM"):
            SceneAsset("tile",self.external(),"bg_vram",512)

    def test_local_rom_gpu_asset_counts_against_vram(self):
        from xgba_memory_plan import SceneAsset,ScenePhase,plan_scene_assets
        a=SceneAsset("a",self.rom(),"obj_vram",16384)
        b=SceneAsset("b",self.external(),"obj_vram",16384,staging_bytes=200)
        with self.assertRaisesRegex(MemoryBudgetError,"real obj_vram"):
            plan_scene_assets([a,b],[ScenePhase("battle",("a","b"))],
                              pool_reserved={"obj_vram":1024})


if __name__=="__main__":unittest.main()
