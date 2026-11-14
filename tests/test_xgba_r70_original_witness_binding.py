"""R70 native Emerald source-witness identity and placement wiring contracts."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
R48=(ROOT/"integration/emerald/xgba_r48_original_npc_scripts.inc").read_text()
R54=(ROOT/"integration/emerald/xgba_r54_native_fly_warp_admission.inc").read_text()
R57=(ROOT/"integration/emerald/xgba_r57_native_source_sprite_installer.inc").read_text()
R58=(ROOT/"integration/emerald/xgba_r58_native_original_fly.inc").read_text()
R70=(ROOT/"integration/common/xgba_r70_original_witness_binding.h").read_text()
class R70OriginalNpcBindingContract(unittest.TestCase):
    def test_exact_original_gfx_identity_held_across_source_and_guest(self):
        self.assertIn("17u,17u,406u",R70)
        self.assertIn("XgbaR70OriginalWitnessRecordPresent(",R57)
        self.assertIn("XgbaR70OriginalWitnessRecordPresent(",R58)
        self.assertIn("XgbaR70ResolveAuthenticWitnessGraphics(",R48)
        self.assertIn("XgbaR70ResolveAuthenticWitnessGraphics(",R54)
        self.assertIn("obj->graphicsId==expected_native_graphics",R48)
        self.assertIn("event->graphicsId!=expected_native_graphics",R48)
        self.assertIn("XgbaR70VerifiedWitnessNativeSlot(",R54)
        self.assertIn("XgbaR55GetVerifiedNativeOriginalObjectGraphics(*slot)",R54)
    def test_fail_closed_and_no_new_permanent_ewram(self):
        self.assertIn("if(found || XgbaR70Le16(p+1u)!=expected_gfx",R70)
        self.assertIn("roster->source_group!=group",R70)
        self.assertIn("roster->source_map!=map",R70)
        self.assertNotIn("EWRAM_DATA",R70)
        self.assertIn("if(source!=0u)return;",R48)
if __name__=="__main__":unittest.main()
