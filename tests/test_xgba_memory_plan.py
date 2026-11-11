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

if __name__=="__main__":unittest.main()
