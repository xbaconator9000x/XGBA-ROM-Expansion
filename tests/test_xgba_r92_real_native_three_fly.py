"""R92 whole-route test: actual original party-menu Fly and 3 native Fly-in frames."""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import xgba_r92_three_world_actual_fly as r92
class NativeR92RealFlyTests(unittest.TestCase):
 def test_real_fly_proof_is_not_physical_door_or_ram_sidechannel(self):
  d=(ROOT/"integration/mgba/xgba_mgba_headless.c").read_text()
  self.assertIn("static void xgba_r92_real_three_world_fly(",d)
  self.assertIn("core->setKeys(core,mask)",d)
  self.assertIn("core->runFrame(core)",d)
  self.assertIn("core->busRead32(core,r48+36u)",d)
  self.assertIn("core->busRead32(core,r54+48u)",d)
  self.assertIn("core->busRead32(core,r58+24u)",d)
  self.assertIn("target_worlds[3]={1u,2u,0u}",d)
  self.assertIn("target_keys[3]={0x00010009u,0x00020004u,0x00000009u}",d)
  self.assertIn("save_native_frame(core,fname);",d)
  self.assertIn(r92.PASS,d)
  self.assertNotIn("busWrite32(core",d[d.index("static void xgba_r92_real_three_world_fly("):d.index("int main(int argc")])
  self.assertIn("Fly requires exclusive owner-private",d)
 def test_private_hns_source_graphics_mandatory(self):
  self.assertEqual(len(r92.HNS_REQUIRED),5)
  self.assertIn("r53.w2.v2.t00f885e4.meta",r92.HNS_REQUIRED)
  self.assertIn("r56.w2.s0196.meta",r92.HNS_REQUIRED)
  self.assertIn("r56.w2.s4010.meta",r92.HNS_REQUIRED)
  py=(ROOT/"tools/xgba_mgba_run.py").read_text()
  self.assertIn('r92_fly_dir=None',py)
  self.assertIn('"--r92-r48"',py)
  self.assertIn('"--r92-r54"',py)
  self.assertIn('"--r92-r58"',py)
if __name__=="__main__":unittest.main()
