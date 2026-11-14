"""R52 actual pinned Emerald ARM field camera, collision and source ABI test.

The original Emerald game must boot and Flash-save with source-aware
512/640 metatile dispatch compiled into its real field engine.
No foreign original graphics/Fly are claimed without private source packs.
"""
from __future__ import annotations
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tests"))
from test_xgba_r51_native_emerald_terrain import NativeEmeraldR51OriginalTerrain as R51
import test_xgba_r17_emerald_external_map as r17

class NativeEmeraldR52VersionedWorld(R51):
    R52_SOURCE_LAYOUT_TEST=True

    def test_actual_original_emeraldoverworld_has_versioned_map_camera_and_collision(self):
        sym=r17.r14.symbols(self.elf)
        self.assertIn("gXgbaR52LayoutProof",sym)
        self.assertIn("XgbaR52PrimaryMetatileCount",sym)
        proof=sym["gXgbaR52LayoutProof"][0]
        self.assertTrue(0x02000000<=proof<0x02040000)
        self.assertIn("PASS_R18_EMERALD_ORIGINAL_FLASH_WRITE",self.log)
        self.assertNotIn("PASS_R52_THREE_WORLD_FLY_COMPLETE",self.log)

if __name__=="__main__":
    unittest.main()
