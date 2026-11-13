"""R53 actual original Emerald ARM + mGBA Flash graphics integration ABI.

This test proves the fieldmap.c background graphics and heap copy hooks
compile/link inside unmodified-source-derived Emerald; no source ROM assets
are published and no foreign map Fly proof is claimed until native travel.
"""
from __future__ import annotations
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tests"))
from test_xgba_r52_native_emerald_versioned_camera import NativeEmeraldR52VersionedWorld as R52
import test_xgba_r17_emerald_external_map as r17

class NativeEmeraldR53OriginalGraphics(R52):
    R53_GRAPHICS_TEST=True

    def test_original_emerald_real_bg_tile_loader_calls_source_verified_streamer(self):
        symbols=r17.r14.symbols(self.elf)
        for required in ("gXgbaR53GraphicsProof",
                         "XgbaR53InstallOriginalSourceGraphics",
                         "XgbaR53TryLoadOriginalTileset",
                         "XgbaR53RefuseCorruptedSourceGraphics"):
            self.assertIn(required,symbols)
        address=symbols["gXgbaR53GraphicsProof"][0]
        self.assertTrue(0x02000000<=address<0x02040000)
        self.assertIn("PASS_R18_EMERALD_ORIGINAL_FLASH_WRITE",self.log)
        self.assertNotIn("PASS_R53_THREE_ROM_FLY",self.log)

if __name__=="__main__":unittest.main()
