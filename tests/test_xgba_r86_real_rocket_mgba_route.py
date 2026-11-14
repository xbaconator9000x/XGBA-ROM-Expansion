"""R86 source checks: real GBA key events and actual LCD + native proof only."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import xgba_r86_private_rocket_mgba_acceptance as r86
class RealRocketNativeControllerTests(unittest.TestCase):
 def test_script_uses_mgba_physical_gba_controller_not_guest_ram_edits(self):
  driver=(ROOT/"integration/mgba/xgba_mgba_headless.c").read_text()
  launcher=(ROOT/"tools/xgba_mgba_run.py").read_text()
  self.assertIn("static void xgba_r86_run_real_rocket_door(",driver)
  self.assertIn("core->setKeys(core,mask);",driver)
  self.assertIn("core->runFrame(core);",driver)
  self.assertIn("core->busRead32(core,proof_addr+4u)",driver)
  self.assertIn("core->busRead32(core,proof_addr+16u)",driver)
  self.assertIn("0x00012304u",driver)
  self.assertIn("0x00010009u",driver)
  self.assertIn("save_native_frame(core,frame_name)",driver)
  self.assertIn("deferred_lcd_frames=80u;",driver)
  self.assertIn("rendered_lcd_arrivals!=2u",driver)
  self.assertIn("different<128u",driver)
  self.assertIn("R89 original room LCD blank or changed source",driver)
  self.assertIn("core->getPixels(core,&pixels,&pixel_stride)",driver)
  self.assertIn("R86 genuine Emerald original Rocket 0:9 -> 35:4 -> 0:9 playthrough NOT accepted",driver)
  self.assertIn(r86.PASS_MARKER,driver)
  self.assertIn("--r86-input-script",driver)
  self.assertIn("--r86-proof",driver)
  self.assertIn("r86_input_dir=None",launcher)
  self.assertIn("r86_input_script=None",launcher)
 def test_actual_gameplay_requires_private_source_and_two_lcd_images(self):
  src=(ROOT/"tools/xgba_r86_private_rocket_mgba_acceptance.py").read_text()
  self.assertIn('authenticated_original_private_resources")!=435',src)
  self.assertIn("if PASS_MARKER not in result.stdout or len(captures)!=2:",src)
  self.assertIn("gXgbaR80SourceRoomProof",src)
  self.assertIn('"three_rom_playthrough_completed":False',src)
if __name__=="__main__":unittest.main()
