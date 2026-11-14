"""R81 source-original Rocket room collision-safe actual native door callsites."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
class FirstHopActualSourceDoor(unittest.TestCase):
 def test_actual_native_player_uses_original_source_preflight_and_fade(self):
  p=(R/"tools/xgba_r17_emerald_patch.py").read_text()
  src=(R/"integration/emerald/xgba_r76_physical_original_warp.inc").read_text()
  r54=(R/"integration/emerald/xgba_r54_native_fly_warp_admission.inc").read_text()
  r58=(R/"integration/emerald/xgba_r58_native_original_fly.inc").read_text()
  r50=(R/"integration/emerald/xgba_r50_original_engine_events.inc").read_text()
  native=(R/"integration/emerald/xgba_r80_native_source_warp.inc").read_text()
  for token in ("TryArrowWarp(","TryStartWarpEventScript(","MetatileBehavior_IsWarpDoor"):
   self.assertIn(token,p)
  self.assertEqual(p.count('XgbaR76NotePhysicalOriginalStepWarp(position->x,position->y,position->elevation))'),2)
  self.assertIn("if (XgbaR76NotePhysicalOriginalStepWarp(",p)
  self.assertIn("XgbaR58PreflightOriginalDestination(",src)
  self.assertIn("XgbaR80QueueVerifiedPhysicalOriginalDoor(&plan)",src)
  self.assertIn("DoWarp();",src)
  self.assertIn("SetWarpDestination(plan.native_group",src)
  self.assertIn("XgbaR80HasSourceWarpPending()",r54)
  self.assertIn("fly_witness_required",r58)
  self.assertIn("header=*gMapGroups[XGBA_R80_NATIVE_GROUP][XGBA_R80_NATIVE_MAP]",r50)
  self.assertIn("gXgbaR53GraphicsProof.source_key!=sXgbaR80Route.to",native)
  self.assertIn("sXgbaR80Route.phase=2u;",native)
 def test_original_scripts_remain_quarantined_and_no_fake_flash_claim(self):
  r50=(R/"integration/emerald/xgba_r50_original_engine_events.inc").read_text()
  native=(R/"integration/emerald/xgba_r80_native_source_warp.inc").read_text()
  self.assertIn("events.warpCount=0u;",r50)
  self.assertIn("header.mapScripts=NULL;",r50)
  self.assertNotIn("SaveGame",native)
if __name__=="__main__":unittest.main()
