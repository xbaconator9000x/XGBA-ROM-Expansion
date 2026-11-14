"""R76 requires actual Emerald metatile and source-world runtime admission."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class R76OriginalStepNative(unittest.TestCase):
 def test_real_emerald_patch_injects_once(self):
  patch=(ROOT/"tools/xgba_r17_emerald_patch.py").read_text()
  core=(ROOT/"integration/emerald/xgba_r76_physical_original_warp.inc").read_text()
  loader=(ROOT/"integration/emerald/xgba_r54_native_fly_warp_admission.inc").read_text()
  header=(ROOT/"integration/emerald/xgba_r17_external_littleroot.inc").read_text()
  self.assertIn("TryStartWarpEventScript(struct MapPosition *position, u16 metatileBehavior)",patch)
  self.assertIn("IsWarpMetatileBehavior(metatileBehavior) == TRUE",patch)
  self.assertIn("XgbaR76NotePhysicalOriginalStepWarp(position->x,position->y,position->elevation)",patch)
  self.assertIn('__XGBA_R76_PHYSICAL_WARP_BRIDGE__',patch)
  self.assertIn('__XGBA_R76_PHYSICAL_WARP_BRIDGE__',header)
  self.assertIn("XgbaR73PreflightLoadedForeignWarp(idx,&route)",core)
  self.assertIn("return FALSE; /* native destination graphics/script installer not ready */",core)
  self.assertIn("static bool8 XgbaR54FailClosedBeforeForeignHeader(void)",loader)
  self.assertIn("SetWarpDestination(0,9,WARP_ID_NONE,",loader)
  self.assertNotIn("for(;;){}",loader)
  self.assertIn("originalSourceWarp == 3u",patch)
  self.assertIn("return FALSE; /* DMA still owns old source pages */",patch)
if __name__=="__main__":unittest.main()
