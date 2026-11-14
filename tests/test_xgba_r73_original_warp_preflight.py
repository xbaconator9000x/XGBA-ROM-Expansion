"""R73 real native Emerald R50/R51 read-only source-warp plumbing."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class TestR73(unittest.TestCase):
 def test_real_native_binding_and_safe_dispatch(self):
  terrain=(ROOT/"integration/emerald/xgba_r51_original_terrain.inc").read_text()
  guest=(ROOT/"integration/emerald/xgba_r73_original_warp_preflight.inc").read_text()
  header=(ROOT/"integration/common/xgba_r73_source_warp_preflight.h").read_text()
  r50=(ROOT/"integration/emerald/xgba_r50_original_engine_events.inc").read_text()
  self.assertIn('#include "xgba_r73_original_warp_preflight.inc"',terrain)
  for needle in ("XgbaR51FindSourceMap(","XgbaR49LoadOriginalMapEvents(",
                 "XgbaR73ProveOriginalWarp(","sXgbaR50OriginalEvents.object_bytes"):
   self.assertIn(needle,guest)
  self.assertIn("XGBA_R73_WORLD_OR_MAP_COLLISION",header)
  self.assertIn("events.warpCount=0u;",r50)
  self.assertNotIn("SetWarpDestination(",guest)
  self.assertNotIn("EWRAM_DATA",header)
if __name__=="__main__":unittest.main()
