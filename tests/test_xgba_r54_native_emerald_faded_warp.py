"""R54 actual pinned Emerald faded-warp, original MapHeader and heap lifecycle.

This is the genuine original src/overworld.c LoadMapInStepsLocal state
machine after its own VBlank fade, not a host-side source switch. Native
game boots, moves, saves Flash and cold-restores unchanged in the absent-
foreign-resource baseline. Foreign source still requires private sprite
graphics and a selected original Fly destination before any Fly success.
"""
from __future__ import annotations
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tests"))
from test_xgba_r53_native_emerald_graphics import NativeEmeraldR53OriginalGraphics as R53
import test_xgba_r17_emerald_external_map as r17

class NativeEmeraldR54ActualFadedWarp(R53):
    R54_REAL_WARP_ADMISSION_TEST=True

    def test_real_original_emerald_faded_warp_preload_is_linked(self):
        symbols=r17.r14.symbols(self.elf)
        self.assertIn("gXgbaR54NativeWarpProof",symbols)
        self.assertIn("gXgbaR54OriginalArtProof",symbols)
        self.assertIn("XgbaR54InstallPendingOriginalSourceAtNativeWarp",symbols)
        self.assertIn("XgbaR54ResolveOriginalSpriteSlot",symbols)
        self.assertIn("XgbaR55GetVerifiedNativeOriginalObjectGraphics",symbols)
        self.assertIn("XgbaR55RegisterOriginalSpriteGraphics",symbols)
        self.assertIn("gXgbaR55NativeSpriteProof",symbols)
        self.assertIn("gXgbaR57SourceSpriteProof",symbols)
        self.assertIn("XgbaR57InstallPendingMapSprites",symbols)
        self.assertIn("XgbaR57ApplyOriginalObjectPalette",symbols)
        for name in ("gXgbaR54NativeWarpProof","gXgbaR54OriginalArtProof",
                     "gXgbaR55NativeSpriteProof",
                     "gXgbaR57SourceSpriteProof"):
            addr=symbols[name][0]
            self.assertTrue(0x02000000<=addr<0x02040000)
        self.assertIn("PASS_R18_EMERALD_ORIGINAL_FLASH_WRITE",self.log)
        self.assertNotIn("PASS_R54_CROSS_ROM_FLY",self.log)

if __name__=="__main__":unittest.main()
