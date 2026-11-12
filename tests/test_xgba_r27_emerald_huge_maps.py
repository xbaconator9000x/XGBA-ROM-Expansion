"""R27 actual source-built Pokémon Emerald 64×64 / 128×32 stress geometry.

Synthetic author-labelled test grids are tiled from the pinned ORIGINAL
Littleroot metatiles, not asserted to be original authored map dimensions.
Actual original Emerald field renderer, EWRAM backup map, camera, BG VRAM and
D-pad execute under pinned patched native mGBA. The unmodified 20×20
ROM layout and original complete Petalburg tileset are source-stripped; all
graphics/data are loaded from SHA-backed resource >32 MiB.
"""
from __future__ import annotations
import unittest
import test_xgba_r17_emerald_external_map as r17

class RealEmeraldHuge64x64(r17.ActualEmeraldLittlerootExternalMap):
    R27_MAP_SHAPE=(64,64)
    def test_full_64_by_64_source_backed_original_game_renderer(self):
        self.assertIn("PASS_R27_REAL_EMERALD_HUGE_MAP width=64 height=64",self.log)
        self.assertIn("full_grid_verified=1 complete_secondary_tileset=1",self.log)
        self.assertEqual(self.geometry_plan.backup_cells,79*78)
        self.assertEqual(self.report["original_emerald_native_all_map_cells_checked"],4096)

class RealEmeraldHuge128x32(r17.ActualEmeraldLittlerootExternalMap):
    R27_MAP_SHAPE=(128,32)
    def test_full_128_by_32_source_backed_original_game_renderer(self):
        self.assertIn("PASS_R27_REAL_EMERALD_HUGE_MAP width=128 height=32",self.log)
        self.assertIn("full_grid_verified=1 complete_secondary_tileset=1",self.log)
        self.assertEqual(self.geometry_plan.backup_cells,143*46)
        self.assertEqual(self.report["original_emerald_native_all_map_cells_checked"],4096)

if __name__=="__main__":
    unittest.main()
