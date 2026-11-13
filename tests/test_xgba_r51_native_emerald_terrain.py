"""R51 real source-built Emerald field integration with source-verified grid reader.

Boot/Flash/LCD must remain real native original Emerald; this does NOT claim
the private Rocket/HnS maps were already loaded or that Fly completed.
"""
from __future__ import annotations
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tests"))
from test_xgba_r50_native_emerald_events import NativeEmeraldR50OriginalEngineEventHooks as R50
import test_xgba_r17_emerald_external_map as r17

class NativeEmeraldR51OriginalTerrain(R50):
    R51_ORIGINAL_GRID_TEST=True

    def test_r51_terrain_runtime_compiles_in_real_original_emerald(self):
        self.assertTrue(self.elf.is_file())
        syms=r17.r14.symbols(self.elf)
        # Source-verified terrain resident is an actual GBA EWRAM symbol,
        # not the host-side authored map viewer used in R45.
        self.assertIn("gXgbaR51TerrainProof",syms)
        address=syms["gXgbaR51TerrainProof"][0]
        self.assertGreaterEqual(address,0x02000000)
        self.assertLess(address,0x02040000)
        self.assertIn("gXgbaR50BridgeProof",syms)
        self.assertIn("PASS_R18_EMERALD_ORIGINAL_FLASH_WRITE",self.log)
        self.assertNotIn("PASS_R51_REAL_THREE_WORLD_FLY",self.log)

if __name__=="__main__":
    unittest.main()
