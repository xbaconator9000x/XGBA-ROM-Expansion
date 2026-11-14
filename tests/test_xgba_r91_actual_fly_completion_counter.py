"""R91: actual Fly completion counter, never a fake route/queued-Fly proof."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class R91RealNativeFlyProof(unittest.TestCase):
 def test_only_original_field_effect_verified_arrival_can_count_fly(self):
  r48=(ROOT/"integration/emerald/xgba_r48_original_npc_scripts.inc").read_text()
  r54=(ROOT/"integration/emerald/xgba_r54_native_fly_warp_admission.inc").read_text()
  assert r48.index("++gXgbaR48OriginalNpcProof.actual_cross_world_fly_warps;") < r48.index(
   "XgbaR54CountVerifiedNativeFlyArrival(sXgbaR48PendingFlyWorld,")
  self.assertIn("XgbaR54CountVerifiedNativeFlyArrival(sXgbaR48PendingFlyWorld",r48)
  self.assertIn("verified!=gXgbaR54NativeWarpProof.actual_native_fly_success+1u",r54)
  self.assertIn("!sXgbaR48SourceMapLoaded",r54)
  self.assertIn("!sXgbaR53SourceActive",r54)
  self.assertIn("!sXgbaR51NativeTerrain.valid",r54)
  self.assertEqual(r54.count("++gXgbaR54NativeWarpProof.actual_native_fly_success;"),1)
  self.assertIn("FieldCallback_FlyIntoMap",r48)
 def test_room_warp_does_not_count_fly(self):
  r80=(ROOT/"integration/emerald/xgba_r80_native_source_warp.inc").read_text()
  r76=(ROOT/"integration/emerald/xgba_r76_physical_original_warp.inc").read_text()
  self.assertNotIn("XgbaR54CountVerifiedNativeFlyArrival",r80)
  self.assertNotIn("XgbaR54CountVerifiedNativeFlyArrival",r76)
if __name__=="__main__":unittest.main()
